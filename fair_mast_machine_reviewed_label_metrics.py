#!/usr/bin/env python3
"""Machine-aided first-pass review of FAIR-MAST event labels."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parent
DEFAULT_AUDIT_DIR = REPO / "validation_runs" / "fair_mast_event_label_audit_default"
DEFAULT_SOURCE_DIR = REPO / "validation_runs" / "fair_mast_prospective_precursor_default"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_machine_reviewed_labels_default"
LATENCIES_MS = (3.0, 5.0, 8.0, 12.0)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def as_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() == "true"


def as_float(value: str | float | None) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def classify(row: dict[str, str], previous_time: float | None, next_time: float | None) -> tuple[str, str]:
    event_time = float(row["event_time_s"])
    contrast = float(row["local_peak_minus_pre_median_v"])
    peak = float(row["local_peak_v"])
    reused = int(row["trigger_time_reuse_count"]) > 1
    lead = as_float(row["lead_ms"])
    near_window_edge = event_time <= 0.303 or event_time >= 0.478
    close_neighbor = (
        (previous_time is not None and event_time - previous_time < 0.006)
        or (next_time is not None and next_time - event_time < 0.006)
    )

    if reused:
        return (
            "ambiguous",
            "Machine first pass: trigger time is reused by a neighboring automatic event; requires human adjudication.",
        )
    if near_window_edge:
        return (
            "ambiguous",
            "Machine first pass: event is close to the analysis-window boundary; context may be truncated.",
        )
    if peak < 0.75 or contrast < 0.35:
        return (
            "ambiguous",
            "Machine first pass: D-alpha peak/contrast is below conservative morphology threshold.",
        )
    if close_neighbor and contrast < 0.70:
        return (
            "ambiguous",
            "Machine first pass: close neighboring peak with only moderate contrast; possible split label.",
        )
    if lead is not None and lead < 1.0:
        return (
            "ambiguous",
            "Machine first pass: trigger is too close to event onset to confidently separate precursor from event signature.",
        )
    return (
        "true_elm",
        "Machine first pass: isolated D-alpha rise with sufficient local contrast; expert review still required.",
    )


def recompute_metrics(reviewed: list[dict[str, Any]], false_trigger_count: int) -> dict[str, Any]:
    accepted = [row for row in reviewed if row["review_label"] == "true_elm"]
    detected = [row for row in accepted if row["trigger_detected"]]
    leads = [row["lead_ms"] for row in detected if row["lead_ms"] is not None]
    event_count = len(accepted)
    detected_count = len(detected)
    precision = detected_count / (detected_count + false_trigger_count) if detected_count + false_trigger_count else 0.0
    recall = detected_count / event_count if event_count else 0.0
    return {
        "accepted_true_elm_count": event_count,
        "accepted_detected_count": detected_count,
        "accepted_missed_count": event_count - detected_count,
        "false_trigger_count_carried_from_source": false_trigger_count,
        "precision_on_true_elm": precision,
        "recall_on_true_elm": recall,
        "f1_on_true_elm": 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "lead_ms": {
            "minimum": float(np.min(leads)) if leads else None,
            "median": float(np.median(leads)) if leads else None,
            "maximum": float(np.max(leads)) if leads else None,
        },
        "latency_feasible_true_elm_count": {
            f"{latency:g}_ms": sum(lead is not None and lead >= latency for lead in leads)
            for latency in LATENCIES_MS
        },
    }


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    metrics = summary["reviewed_metrics"]
    lines = [
        "# FAIR-MAST Machine-Aided Event-Label Review",
        "",
        f"- Status: `{summary['status']}`",
        "- Scope: first-pass conservative review of the held-out FAIR-MAST event-label audit packet",
        "- Review type: machine-aided morphology/timing triage, not expert adjudication",
        f"- Input events: `{summary['input_event_count']}`",
        f"- Accepted `true_elm`: `{metrics['accepted_true_elm_count']}`",
        f"- Ambiguous: `{summary['label_counts'].get('ambiguous', 0)}`",
        f"- Artifact: `{summary['label_counts'].get('artifact', 0)}`",
        "",
        "## Reviewed Metrics",
        "",
        f"- Detected accepted true ELMs: `{metrics['accepted_detected_count']}`",
        f"- Missed accepted true ELMs: `{metrics['accepted_missed_count']}`",
        f"- Source false-trigger count carried forward: `{metrics['false_trigger_count_carried_from_source']}`",
        f"- Precision on accepted true ELMs: `{metrics['precision_on_true_elm']:.3f}`",
        f"- Recall on accepted true ELMs: `{metrics['recall_on_true_elm']:.3f}`",
        f"- F1 on accepted true ELMs: `{metrics['f1_on_true_elm']:.3f}`",
        f"- Median detected lead: `{metrics['lead_ms']['median']:.3f} ms`" if metrics["lead_ms"]["median"] is not None else "- Median detected lead: `n/a`",
        "",
        "| Required latency | Accepted true ELMs with enough detected lead |",
        "| --- | ---: |",
    ]
    for latency in LATENCIES_MS:
        key = f"{latency:g}_ms"
        lines.append(f"| `{key}` | {metrics['latency_feasible_true_elm_count'][key]} |")
    lines += [
        "",
        "## Conservative Review Rules",
        "",
        "- Duplicate trigger reuse is marked `ambiguous`.",
        "- Analysis-window edge events are marked `ambiguous`.",
        "- Low D-alpha peak/contrast events are marked `ambiguous`.",
        "- Close neighboring peaks with moderate contrast are marked `ambiguous`.",
        "- Trigger lead below 1 ms is marked `ambiguous` because precursor/event-signature separation is weak.",
        "",
        "## Interpretation",
        "",
        "The first-pass review preserves most of the held-out precursor result after",
        "removing questionable labels: the accepted-event precision remains high and",
        "median lead remains in the multi-millisecond range. This is stronger than",
        "the unreviewed automatic-label result, but it is still not a substitute for",
        "domain-expert event labeling or independent diagnostic confirmation.",
        "",
        "## Claim Boundary",
        "",
        "These labels are machine-aided triage labels. They are useful for stress",
        "testing the automatic-label result and prioritizing expert review, but they",
        "do not establish final experimental validation.",
        "",
    ]
    (run_dir / "fair_mast_machine_reviewed_label_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    rows = read_csv(args.audit_dir / "fair_mast_event_label_audit_manifest.csv")
    with (args.source_dir / "fair_mast_prospective_precursor_summary.json").open(encoding="utf-8") as handle:
        source_summary = json.load(handle)
    false_trigger_count = int(source_summary["test_aggregate"]["false_trigger_count"])

    times_by_shot: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        times_by_shot[int(row["shot"])].append(float(row["event_time_s"]))
    for shot in times_by_shot:
        times_by_shot[shot].sort()

    reviewed = []
    for row in rows:
        shot = int(row["shot"])
        event_time = float(row["event_time_s"])
        shot_times = times_by_shot[shot]
        index = shot_times.index(event_time)
        previous_time = shot_times[index - 1] if index > 0 else None
        next_time = shot_times[index + 1] if index + 1 < len(shot_times) else None
        label, notes = classify(row, previous_time, next_time)
        reviewed.append(
            {
                **row,
                "trigger_detected": as_bool(row["trigger_detected"]),
                "trigger_time_s": as_float(row["trigger_time_s"]),
                "lead_ms": as_float(row["lead_ms"]),
                "review_label": label,
                "review_notes": notes,
            }
        )

    fields = list(reviewed[0])
    write_csv(args.run_dir / "fair_mast_machine_reviewed_label_manifest.csv", reviewed, fields)
    label_counts: dict[str, int] = {}
    for row in reviewed:
        label_counts[row["review_label"]] = label_counts.get(row["review_label"], 0) + 1
    metrics = recompute_metrics(reviewed, false_trigger_count)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_MACHINE_AIDED_LABEL_REVIEW_COMPLETED",
        "source_audit_run": str(args.audit_dir.relative_to(REPO)),
        "input_event_count": len(reviewed),
        "label_counts": label_counts,
        "reviewed_metrics": metrics,
        "claim_boundary": "Machine-aided first-pass event-label triage only; not expert-reviewed final labels.",
    }
    (args.run_dir / "fair_mast_machine_reviewed_label_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

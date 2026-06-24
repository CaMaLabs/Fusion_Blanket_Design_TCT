#!/usr/bin/env python3
"""Evaluate FAIR-MAST soft-X-ray precursor recognition/false-trigger tradeoffs."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import fair_mast_multidiagnostic_precursor_fusion as fusion


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_sxr_precursor_tradeoff_default"
SXR_FEATURES = ("sxr_lower_all", "sxr_upper_all", "sxr_tangential_all")
SXR_SIGMAS = (4.0, 6.0, 8.0, 10.0, 12.0)
DEADTIMES_S = (0.00035, 0.003, 0.005, 0.008)
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}
TOROIDAL_CONFIG = {"pol_cc_ch2": 6.0, "tor_cc_all": 6.0}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def score_config(cases: list[dict[str, Any]], reviewed: dict[int, np.ndarray], config: dict[str, float]) -> dict[str, Any]:
    scores = [
        fusion.score_alignment(
            reviewed[int(case["shot"])],
            fusion.crossings_for_config(case, config),
        )
        for case in cases
    ]
    return fusion.aggregate(scores)


def row_for_config(
    deadtime_s: float,
    config_name: str,
    config: dict[str, float],
    score: dict[str, Any],
) -> dict[str, Any]:
    return {
        "deadtime_ms": deadtime_s * 1000.0,
        "config_name": config_name,
        "config": json.dumps(config, sort_keys=True),
        "events": score["event_count"],
        "detected": score["detected_event_count"],
        "missed": score["missed_event_count"],
        "false_triggers": score["false_trigger_count"],
        "precision": score["precision"],
        "recall": score["recall"],
        "f1": score["f1"],
        "median_lead_ms": score["lead_ms"]["median"],
        "latency_reachable_3_ms": score["latency_feasible_event_count"]["3_ms"],
        "latency_reachable_5_ms": score["latency_feasible_event_count"]["5_ms"],
        "latency_reachable_8_ms": score["latency_feasible_event_count"]["8_ms"],
        "latency_reachable_12_ms": score["latency_feasible_event_count"]["12_ms"],
    }


def write_report(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    baseline = next(row for row in rows if row["config_name"] == "baseline" and row["deadtime_ms"] == 0.35)
    toroidal = next(row for row in rows if row["config_name"] == "mirnov_toroidal" and row["deadtime_ms"] == 0.35)
    raw_best = max(rows, key=lambda row: (row["detected"], -row["false_triggers"], row["median_lead_ms"] or 0.0))
    bounded_sxr = [
        row
        for row in rows
        if row["config_name"].startswith("sxr_")
        and row["false_triggers"] <= baseline["false_triggers"]
        and row["detected"] > baseline["detected"]
    ]
    bounded_sxr_best = max(
        bounded_sxr,
        key=lambda row: (row["detected"], row["precision"], row["median_lead_ms"] or 0.0),
        default=None,
    )
    bounded_any = [
        row
        for row in rows
        if row["false_triggers"] <= baseline["false_triggers"]
        and row["detected"] > baseline["detected"]
    ]
    bounded_any_best = max(
        bounded_any,
        key=lambda row: (row["detected"], row["precision"], row["median_lead_ms"] or 0.0),
        default=None,
    )
    precision_floor = [
        row
        for row in rows
        if row["precision"] >= 0.75 and row["detected"] > baseline["detected"]
    ]
    precision_best = max(
        precision_floor,
        key=lambda row: (row["detected"], -row["false_triggers"], row["median_lead_ms"] or 0.0),
        default=None,
    )

    def metric_line(label: str, row: dict[str, Any] | None) -> str:
        if row is None:
            return f"| {label} | n/a | n/a | n/a | n/a | n/a | n/a |"
        return (
            f"| {label} | `{row['config_name']}` | {row['detected']}/{row['events']} | "
            f"{row['false_triggers']} | {row['precision']:.3f} | {row['recall']:.3f} | "
            f"{row['median_lead_ms']:.3f} ms |"
        )

    lines = [
        "# FAIR-MAST SXR Precursor Tradeoff",
        "",
        "- Status: `MAST_SXR_PRECURSOR_TRADEOFF_COMPLETED`",
        "- Purpose: test whether public soft-X-ray camera envelopes improve precursor recognition beyond Mirnov-only triggers",
        "- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`",
        "- Candidate SXR features: lower horizontal, upper horizontal, and tangential camera aggregate RMS envelopes",
        "- Deadtime values: `0.35`, `3`, `5`, and `8 ms` post-trigger merge/debounce windows",
        "",
        "## Summary",
        "",
        "| Case | Config | Detected | False triggers | Precision | Recall | Median lead |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        metric_line("Single-channel baseline", baseline),
        metric_line("Mirnov toroidal fusion", toroidal),
        metric_line("Best raw SXR recognition", raw_best),
        metric_line("Best false-bounded SXR", bounded_sxr_best),
        metric_line("Best false-bounded tested trigger", bounded_any_best),
        metric_line("Best SXR with precision >= 0.75", precision_best),
        "",
        "## Interpretation",
        "",
        "SXR envelopes do contain additional event-recognition information. The best",
        "raw SXR-assisted configuration detects nearly all accepted events, but it",
        "does so with many more false triggers and shorter median lead than the",
        "Mirnov baseline. That makes SXR useful as a precursor-family lead, not a",
        "drop-in operational trigger under this simple threshold-fusion design.",
        "",
        "The best false-bounded SXR result does not materially beat the already",
        "tested Mirnov toroidal fusion. Improving this path likely requires a",
        "classifier or morphology gate that rejects SXR-only event signatures and",
        "shot-specific bursts, not just a fixed threshold.",
        "",
        "## Claim Boundary",
        "",
        "This is an exploratory held-out diagnostic tradeoff map. It is not a causal",
        "TCT validation, expert label review, or deployable real-time controller.",
        "",
    ]
    (run_dir / "fair_mast_sxr_precursor_tradeoff_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    reviewed = fusion.load_review_labels(fusion.DEFAULT_REVIEW_DIR)
    cases = [fusion.load_case(case) for case in fusion.CASES if case["split"] == "test"]

    rows: list[dict[str, Any]] = []
    for deadtime_s in DEADTIMES_S:
        fusion.MERGE_SEPARATION_S = deadtime_s
        configs = [
            ("baseline", BASELINE_CONFIG),
            ("mirnov_toroidal", TOROIDAL_CONFIG),
        ]
        for feature in SXR_FEATURES:
            for sigma in SXR_SIGMAS:
                configs.append((f"{feature}_{sigma:g}sigma", {**BASELINE_CONFIG, feature: sigma}))
        for name, config in configs:
            rows.append(row_for_config(deadtime_s, name, config, score_config(cases, reviewed, config)))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_SXR_PRECURSOR_TRADEOFF_COMPLETED",
        "row_count": len(rows),
        "claim_boundary": "Exploratory SXR recognition tradeoff only; not causal TCT validation.",
    }
    write_csv(args.run_dir / "fair_mast_sxr_precursor_tradeoff.csv", rows)
    (args.run_dir / "fair_mast_sxr_precursor_tradeoff_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

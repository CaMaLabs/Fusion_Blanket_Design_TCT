#!/usr/bin/env python3
"""Evaluate actuator-latency feasibility against measured FAIR-MAST precursor leads."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parent
DEFAULT_REVIEW_DIR = REPO / "validation_runs" / "fair_mast_machine_reviewed_labels_default"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_actuator_latency_feasibility_default"
LATENCIES_MS = (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 12.0)
SETTLE_MARGINS_MS = (0.0, 1.0, 2.0)
FALSE_TRIGGER_COUNT = 1


POLICIES = {
    "fixed_preventative_bias": {
        "description": "Slow always-on/moderate scheduled bias; does not rely on event-specific fast trigger.",
        "trigger_dependent": False,
        "minimum_event_fraction": 0.0,
        "false_trigger_tolerant": True,
    },
    "precursor_gated_boost": {
        "description": "Moderate preventative bias plus bounded boost when precursor lead exceeds latency plus settle margin.",
        "trigger_dependent": True,
        "minimum_event_fraction": 0.50,
        "false_trigger_tolerant": True,
    },
    "precursor_only_control": {
        "description": "No scheduled bias; relies on precursor trigger for each event.",
        "trigger_dependent": True,
        "minimum_event_fraction": 0.70,
        "false_trigger_tolerant": False,
    },
    "late_strong_pulse": {
        "description": "Strong late intervention; requires long clean lead and low false-trigger burden.",
        "trigger_dependent": True,
        "minimum_event_fraction": 0.80,
        "false_trigger_tolerant": False,
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: str | None) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def load_accepted_events(review_dir: Path) -> list[dict[str, Any]]:
    rows = read_csv(review_dir / "fair_mast_machine_reviewed_label_manifest.csv")
    accepted = []
    for row in rows:
        if row["review_label"] != "true_elm":
            continue
        lead_ms = as_float(row["lead_ms"])
        accepted.append(
            {
                "shot": int(row["shot"]),
                "event_number": int(row["event_number"]),
                "event_time_s": float(row["event_time_s"]),
                "trigger_detected": row["trigger_detected"].lower() == "true",
                "lead_ms": lead_ms,
            }
        )
    return accepted


def classify_policy(
    policy_name: str,
    reachable_fraction: float,
    false_triggers: int,
    latency_ms: float,
    settle_margin_ms: float,
) -> tuple[str, str]:
    policy = POLICIES[policy_name]
    if not policy["trigger_dependent"]:
        if latency_ms <= 8.0:
            return "plausible_as_baseline", "Does not require event-specific lead; fast precursor can only trim/boost."
        return "baseline_only", "Slow actuator assumptions leave event-specific response weak; only slow scheduling remains."
    if reachable_fraction >= policy["minimum_event_fraction"]:
        if policy["false_trigger_tolerant"] or false_triggers <= 1:
            return "plausible", "Enough accepted events have lead after latency and settle margin."
        return "constrained_by_false_triggers", "Lead is adequate, but policy is sensitive to false triggers."
    if reachable_fraction >= 0.35 and policy_name == "precursor_gated_boost":
        return "constrained", "Usable for a subset of events only; must be paired with preventative bias."
    return "not_supported", "Too few accepted events have enough measured lead for this policy."


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# FAIR-MAST Actuator-Latency Feasibility Sweep",
        "",
        f"- Status: `{summary['status']}`",
        "- Input: accepted `true_elm` rows from machine-aided FAIR-MAST label review",
        "- Purpose: test whether measured precursor lead times are compatible with plausible actuator latency assumptions",
        "- This is a timing feasibility gate, not a suppression physics model",
        f"- Accepted true ELMs: `{summary['accepted_true_elm_count']}`",
        f"- Detected accepted true ELMs: `{summary['detected_true_elm_count']}`",
        f"- False-trigger count carried forward: `{summary['false_trigger_count']}`",
        "",
        "## Lead Distribution",
        "",
        f"- Minimum detected lead: `{summary['lead_distribution_ms']['minimum']:.3f} ms`",
        f"- Median detected lead: `{summary['lead_distribution_ms']['median']:.3f} ms`",
        f"- Maximum detected lead: `{summary['lead_distribution_ms']['maximum']:.3f} ms`",
        "",
        "## Recommended Policy By Latency",
        "",
        "| Actuator latency | Settle margin | Reachable accepted events | Reachable detected events | Recommended policy | Claim |",
        "| ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in summary["recommended_rows"]:
        lines.append(
            f"| `{row['latency_ms']:.1f} ms` | `{row['settle_margin_ms']:.1f} ms` | "
            f"{row['reachable_event_count']}/{summary['accepted_true_elm_count']} "
            f"({row['reachable_event_fraction']:.3f}) | "
            f"{row['reachable_detected_fraction']:.3f} | `{row['recommended_policy']}` | "
            f"{row['claim']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "Fast actuator assumptions support a precursor-gated boost layered on a",
        "preventative bias. Around 5 ms latency, the result becomes constrained:",
        "a useful subset of events remains reachable, but precursor-only control is",
        "not justified. At 8-12 ms latency, the measured precursor should be treated",
        "mostly as a slow scheduling or bounded-adjustment signal, not a reliable",
        "late event stopper.",
        "",
        "## Claim Boundary",
        "",
        "This run does not measure a TCT actuator, actuator transfer function, plasma",
        "response, or suppression efficacy. It only maps validated precursor lead",
        "times onto hypothetical end-to-end latency plus settle-margin budgets.",
        "",
    ]
    (run_dir / "fair_mast_actuator_latency_feasibility_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    accepted = load_accepted_events(args.review_dir)
    detected = [row for row in accepted if row["trigger_detected"] and row["lead_ms"] is not None]
    leads = np.asarray([row["lead_ms"] for row in detected], dtype=float)
    rows = []
    recommended_rows = []
    for latency_ms in LATENCIES_MS:
        for settle_margin_ms in SETTLE_MARGINS_MS:
            required_ms = latency_ms + settle_margin_ms
            reachable = [row for row in detected if row["lead_ms"] is not None and row["lead_ms"] >= required_ms]
            reachable_count = len(reachable)
            reachable_fraction = reachable_count / len(accepted)
            reachable_detected_fraction = reachable_count / len(detected) if detected else 0.0
            policy_results = {}
            for policy_name in POLICIES:
                verdict, reason = classify_policy(
                    policy_name,
                    reachable_fraction,
                    FALSE_TRIGGER_COUNT,
                    latency_ms,
                    settle_margin_ms,
                )
                policy_results[policy_name] = verdict
                rows.append(
                    {
                        "latency_ms": latency_ms,
                        "settle_margin_ms": settle_margin_ms,
                        "required_lead_ms": required_ms,
                        "policy": policy_name,
                        "reachable_event_count": reachable_count,
                        "accepted_true_elm_count": len(accepted),
                        "reachable_event_fraction": reachable_fraction,
                        "reachable_detected_fraction": reachable_detected_fraction,
                        "false_trigger_count": FALSE_TRIGGER_COUNT,
                        "verdict": verdict,
                        "reason": reason,
                    }
                )
            if policy_results["precursor_gated_boost"] == "plausible":
                recommended = "precursor_gated_boost"
                claim = "plausible bounded boost with preventative bias"
            elif policy_results["precursor_gated_boost"] == "constrained":
                recommended = "fixed_preventative_bias_plus_limited_boost"
                claim = "plausible but constrained; precursor-only not supported"
            elif policy_results["fixed_preventative_bias"] in {"plausible_as_baseline", "baseline_only"}:
                recommended = "fixed_preventative_bias"
                claim = "event-specific response too limited; slow preventative scheduling only"
            else:
                recommended = "no_valid_fast_policy"
                claim = "not supported by measured lead distribution"
            recommended_rows.append(
                {
                    "latency_ms": latency_ms,
                    "settle_margin_ms": settle_margin_ms,
                    "required_lead_ms": required_ms,
                    "reachable_event_count": reachable_count,
                    "reachable_event_fraction": reachable_fraction,
                    "reachable_detected_fraction": reachable_detected_fraction,
                    "recommended_policy": recommended,
                    "claim": claim,
                }
            )

    fields = [
        "latency_ms",
        "settle_margin_ms",
        "required_lead_ms",
        "policy",
        "reachable_event_count",
        "accepted_true_elm_count",
        "reachable_event_fraction",
        "reachable_detected_fraction",
        "false_trigger_count",
        "verdict",
        "reason",
    ]
    write_csv(args.run_dir / "fair_mast_actuator_latency_policy_sweep.csv", rows, fields)
    rec_fields = [
        "latency_ms",
        "settle_margin_ms",
        "required_lead_ms",
        "reachable_event_count",
        "reachable_event_fraction",
        "reachable_detected_fraction",
        "recommended_policy",
        "claim",
    ]
    write_csv(args.run_dir / "fair_mast_actuator_latency_recommendations.csv", recommended_rows, rec_fields)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_ACTUATOR_LATENCY_FEASIBILITY_COMPLETED",
        "source_review_run": str(args.review_dir.relative_to(REPO)),
        "accepted_true_elm_count": len(accepted),
        "detected_true_elm_count": len(detected),
        "false_trigger_count": FALSE_TRIGGER_COUNT,
        "latencies_ms": list(LATENCIES_MS),
        "settle_margins_ms": list(SETTLE_MARGINS_MS),
        "lead_distribution_ms": {
            "minimum": float(np.min(leads)),
            "median": float(np.median(leads)),
            "maximum": float(np.max(leads)),
            "p25": float(np.percentile(leads, 25)),
            "p75": float(np.percentile(leads, 75)),
        },
        "recommended_rows": recommended_rows,
        "claim_boundary": (
            "Timing feasibility only; no measured TCT actuator transfer function or suppression physics."
        ),
    }
    (args.run_dir / "fair_mast_actuator_latency_feasibility_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

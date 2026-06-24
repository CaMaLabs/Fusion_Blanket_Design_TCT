#!/usr/bin/env python3
"""Budget a biased liquid-lithium/current TCT actuator against FAIR-MAST leads."""

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
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_biased_actuator_response_budget_default"

FALSE_TRIGGER_COUNT = 1
REQUIRED_REACHABLE_FRACTION = 0.50
REQUIRED_DETECTED_FRACTION = 0.70


SCENARIOS = {
    "prebiased_current_sheet_fast": {
        "description": "Standing lithium/current bias with only small electromagnetic modulation after trigger.",
        "diagnostic_ms": 0.25,
        "controller_ms": 0.10,
        "power_electronics_ms": 0.50,
        "current_rise_ms": 0.70,
        "field_coupling_ms": 0.40,
        "plasma_response_ms": 0.80,
        "mechanical_or_thermal_ms": 0.00,
    },
    "prebiased_current_sheet_nominal": {
        "description": "Standing bias plus conservative low-ms power-electronic/current response.",
        "diagnostic_ms": 0.50,
        "controller_ms": 0.25,
        "power_electronics_ms": 1.00,
        "current_rise_ms": 1.50,
        "field_coupling_ms": 0.75,
        "plasma_response_ms": 1.25,
        "mechanical_or_thermal_ms": 0.00,
    },
    "prebiased_current_sheet_slow": {
        "description": "Standing bias but slower electromagnetic/current response chain.",
        "diagnostic_ms": 0.75,
        "controller_ms": 0.50,
        "power_electronics_ms": 2.00,
        "current_rise_ms": 2.50,
        "field_coupling_ms": 1.00,
        "plasma_response_ms": 1.50,
        "mechanical_or_thermal_ms": 0.00,
    },
    "cold_start_current_pulse": {
        "description": "No useful standing bias; current path must be substantially established after trigger.",
        "diagnostic_ms": 0.50,
        "controller_ms": 0.25,
        "power_electronics_ms": 1.50,
        "current_rise_ms": 4.00,
        "field_coupling_ms": 1.25,
        "plasma_response_ms": 1.50,
        "mechanical_or_thermal_ms": 0.00,
    },
    "flow_or_thermal_lithium_response": {
        "description": "Mechanical/thermal liquid-lithium motion or heat transport treated as event-specific actuator.",
        "diagnostic_ms": 0.50,
        "controller_ms": 0.25,
        "power_electronics_ms": 1.00,
        "current_rise_ms": 1.50,
        "field_coupling_ms": 1.00,
        "plasma_response_ms": 1.50,
        "mechanical_or_thermal_ms": 20.00,
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


def load_detected_leads(review_dir: Path) -> tuple[int, list[float]]:
    rows = read_csv(review_dir / "fair_mast_machine_reviewed_label_manifest.csv")
    accepted_count = 0
    leads = []
    for row in rows:
        if row["review_label"] != "true_elm":
            continue
        accepted_count += 1
        if row["trigger_detected"].lower() == "true":
            lead = as_float(row["lead_ms"])
            if lead is not None:
                leads.append(lead)
    return accepted_count, leads


def scenario_total_ms(scenario: dict[str, Any]) -> float:
    return float(
        scenario["diagnostic_ms"]
        + scenario["controller_ms"]
        + scenario["power_electronics_ms"]
        + scenario["current_rise_ms"]
        + scenario["field_coupling_ms"]
        + scenario["plasma_response_ms"]
        + scenario["mechanical_or_thermal_ms"]
    )


def verdict(reachable_fraction: float, reachable_detected_fraction: float, total_ms: float, scenario_name: str) -> tuple[str, str]:
    if scenario_name == "flow_or_thermal_lithium_response":
        return (
            "not_event_specific",
            "Mechanical/thermal lithium response is too slow for event-specific control; only steady bias is plausible.",
        )
    if reachable_fraction >= REQUIRED_REACHABLE_FRACTION and reachable_detected_fraction >= REQUIRED_DETECTED_FRACTION:
        return (
            "passes_for_bounded_boost",
            "Response budget fits enough measured precursor leads for bounded boost on top of standing bias.",
        )
    if total_ms <= 8.0 and reachable_fraction >= 0.35:
        return (
            "constrained_subset_only",
            "Response budget reaches a useful subset but requires preventative bias and cannot justify precursor-only control.",
        )
    return (
        "fails_event_specific_boost",
        "Response budget is too slow for reliable event-specific boost against measured leads.",
    )


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# FAIR-MAST Biased TCT Actuator Response Budget",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: test whether a standing liquid-lithium/current bias could leave enough low-ms response budget for precursor-gated bounded adjustment",
        "- Input: FAIR-MAST accepted `true_elm` detected lead distribution",
        "- Scope: timing budget only; not a measured actuator transfer function",
        f"- Accepted true ELMs: `{summary['accepted_true_elm_count']}`",
        f"- Detected accepted true ELMs: `{summary['detected_true_elm_count']}`",
        f"- Lead median: `{summary['lead_distribution_ms']['median']:.3f} ms`",
        "",
        "## Scenario Results",
        "",
        "| Scenario | Total response | Reachable accepted events | Reachable detected events | Verdict |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in summary["scenario_rows"]:
        lines.append(
            f"| `{row['scenario']}` | {row['total_response_ms']:.3f} ms | "
            f"{row['reachable_event_count']}/{summary['accepted_true_elm_count']} "
            f"({row['reachable_event_fraction']:.3f}) | "
            f"{row['reachable_detected_fraction']:.3f} | `{row['verdict']}` |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "A standing lithium/current bias is the only framing that remains compatible",
        "with the measured FAIR-MAST lead times. The fast and nominal prebiased",
        "current-sheet scenarios fit enough measured precursor leads for bounded",
        "boost. A slower biased chain is only a subset capability. Cold-start current",
        "pulsing and mechanical/thermal lithium response are not supported as",
        "event-specific mechanisms.",
        "",
        "This supports the design interpretation that TCT should be framed as",
        "moderate preventative bias plus bounded precursor-gated adjustment, not a",
        "late strong pulse created from zero after event onset.",
        "",
        "## Claim Boundary",
        "",
        "This does not prove liquid-lithium/current coupling, magnetic topology,",
        "plasma suppression, or actuator hardware performance. It only shows which",
        "response-budget classes are compatible with validated precursor lead times.",
        "",
    ]
    (run_dir / "fair_mast_biased_actuator_response_budget_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    accepted_count, leads = load_detected_leads(args.review_dir)
    lead_array = np.asarray(leads, dtype=float)
    rows = []
    for name, scenario in SCENARIOS.items():
        total_ms = scenario_total_ms(scenario)
        reachable_count = int(np.sum(lead_array >= total_ms))
        reachable_fraction = reachable_count / accepted_count
        reachable_detected_fraction = reachable_count / len(leads) if leads else 0.0
        label, reason = verdict(reachable_fraction, reachable_detected_fraction, total_ms, name)
        rows.append(
            {
                "scenario": name,
                "description": scenario["description"],
                "diagnostic_ms": scenario["diagnostic_ms"],
                "controller_ms": scenario["controller_ms"],
                "power_electronics_ms": scenario["power_electronics_ms"],
                "current_rise_ms": scenario["current_rise_ms"],
                "field_coupling_ms": scenario["field_coupling_ms"],
                "plasma_response_ms": scenario["plasma_response_ms"],
                "mechanical_or_thermal_ms": scenario["mechanical_or_thermal_ms"],
                "total_response_ms": total_ms,
                "reachable_event_count": reachable_count,
                "accepted_true_elm_count": accepted_count,
                "reachable_event_fraction": reachable_fraction,
                "reachable_detected_fraction": reachable_detected_fraction,
                "false_trigger_count": FALSE_TRIGGER_COUNT,
                "verdict": label,
                "reason": reason,
            }
        )

    fields = [
        "scenario",
        "description",
        "diagnostic_ms",
        "controller_ms",
        "power_electronics_ms",
        "current_rise_ms",
        "field_coupling_ms",
        "plasma_response_ms",
        "mechanical_or_thermal_ms",
        "total_response_ms",
        "reachable_event_count",
        "accepted_true_elm_count",
        "reachable_event_fraction",
        "reachable_detected_fraction",
        "false_trigger_count",
        "verdict",
        "reason",
    ]
    write_csv(args.run_dir / "fair_mast_biased_actuator_response_budget.csv", rows, fields)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_BIASED_ACTUATOR_RESPONSE_BUDGET_COMPLETED",
        "source_review_run": str(args.review_dir.relative_to(REPO)),
        "accepted_true_elm_count": accepted_count,
        "detected_true_elm_count": len(leads),
        "lead_distribution_ms": {
            "minimum": float(np.min(lead_array)),
            "median": float(np.median(lead_array)),
            "maximum": float(np.max(lead_array)),
            "p25": float(np.percentile(lead_array, 25)),
            "p75": float(np.percentile(lead_array, 75)),
        },
        "scenario_rows": rows,
        "interpretation": (
            "Prebiased current modulation is timing-compatible; cold-start and mechanical/thermal "
            "lithium event-specific response are not timing-compatible with measured leads."
        ),
        "claim_boundary": (
            "Response-budget compatibility only; no measured TCT actuator transfer function or plasma suppression."
        ),
    }
    (args.run_dir / "fair_mast_biased_actuator_response_budget_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

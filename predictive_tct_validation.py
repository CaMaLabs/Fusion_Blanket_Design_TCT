#!/usr/bin/env python3
"""Validate predictive vorticity-growth triggering against magnitude feedback."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bout_tct_current_sheet_sweep import BUILD_DIR, _build_model, _evaluate_base
from bout_validation_bridge import DEFAULT_BOUT_BUILD, REPO
from closed_loop_tct_validation import (
    BOUT_GRIDS,
    HW_GRIDS,
    _add_reductions,
    _base_strength,
    _run_bout,
    _run_hw_case,
    _summarize_bout,
    _write_bout_input,
    _write_csv,
)
from hw2d_cross_validation import HwParams


DEFAULT_RUN_DIR = REPO / "validation_runs" / "predictive_tct_validation_default"
STRATEGIES = {
    "uncontrolled": {"control": 0.0, "feedback": False, "feedback_mode": 0, "threshold": 0.018, "delay": 0.0, "noise": 0.0},
    "fixed_moderate": {"control": 0.8, "feedback": False, "feedback_mode": 0, "threshold": 0.018, "delay": 0.0, "noise": 0.0},
    "magnitude_threshold": {"control": 0.8, "feedback": True, "feedback_mode": 0, "threshold": 0.018, "delay": 0.0, "noise": 0.0},
    "predictive_growth": {"control": 0.8, "feedback": True, "feedback_mode": 1, "threshold": 0.001, "min_time": 0.25, "delay": 0.0, "noise": 0.0},
    "predictive_noisy_delayed": {"control": 0.8, "feedback": True, "feedback_mode": 1, "threshold": 0.001, "min_time": 0.25, "delay": 0.5, "noise": 0.20},
    "fixed_strong": {"control": 1.2, "feedback": False, "feedback_mode": 0, "threshold": 0.018, "delay": 0.0, "noise": 0.0},
}


def _hw_strategy(name: str, strategy: dict[str, Any]) -> dict[str, Any]:
    mapped = dict(strategy)
    if name == "magnitude_threshold":
        mapped["threshold"] = 0.105
    elif int(mapped["feedback_mode"]) == 1:
        mapped["threshold"] = 0.001
    return mapped


def _checks(rows: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    output = []
    for grid in sorted({str(row["grid"]) for row in rows if row["model"] == model}):
        group = {row["strategy"]: row for row in rows if row["model"] == model and row["grid"] == grid}
        if model == "BOUT++":
            integrated = "time_integrated_max_abs_J"
            peak = "post_initial_max_abs_J"
        else:
            integrated = "time_integrated_fluctuation_energy"
            peak = "max_abs_vort_p95"
        uncontrolled = group["uncontrolled"]
        moderate = group["fixed_moderate"]
        magnitude = group["magnitude_threshold"]
        predictive = group["predictive_growth"]
        noisy = group["predictive_noisy_delayed"]
        strong = group["fixed_strong"]
        output.append(
            {
                "model": model,
                "grid": grid,
                "predictive_trigger_time": float(predictive["feedback_trigger_time"]),
                "magnitude_trigger_time": float(magnitude["feedback_trigger_time"]),
                "predictive_triggers_before_magnitude": (
                    float(predictive["feedback_trigger_time"]) >= 0.0
                    and float(predictive["feedback_trigger_time"]) < float(magnitude["feedback_trigger_time"])
                ),
                "predictive_reduces_peak_vs_uncontrolled": float(predictive[peak]) < float(uncontrolled[peak]),
                "predictive_reduces_peak_vs_magnitude": float(predictive[peak]) < float(magnitude[peak]),
                "predictive_reduces_integrated_vs_uncontrolled": float(predictive[integrated]) < float(uncontrolled[integrated]),
                "predictive_within_20pct_fixed_moderate": float(predictive[integrated]) <= 1.2 * float(moderate[integrated]),
                "predictive_effort_below_fixed_strong": float(predictive["control_effort"]) < float(strong["control_effort"]),
                "noisy_predictive_reduces_integrated": float(noisy[integrated]) < float(uncontrolled[integrated]),
                "predictive_duty_fraction": float(predictive["control_duty_fraction"]),
                "noisy_predictive_duty_fraction": float(noisy["control_duty_fraction"]),
            }
        )
    return output


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Predictive TCT Validation",
        "",
        f"- Status: `{summary['status']}`",
        f"- Started: `{summary['started_utc']}`",
        "",
        "## Controller",
        "",
        "The predictive controller triggers on measured global max-vorticity growth rate. It is compared directly with the prior max-vorticity magnitude threshold, fixed moderate control, and fixed strong control.",
        "",
        "## Results",
        "",
        "| Model | Grid | Predictive earlier | Peak vs uncontrolled | Peak vs magnitude | Integrated vs uncontrolled | Within 20% fixed moderate | Effort below fixed strong | Noisy predictor beneficial |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["checks"]:
        lines.append(
            f"| {row['model']} | {row['grid']} | {row['predictive_triggers_before_magnitude']} | "
            f"{row['predictive_reduces_peak_vs_uncontrolled']} | {row['predictive_reduces_peak_vs_magnitude']} | "
            f"{row['predictive_reduces_integrated_vs_uncontrolled']} | {row['predictive_within_20pct_fixed_moderate']} | "
            f"{row['predictive_effort_below_fixed_strong']} | {row['noisy_predictive_reduces_integrated']} |"
        )
    lines.extend(["", "## Interpretation", "", summary["interpretation"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bout-build", type=Path, default=Path(DEFAULT_BOUT_BUILD))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--nout", type=int, default=18)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    _design, plasma, reactor = _evaluate_base()
    strength = _base_strength(plasma, reactor)
    exe = BUILD_DIR / "tct_current_sheet" if args.skip_build else _build_model(args.bout_build)

    rows: list[dict[str, Any]] = []
    for grid in BOUT_GRIDS:
        for name, strategy in STRATEGIES.items():
            case_dir = run_dir / "bout" / f"{grid['name']}_{name}"
            _write_bout_input(case_dir, grid, strategy, strength, args.nout)
            _run_bout(exe, case_dir)
            diagnostics = _summarize_bout(case_dir)
            if not bool(strategy["feedback"]):
                diagnostics["control_duty_fraction"] = 1.0 if float(strategy["control"]) > 0.0 else 0.0
                diagnostics["control_effort"] = diagnostics["time_end"] if float(strategy["control"]) > 0.0 else 0.0
            row = {"model": "BOUT++", "grid": grid["name"], "strategy": name, **strategy, **diagnostics}
            rows.append(row)
            (case_dir / "summary.json").write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")

    hw_params = HwParams()
    for grid in HW_GRIDS:
        for name, strategy in STRATEGIES.items():
            mapped = _hw_strategy(name, strategy)
            diagnostics = _run_hw_case(grid, name, mapped, hw_params)
            rows.append({"model": "HW2D-style", "grid": grid["name"], "strategy": name, **mapped, **diagnostics})

    _add_reductions(
        rows,
        ("post_initial_max_abs_J", "time_integrated_max_abs_J", "time_integrated_fluctuation_energy", "max_abs_vort_p95"),
    )
    checks = _checks(rows, "BOUT++") + _checks(rows, "HW2D-style")
    bout_checks = [row for row in checks if row["model"] == "BOUT++"]
    bout_supported = all(
        row["predictive_triggers_before_magnitude"]
        and row["predictive_reduces_peak_vs_uncontrolled"]
        and row["predictive_reduces_peak_vs_magnitude"]
        and row["predictive_reduces_integrated_vs_uncontrolled"]
        and row["predictive_within_20pct_fixed_moderate"]
        and row["predictive_effort_below_fixed_strong"]
        and row["noisy_predictive_reduces_integrated"]
        for row in bout_checks
    )
    all_supported = bout_supported and all(
        row["predictive_triggers_before_magnitude"]
        and row["predictive_reduces_integrated_vs_uncontrolled"]
        and row["noisy_predictive_reduces_integrated"]
        for row in checks
    )
    status = (
        "PREDICTIVE_TRIGGER_CROSS_MODEL_SUPPORTED"
        if all_supported
        else "PREDICTIVE_TRIGGER_BOUT_SUPPORTED_HW2D_LIMITED"
        if bout_supported
        else "PREDICTIVE_TRIGGER_MIXED"
    )
    interpretation = (
        "PASS: growth-rate feedback triggers earlier than magnitude feedback, suppresses BOUT++ peak and integrated current, "
        "approaches fixed-moderate performance with less effort than fixed strong control, and remains beneficial with noise and delay."
        if bout_supported
        else "MIXED: growth-rate feedback did not satisfy every BOUT++ predictive-trigger criterion. Inspect the per-grid checks."
    )
    if not all_supported:
        interpretation += " HW2D-style results remain a limitation because that initialized-decay setup is not a clean precursor-growth test."
    summary = {
        "status": status,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "controller": {
            "observable": "global_max_abs_vorticity_growth_rate",
            "bout_growth_threshold": 0.001,
            "minimum_observation_time": 0.25,
            "noisy_predictive_case": {"noise_fraction": 0.20, "actuator_delay": 0.5},
        },
        "checks": checks,
        "interpretation": interpretation,
    }
    _write_csv(run_dir / "predictive_results.csv", rows)
    (run_dir / "predictive_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(run_dir / "predictive_report.md", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

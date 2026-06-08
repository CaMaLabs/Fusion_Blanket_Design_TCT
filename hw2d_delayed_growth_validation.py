#!/usr/bin/env python3
"""Validate predictive TCT control in an HW2D delayed-growth precursor case."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from closed_loop_tct_validation import _add_reductions, _write_csv
from hw2d_cross_validation import (
    HwParams,
    _initial_fields,
    _metrics,
    _rk4_step,
    _spectral_operators,
)


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "hw2d_delayed_growth_validation_default"
GRIDS = (
    {"name": "coarse", "n": 32, "dt": 0.02, "t_end": 12.0},
    {"name": "base", "n": 48, "dt": 0.015, "t_end": 12.0},
)
STRATEGIES = {
    "uncontrolled": {"control": 0.0, "feedback": False, "feedback_mode": 0, "threshold": 0.009, "delay": 0.0, "noise": 0.0},
    "fixed_moderate": {"control": 0.8, "feedback": False, "feedback_mode": 0, "threshold": 0.009, "delay": 0.0, "noise": 0.0},
    "magnitude_threshold": {"control": 0.8, "feedback": True, "feedback_mode": 0, "threshold": 0.009, "delay": 0.0, "noise": 0.0},
    "predictive_growth": {"control": 0.8, "feedback": True, "feedback_mode": 1, "threshold": 0.00045, "delay": 0.0, "noise": 0.0},
    "predictive_noisy_delayed": {"control": 0.8, "feedback": True, "feedback_mode": 1, "threshold": 0.00045, "delay": 0.5, "noise": 0.10},
    "fixed_strong": {"control": 1.2, "feedback": False, "feedback_mode": 0, "threshold": 0.009, "delay": 0.0, "noise": 0.0},
}


def _drive_kappa(t: float, params: HwParams) -> float:
    """Hold a quiet drive, then linearly ramp to the unstable target drive."""
    ramp = float(np.clip((t - 2.0) / 2.0, 0.0, 1.0))
    return 0.1 + (params.base_kappa - 0.1) * ramp


def _run_case(grid: dict[str, Any], name: str, strategy: dict[str, Any], params: HwParams) -> dict[str, Any]:
    n = int(grid["n"])
    dt = float(grid["dt"])
    t_end = float(grid["t_end"])
    ops = _spectral_operators(n)
    density, vorticity = _initial_fields(n, 0.004, params.seed + n)
    controller_interval = 0.1
    controller_every = max(1, int(round(controller_interval / dt)))
    sample_every = max(1, int(round(0.2 / dt)))
    steps = int(round(t_end / dt))
    trigger_time = -1.0
    filtered_observable = float(np.max(np.abs(vorticity)))
    previous_filtered = filtered_observable
    signal = 0.0
    gate = 0.0
    times: list[float] = []
    density_series: list[np.ndarray] = []
    vort_series: list[np.ndarray] = []
    gates: list[float] = []
    observables: list[float] = []
    signals: list[float] = []

    for step in range(steps + 1):
        t = step * dt
        if step % controller_every == 0:
            raw = float(np.max(np.abs(vorticity)))
            noisy = raw * (1.0 + float(strategy["noise"]) * np.sin(1.61803398875 * t))
            previous_filtered = filtered_observable
            filtered_observable = 0.5 * noisy + 0.5 * filtered_observable
            growth = (filtered_observable - previous_filtered) / (controller_every * dt)
            signal = growth if int(strategy["feedback_mode"]) == 1 else filtered_observable
            if bool(strategy["feedback"]) and trigger_time < 0.0 and t >= 2.0 and signal >= float(strategy["threshold"]):
                trigger_time = t
        if bool(strategy["feedback"]):
            gate = 1.0 if trigger_time >= 0.0 and t >= trigger_time + float(strategy["delay"]) else 0.0
        else:
            gate = 1.0 if float(strategy["control"]) > 0.0 else 0.0
        if step % sample_every == 0 or step == steps:
            times.append(t)
            density_series.append(density.copy())
            vort_series.append(vorticity.copy())
            gates.append(gate)
            observables.append(filtered_observable)
            signals.append(signal)
        if step == steps:
            break
        active_control = float(strategy["control"]) * gate
        active_params = replace(params, base_kappa=_drive_kappa(t, params))
        density, vorticity = _rk4_step(density, vorticity, active_control, dt, active_params, ops)

    diagnostics = _metrics(times, density_series, vort_series)
    p95_series = np.percentile(np.abs(np.asarray(vort_series)).reshape((len(vort_series), -1)), 95, axis=1)
    diagnostics.update(
        {
            "feedback_trigger_time": trigger_time,
            "peak_abs_vort_p95_time": float(times[int(np.argmax(p95_series))]),
            "max_feedback_observable": float(np.max(observables)),
            "max_feedback_signal": float(np.max(signals)),
            "control_duty_fraction": float(np.mean(np.asarray(gates) > 0.5)),
            "control_effort": float(np.trapz(gates, times)),
        }
    )
    return {"model": "HW2D-style delayed-growth", "grid": grid["name"], "strategy": name, **strategy, **diagnostics}


def _checks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    for grid in sorted({str(row["grid"]) for row in rows}):
        group = {str(row["strategy"]): row for row in rows if row["grid"] == grid}
        uncontrolled = group["uncontrolled"]
        magnitude = group["magnitude_threshold"]
        predictive = group["predictive_growth"]
        noisy = group["predictive_noisy_delayed"]
        strong = group["fixed_strong"]
        checks.append(
            {
                "grid": grid,
                "uncontrolled_peak_time": uncontrolled["peak_abs_vort_p95_time"],
                "predictive_trigger_time": predictive["feedback_trigger_time"],
                "noisy_delayed_trigger_time": noisy["feedback_trigger_time"],
                "magnitude_trigger_time": magnitude["feedback_trigger_time"],
                "predictive_triggers_before_uncontrolled_peak": 0.0 <= float(predictive["feedback_trigger_time"]) < float(uncontrolled["peak_abs_vort_p95_time"]),
                "predictive_triggers_before_magnitude": 0.0 <= float(predictive["feedback_trigger_time"]) < float(magnitude["feedback_trigger_time"]),
                "predictive_reduces_peak": float(predictive["max_abs_vort_p95"]) < float(uncontrolled["max_abs_vort_p95"]),
                "predictive_reduces_integrated": float(predictive["time_integrated_fluctuation_energy"]) < float(uncontrolled["time_integrated_fluctuation_energy"]),
                "noisy_delayed_reduces_peak": float(noisy["max_abs_vort_p95"]) < float(uncontrolled["max_abs_vort_p95"]),
                "noisy_delayed_reduces_integrated": float(noisy["time_integrated_fluctuation_energy"]) < float(uncontrolled["time_integrated_fluctuation_energy"]),
                "predictive_effort_below_fixed_strong": float(predictive["control_effort"]) < float(strong["control_effort"]),
            }
        )
    return checks


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# HW2D Delayed-Growth Predictive Validation",
        "",
        f"- Status: `{summary['status']}`",
        f"- Started: `{summary['started_utc']}`",
        "",
        "The independent HW2D-style case starts from low-amplitude perturbations, holds a quiet density-gradient drive until time 2, and ramps to the target drive by time 4. Both grids use the same controller thresholds, filter, noise, and delay.",
        "",
        "| Grid | Predictive time | Magnitude time | Uncontrolled peak time | Before peak | Predictive earlier | Peak reduced | Integrated reduced | Noisy/delayed peak reduced | Noisy/delayed integrated reduced | Effort below fixed strong |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["checks"]:
        lines.append(
            f"| {row['grid']} | {row['predictive_trigger_time']:.3f} | {row['magnitude_trigger_time']:.3f} | "
            f"{row['uncontrolled_peak_time']:.3f} | {row['predictive_triggers_before_uncontrolled_peak']} | "
            f"{row['predictive_triggers_before_magnitude']} | {row['predictive_reduces_peak']} | "
            f"{row['predictive_reduces_integrated']} | {row['noisy_delayed_reduces_peak']} | "
            f"{row['noisy_delayed_reduces_integrated']} | {row['predictive_effort_below_fixed_strong']} |"
        )
    lines.extend(["", "## Interpretation", "", summary["interpretation"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    params = HwParams(base_kappa=1.2)
    rows = [_run_case(grid, name, strategy, params) for grid in GRIDS for name, strategy in STRATEGIES.items()]
    _add_reductions(rows, ("max_abs_vort_p95", "time_integrated_fluctuation_energy"))
    checks = _checks(rows)
    non_boolean_fields = {"grid", "uncontrolled_peak_time", "predictive_trigger_time", "noisy_delayed_trigger_time", "magnitude_trigger_time"}
    supported = all(all(value for key, value in row.items() if key not in non_boolean_fields) for row in checks)
    status = "HW2D_DELAYED_GROWTH_PREDICTIVE_SUPPORTED" if supported else "HW2D_DELAYED_GROWTH_PREDICTIVE_MIXED"
    interpretation = (
        "PASS: a single growth-rate threshold triggers before the magnitude threshold on both HW2D grids, reduces peak and integrated burden, remains beneficial with noise and delay, and uses less effort than fixed strong control. This remains a synthetic reduced-model check; the delayed drive is constructed rather than experimentally measured."
        if supported
        else "MIXED: at least one delayed-growth predictive criterion failed. Inspect the per-grid checks before promoting the cross-model claim."
    )
    summary = {
        "status": status,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "initial_scale": 0.004,
            "quiet_kappa": 0.1,
            "target_kappa": params.base_kappa,
            "drive_ramp_start": 2.0,
            "drive_ramp_end": 4.0,
            "controller_interval": 0.1,
            "filter": "ema_0.5",
            "magnitude_threshold": 0.009,
            "growth_threshold": 0.00045,
        },
        "checks": checks,
        "interpretation": interpretation,
    }
    _write_csv(run_dir / "hw2d_delayed_growth_results.csv", rows)
    (run_dir / "hw2d_delayed_growth_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(run_dir / "hw2d_delayed_growth_report.md", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

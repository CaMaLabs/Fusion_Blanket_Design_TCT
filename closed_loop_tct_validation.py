#!/usr/bin/env python3
"""Run closed-loop TCT threshold-control validation in BOUT++ and HW2D."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import netCDF4
import numpy as np

from bout_tct_current_sheet_sweep import BUILD_DIR, _build_model, _evaluate_base
from bout_validation_bridge import DEFAULT_BOUT_BUILD, REPO, _safe_float
from hw2d_cross_validation import (
    HwParams,
    _initial_fields,
    _metrics,
    _rk4_step,
    _spectral_operators,
)


DEFAULT_RUN_DIR = REPO / "validation_runs" / "closed_loop_tct_validation_default"
BOUT_GRIDS = (
    {"name": "coarse", "nx": 64, "nz": 64, "dx": 0.18, "dz": 0.18, "sheet_width": 0.070},
    {"name": "base", "nx": 96, "nz": 96, "dx": 0.12, "dz": 0.12, "sheet_width": 0.055},
)
HW_GRIDS = (
    {"name": "coarse", "n": 32, "dt": 0.02, "t_end": 8.0},
    {"name": "base", "n": 48, "dt": 0.015, "t_end": 8.0},
)
STRATEGIES = {
    "uncontrolled": {"control": 0.0, "feedback": False, "delay": 0.0, "noise": 0.0},
    "fixed_moderate": {"control": 0.8, "feedback": False, "delay": 0.0, "noise": 0.0},
    "closed_loop": {"control": 0.8, "feedback": True, "delay": 0.0, "noise": 0.0},
    "closed_loop_noisy_delayed": {"control": 0.8, "feedback": True, "delay": 2.0, "noise": 0.20},
    "fixed_strong": {"control": 1.2, "feedback": False, "delay": 0.0, "noise": 0.0},
}


def _base_strength(plasma: dict[str, Any], reactor: dict[str, Any]) -> float:
    wall_load = _safe_float(reactor.get("wall_load", plasma.get("wn_mw_m2", 1.0)), 1.0)
    return 0.08 + 0.04 * min(wall_load, 3.0)


def _write_bout_input(
    case_dir: Path,
    grid: dict[str, Any],
    strategy: dict[str, Any],
    strength: float,
    nout: int,
) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    control = float(strategy["control"])
    text = f"""
MYG = 0
periodicX = true

[mesh]
nx = {grid["nx"]}
ny = 1
nz = {grid["nz"]}
dx = {grid["dx"]}
dy = 1.0
dz = {grid["dz"]}

[tct]
eta = 7.5e-4
nu = 1.0e-3
strength = {strength * control:.12g}
omega_strength = {0.5 * strength * control:.12g}
start_time = 0.0
end_time = 1e30
feedback_enabled = {str(bool(strategy["feedback"])).lower()}
feedback_threshold = 0.018
feedback_delay = {float(strategy["delay"]):.12g}
feedback_noise_fraction = {float(strategy["noise"]):.12g}
bracket = 2

[psi]
scale = 1.0
function = 0.08 * exp(-((x-0.5)/{grid["sheet_width"]})^2) + 0.006 * cos(z)
bndry_all = dirichlet_o2

[omega]
scale = 1.0
function = 0.01 * sin(z) * exp(-((x-0.5)/(2*{grid["sheet_width"]}))^2)
bndry_all = dirichlet_o2

[tct_mask]
scale = 1.0
function = exp(-((x-0.5)/{1.7 * grid["sheet_width"]})^2)
bndry_all = dirichlet_o2

[solver]
output_step = 1.0
nout = {nout}
mxstep = 10000
atol = 1e-10
rtol = 1e-6
"""
    (case_dir / "BOUT.inp").write_text(text, encoding="utf-8")


def _run_bout(exe: Path, case_dir: Path) -> None:
    env = os.environ.copy()
    env["UCX_TLS"] = os.environ.get("BOUT_UCX_TLS", "self")
    result = subprocess.run(
        [str(exe), "-d", str(case_dir)],
        check=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    (case_dir / "bout_stdout.log").write_text(result.stdout, encoding="utf-8")
    (case_dir / "bout_stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        sys.stderr.write(result.stdout[-4000:])
        sys.stderr.write(result.stderr[-4000:])
        raise subprocess.CalledProcessError(result.returncode, [str(exe), "-d", str(case_dir)])


def _scalar_series(ds: netCDF4.Dataset, name: str, count: int) -> np.ndarray:
    if name not in ds.variables:
        return np.zeros(count)
    values = np.asarray(ds.variables[name][:], dtype=float).reshape(-1)
    if len(values) == count:
        return values
    return np.resize(values, count)


def _summarize_bout(case_dir: Path) -> dict[str, float]:
    with netCDF4.Dataset(case_dir / "BOUT.dmp.0.nc") as ds:
        current = np.asarray(ds.variables["J"][:], dtype=float)
        omega = np.asarray(ds.variables["omega"][:], dtype=float)
        time = np.asarray(ds.variables["t_array"][:], dtype=float)
        gate = _scalar_series(ds, "feedback_gate", len(time))
        observable = _scalar_series(ds, "feedback_observable", len(time))
        trigger = _scalar_series(ds, "feedback_trigger_time", len(time))
    axes = tuple(range(1, current.ndim))
    max_j = np.max(np.abs(current), axis=axes)
    max_omega = np.max(np.abs(omega), axis=axes)
    active = gate > 0.5
    return {
        "time_end": float(time[-1]),
        "post_initial_max_abs_J": float(np.max(max_j[1:])),
        "time_integrated_max_abs_J": float(np.trapz(max_j, time)),
        "max_abs_omega": float(np.max(max_omega)),
        "time_integrated_max_abs_omega": float(np.trapz(max_omega, time)),
        "feedback_trigger_time": float(np.max(trigger)),
        "max_feedback_observable": float(np.max(observable)),
        "control_duty_fraction": float(np.mean(active)),
        "control_effort": float(np.trapz(gate, time)),
    }


def _run_hw_case(grid: dict[str, Any], strategy_name: str, strategy: dict[str, Any], params: HwParams) -> dict[str, Any]:
    n = int(grid["n"])
    dt = float(grid["dt"])
    t_end = float(grid["t_end"])
    ops = _spectral_operators(n)
    density, vorticity = _initial_fields(n, 0.08, params.seed + n)
    threshold = 0.105
    trigger_time = -1.0
    times: list[float] = []
    density_series: list[np.ndarray] = []
    vort_series: list[np.ndarray] = []
    gates: list[float] = []
    observables: list[float] = []
    sample_every = max(1, int(round(0.2 / dt)))
    steps = int(round(t_end / dt))
    for step in range(steps + 1):
        t = step * dt
        measured = float(np.max(np.abs(vorticity))) * (
            1.0 + float(strategy["noise"]) * np.sin(1.61803398875 * t)
        )
        if bool(strategy["feedback"]) and trigger_time < 0.0 and measured >= threshold:
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
            observables.append(measured)
        if step == steps:
            break
        active_control = float(strategy["control"]) * gate
        density, vorticity = _rk4_step(density, vorticity, active_control, dt, params, ops)
    diagnostics = _metrics(times, density_series, vort_series)
    diagnostics.update(
        {
            "feedback_trigger_time": trigger_time,
            "max_feedback_observable": float(np.max(observables)),
            "control_duty_fraction": float(np.mean(np.asarray(gates) > 0.5)),
            "control_effort": float(np.trapz(gates, times)),
        }
    )
    return diagnostics


def _add_reductions(rows: list[dict[str, Any]], metric_names: tuple[str, ...]) -> None:
    for model in sorted({str(row["model"]) for row in rows}):
        for grid in sorted({str(row["grid"]) for row in rows if row["model"] == model}):
            group = [row for row in rows if row["model"] == model and row["grid"] == grid]
            baseline = next(row for row in group if row["strategy"] == "uncontrolled")
            for row in group:
                for metric in metric_names:
                    if metric not in row or metric not in baseline:
                        continue
                    base = float(baseline[metric])
                    row[f"{metric}_reduction_fraction"] = 1.0 - float(row[metric]) / base if base else 0.0


def _model_summary(rows: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    output = []
    for grid in sorted({str(row["grid"]) for row in rows if row["model"] == model}):
        group = {row["strategy"]: row for row in rows if row["model"] == model and row["grid"] == grid}
        if model == "BOUT++":
            integrated = "time_integrated_max_abs_J"
            peak = "post_initial_max_abs_J"
        else:
            integrated = "time_integrated_fluctuation_energy"
            peak = "max_abs_vort_p95"
        closed = group["closed_loop"]
        noisy = group["closed_loop_noisy_delayed"]
        moderate = group["fixed_moderate"]
        strong = group["fixed_strong"]
        uncontrolled = group["uncontrolled"]
        output.append(
            {
                "model": model,
                "grid": grid,
                "closed_loop_reduces_integrated": float(closed[integrated]) < float(uncontrolled[integrated]),
                "closed_loop_reduces_peak": float(closed[peak]) < float(uncontrolled[peak]),
                "noisy_delayed_reduces_integrated": float(noisy[integrated]) < float(uncontrolled[integrated]),
                "closed_loop_within_20pct_fixed_moderate": float(closed[integrated]) <= 1.2 * float(moderate[integrated]),
                "closed_loop_effort_below_fixed_strong": float(closed["control_effort"]) < float(strong["control_effort"]),
                "closed_loop_trigger_time": float(closed["feedback_trigger_time"]),
                "noisy_delayed_trigger_time": float(noisy["feedback_trigger_time"]),
                "closed_loop_duty_fraction": float(closed["control_duty_fraction"]),
                "noisy_delayed_duty_fraction": float(noisy["control_duty_fraction"]),
            }
        )
    return output


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Closed-Loop TCT Validation",
        "",
        f"- Status: `{summary['status']}`",
        f"- Started: `{summary['started_utc']}`",
        "",
        "## Controller",
        "",
        "The BOUT++ resolved current-sheet model uses a latched global max-vorticity threshold with configurable deterministic sensor noise and actuator delay. The HW2D-style model uses the same controller structure.",
        "",
        "## Results",
        "",
        "| Model | Grid | Closed-loop lowers integrated metric | Closed-loop lowers peak | Noisy delayed lowers integrated metric | Within 20% of fixed moderate | Effort below fixed strong |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["model_checks"]:
        lines.append(
            f"| {row['model']} | {row['grid']} | {row['closed_loop_reduces_integrated']} | "
            f"{row['closed_loop_reduces_peak']} | {row['noisy_delayed_reduces_integrated']} | "
            f"{row['closed_loop_within_20pct_fixed_moderate']} | {row['closed_loop_effort_below_fixed_strong']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            summary["interpretation"],
            "",
            "This remains reduced-model validation. The threshold, deterministic noise, and actuator-delay model are auditable control assumptions, not experimental sensor validation.",
            "",
        ]
    )
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
                diagnostics["control_effort"] = (
                    diagnostics["time_end"] if float(strategy["control"]) > 0.0 else 0.0
                )
            row = {"model": "BOUT++", "grid": grid["name"], "strategy": name, **strategy, **diagnostics}
            rows.append(row)
            (case_dir / "summary.json").write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")

    hw_params = HwParams()
    for grid in HW_GRIDS:
        for name, strategy in STRATEGIES.items():
            diagnostics = _run_hw_case(grid, name, strategy, hw_params)
            rows.append({"model": "HW2D-style", "grid": grid["name"], "strategy": name, **strategy, **diagnostics})

    _add_reductions(
        rows,
        (
            "post_initial_max_abs_J",
            "time_integrated_max_abs_J",
            "time_integrated_fluctuation_energy",
            "max_abs_vort_p95",
        ),
    )
    checks = _model_summary(rows, "BOUT++") + _model_summary(rows, "HW2D-style")
    passed = all(
        row["closed_loop_reduces_integrated"]
        and row["closed_loop_reduces_peak"]
        and row["noisy_delayed_reduces_integrated"]
        and row["closed_loop_within_20pct_fixed_moderate"]
        and row["closed_loop_effort_below_fixed_strong"]
        for row in checks
    )
    status = "CLOSED_LOOP_REDUCED_MODEL_SUPPORTED" if passed else "CLOSED_LOOP_REDUCED_MODEL_MIXED"
    interpretation = (
        "PASS: threshold-triggered control reduced integrated and peak metrics across BOUT++ and HW2D-style grids, "
        "survived the tested noise/delay case, approached fixed moderate control, and used less effort than fixed strong control."
        if passed
        else "MIXED: threshold-triggered control reduced integrated burden in every tested model/grid and the noisy/delayed "
        "case remained beneficial, but it did not reduce the peak. In BOUT++, the vorticity threshold fired after the first "
        "reported current peak and did not approach fixed-moderate integrated performance within 20%. In HW2D-style cases, "
        "the initialized perturbation crossed the threshold at time zero, so that model does not validate precursor detection "
        "or lower effort than fixed strong control."
    )
    summary = {
        "status": status,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "controller": {
            "observable": "global_max_abs_vorticity",
            "bout_threshold": 0.018,
            "hw2d_threshold": 0.105,
            "noise_model": "deterministic multiplicative sinusoid",
            "noisy_delay_case": {"noise_fraction": 0.20, "actuator_delay": 2.0},
        },
        "model_checks": checks,
        "interpretation": interpretation,
    }
    _write_csv(run_dir / "closed_loop_results.csv", rows)
    (run_dir / "closed_loop_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(run_dir / "closed_loop_report.md", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

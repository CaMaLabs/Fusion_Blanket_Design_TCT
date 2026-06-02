#!/usr/bin/env python3
"""Run robustness checks for the resolved BOUT++ TCT current-sheet actuator."""

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

from bout_tct_current_sheet_sweep import BUILD_DIR, MODEL_DIR, _build_model, _evaluate_base
from bout_validation_bridge import DEFAULT_BOUT_BUILD, DEFAULT_BOUT_TOP, REPO, _safe_float


BASE_GRID = {"name": "base", "nx": 96, "nz": 96, "dx": 0.12, "dz": 0.12, "sheet_width": 0.055}
FINE_GRID = {"name": "fine", "nx": 128, "nz": 128, "dx": 0.09, "dz": 0.09, "sheet_width": 0.045}


def _base_strength(plasma: dict[str, Any], reactor: dict[str, Any]) -> float:
    wall_load = _safe_float(reactor.get("wall_load", plasma.get("wn_mw_m2", 1.0)), 1.0)
    return 0.08 + 0.04 * min(wall_load, 3.0)


def _cases(plasma: dict[str, Any], reactor: dict[str, Any]) -> list[dict[str, Any]]:
    strength = _base_strength(plasma, reactor)
    cases: list[dict[str, Any]] = [
        {
            "case": "base_uncontrolled",
            "family": "baseline",
            "grid": BASE_GRID,
            "control": 0.0,
            "actuator_center": 0.5,
            "actuator_width": 1.7 * BASE_GRID["sheet_width"],
            "start_time": 0.0,
            "end_time": 1e30,
        },
        {
            "case": "base_nominal",
            "family": "baseline",
            "grid": BASE_GRID,
            "control": 0.8,
            "actuator_center": 0.5,
            "actuator_width": 1.7 * BASE_GRID["sheet_width"],
            "start_time": 0.0,
            "end_time": 1e30,
        },
    ]

    for offset in (-0.08, -0.04, 0.04, 0.08):
        cases.append(
            {
                "case": f"placement_{offset:+.2f}".replace("+", "p").replace("-", "m").replace(".", "p"),
                "family": "placement",
                "grid": BASE_GRID,
                "control": 0.8,
                "actuator_center": 0.5 + offset,
                "actuator_width": 1.7 * BASE_GRID["sheet_width"],
                "start_time": 0.0,
                "end_time": 1e30,
            }
        )

    for width_scale in (0.8, 1.2, 2.2):
        cases.append(
            {
                "case": f"width_{width_scale:.1f}x".replace(".", "p"),
                "family": "width",
                "grid": BASE_GRID,
                "control": 0.8,
                "actuator_center": 0.5,
                "actuator_width": width_scale * BASE_GRID["sheet_width"],
                "start_time": 0.0,
                "end_time": 1e30,
            }
        )

    for label, start_time, end_time in (("delayed2", 2.0, 1e30), ("delayed4", 4.0, 1e30), ("pulse0_8", 0.0, 8.0)):
        cases.append(
            {
                "case": f"timing_{label}",
                "family": "timing",
                "grid": BASE_GRID,
                "control": 0.8,
                "actuator_center": 0.5,
                "actuator_width": 1.7 * BASE_GRID["sheet_width"],
                "start_time": start_time,
                "end_time": end_time,
            }
        )

    for control in (0.4, 1.2):
        cases.append(
            {
                "case": f"strength_{control:.1f}".replace(".", "p"),
                "family": "strength",
                "grid": BASE_GRID,
                "control": control,
                "actuator_center": 0.5,
                "actuator_width": 1.7 * BASE_GRID["sheet_width"],
                "start_time": 0.0,
                "end_time": 1e30,
            }
        )

    for control in (0.0, 0.8):
        cases.append(
            {
                "case": f"fine_tct{int(round(control * 100)):03d}",
                "family": "resolution",
                "grid": FINE_GRID,
                "control": control,
                "actuator_center": 0.5,
                "actuator_width": 1.7 * FINE_GRID["sheet_width"],
                "start_time": 0.0,
                "end_time": 1e30,
            }
        )

    for case in cases:
        case["tct_strength"] = strength * float(case["control"])
        case["omega_tct_strength"] = 0.5 * strength * float(case["control"])
        case["eta"] = 7.5e-4
        case["nu"] = 1.0e-3
        case["psi_amp"] = 0.08
        case["island_seed"] = 0.006
        case["omega_seed"] = 0.01
    return cases


def _write_inp(case_dir: Path, case: dict[str, Any], nout: int) -> None:
    grid = case["grid"]
    case_dir.mkdir(parents=True, exist_ok=True)
    text = f"""
MYG = 0
periodicX = true

[mesh]
nx = {int(grid["nx"])}
ny = 1
nz = {int(grid["nz"])}
dx = {float(grid["dx"]):.8g}
dy = 1.0
dz = {float(grid["dz"]):.8g}

[tct]
eta = {case["eta"]:.8g}
nu = {case["nu"]:.8g}
strength = {case["tct_strength"]:.8g}
omega_strength = {case["omega_tct_strength"]:.8g}
start_time = {case["start_time"]:.8g}
end_time = {case["end_time"]:.8g}
bracket = 2

[psi]
scale = 1.0
function = {case["psi_amp"]:.8g} * exp(-((x-0.5)/{grid["sheet_width"]:.8g})^2) + {case["island_seed"]:.8g} * cos(z)
bndry_all = dirichlet_o2

[omega]
scale = 1.0
function = {case["omega_seed"]:.8g} * sin(z) * exp(-((x-0.5)/(2*{grid["sheet_width"]:.8g}))^2)
bndry_all = dirichlet_o2

[tct_mask]
scale = 1.0
function = exp(-((x-{case["actuator_center"]:.8g})/{case["actuator_width"]:.8g})^2)
bndry_all = dirichlet_o2

[solver]
output_step = 1.0
nout = {int(nout)}
mxstep = 10000
atol = 1e-10
rtol = 1e-6
"""
    (case_dir / "BOUT.inp").write_text(text, encoding="utf-8")


def _run_case(exe: Path, case_dir: Path) -> None:
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


def _summarize(case_dir: Path) -> dict[str, float]:
    output = case_dir / "BOUT.dmp.0.nc"
    if not output.exists():
        raise FileNotFoundError(f"BOUT++ output not found: {output}")

    with netCDF4.Dataset(output) as ds:
        current = np.asarray(ds.variables["J"][:], dtype=float)
        omega = np.asarray(ds.variables["omega"][:], dtype=float)
        psi = np.asarray(ds.variables["psi"][:], dtype=float)
        time = np.asarray(ds.variables["t_array"][:], dtype=float)

    axes = tuple(range(1, current.ndim))
    abs_j = np.abs(current)
    abs_omega = np.abs(omega)
    max_j = np.max(abs_j, axis=axes)
    p99_j = np.percentile(abs_j.reshape((abs_j.shape[0], -1)), 99, axis=1)
    max_omega = np.max(abs_omega, axis=axes)
    magnetic_energy = 0.5 * np.mean(psi * psi, axis=axes)

    return {
        "time_end": float(time[-1]),
        "initial_max_abs_J": float(max_j[0]),
        "post_initial_max_abs_J": float(np.max(max_j[1:])) if len(max_j) > 1 else float(max_j[0]),
        "final_max_abs_J": float(max_j[-1]),
        "time_integrated_max_abs_J": float(np.trapz(max_j, time)),
        "post_initial_max_abs_J_p99": float(np.max(p99_j[1:])) if len(p99_j) > 1 else float(p99_j[0]),
        "final_abs_J_p99": float(p99_j[-1]),
        "max_abs_omega": float(np.max(max_omega)),
        "time_integrated_max_abs_omega": float(np.trapz(max_omega, time)),
        "initial_magnetic_energy": float(magnetic_energy[0]),
        "final_magnetic_energy": float(magnetic_energy[-1]),
    }


def _row(case_dir: Path, case: dict[str, Any], diagnostics: dict[str, float]) -> dict[str, Any]:
    grid = case["grid"]
    fields = {
        key: value
        for key, value in case.items()
        if key not in {"grid"}
    }
    return {
        "case": case_dir.name,
        "case_dir": str(case_dir),
        "grid": grid["name"],
        "nx": grid["nx"],
        "nz": grid["nz"],
        "sheet_width": grid["sheet_width"],
        **fields,
        **diagnostics,
    }


def _add_reductions(rows: list[dict[str, Any]]) -> None:
    baselines = {
        str(row["grid"]): row
        for row in rows
        if row["family"] in {"baseline", "resolution"} and float(row["control"]) == 0.0
    }
    for row in rows:
        baseline = baselines[str(row["grid"])]
        for metric in ("post_initial_max_abs_J", "time_integrated_max_abs_J", "post_initial_max_abs_J_p99"):
            base_value = float(baseline[metric])
            value = float(row[metric])
            row[f"{metric}_reduction_fraction"] = 1.0 - value / base_value if base_value else float("nan")


def _trend(rows: list[dict[str, Any]]) -> dict[str, Any]:
    _add_reductions(rows)
    controlled = [row for row in rows if float(row["control"]) > 0.0]
    robust = [
        row
        for row in controlled
        if float(row["post_initial_max_abs_J_reduction_fraction"]) > 0.0
        and float(row["time_integrated_max_abs_J_reduction_fraction"]) > 0.0
    ]
    ranked = sorted(
        controlled,
        key=lambda row: (
            float(row["time_integrated_max_abs_J_reduction_fraction"]),
            float(row["post_initial_max_abs_J_reduction_fraction"]),
        ),
        reverse=True,
    )
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in controlled:
        by_family.setdefault(str(row["family"]), []).append(row)

    family_summary = {}
    for family, group in sorted(by_family.items()):
        family_summary[family] = {
            "cases": len(group),
            "all_reduce_post_initial_peak_J": all(float(row["post_initial_max_abs_J_reduction_fraction"]) > 0.0 for row in group),
            "all_reduce_integrated_J": all(float(row["time_integrated_max_abs_J_reduction_fraction"]) > 0.0 for row in group),
            "min_post_initial_peak_J_reduction_fraction": min(
                float(row["post_initial_max_abs_J_reduction_fraction"]) for row in group
            ),
            "min_integrated_J_reduction_fraction": min(
                float(row["time_integrated_max_abs_J_reduction_fraction"]) for row in group
            ),
            "max_integrated_J_reduction_fraction": max(
                float(row["time_integrated_max_abs_J_reduction_fraction"]) for row in group
            ),
        }

    return {
        "interpretation": (
            "PASS: all tested resolved TCT actuator robustness cases reduced current-sheet peak and integrated current."
            if len(robust) == len(controlled)
            else "CHECK: at least one resolved TCT actuator robustness case failed a current reduction metric."
        ),
        "controlled_cases": len(controlled),
        "robust_cases": len(robust),
        "family_summary": family_summary,
        "top_cases": [
            {
                "case": row["case"],
                "family": row["family"],
                "grid": row["grid"],
                "post_initial_max_J_reduction_fraction": row["post_initial_max_abs_J_reduction_fraction"],
                "integrated_J_reduction_fraction": row["time_integrated_max_abs_J_reduction_fraction"],
            }
            for row in ranked[:5]
        ],
        "weakest_cases": [
            {
                "case": row["case"],
                "family": row["family"],
                "grid": row["grid"],
                "post_initial_max_J_reduction_fraction": row["post_initial_max_abs_J_reduction_fraction"],
                "integrated_J_reduction_fraction": row["time_integrated_max_abs_J_reduction_fraction"],
            }
            for row in ranked[-5:]
        ],
    }


def _write_outputs(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with (run_dir / "tct_actuator_robustness_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "tct_actuator_robustness_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bout-top", type=Path, default=Path(DEFAULT_BOUT_TOP))
    parser.add_argument("--bout-build", type=Path, default=Path(DEFAULT_BOUT_BUILD))
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--nout", type=int, default=18)
    parser.add_argument("--keep-existing", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    _design, plasma, reactor = _evaluate_base()
    exe = BUILD_DIR / "tct_current_sheet" if args.skip_build else _build_model(args.bout_build)
    if args.run_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = REPO / "validation_runs" / f"bout_tct_actuator_robustness_{stamp}"
    else:
        run_dir = args.run_dir

    if run_dir.exists() and not args.keep_existing:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for case in _cases(plasma, reactor):
        case_dir = run_dir / str(case["case"])
        _write_inp(case_dir, case, args.nout)
        _run_case(exe, case_dir)
        diagnostics = _summarize(case_dir)
        case_summary = {"case_parameters": {k: v for k, v in case.items() if k != "grid"}, "grid": case["grid"], "diagnostics": diagnostics}
        (case_dir / "summary.json").write_text(json.dumps(case_summary, indent=2, sort_keys=True), encoding="utf-8")
        rows.append(_row(case_dir, case, diagnostics))
        cases.append({"case": case_dir.name, **case_summary})

    summary = {
        "run_dir": str(run_dir),
        "model_dir": str(MODEL_DIR),
        "executable": str(exe),
        "bout_top": str(args.bout_top),
        "bout_build": str(args.bout_build),
        "control_mapping": "localized_resolved_psi_and_vorticity_damping_mask_with_position_width_timing_strength_variants",
        "base_plasma_summary": {
            "pfus_mw": _safe_float(plasma.get("pfus_mw"), 0.0),
            "wn_mw_m2": _safe_float(plasma.get("wn_mw_m2"), 0.0),
            "betaN": _safe_float(plasma.get("betaN"), 0.0),
            "qstar": _safe_float(plasma.get("qstar"), 0.0),
        },
        "base_reactor_summary": {
            "wall_load": _safe_float(reactor.get("wall_load"), 0.0),
            "event_loss_frac": _safe_float(reactor.get("event_loss_frac"), 0.0),
        },
        "trend_summary": _trend(rows),
        "cases": cases,
    }
    _write_outputs(run_dir, rows, summary)
    print(json.dumps({"run_dir": str(run_dir), **summary["trend_summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

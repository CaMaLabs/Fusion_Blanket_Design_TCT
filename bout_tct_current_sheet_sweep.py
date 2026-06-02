#!/usr/bin/env python3
"""Build and run a resolved BOUT++ TCT current-sheet validation sweep."""

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

from bout_validation_bridge import DEFAULT_BOUT_BUILD, DEFAULT_BOUT_TOP, REPO, _safe_float
from fusion_engine_v5.engine.config import DEFAULT_DESIGN
from fusion_engine_v5.engine.plasma_model import evaluate_case
from fusion_engine_v5.engine.reactor_simulation import simulate_reactor


MODEL_DIR = REPO / "validation_models" / "tct_current_sheet"
BUILD_DIR = MODEL_DIR / "build"
CONTROLS = (0.0, 0.4, 0.8)
GRID_CASES = (
    {"name": "coarse", "nx": 64, "nz": 64, "dx": 0.18, "dz": 0.18, "sheet_width": 0.070},
    {"name": "base", "nx": 96, "nz": 96, "dx": 0.12, "dz": 0.12, "sheet_width": 0.055},
)


def _evaluate_base() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    design = dict(DEFAULT_DESIGN)
    plasma = evaluate_case(
        design["R"],
        design["a"],
        design["kappa"],
        design["B0"],
        design["Ip"],
        design["Ti"],
        design["Te"],
        design["H98"],
        design["fG"],
        design["frac_cap"],
    )
    reactor = simulate_reactor(design, blanket_validate=False)
    return design, plasma, reactor


def _build_model(bout_build: Path) -> Path:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    mpicxx = os.environ.get("MPICXX", "/usr/bin/mpicxx.mpich")
    subprocess.run(
        [
            "cmake",
            "-S",
            str(MODEL_DIR),
            "-B",
            str(BUILD_DIR),
            f"-Dbout++_DIR={bout_build}",
            f"-DCMAKE_CXX_COMPILER={mpicxx}",
            f"-DMPI_CXX_COMPILER={mpicxx}",
            "-DMPIEXEC_EXECUTABLE=/usr/bin/mpiexec.mpich",
        ],
        check=True,
    )
    subprocess.run(["cmake", "--build", str(BUILD_DIR), "-j2"], check=True)
    exe = BUILD_DIR / "tct_current_sheet"
    if not exe.exists():
        raise FileNotFoundError(f"Current-sheet executable not found: {exe}")
    return exe


def _case_name(grid: dict[str, Any], control: float) -> str:
    return f"{grid['name']}_resolved_tct{int(round(control * 100)):03d}"


def _params(plasma: dict[str, Any], reactor: dict[str, Any], grid: dict[str, Any], control: float) -> dict[str, float]:
    wall_load = _safe_float(reactor.get("wall_load", plasma.get("wn_mw_m2", 1.0)), 1.0)
    base_strength = 0.08 + 0.04 * min(wall_load, 3.0)
    return {
        "control": float(control),
        "tct_strength": float(base_strength * control),
        "omega_tct_strength": float(0.5 * base_strength * control),
        "eta": 7.5e-4,
        "nu": 1.0e-3,
        "sheet_width": float(grid["sheet_width"]),
        "actuator_width": float(1.7 * grid["sheet_width"]),
        "psi_amp": 0.08,
        "island_seed": 0.006,
        "omega_seed": 0.01,
        "wall_load_mw_m2": wall_load,
    }


def _write_inp(case_dir: Path, grid: dict[str, Any], params: dict[str, float], nout: int) -> None:
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
eta = {params["eta"]:.8g}
nu = {params["nu"]:.8g}
strength = {params["tct_strength"]:.8g}
omega_strength = {params["omega_tct_strength"]:.8g}
bracket = 2

[psi]
scale = 1.0
function = {params["psi_amp"]:.8g} * exp(-((x-0.5)/{params["sheet_width"]:.8g})^2) + {params["island_seed"]:.8g} * cos(z)
bndry_all = dirichlet_o2

[omega]
scale = 1.0
function = {params["omega_seed"]:.8g} * sin(z) * exp(-((x-0.5)/(2*{params["sheet_width"]:.8g}))^2)
bndry_all = dirichlet_o2

[tct_mask]
scale = 1.0
function = exp(-((x-0.5)/{params["actuator_width"]:.8g})^2)
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
    current_integral = np.sum(abs_j, axis=axes)
    current_concentration = np.divide(max_j, current_integral, out=np.zeros_like(max_j), where=current_integral > 0.0)

    return {
        "time_start": float(time[0]),
        "time_end": float(time[-1]),
        "initial_max_abs_J": float(max_j[0]),
        "final_max_abs_J": float(max_j[-1]),
        "max_abs_J": float(np.max(max_j)),
        "post_initial_max_abs_J": float(np.max(max_j[1:])) if len(max_j) > 1 else float(max_j[0]),
        "time_integrated_max_abs_J": float(np.trapz(max_j, time)),
        "max_abs_J_p99": float(np.max(p99_j)),
        "post_initial_max_abs_J_p99": float(np.max(p99_j[1:])) if len(p99_j) > 1 else float(p99_j[0]),
        "final_abs_J_p99": float(p99_j[-1]),
        "max_abs_omega": float(np.max(max_omega)),
        "time_integrated_max_abs_omega": float(np.trapz(max_omega, time)),
        "initial_magnetic_energy": float(magnetic_energy[0]),
        "final_magnetic_energy": float(magnetic_energy[-1]),
        "max_current_concentration": float(np.max(current_concentration)),
        "final_current_concentration": float(current_concentration[-1]),
    }


def _row(case_dir: Path, grid: dict[str, Any], params: dict[str, float], summary: dict[str, float]) -> dict[str, Any]:
    return {
        "case": case_dir.name,
        "case_dir": str(case_dir),
        "grid": grid["name"],
        "nx": grid["nx"],
        "nz": grid["nz"],
        **params,
        **summary,
    }


def _trend(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_grid: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_grid.setdefault(str(row["grid"]), []).append(row)

    grid_trends = []
    for grid, group in sorted(by_grid.items()):
        ordered = sorted(group, key=lambda row: float(row["control"]))
        max_j = [float(row["post_initial_max_abs_J"]) for row in ordered]
        int_j = [float(row["time_integrated_max_abs_J"]) for row in ordered]
        p99_j = [float(row["post_initial_max_abs_J_p99"]) for row in ordered]
        grid_trends.append(
            {
                "grid": grid,
                "max_J_monotonic_decrease": all(a >= b for a, b in zip(max_j, max_j[1:])),
                "integrated_J_monotonic_decrease": all(a >= b for a, b in zip(int_j, int_j[1:])),
                "p99_J_monotonic_decrease": all(a >= b for a, b in zip(p99_j, p99_j[1:])),
                "post_initial_max_J_at_control_0": max_j[0],
                "post_initial_max_J_at_control_1": max_j[-1],
                "post_initial_max_J_reduction_fraction": 1.0 - max_j[-1] / max_j[0] if max_j[0] else float("nan"),
                "integrated_J_at_control_0": int_j[0],
                "integrated_J_at_control_1": int_j[-1],
                "integrated_J_reduction_fraction": 1.0 - int_j[-1] / int_j[0] if int_j[0] else float("nan"),
            }
        )

    supported = all(
        item["max_J_monotonic_decrease"] and item["integrated_J_monotonic_decrease"] for item in grid_trends
    )
    return {
        "grid_trends": grid_trends,
        "all_grid_trends_supported": supported,
        "interpretation": (
            "PASS: resolved TCT actuator reduced current-sheet peak and integrated current diagnostics."
            if supported
            else "CHECK: resolved TCT actuator failed at least one current-sheet trend."
        ),
    }


def _write_outputs(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with (run_dir / "tct_current_sheet_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "tct_current_sheet_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bout-top", type=Path, default=Path(DEFAULT_BOUT_TOP))
    parser.add_argument("--bout-build", type=Path, default=Path(DEFAULT_BOUT_BUILD))
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--nout", type=int, default=20)
    parser.add_argument("--keep-existing", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    _design, plasma, reactor = _evaluate_base()
    exe = BUILD_DIR / "tct_current_sheet" if args.skip_build else _build_model(args.bout_build)
    if args.run_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = REPO / "validation_runs" / f"bout_tct_current_sheet_sweep_{stamp}"
    else:
        run_dir = args.run_dir

    if run_dir.exists() and not args.keep_existing:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for grid in GRID_CASES:
        for control in CONTROLS:
            params = _params(plasma, reactor, grid, control)
            case_dir = run_dir / _case_name(grid, control)
            _write_inp(case_dir, grid, params, args.nout)
            _run_case(exe, case_dir)
            diagnostics = _summarize(case_dir)
            case_summary = {"grid": grid, "mapped_parameters": params, "diagnostics": diagnostics}
            (case_dir / "summary.json").write_text(json.dumps(case_summary, indent=2, sort_keys=True), encoding="utf-8")
            rows.append(_row(case_dir, grid, params, diagnostics))
            cases.append({"case": case_dir.name, **case_summary})

    summary = {
        "run_dir": str(run_dir),
        "model_dir": str(MODEL_DIR),
        "executable": str(exe),
        "bout_top": str(args.bout_top),
        "bout_build": str(args.bout_build),
        "controls": list(CONTROLS),
        "control_mapping": "localized_resolved_psi_and_vorticity_damping_mask",
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

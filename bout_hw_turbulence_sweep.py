#!/usr/bin/env python3
"""Run a BOUT++ Hasegawa-Wakatani reduced-turbulence validation sweep."""

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


CONTROLS = (0.0, 0.5, 1.0)
GRID_CASES = (
    {"name": "coarse", "nx": 48, "nz": 48, "dx": 0.28, "dz": 0.28},
    {"name": "base", "nx": 64, "nz": 64, "dx": 0.22, "dz": 0.22},
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


def _hw_params(plasma: dict[str, Any], reactor: dict[str, Any], control: float) -> dict[str, float]:
    wall_load = _safe_float(reactor.get("wall_load", plasma.get("wn_mw_m2", 1.0)), 1.0)
    base_kappa = max(0.2, min(0.9, 0.25 + 0.15 * wall_load))
    return {
        "control": float(control),
        "alpha": 1.0,
        "kappa": float(base_kappa * (1.0 - 0.45 * control)),
        "Dvort": 1e-4,
        "Dn": 1e-4,
        "vort_scale": float(0.08 * (1.0 - 0.25 * control)),
        "wall_load_mw_m2": wall_load,
        "base_kappa": float(base_kappa),
    }


def _case_name(grid: dict[str, Any], control: float) -> str:
    return f"{grid['name']}_drive_tct{int(round(control * 100)):03d}"


def _write_hw_inp(case_dir: Path, grid: dict[str, Any], params: dict[str, float], nout: int) -> None:
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

[hw]
alpha = {params["alpha"]:.8g}
kappa = {params["kappa"]:.8g}
Dvort = {params["Dvort"]:.8g}
Dn = {params["Dn"]:.8g}
modified = true
bracket = 2

[all]
scale = 0.0
bndry_all = dirichlet_o2

[vort]
scale = {params["vort_scale"]:.8g}
function = mixmode(2*pi*x) * mixmode(z)

[solver]
output_step = 1.0
nout = {int(nout)}
"""
    (case_dir / "BOUT.inp").write_text(text, encoding="utf-8")


def _run_hw(case_dir: Path, bout_build: Path) -> None:
    exe = bout_build / "examples" / "hasegawa-wakatani" / "hasegawa-wakatani"
    if not exe.exists():
        raise FileNotFoundError(f"BOUT++ Hasegawa-Wakatani executable not found: {exe}")

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


def _summarize_hw(case_dir: Path) -> dict[str, float]:
    output = case_dir / "BOUT.dmp.0.nc"
    if not output.exists():
        raise FileNotFoundError(f"BOUT++ output not found: {output}")

    with netCDF4.Dataset(output) as ds:
        density = np.asarray(ds.variables["n"][:], dtype=float)
        vort = np.asarray(ds.variables["vort"][:], dtype=float)
        phi = np.asarray(ds.variables["phi"][:], dtype=float)
        time = np.asarray(ds.variables["t_array"][:], dtype=float)

    axes = tuple(range(1, density.ndim))
    n_rms = np.sqrt(np.mean(density * density, axis=axes))
    vort_rms = np.sqrt(np.mean(vort * vort, axis=axes))
    phi_rms = np.sqrt(np.mean(phi * phi, axis=axes))
    fluct_energy = 0.5 * (n_rms * n_rms + vort_rms * vort_rms)
    n_abs = np.abs(density.reshape((density.shape[0], -1)))
    vort_abs = np.abs(vort.reshape((vort.shape[0], -1)))

    return {
        "time_start": float(time[0]),
        "time_end": float(time[-1]),
        "max_n_rms": float(np.max(n_rms)),
        "final_n_rms": float(n_rms[-1]),
        "max_vort_rms": float(np.max(vort_rms)),
        "final_vort_rms": float(vort_rms[-1]),
        "max_phi_rms": float(np.max(phi_rms)),
        "max_fluctuation_energy": float(np.max(fluct_energy)),
        "final_fluctuation_energy": float(fluct_energy[-1]),
        "time_integrated_fluctuation_energy": float(np.trapz(fluct_energy, time)),
        "max_abs_n_p95": float(np.max(np.percentile(n_abs, 95, axis=1))),
        "max_abs_vort_p95": float(np.max(np.percentile(vort_abs, 95, axis=1))),
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
        max_energy = [float(row["max_fluctuation_energy"]) for row in ordered]
        integrated_energy = [float(row["time_integrated_fluctuation_energy"]) for row in ordered]
        n_p95 = [float(row["max_abs_n_p95"]) for row in ordered]
        grid_trends.append(
            {
                "grid": grid,
                "max_energy_monotonic_decrease": all(a >= b for a, b in zip(max_energy, max_energy[1:])),
                "integrated_energy_monotonic_decrease": all(a >= b for a, b in zip(integrated_energy, integrated_energy[1:])),
                "density_p95_monotonic_decrease": all(a >= b for a, b in zip(n_p95, n_p95[1:])),
                "max_energy_at_control_0": max_energy[0],
                "max_energy_at_control_1": max_energy[-1],
                "max_energy_reduction_fraction": 1.0 - max_energy[-1] / max_energy[0] if max_energy[0] else float("nan"),
                "integrated_energy_at_control_0": integrated_energy[0],
                "integrated_energy_at_control_1": integrated_energy[-1],
                "integrated_energy_reduction_fraction": (
                    1.0 - integrated_energy[-1] / integrated_energy[0] if integrated_energy[0] else float("nan")
                ),
            }
        )

    supported = all(
        item["max_energy_monotonic_decrease"] and item["integrated_energy_monotonic_decrease"]
        for item in grid_trends
    )
    return {
        "grid_trends": grid_trends,
        "all_grid_trends_supported": supported,
        "interpretation": (
            "PASS: reduced-gradient HW cases reduce fluctuation energy across tested grids."
            if supported
            else "CHECK: reduced-gradient HW cases failed at least one grid trend."
        ),
    }


def _write_outputs(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with (run_dir / "hw_turbulence_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "hw_turbulence_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bout-top", type=Path, default=Path(DEFAULT_BOUT_TOP))
    parser.add_argument("--bout-build", type=Path, default=Path(DEFAULT_BOUT_BUILD))
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--nout", type=int, default=40)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    _design, plasma, reactor = _evaluate_base()
    if args.run_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = REPO / "validation_runs" / f"bout_hw_turbulence_sweep_{stamp}"
    else:
        run_dir = args.run_dir

    if run_dir.exists() and not args.keep_existing:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for grid in GRID_CASES:
        for control in CONTROLS:
            params = _hw_params(plasma, reactor, control)
            case_dir = run_dir / _case_name(grid, control)
            _write_hw_inp(case_dir, grid, params, args.nout)
            _run_hw(case_dir, args.bout_build)
            hw_summary = _summarize_hw(case_dir)
            case_summary = {"grid": grid, "mapped_parameters": params, "hw_summary": hw_summary}
            (case_dir / "summary.json").write_text(json.dumps(case_summary, indent=2, sort_keys=True), encoding="utf-8")
            rows.append(_row(case_dir, grid, params, hw_summary))
            cases.append({"case": case_dir.name, **case_summary})

    summary = {
        "run_dir": str(run_dir),
        "bout_top": str(args.bout_top),
        "bout_build": str(args.bout_build),
        "controls": list(CONTROLS),
        "control_mapping": "reduced_gradient_drive_and_initial_vorticity",
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

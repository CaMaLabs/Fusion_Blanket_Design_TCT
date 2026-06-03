#!/usr/bin/env python3
"""Run a BOUT++ blob/SOL-style validation sweep for TCT source shaping."""

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
    {"name": "coarse", "nx": 48, "nz": 48, "dx": 0.35, "dz": 0.35},
    {"name": "base", "nx": 64, "nz": 64, "dx": 0.3, "dz": 0.3},
    {"name": "fine", "nx": 96, "nz": 96, "dx": 0.2, "dz": 0.2},
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


def _blob_params(design: dict[str, Any], plasma: dict[str, Any], reactor: dict[str, Any], control: float) -> dict[str, float]:
    wall_load = _safe_float(reactor.get("wall_load", plasma.get("wn_mw_m2", 1.0)), 1.0)
    base_height = max(0.1, min(0.9, 0.25 * wall_load + 0.12))
    base_width = 0.055
    spread = 1.0 + 0.75 * control

    return {
        "control": float(control),
        "height": float(base_height / (spread * spread)),
        "width": float(base_width * spread),
        "inventory_proxy": float(base_height * base_width * base_width),
        "D_n": 1e-6,
        "D_vort": 1e-6,
        "Te0": _safe_float(plasma.get("Te_keV", design.get("Te")), 15.0) * 1000.0,
        "B0": _safe_float(plasma.get("B0_T", design.get("B0")), 6.0),
        "R_c": max(1.0, _safe_float(design.get("R"), 8.0) / 4.0),
        "L_par": max(5.0, 2.0 * np.pi * _safe_float(design.get("R"), 8.0)),
        "wall_load_mw_m2": wall_load,
    }


def _case_name(grid: dict[str, Any], control: float) -> str:
    return f"{grid['name']}_source_tct{int(round(control * 100)):03d}"


def _write_blob_inp(case_dir: Path, grid: dict[str, Any], params: dict[str, float], nout: int) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    text = f"""
MXG = 2
MYG = 0

[mesh]
nx = {int(grid["nx"])}
ny = 1
nz = {int(grid["nz"])}
dx = {float(grid["dx"]):.8g}
dz = {float(grid["dz"]):.8g}

[mesh:ddx]
first = C2
second = C2
upwind = W3

[mesh:ddy]
first = C2
second = C2
upwind = W3

[mesh:ddz]
first = C2
second = C2
upwind = W3

[solver]
atol = 1e-10
rtol = 1e-05
mxstep = 10000
output_step = 5
nout = {int(nout)}

[phiSolver]
type = tri
fourth_order = true

[model]
Te0 = {params["Te0"]:.8g}
B0 = {params["B0"]:.8g}
D_vort = {params["D_vort"]:.8g}
D_n = {params["D_n"]:.8g}
R_c = {params["R_c"]:.8g}
L_par = {params["L_par"]:.8g}
compressible = false
boussinesq = true
sheath = true

[all]
scale = 0.0
bndry_all = neumann

[n]
scale = 1.0
height = {params["height"]:.8g}
width = {params["width"]:.8g}
function = 1 + height * exp(-((x-0.25)/width)^2 - ((z/(2*pi) - 0.5)/width)^2)
"""
    (case_dir / "BOUT.inp").write_text(text, encoding="utf-8")


def _run_blob(case_dir: Path, bout_build: Path) -> None:
    exe = bout_build / "examples" / "blob2d" / "blob2d"
    if not exe.exists():
        raise FileNotFoundError(f"BOUT++ blob2d executable not found: {exe}")

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


def _summarize_blob(case_dir: Path) -> dict[str, float]:
    output = case_dir / "BOUT.dmp.0.nc"
    if not output.exists():
        raise FileNotFoundError(f"BOUT++ output not found: {output}")

    with netCDF4.Dataset(output) as ds:
        density = np.asarray(ds.variables["n"][:], dtype=float)
        time = np.asarray(ds.variables["t_array"][:], dtype=float)

    excess = np.maximum(density - 1.0, 0.0)
    axes = tuple(range(1, excess.ndim))
    peak = np.max(excess, axis=axes)
    total = np.sum(excess, axis=axes)
    p95 = np.percentile(excess.reshape((excess.shape[0], -1)), 95, axis=1)
    concentration = np.divide(peak, total, out=np.zeros_like(peak), where=total > 0.0)

    return {
        "time_start": float(time[0]),
        "time_end": float(time[-1]),
        "initial_peak_excess": float(peak[0]),
        "final_peak_excess": float(peak[-1]),
        "max_peak_excess": float(np.max(peak)),
        "mean_peak_excess": float(np.mean(peak)),
        "time_integrated_peak_excess": float(np.trapz(peak, time)),
        "initial_total_excess": float(total[0]),
        "final_total_excess": float(total[-1]),
        "total_excess_fraction": float(total[-1] / total[0]) if total[0] else float("nan"),
        "max_p95_excess": float(np.max(p95)),
        "max_concentration": float(np.max(concentration)),
        "final_concentration": float(concentration[-1]),
    }


def _row(case_dir: Path, grid: dict[str, Any], params: dict[str, float], summary: dict[str, float]) -> dict[str, Any]:
    return {
        "case": case_dir.name,
        "case_dir": str(case_dir),
        "grid": grid["name"],
        "nx": grid["nx"],
        "nz": grid["nz"],
        "control": params["control"],
        "height": params["height"],
        "width": params["width"],
        "inventory_proxy": params["inventory_proxy"],
        "wall_load_mw_m2": params["wall_load_mw_m2"],
        **summary,
    }


def _trend(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_grid: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_grid.setdefault(str(row["grid"]), []).append(row)

    grid_trends = []
    for grid, group in sorted(by_grid.items()):
        ordered = sorted(group, key=lambda row: float(row["control"]))
        max_peaks = [float(row["max_peak_excess"]) for row in ordered]
        peak_integrals = [float(row["time_integrated_peak_excess"]) for row in ordered]
        concentrations = [float(row["max_concentration"]) for row in ordered]
        grid_trends.append(
            {
                "grid": grid,
                "max_peak_monotonic_decrease": all(a >= b for a, b in zip(max_peaks, max_peaks[1:])),
                "integrated_peak_monotonic_decrease": all(a >= b for a, b in zip(peak_integrals, peak_integrals[1:])),
                "concentration_monotonic_decrease": all(a >= b for a, b in zip(concentrations, concentrations[1:])),
                "max_peak_at_control_0": max_peaks[0],
                "max_peak_at_control_1": max_peaks[-1],
                "max_peak_reduction_fraction": 1.0 - max_peaks[-1] / max_peaks[0] if max_peaks[0] else float("nan"),
                "integrated_peak_at_control_0": peak_integrals[0],
                "integrated_peak_at_control_1": peak_integrals[-1],
                "integrated_peak_reduction_fraction": (
                    1.0 - peak_integrals[-1] / peak_integrals[0] if peak_integrals[0] else float("nan")
                ),
            }
        )

    supported = all(
        item["max_peak_monotonic_decrease"] and item["integrated_peak_monotonic_decrease"] for item in grid_trends
    )
    return {
        "grid_trends": grid_trends,
        "all_grid_trends_supported": supported,
        "interpretation": (
            "PASS: source-shaped blob cases reduce peak and time-integrated peak excess across tested grids."
            if supported
            else "CHECK: source-shaped blob cases failed at least one grid trend."
        ),
    }


def _write_outputs(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with (run_dir / "blob_sol_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "blob_sol_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bout-top", type=Path, default=Path(DEFAULT_BOUT_TOP))
    parser.add_argument("--bout-build", type=Path, default=Path(DEFAULT_BOUT_BUILD))
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--nout", type=int, default=12)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    design, plasma, reactor = _evaluate_base()
    if args.run_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = REPO / "validation_runs" / f"bout_blob_sol_sweep_{stamp}"
    else:
        run_dir = args.run_dir

    if run_dir.exists() and not args.keep_existing:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for grid in GRID_CASES:
        for control in CONTROLS:
            params = _blob_params(design, plasma, reactor, control)
            case_dir = run_dir / _case_name(grid, control)
            _write_blob_inp(case_dir, grid, params, args.nout)
            _run_blob(case_dir, args.bout_build)
            blob_summary = _summarize_blob(case_dir)
            case_summary = {"grid": grid, "mapped_parameters": params, "blob_summary": blob_summary}
            (case_dir / "summary.json").write_text(json.dumps(case_summary, indent=2, sort_keys=True), encoding="utf-8")
            rows.append(_row(case_dir, grid, params, blob_summary))
            cases.append({"case": case_dir.name, **case_summary})

    summary = {
        "run_dir": str(run_dir),
        "bout_top": str(args.bout_top),
        "bout_build": str(args.bout_build),
        "controls": list(CONTROLS),
        "control_mapping": "source_shaping_inventory_proxy_conserved",
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

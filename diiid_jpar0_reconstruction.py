#!/usr/bin/env python3
"""Reconstruct and validate a provisional DIII-D Jpar0 field from GEQDSK profiles."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import netCDF4
import numpy as np
from hypnotoad.cases import tokamak

from machine_equilibrium_readiness import _parse_geqdsk


REPO = Path(__file__).resolve().parent
CASE_DIR = REPO / "validation_inputs" / "geqdsk_efit_baseline" / "diii_d_158103_03796"
DEFAULT_GEQDSK = CASE_DIR / "geqdsk"
DEFAULT_GRID = CASE_DIR / "diii_d_158103_03796_hypnotoad.grd.nc"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "diiid_jpar0_reconstruction_default"
MU0 = 4.0e-7 * np.pi


def equilibrium(path: Path):
    with path.open() as handle, contextlib.redirect_stdout(io.StringIO()):
        return tokamak.read_geqdsk(handle, make_regions=False, settings={}, nonorthogonal_settings={})


def profile_derivative(function, psi: np.ndarray, span: float) -> np.ndarray:
    step = abs(span) * 1e-5
    return (function(psi + step) - function(psi - step)) / (2.0 * step)


def current_fields(eq, r: np.ndarray, psi: np.ndarray, br: np.ndarray, bz: np.ndarray, bt: np.ndarray):
    fpol = eq.fpol(psi)
    fprime = eq.fpolprime(psi)
    pprime = profile_derivative(eq.pressure, psi, eq.psi_bdry - eq.psi_axis)
    # Hypnotoad's GEQDSK sign convention requires the leading minus sign.
    jphi = -(r * pprime + fpol * fprime / (MU0 * r))
    jr = -(fprime / MU0) * br
    jz = -(fprime / MU0) * bz
    b = np.sqrt(br * br + bz * bz + bt * bt)
    jpar = (jr * br + jz * bz + jphi * bt) / b
    return jpar, jphi


def total_current_check(eq, geqdsk: dict[str, Any]) -> dict[str, float]:
    r = np.linspace(geqdsk["rleft_m"], geqdsk["rleft_m"] + geqdsk["rdim_m"], geqdsk["nw"])
    z = np.linspace(
        geqdsk["zmid_m"] - geqdsk["zdim_m"] / 2.0,
        geqdsk["zmid_m"] + geqdsk["zdim_m"] / 2.0,
        geqdsk["nh"],
    )
    rr, zz = np.meshgrid(r, z, indexing="ij")
    psi = eq.psi(rr, zz)
    psinorm = (psi - eq.psi_axis) / (eq.psi_bdry - eq.psi_axis)
    fpol = eq.fpol(psi)
    fprime = eq.fpolprime(psi)
    pprime = profile_derivative(eq.pressure, psi, eq.psi_bdry - eq.psi_axis)
    jphi = -(rr * pprime + fpol * fprime / (MU0 * rr))
    inside = (psinorm >= 0.0) & (psinorm <= 1.0)
    integrated = float(np.trapz(np.trapz(np.where(inside, jphi, 0.0), z, axis=1), r))
    reported = float(geqdsk["current_a"])
    return {
        "efit_reported_current_a": reported,
        "reconstructed_current_a": integrated,
        "relative_error": abs(integrated - reported) / abs(reported),
    }


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    check = summary["total_current_check"]
    stats = summary["mesh_jpar0"]
    lines = [
        "# DIII-D GEQDSK Jpar0 Reconstruction",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated: `{summary['generated_at']}`",
        "",
        "## Current reconstruction check",
        "",
        f"- EFIT-reported plasma current: `{check['efit_reported_current_a']:.8e}` A",
        f"- Reconstructed toroidal-current integral: `{check['reconstructed_current_a']:.8e}` A",
        f"- Relative difference: `{check['relative_error']:.6%}`",
        "",
        "## Machine-mesh Jpar0",
        "",
        f"- All values finite: `{stats['finite']}`",
        f"- Minimum: `{stats['minimum_a_per_m2']:.8e}` A/m^2",
        f"- Maximum: `{stats['maximum_a_per_m2']:.8e}` A/m^2",
        f"- RMS: `{stats['rms_a_per_m2']:.8e}` A/m^2",
        "",
        "The generated grid is retained only when `--keep-grid` is supplied. The summary",
        "records the reproducible reconstruction and its total-current residual.",
        "",
        "## Claim boundary",
        "",
        "This is a provisional axisymmetric GEQDSK-derived equilibrium-current field.",
        "It passes a total-current consistency check, but has not been independently",
        "verified against an EFIT-exported Jpar profile, exact-X-point BOUT++ evolution,",
        "or experimental current diagnostics.",
        "",
    ]
    (run_dir / "diiid_jpar0_reconstruction_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geqdsk", type=Path, default=DEFAULT_GEQDSK)
    parser.add_argument("--grid", type=Path, default=DEFAULT_GRID)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--keep-grid", action="store_true")
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    eq = equilibrium(args.geqdsk)
    geqdsk = _parse_geqdsk(args.geqdsk)
    output_grid = args.run_dir / "diii_d_158103_03796_with_jpar0.grd.nc"
    shutil.copy2(args.grid, output_grid)
    with netCDF4.Dataset(output_grid, "r+") as dataset:
        r = np.asarray(dataset["Rxy"][:], dtype=float)
        psi = np.asarray(dataset["psixy"][:], dtype=float)
        br = np.asarray(dataset["Brxy"][:], dtype=float)
        bz = np.asarray(dataset["Bzxy"][:], dtype=float)
        bt = np.asarray(dataset["Btxy"][:], dtype=float)
        jpar, _ = current_fields(eq, r, psi, br, bz, bt)
        variable = dataset.createVariable("Jpar0", "f8", ("x", "y"))
        variable.units = "A / m^2"
        variable.long_name = "Provisional GEQDSK-derived equilibrium parallel current density"
        variable[:] = jpar
        dataset.setncattr(
            "Jpar0_reconstruction",
            "Axisymmetric GEQDSK profile reconstruction; validate independently before physics claims.",
        )

    check = total_current_check(eq, geqdsk)
    mesh_stats = {
        "finite": bool(np.isfinite(jpar).all()),
        "minimum_a_per_m2": float(np.min(jpar)),
        "maximum_a_per_m2": float(np.max(jpar)),
        "rms_a_per_m2": float(np.sqrt(np.mean(jpar * jpar))),
    }
    passed = mesh_stats["finite"] and check["relative_error"] < 0.05
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "DIIID_GEQDSK_JPAR0_PROVISIONAL_SUPPORTED" if passed else "DIIID_GEQDSK_JPAR0_RECONSTRUCTION_FAILED",
        "total_current_check": check,
        "mesh_jpar0": mesh_stats,
        "formula": "Jphi=-(R*pprime+F*Fprime/(mu0*R)); Jpol=-(Fprime/mu0)*Bpol; Jpar=J dot B/|B|",
    }
    (args.run_dir / "diiid_jpar0_reconstruction_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    if not args.keep_grid:
        output_grid.unlink()
    print(json.dumps({"status": summary["status"], "total_current_relative_error": check["relative_error"]}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

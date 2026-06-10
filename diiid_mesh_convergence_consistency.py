#!/usr/bin/env python3
"""Validate DIII-D Hypnotoad mesh convergence and GEQDSK consistency."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from hypnotoad.cases import tokamak
from netCDF4 import Dataset
from scipy.interpolate import RegularGridInterpolator


REPO = Path(__file__).resolve().parent
CASE_DIR = REPO / "validation_inputs" / "geqdsk_efit_baseline" / "diii_d_158103_03796"
DEFAULT_GEQDSK = CASE_DIR / "geqdsk"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "diiid_mesh_convergence_consistency_default"
DEFAULT_HYPNOTOAD = Path("/root/.venvs/hypnotoad/bin/hypnotoad-geqdsk")

COMMON_OPTIONS = {
    "orthogonal": True,
    "psinorm_core": 0.9,
    "psinorm_pf": 0.9,
    "psinorm_sol": 1.05,
    "psinorm_sol_inner": 1.05,
    "finecontour_Nfine": 200,
    "number_of_processors": 1,
}
RESOLUTIONS = {
    "coarse": {
        "nx_core": 12,
        "nx_sol": 8,
        "ny_inner_divertor": 12,
        "ny_outer_divertor": 12,
        "ny_sol": 32,
    },
    "base": {
        "nx_core": 24,
        "nx_sol": 16,
        "ny_inner_divertor": 24,
        "ny_outer_divertor": 24,
        "ny_sol": 64,
    },
    "fine": {
        "nx_core": 36,
        "nx_sol": 24,
        "ny_inner_divertor": 36,
        "ny_outer_divertor": 36,
        "ny_sol": 96,
    },
}
CONSISTENCY_FIELDS = {
    "psixy": "psi",
    "Brxy": "Bp_R",
    "Bzxy": "Bp_Z",
    "Btxy": "Bt",
}
CONVERGENCE_FIELDS = (
    "Rxy",
    "Zxy",
    "psixy",
    "Brxy",
    "Bzxy",
    "Bpxy",
    "Btxy",
    "Bxy",
    "J",
    "g11",
    "g22",
    "g33",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_rmse(actual: np.ndarray, reference: np.ndarray) -> float:
    difference = actual - reference
    return float(np.sqrt(np.mean(difference * difference)) / max(np.sqrt(np.mean(reference * reference)), 1e-300))


def generate_mesh(hypnotoad: Path, geqdsk: Path, options: Path, output: Path, log: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="diiid_mesh_convergence_") as temp:
        environment = dict(os.environ)
        environment.setdefault("MPLBACKEND", "Agg")
        result = subprocess.run(
            [str(hypnotoad), str(geqdsk.resolve()), str(options.resolve())],
            cwd=temp,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"Hypnotoad failed for {options}; see {log}")
        shutil.copy2(Path(temp) / "bout.grd.nc", output)


def load_equilibrium(geqdsk: Path, options: dict[str, Any]):
    with geqdsk.open() as handle, contextlib.redirect_stdout(io.StringIO()):
        return tokamak.read_geqdsk(
            handle,
            make_regions=False,
            settings=options,
            nonorthogonal_settings=options,
        )


def source_consistency(mesh: Path, equilibrium) -> dict[str, Any]:
    with Dataset(mesh) as dataset:
        r = np.asarray(dataset["Rxy"][:])
        z = np.asarray(dataset["Zxy"][:])
        psi = np.asarray(dataset["psixy"][:])
        direct = {
            "psixy": equilibrium.psi(r, z),
            "Brxy": equilibrium.Bp_R(r, z),
            "Bzxy": equilibrium.Bp_Z(r, z),
            "Btxy": equilibrium.fpol(psi) / r,
        }
        fields = {}
        for name, expected in direct.items():
            actual = np.asarray(dataset[name][:])
            fields[name] = {
                "relative_rmse": relative_rmse(actual, expected),
                "maximum_absolute_error": float(np.max(np.abs(actual - expected))),
            }

        pressure = np.asarray(dataset["pressure"][:])
        direct_pressure = equilibrium.pressure(psi)
        jy1 = int(np.asarray(dataset["jyseps1_1"][:]).item()) + 1
        jy2 = int(np.asarray(dataset["jyseps2_2"][:]).item()) + 1
        connected = (slice(None), slice(jy1, jy2))
        legs = np.ones(pressure.shape, dtype=bool)
        legs[connected] = False
        pressure_result = {
            "connected_region_relative_rmse": relative_rmse(pressure[connected], direct_pressure[connected]),
            "connected_region_maximum_absolute_error": float(np.max(np.abs(pressure[connected] - direct_pressure[connected]))),
            "divertor_leg_direct_profile_relative_rmse": relative_rmse(pressure[legs], direct_pressure[legs]),
            "divertor_leg_behavior": "Hypnotoad intentionally reflects pressure in private-flux leg regions.",
        }

        topology = {
            name: int(np.asarray(dataset[name][:]).item())
            for name in (
                "nx",
                "ny",
                "ixseps1",
                "ixseps2",
                "jyseps1_1",
                "jyseps1_2",
                "jyseps2_1",
                "jyseps2_2",
            )
        }
        finite = {
            name: bool(np.isfinite(np.asarray(dataset[name][:])).all())
            for name in CONVERGENCE_FIELDS
        }
    return {
        "topology": topology,
        "source_fields": fields,
        "pressure": pressure_result,
        "required_fields_finite": all(finite.values()),
        "finite_fields": finite,
    }


def resample(mesh: Path, field: str, shape: tuple[int, int] = (120, 336)) -> np.ndarray:
    with Dataset(mesh) as dataset:
        values = np.asarray(dataset[field][:], dtype=float)
    source_x = np.linspace(0.0, 1.0, values.shape[0])
    source_y = np.linspace(0.0, 1.0, values.shape[1])
    target_x = np.linspace(0.0, 1.0, shape[0])
    target_y = np.linspace(0.0, 1.0, shape[1])
    xx, yy = np.meshgrid(target_x, target_y, indexing="ij")
    interpolator = RegularGridInterpolator((source_x, source_y), values, method="linear")
    return interpolator(np.column_stack((xx.ravel(), yy.ravel()))).reshape(shape)


def pairwise_convergence(meshes: dict[str, Path]) -> dict[str, Any]:
    results = {}
    for lower, higher in (("coarse", "base"), ("base", "fine")):
        fields = {}
        for name in CONVERGENCE_FIELDS:
            low = resample(meshes[lower], name)
            high = resample(meshes[higher], name)
            fields[name] = {
                "relative_rmse": relative_rmse(low, high),
                "maximum_absolute_difference": float(np.max(np.abs(low - high))),
            }
        results[f"{lower}_to_{higher}"] = fields
    improving = {}
    for name in CONVERGENCE_FIELDS:
        coarse_base = results["coarse_to_base"][name]["relative_rmse"]
        base_fine = results["base_to_fine"][name]["relative_rmse"]
        improving[name] = {
            "coarse_to_base_relative_rmse": coarse_base,
            "base_to_fine_relative_rmse": base_fine,
            "improves": base_fine < coarse_base,
            "improvement_ratio": base_fine / max(coarse_base, 1e-300),
        }
    return {"pairs": results, "field_trends": improving}


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# DIII-D Mesh Resolution Convergence and GEQDSK Consistency",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated: `{summary['generated_at']}`",
        f"- GEQDSK SHA-256: `{summary['geqdsk_sha256']}`",
        "",
        "## Source-equilibrium consistency",
        "",
        "| Mesh | Dimensions | psi rel. RMSE | Br rel. RMSE | Bz rel. RMSE | Bt rel. RMSE | Connected pressure rel. RMSE |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, result in summary["meshes"].items():
        topology = result["topology"]
        fields = result["source_fields"]
        lines.append(
            f"| {name} | {topology['nx']} x {topology['ny']} | "
            f"{fields['psixy']['relative_rmse']:.3e} | {fields['Brxy']['relative_rmse']:.3e} | "
            f"{fields['Bzxy']['relative_rmse']:.3e} | {fields['Btxy']['relative_rmse']:.3e} | "
            f"{result['pressure']['connected_region_relative_rmse']:.3e} |"
        )
    lines.extend(
        [
            "",
            "The pressure comparison is restricted to the core/SOL-connected region.",
            "Hypnotoad intentionally reflects pressure across flux in private-flux",
            "divertor legs, so direct GEQDSK profile equality is not expected there.",
            "",
            "## Resolution convergence",
            "",
            "| Field | Coarse to base rel. RMSE | Base to fine rel. RMSE | Improves |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for name, trend in summary["convergence"]["field_trends"].items():
        lines.append(
            f"| `{name}` | {trend['coarse_to_base_relative_rmse']:.6e} | "
            f"{trend['base_to_fine_relative_rmse']:.6e} | {trend['improves']} |"
        )
    lines.extend(
        [
            "",
            f"- Improving fields: `{summary['improving_field_count']} / {summary['field_count']}`",
            f"- All required mesh fields finite: `{summary['all_required_fields_finite']}`",
            f"- All source-equilibrium checks pass: `{summary['all_source_checks_pass']}`",
            "",
            "## Claim boundary",
            "",
            "This validates field-aligned mesh generation consistency and quantifies",
            "resolution sensitivity for one DIII-D equilibrium. It does not establish",
            "physics-solution convergence, exact-topology BOUT++ evolution, TCT control",
            "performance, or agreement with experimental diagnostics.",
            "",
        ]
    )
    (run_dir / "diiid_mesh_convergence_consistency_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geqdsk", type=Path, default=DEFAULT_GEQDSK)
    parser.add_argument("--hypnotoad", type=Path, default=DEFAULT_HYPNOTOAD)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--keep-meshes", action="store_true")
    args = parser.parse_args()

    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)
    meshes: dict[str, Path] = {}
    consistency = {}
    for name, resolution in RESOLUTIONS.items():
        options = {**COMMON_OPTIONS, **resolution}
        options_path = args.run_dir / f"{name}_hypnotoad.yml"
        options_path.write_text(yaml.safe_dump(options, sort_keys=False), encoding="utf-8")
        mesh_path = args.run_dir / f"{name}.grd.nc"
        generate_mesh(args.hypnotoad, args.geqdsk, options_path, mesh_path, args.run_dir / f"{name}_hypnotoad.log")
        meshes[name] = mesh_path
        equilibrium = load_equilibrium(args.geqdsk, options)
        consistency[name] = source_consistency(mesh_path, equilibrium)

    convergence = pairwise_convergence(meshes)
    improving_count = sum(item["improves"] for item in convergence["field_trends"].values())
    all_finite = all(item["required_fields_finite"] for item in consistency.values())
    source_tolerance = 1e-12
    source_pass = all(
        all(field["relative_rmse"] <= source_tolerance for field in result["source_fields"].values())
        and result["pressure"]["connected_region_relative_rmse"] <= source_tolerance
        for result in consistency.values()
    )
    passed = all_finite and source_pass and improving_count >= len(CONVERGENCE_FIELDS) - 2
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "DIIID_MESH_CONVERGENCE_AND_GEQDSK_CONSISTENCY_SUPPORTED"
            if passed
            else "DIIID_MESH_CONVERGENCE_OR_CONSISTENCY_CHECK_FAILED"
        ),
        "geqdsk": str(args.geqdsk.relative_to(REPO)),
        "geqdsk_sha256": sha256(args.geqdsk),
        "resolutions": RESOLUTIONS,
        "meshes": consistency,
        "convergence": convergence,
        "field_count": len(CONVERGENCE_FIELDS),
        "improving_field_count": improving_count,
        "all_required_fields_finite": all_finite,
        "all_source_checks_pass": source_pass,
    }
    (args.run_dir / "diiid_mesh_convergence_consistency_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    if not args.keep_meshes:
        for mesh in meshes.values():
            mesh.unlink()
        for log in args.run_dir.glob("*_hypnotoad.log"):
            log.unlink()
    print(json.dumps({"status": summary["status"], "improving_fields": improving_count}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

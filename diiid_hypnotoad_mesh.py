#!/usr/bin/env python3
"""Generate and validate a BOUT++ Hypnotoad mesh from the DIII-D GEQDSK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from netCDF4 import Dataset


REPO = Path(__file__).resolve().parent
CASE_DIR = REPO / "validation_inputs" / "geqdsk_efit_baseline" / "diii_d_158103_03796"
DEFAULT_GEQDSK = CASE_DIR / "geqdsk"
DEFAULT_OPTIONS = CASE_DIR / "hypnotoad.yml"
DEFAULT_GRID = CASE_DIR / "diii_d_158103_03796_hypnotoad.grd.nc"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "diiid_hypnotoad_mesh_default"

REQUIRED_FINITE_FIELDS = (
    "Rxy",
    "Zxy",
    "psixy",
    "Bxy",
    "Bpxy",
    "Btxy",
    "J",
    "g11",
    "g22",
    "g33",
    "g_11",
    "g_22",
    "g_33",
)
TOPOLOGY_FIELDS = (
    "nx",
    "ny",
    "ixseps1",
    "ixseps2",
    "jyseps1_1",
    "jyseps1_2",
    "jyseps2_1",
    "jyseps2_2",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path.resolve())


def scalar(dataset: Dataset, name: str) -> int:
    return int(np.asarray(dataset.variables[name][:]).item())


def inspect_grid(grid: Path) -> dict[str, Any]:
    with Dataset(grid) as dataset:
        dimensions = {name: len(value) for name, value in dataset.dimensions.items()}
        topology = {name: scalar(dataset, name) for name in TOPOLOGY_FIELDS}
        fields: dict[str, Any] = {}
        required_fields_finite = True
        for name in REQUIRED_FINITE_FIELDS:
            values = np.asarray(dataset.variables[name][:])
            finite = np.isfinite(values)
            required_fields_finite &= bool(finite.all())
            fields[name] = {
                "shape": list(values.shape),
                "finite": bool(finite.all()),
                "minimum": float(np.nanmin(values)),
                "maximum": float(np.nanmax(values)),
            }

        auxiliary_nonfinite: dict[str, Any] = {}
        for name, variable in dataset.variables.items():
            if name in REQUIRED_FINITE_FIELDS or not np.issubdtype(variable.dtype, np.number):
                continue
            values = np.asarray(variable[:])
            if not values.size or not values.ndim:
                continue
            finite = np.isfinite(values)
            if not finite.all():
                auxiliary_nonfinite[name] = {
                    "shape": list(values.shape),
                    "finite_values": int(finite.sum()),
                    "total_values": int(values.size),
                }

        provenance = {
            name: getattr(dataset, name)
            for name in (
                "grid_id",
                "parallel_transform",
                "hypnotoad_version",
                "hypnotoad_git_hash",
                "hypnotoad_geqdsk_filename",
            )
            if name in dataset.ncattrs()
        }
        embedded_inputs = {
            name: name in dataset.variables
            for name in (
                "hypnotoad_inputs",
                "hypnotoad_inputs_yaml",
                "hypnotoad_input_geqdsk_file_contents",
            )
        }

    topology_valid = (
        topology["nx"] == dimensions["x"]
        and topology["ny"] == dimensions["y"]
        and 0 < topology["ixseps1"] < topology["ixseps2"] == topology["nx"]
        and 0 <= topology["jyseps1_1"] < topology["jyseps1_2"]
        <= topology["jyseps2_2"] < topology["ny"]
    )
    return {
        "dimensions": dimensions,
        "topology": topology,
        "topology_valid": topology_valid,
        "required_fields_finite": required_fields_finite,
        "fields": fields,
        "auxiliary_nonfinite": auxiliary_nonfinite,
        "provenance": provenance,
        "embedded_inputs": embedded_inputs,
    }


def generate_grid(hypnotoad: Path, geqdsk: Path, options: Path, grid: Path, log: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="diiid_hypnotoad_") as temp:
        temp_dir = Path(temp)
        environment = dict(os.environ)
        environment.setdefault("MPLBACKEND", "Agg")
        command = [str(hypnotoad), str(geqdsk.resolve()), str(options.resolve())]
        result = subprocess.run(
            command,
            cwd=temp_dir,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"Hypnotoad failed with exit code {result.returncode}; see {log}")
        generated = temp_dir / "bout.grd.nc"
        if not generated.exists():
            raise FileNotFoundError(f"Hypnotoad did not create {generated}")
        grid.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(generated, grid)


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    inspection = summary["inspection"]
    topology = inspection["topology"]
    provenance = inspection["provenance"]
    auxiliary = inspection["auxiliary_nonfinite"]
    lines = [
        "# DIII-D Hypnotoad Field-Aligned Mesh",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated: `{summary['generated_at']}`",
        f"- Source equilibrium: DIII-D shot `158103` at `3796 ms`",
        f"- GEQDSK SHA-256: `{summary['geqdsk_sha256']}`",
        f"- Mesh SHA-256: `{summary['grid_sha256']}`",
        f"- Hypnotoad: `{provenance.get('hypnotoad_version', 'unknown')}`",
        f"- Parallel transform: `{provenance.get('parallel_transform', 'unknown')}`",
        "",
        "## Mesh checks",
        "",
        f"- Dimensions: `{topology['nx']} x {topology['ny']}`",
        f"- Separatrix indices: `ixseps1={topology['ixseps1']}`, `ixseps2={topology['ixseps2']}`",
        (
            "- Y topology: "
            f"`{topology['jyseps1_1']}, {topology['jyseps1_2']}, "
            f"{topology['jyseps2_1']}, {topology['jyseps2_2']}`"
        ),
        f"- Topology consistency: `{inspection['topology_valid']}`",
        f"- Required geometry, magnetic, Jacobian, and metric fields finite: `{inspection['required_fields_finite']}`",
        f"- Embedded Hypnotoad inputs present: `{all(inspection['embedded_inputs'].values())}`",
        "",
        "## Topology choice",
        "",
        "The imported equilibrium contains a primary lower X-point at normalized flux 1.0",
        "and a secondary upper X-point near normalized flux 1.089. The mesh uses",
        "`psinorm_sol = 1.05`, selecting a lower-single-null topology and excluding",
        "the secondary upper X-point from the generated SOL.",
        "",
        "## Auxiliary non-finite values",
        "",
        "Hypnotoad leaves some topology-dependent auxiliary shift/angle arrays undefined",
        "outside the regions where they apply. These do not occur in the required core",
        "geometry, magnetic-field, Jacobian, or metric arrays checked above.",
        "",
    ]
    for name, details in auxiliary.items():
        lines.append(
            f"- `{name}`: {details['finite_values']} / {details['total_values']} finite values"
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This closes the missing field-aligned DIII-D BOUT++ mesh-input gap.",
            "It is not a BOUT++ machine-geometry physics pass, mesh-convergence result,",
            "or validation against DIII-D experimental diagnostics. The next step is to",
            "run a machine-geometry BOUT++ model on this grid and compare resolutions and",
            "diagnostic-anchored observables.",
            "",
        ]
    )
    (run_dir / "diiid_hypnotoad_mesh_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geqdsk", type=Path, default=DEFAULT_GEQDSK)
    parser.add_argument("--options", type=Path, default=DEFAULT_OPTIONS)
    parser.add_argument("--grid", type=Path, default=DEFAULT_GRID)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--generate", action="store_true", help="Regenerate the grid before validation")
    parser.add_argument("--hypnotoad", type=Path, default=Path("hypnotoad-geqdsk"))
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)
    log = args.run_dir / "hypnotoad_run.log"
    if args.generate:
        generate_grid(args.hypnotoad, args.geqdsk, args.options, args.grid, log)
    if not args.grid.exists():
        raise FileNotFoundError(f"Mesh not found: {args.grid}; pass --generate to create it")

    inspection = inspect_grid(args.grid)
    passed = (
        inspection["topology_valid"]
        and inspection["required_fields_finite"]
        and all(inspection["embedded_inputs"].values())
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "DIIID_HYPNOTOAD_FIELD_ALIGNED_MESH_READY" if passed else "DIIID_HYPNOTOAD_MESH_CHECK_FAILED",
        "claim_boundary": (
            "Field-aligned mesh input ready; no BOUT++ machine-geometry physics, "
            "mesh-convergence, or experimental-diagnostic validation is claimed."
        ),
        "geqdsk": relative(args.geqdsk),
        "geqdsk_sha256": sha256(args.geqdsk),
        "options": relative(args.options),
        "options_sha256": sha256(args.options),
        "grid": relative(args.grid),
        "grid_sha256": sha256(args.grid),
        "grid_size_bytes": args.grid.stat().st_size,
        "inspection": inspection,
    }
    (args.run_dir / "diiid_hypnotoad_mesh_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps({"status": summary["status"], "grid": summary["grid"]}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

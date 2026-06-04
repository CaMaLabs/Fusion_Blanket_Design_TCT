#!/usr/bin/env python3
"""Run a short M3D-C1 startup smoke test using the imported DIII-D GEQDSK case."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent
DEFAULT_BASELINE = REPO / "validation_inputs" / "geqdsk_efit_baseline" / "diii_d_158103_03796"
DEFAULT_SCAFFOLD = Path("/root/M3DC1/unstructured/runs/first_linear")
DEFAULT_BINARY_CANDIDATES = (
    Path("/root/M3DC1/unstructured/build-mpich325/m3dc1_2d"),
    Path("/root/M3DC1/unstructured/build-openmpi319/m3dc1_2d"),
)
DEFAULT_RUN_DIR = REPO / "validation_runs" / "m3dc1_geqdsk_diiid_smoke_default"


def replace_assignment(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)(.*?)(\s*(?:!.*)?$)", re.MULTILINE)
    replacement = rf"\g<1>{value}\g<3>"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    return text.replace("\n /", f"\n\t{key} = {value}\n /", 1)


def copy_required(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    shutil.copy2(src, dst)


def hdf5_inventory(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0}
    if not path.exists():
        return info
    try:
        import h5py  # type: ignore

        datasets: list[str] = []
        groups: list[str] = []
        with h5py.File(path, "r") as h5:
            def visit(name: str, obj: Any) -> None:
                if isinstance(obj, h5py.Dataset):
                    datasets.append(name)
                elif isinstance(obj, h5py.Group):
                    groups.append(name)

            h5.visititems(visit)
            info["top_level"] = list(h5.keys())
        info["readable"] = True
        info["groups_sample"] = groups[:20]
        info["datasets_sample"] = datasets[:40]
        info["dataset_count"] = len(datasets)
    except Exception as exc:  # h5py raises for the small C1.h5 link container in this build.
        info["readable"] = False
        info["read_error"] = str(exc)
    return info


def parse_geqdsk_header(path: Path) -> dict[str, Any]:
    first = path.read_text(errors="replace").splitlines()[0]
    ints = re.findall(r"[-+]?\d+", first)
    nw = int(ints[-2])
    nh = int(ints[-1])
    return {"header": first, "nw": nw, "nh": nh}


def write_report(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# M3D-C1 DIII-D GEQDSK Smoke Run",
        "",
        f"- Status: `{summary['status']}`",
        f"- Started: `{summary['started_utc']}`",
        f"- Runtime: `{summary['runtime_seconds']:.3f}` seconds",
        f"- Return code: `{summary['returncode']}`",
        f"- Timed out: `{summary['timed_out']}`",
        f"- M3D-C1 binary: `{summary['binary']}`",
        f"- Run directory: `{summary['run_dir']}`",
        f"- GEQDSK header: `{summary['geqdsk']['header']}`",
        f"- GEQDSK grid: `{summary['geqdsk']['nw']} x {summary['geqdsk']['nh']}`",
        f"- M3D-C1 smoke flags: `{', '.join(summary['m3dc1_smoke_flags']) or 'none'}`",
        "",
        "## What This Validates",
        "",
        "This is a solver startup smoke test using the imported DIII-D shot 158103 / 3796 ms GEQDSK as the solver-facing `geqdsk` input.",
        "The run uses the local M3D-C1 first-linear DIII-D SCOREC mesh/wall scaffold because the public EFIT package does not include a shot-specific mesh model.",
        "",
        "## What This Does Not Validate",
        "",
        "This is not a completed nonlinear M3D-C1 campaign, not a BOUT++ machine-geometry run, and not a direct comparison to raw DIII-D diagnostics.",
        "It should be treated as the first executable gate after GEQDSK/EFIT import: the solver can be launched against the imported equilibrium package and any emitted HDF5 artifacts are inventoried below.",
        "This run is also not a validation of the M3D-C1 wall-distance auxiliary solve; the smoke harness sets `M3DC1_SKIP_WALL_DIST_SOLVE=1` so the imported-equilibrium startup gate can proceed while keeping `wall_dist` as a neutral zero field.",
        "",
        "## Output Artifacts",
        "",
        "| File | Exists | Size bytes | HDF5 readable | Notes |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, artifact in summary["artifacts"].items():
        notes = artifact.get("read_error", "")
        lines.append(
            f"| `{name}` | {artifact['exists']} | {artifact['size_bytes']} | "
            f"{artifact.get('readable', '')} | {notes} |"
        )
    lines.extend(
        [
            "",
            "## Log Tail",
            "",
            "```text",
            summary["log_tail"],
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--scaffold-dir", type=Path, default=DEFAULT_SCAFFOLD)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--binary", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    baseline_dir = args.baseline_dir.resolve()
    scaffold_dir = args.scaffold_dir.resolve()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    binary = args.binary
    if binary is None:
        binary = next((candidate for candidate in DEFAULT_BINARY_CANDIDATES if candidate.exists()), None)
    if binary is None or not binary.exists():
        raise FileNotFoundError("No local m3dc1_2d binary found")
    binary = binary.resolve()

    for old in ("C1.h5", "equilibrium.h5", "time_000.h5", "run.log"):
        target = run_dir / old
        if target.exists():
            target.unlink()

    copy_required(baseline_dir / "geqdsk", run_dir / "geqdsk")
    copy_required(baseline_dir / "C1input.geqdsk_baseline", run_dir / "C1input.geqdsk_baseline.original")
    copy_required(baseline_dir / "profile_density.csv", run_dir / "profile_density.csv")
    copy_required(scaffold_dir / "coil.dat", run_dir / "coil.dat")
    copy_required(scaffold_dir / "current.dat", run_dir / "current.dat")
    copy_required(scaffold_dir / "diii-d_rw1.txt", run_dir / "diii-d_rw1.txt")
    copy_required(scaffold_dir / "diii-d_rw1-9K0.smb", run_dir / "diii-d_rw1-9K0.smb")
    copy_required(scaffold_dir / "diii-d_rw1-9K0.smb", run_dir / "diii-d_rw1-9K.smb")

    input_text = (scaffold_dir / "C1input.smoke.local").read_text(encoding="utf-8")
    replacements = {
        "ntimemax": "0",
        "ntimepr": "1",
        "iprint": "2",
        "iread_eqdsk": "1",
        "iwrite_hdf5": "1",
        "iread_ne": "0",
        "iread_te": "0",
        # M3D-C1/SCOREC expects the partitioned mesh basename and appends rank ids.
        "mesh_filename": "'diii-d_rw1-9K.smb'",
        "mesh_model": "'diii-d_rw1.txt'",
    }
    for key, value in replacements.items():
        input_text = replace_assignment(input_text, key, value)
    (run_dir / "C1input").write_text(input_text, encoding="utf-8")

    env = os.environ.copy()
    env["UCX_TLS"] = env.get("UCX_TLS", "self,tcp")
    env["UCX_NET_DEVICES"] = env.get("UCX_NET_DEVICES", "lo")
    env["UCX_MEMTYPE_CACHE"] = env.get("UCX_MEMTYPE_CACHE", "n")
    env["MPIR_CVAR_CH4_SHM_ENABLE"] = env.get("MPIR_CVAR_CH4_SHM_ENABLE", "0")
    env["M3DC1_SKIP_WALL_DIST_SOLVE"] = "1"

    mpi = shutil.which("mpiexec.mpich") or shutil.which("mpirun")
    if mpi is None:
        raise FileNotFoundError("No mpiexec.mpich or mpirun found")
    command = [mpi, "-np", "1", str(binary)]

    started = datetime.now(timezone.utc)
    start_time = time.monotonic()
    timed_out = False
    returncode: int | None = None
    stdout = ""
    stderr = ""
    with (run_dir / "C1input").open("rb") as stdin:
        try:
            proc = subprocess.run(
                command,
                cwd=run_dir,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=args.timeout,
                check=False,
            )
            returncode = proc.returncode
            stdout = proc.stdout.decode(errors="replace")
            stderr = proc.stderr.decode(errors="replace")
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = None
            stdout = (exc.stdout or b"").decode(errors="replace")
            stderr = (exc.stderr or b"").decode(errors="replace")
    runtime = time.monotonic() - start_time
    log_text = stdout + ("\n--- STDERR ---\n" + stderr if stderr else "")
    log_text = "".join(
        char if char in "\n\r\t" or ord(char) >= 32 else f"\\x{ord(char):02x}"
        for char in log_text
    )
    (run_dir / "run.log").write_text(log_text, encoding="utf-8")

    artifacts = {
        name: hdf5_inventory(run_dir / name)
        for name in ("C1.h5", "equilibrium.h5", "time_000.h5")
    }
    emitted_readable_hdf5 = any(item.get("readable") for item in artifacts.values())
    petsc_abort = "PETSC ERROR" in log_text or "MPI_Abort" in log_text or "Segmentation Violation" in log_text
    mesh_missing = "mesh file not found" in log_text or "SCOREC mesh file not found" in log_text
    if timed_out and emitted_readable_hdf5:
        status = "M3DC1_STARTUP_TIMEOUT_HDF5_EMITTED"
    elif timed_out:
        status = "M3DC1_STARTUP_TIMEOUT_NO_HDF5"
    elif returncode == 0 and emitted_readable_hdf5:
        status = "M3DC1_STARTUP_SMOKE_PASSED"
    elif emitted_readable_hdf5:
        status = "M3DC1_STARTUP_NONZERO_EXIT_HDF5_EMITTED"
    elif petsc_abort:
        status = "M3DC1_STARTUP_PETSC_ABORT_NO_HDF5"
    elif mesh_missing:
        status = "M3DC1_STARTUP_MESH_MISSING_NO_HDF5"
    else:
        status = "M3DC1_STARTUP_FAILED_NO_HDF5"

    summary: dict[str, Any] = {
        "status": status,
        "started_utc": started.isoformat(),
        "runtime_seconds": runtime,
        "returncode": returncode,
        "timed_out": timed_out,
        "command": command,
        "binary": str(binary),
        "baseline_dir": str(baseline_dir),
        "scaffold_dir": str(scaffold_dir),
        "run_dir": str(run_dir),
        "m3dc1_smoke_flags": ["M3DC1_SKIP_WALL_DIST_SOLVE=1"],
        "geqdsk": parse_geqdsk_header(run_dir / "geqdsk"),
        "artifacts": artifacts,
        "detected_runtime_conditions": {
            "petsc_abort": petsc_abort,
            "mesh_missing": mesh_missing,
            "emitted_readable_hdf5": emitted_readable_hdf5,
        },
        "log_tail": "\n".join(log_text.splitlines()[-80:]),
    }

    (run_dir / "m3dc1_geqdsk_smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(summary, run_dir / "m3dc1_geqdsk_smoke_report.md")
    with (run_dir / "m3dc1_geqdsk_smoke_metrics.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["metric", "value"])
        writer.writeheader()
        for key in ("status", "runtime_seconds", "returncode", "timed_out"):
            writer.writerow({"metric": key, "value": summary[key]})
        for name, artifact in artifacts.items():
            writer.writerow({"metric": f"{name}_exists", "value": artifact["exists"]})
            writer.writerow({"metric": f"{name}_size_bytes", "value": artifact["size_bytes"]})
            writer.writerow({"metric": f"{name}_readable_hdf5", "value": artifact.get("readable", "")})
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

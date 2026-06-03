#!/usr/bin/env python3
"""Create a concrete GEQDSK/EFIT baseline case from the public DIII-D package."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from machine_equilibrium_readiness import _parse_geqdsk


REPO = Path(__file__).resolve().parent
DEFAULT_MACHINE_INPUT = REPO / "validation_inputs" / "machine_equilibria" / "diii_d"
DEFAULT_CASE_DIR = REPO / "validation_inputs" / "geqdsk_efit_baseline" / "diii_d_158103_03796"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "geqdsk_efit_baseline_default"

FILLED_VALUES = {
    "iread_eqdsk": "1",
    "irmp": "0",
    "extsubtract": "0",
    "max_ke": "1e99",
    "itime_independent": "0",
    "idevice": "4",
    "eps": "1e-6",
    "db_fac": "0.0",
    "mesh_filename": "'diii_d_158103_03796.smd'",
    "mesh_model": "'diii_d_158103_03796.dmg'",
    "icsubtract": "0",
    "imulti_region": "0",
    "ntor": "1",
}


def _copy(src: Path, dest: Path) -> str:
    if not src.exists():
        raise FileNotFoundError(src)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return str(dest)


def _fill_c1input(template: Path, output: Path) -> dict[str, str]:
    replacements: dict[str, str] = {}
    lines = []
    pattern = re.compile(r"^(\s*)([A-Za-z0-9_()]+)\s*=\s*(?:!.*)?$")
    for line in template.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            indent, key = match.group(1), match.group(2)
            if key in FILLED_VALUES:
                line = f"{indent}{key} = {FILLED_VALUES[key]}"
                replacements[key] = FILLED_VALUES[key]
        lines.append(line)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return replacements


def _profile_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    rows = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        header = handle.readline().strip()
        declared_rows = int(header.split()[0]) if header.split() and header.split()[0].isdigit() else None
        for line in handle:
            if declared_rows is not None and len(rows) >= declared_rows:
                break
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                rows.append([float(part) for part in parts[:3]])
            except ValueError:
                continue
    if not rows:
        return {"path": str(path), "exists": True, "header": header, "rows": 0}
    psi = [row[0] for row in rows]
    ne = [row[1] for row in rows]
    return {
        "path": str(path),
        "exists": True,
        "header": header,
        "declared_rows": declared_rows,
        "rows": len(rows),
        "psi_min": min(psi),
        "psi_max": max(psi),
        "ne_1e20_m3_min": min(ne),
        "ne_1e20_m3_max": max(ne),
    }


def _write_profile_csv(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    rows = []
    with src.open(encoding="utf-8", errors="replace") as handle:
        header = handle.readline().strip()
        declared_rows = int(header.split()[0]) if header.split() and header.split()[0].isdigit() else None
        for line in handle:
            if declared_rows is not None and len(rows) >= declared_rows:
                break
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                rows.append([float(parts[0]), float(parts[1]), float(parts[2])])
            except ValueError:
                continue
    with dest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["psinorm", "ne_1e20_m3", "dne_dpsin"])
        writer.writerows(rows)


def _write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    geq = summary["geqdsk"]
    profile = summary["profile"]
    lines = [
        "# GEQDSK / EFIT Baseline Case",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        f"Status: **{summary['status']}**",
        "",
        "## Case",
        "",
        f"- Machine: `{summary['machine']}`",
        f"- Shot/time: `{summary['shot_time']}`",
        f"- Baseline case directory: `{summary['case_dir']}`",
        f"- M3D-C1 input deck: `{summary['case_files']['c1input']}`",
        f"- Solver-facing GEQDSK filename: `{summary['case_files']['geqdsk']}`",
        "",
        "## Parsed GEQDSK",
        "",
        f"- Grid: `{geq['nw']} x {geq['nh']}`",
        f"- R dimension: `{geq['rdim_m']}` m",
        f"- Z dimension: `{geq['zdim_m']}` m",
        f"- Magnetic axis: R=`{geq['rmaxis_m']}` m, Z=`{geq['zmaxis_m']}` m",
        f"- Boundary flux: `{geq['sibry_wb']}` Wb",
        f"- Central field: `{geq['bcentr_t']}` T",
        f"- Plasma current: `{geq['current_a']}` A",
        f"- q range: `{geq['qpsi_min']}` to `{geq['qpsi_max']}`",
        "",
        "## Profile Anchor",
        "",
        f"- Profile rows: `{profile.get('rows', 0)}`",
        f"- Density range: `{profile.get('ne_1e20_m3_min')}` to `{profile.get('ne_1e20_m3_max')}` 1e20 m^-3",
        "",
        "## Boundary",
        "",
        "This is an EFIT-backed baseline input package, not a completed M3D-C1 or BOUT++ machine-geometry run.",
        "It is the correct next anchor for replacing the reduced slab/current-sheet validation chain with an experiment-referenced equilibrium.",
        "Raw experimental diagnostic archives are still absent.",
        "",
    ]
    (run_dir / "geqdsk_efit_baseline_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine-input", type=Path, default=DEFAULT_MACHINE_INPUT)
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()

    if args.case_dir.exists():
        shutil.rmtree(args.case_dir)
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.case_dir.mkdir(parents=True, exist_ok=True)
    args.run_dir.mkdir(parents=True, exist_ok=True)

    efit_dir = args.machine_input / "efit"
    gfile = efit_dir / "g158103.03796"
    afile = efit_dir / "a158103.03796"
    pfile = efit_dir / "p158103.03796"
    template = args.machine_input / "C1input_base"

    case_efit = args.case_dir / "efit"
    files = {
        "geqdsk": _copy(gfile, args.case_dir / "geqdsk"),
        "gfile_original": _copy(gfile, case_efit / gfile.name),
        "aeqdsk": _copy(afile, case_efit / afile.name),
        "profile": _copy(pfile, case_efit / pfile.name),
        "c1input_base": _copy(template, args.case_dir / "C1input_base"),
    }
    replacements = _fill_c1input(template, args.case_dir / "C1input.geqdsk_baseline")
    files["c1input"] = str(args.case_dir / "C1input.geqdsk_baseline")
    _write_profile_csv(pfile, args.case_dir / "profile_density.csv")
    files["profile_density_csv"] = str(args.case_dir / "profile_density.csv")

    geqdsk = _parse_geqdsk(Path(files["geqdsk"]))
    profile = _profile_summary(Path(files["profile"]))
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "GEQDSK_EFIT_BASELINE_READY",
        "machine": "DIII-D",
        "shot_time": "158103 @ 3796 ms",
        "case_dir": str(args.case_dir),
        "case_files": files,
        "filled_c1input_values": replacements,
        "geqdsk": geqdsk,
        "profile": profile,
        "raw_experimental_diagnostics_present": False,
    }
    (args.run_dir / "geqdsk_efit_baseline_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    with (args.run_dir / "geqdsk_efit_baseline_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "machine",
                "shot_time",
                "status",
                "nw",
                "nh",
                "bcentr_t",
                "current_a",
                "rmaxis_m",
                "zmaxis_m",
                "qpsi_min",
                "qpsi_max",
                "profile_rows",
                "raw_experimental_diagnostics_present",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "machine": summary["machine"],
                "shot_time": summary["shot_time"],
                "status": summary["status"],
                "nw": geqdsk["nw"],
                "nh": geqdsk["nh"],
                "bcentr_t": geqdsk["bcentr_t"],
                "current_a": geqdsk["current_a"],
                "rmaxis_m": geqdsk["rmaxis_m"],
                "zmaxis_m": geqdsk["zmaxis_m"],
                "qpsi_min": geqdsk["qpsi_min"],
                "qpsi_max": geqdsk["qpsi_max"],
                "profile_rows": profile.get("rows", 0),
                "raw_experimental_diagnostics_present": False,
            }
        )
    _write_report(args.run_dir, summary)
    print(json.dumps({"run_dir": str(args.run_dir), "case_dir": str(args.case_dir), "status": summary["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a machine-equilibrium readiness package from public M3D-C1 artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent
DEFAULT_M3DC1_REPO = Path("/root/CaMaLabs_M3DC1")
DEFAULT_INPUT_DIR = REPO / "validation_inputs" / "machine_equilibria"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "machine_equilibrium_readiness_default"
FLOAT_RE = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][+-]?\d+)?")


@dataclass(frozen=True)
class MachineTarget:
    name: str
    m3dc1_template_name: str
    idevice: int | None
    requires_real_efit: bool


TARGETS = (
    MachineTarget("DIII-D", "DIII-D", 4, True),
    MachineTarget("NSTX-U", "NSTX-U", 2, True),
    MachineTarget("ITER", "ITER", 3, False),
)


def _floats_from_text(text: str) -> list[float]:
    return [float(match.group(0).replace("D", "E").replace("d", "e")) for match in FLOAT_RE.finditer(text)]


def _parse_geqdsk(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        raise ValueError(f"empty GEQDSK file: {path}")
    header_ints = [int(item) for item in re.findall(r"[+-]?\d+", lines[0])]
    if len(header_ints) < 2:
        raise ValueError(f"cannot parse GEQDSK dimensions from header: {lines[0]!r}")
    nw, nh = header_ints[-2], header_ints[-1]
    values = _floats_from_text("\n".join(lines[1:]))
    if len(values) < 20 + 5 * nw + nw * nh:
        raise ValueError(f"GEQDSK has too few numeric values for nw={nw}, nh={nh}: {path}")

    scalars = values[:20]
    fpol = values[20 : 20 + nw]
    pres = values[20 + nw : 20 + 2 * nw]
    psirz_start = 20 + 4 * nw
    psirz = values[psirz_start : psirz_start + nw * nh]
    qpsi = values[psirz_start + nw * nh : psirz_start + nw * nh + nw]

    return {
        "path": str(path),
        "header": lines[0].strip(),
        "nw": nw,
        "nh": nh,
        "rdim_m": scalars[0],
        "zdim_m": scalars[1],
        "rcentr_m": scalars[2],
        "rleft_m": scalars[3],
        "zmid_m": scalars[4],
        "rmaxis_m": scalars[5],
        "zmaxis_m": scalars[6],
        "simag_wb": scalars[7],
        "sibry_wb": scalars[8],
        "bcentr_t": scalars[9],
        "current_a": scalars[10],
        "fpol_min": min(fpol),
        "fpol_max": max(fpol),
        "pressure_min": min(pres),
        "pressure_max": max(pres),
        "psi_grid_min": min(psirz),
        "psi_grid_max": max(psirz),
        "qpsi_min": min(qpsi) if qpsi else None,
        "qpsi_max": max(qpsi) if qpsi else None,
        "numeric_values": len(values),
        "size_bytes": path.stat().st_size,
    }


def _copy_if_exists(src: Path, dest: Path) -> str | None:
    if not src.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return str(dest)


def _template_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        key = key.strip()
        if key in {"iread_eqdsk", "idevice", "iread_ne", "iread_te", "eqsubtract", "icalc_scalars"}:
            values[key] = raw.split("!")[0].strip()
    return values


def _write_c1input_stub(path: Path, target: MachineTarget, has_geqdsk: bool) -> None:
    lines = [
        "# M3D-C1 machine-equilibrium validation stub",
        f"# machine = {target.name}",
        "# Fill remaining solver and mesh settings from the corresponding public M3D-C1 template.",
        "",
        "&input",
        f"  idevice = {target.idevice if target.idevice is not None else 0}",
        f"  iread_eqdsk = {1 if has_geqdsk else 0}",
        "  iread_ne = 1",
        "  iread_te = 1",
        "  eqsubtract = 1",
        "  icalc_scalars = 1",
        "/",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_package(m3dc1_repo: Path, input_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    geqdsk_summaries: list[dict[str, Any]] = []

    for target in TARGETS:
        template_dir = m3dc1_repo / "templates_from_autoc1" / target.m3dc1_template_name
        template = template_dir / "C1input_base"
        efit_dir = template_dir / "efit"
        machine_dir = input_dir / target.name.replace("-", "_").lower()

        gfiles = sorted(efit_dir.glob("g*")) if efit_dir.exists() else []
        afiles = sorted(efit_dir.glob("a*")) if efit_dir.exists() else []
        pfiles = sorted(efit_dir.glob("p*")) if efit_dir.exists() else []
        copied_gfiles = [
            _copy_if_exists(path, machine_dir / "efit" / path.name)
            for path in gfiles
        ]
        copied_afiles = [
            _copy_if_exists(path, machine_dir / "efit" / path.name)
            for path in afiles
        ]
        copied_pfiles = [
            _copy_if_exists(path, machine_dir / "efit" / path.name)
            for path in pfiles
        ]
        copied_template = _copy_if_exists(template, machine_dir / "C1input_base")

        parsed_gfiles = []
        for copied in copied_gfiles:
            if copied is None:
                continue
            summary = _parse_geqdsk(Path(copied))
            geqdsk_summaries.append({"machine": target.name, **summary})
            parsed_gfiles.append(copied)

        has_real_geqdsk = bool(parsed_gfiles)
        has_profiles = bool([item for item in copied_pfiles if item])
        has_aeqdsk = bool([item for item in copied_afiles if item])
        has_template = copied_template is not None
        has_coils = (template_dir / "coil.dat").exists()
        status = (
            "ready_with_public_efit"
            if has_real_geqdsk and has_aeqdsk and has_profiles
            else "template_only_missing_public_efit"
            if has_template
            else "missing_template"
        )
        if target.requires_real_efit and not has_real_geqdsk:
            status = "blocked_missing_real_efit"

        _write_c1input_stub(machine_dir / "C1input.machine_equilibrium_stub", target, has_real_geqdsk)
        rows.append(
            {
                "machine": target.name,
                "m3dc1_idevice": target.idevice,
                "template_source": str(template),
                "copied_template": copied_template,
                "template_values": _template_values(template),
                "has_public_geqdsk": has_real_geqdsk,
                "public_geqdsk_files": parsed_gfiles,
                "has_aeqdsk": has_aeqdsk,
                "has_profile_file": has_profiles,
                "has_coil_file": has_coils,
                "has_experimental_diagnostics": False,
                "requires_real_efit": target.requires_real_efit,
                "status": status,
            }
        )

    return rows, geqdsk_summaries


def _write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Machine Equilibrium Readiness",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        f"Overall status: **{summary['overall_status']}**",
        "",
        "## Machine Inputs",
        "",
        "| Machine | Status | GEQDSK | AEQDSK | Profiles | Coil file | Raw diagnostics |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary["machines"]:
        lines.append(
            "| {machine} | {status} | {geqdsk} | {aeqdsk} | {profiles} | {coils} | {diagnostics} |".format(
                machine=row["machine"],
                status=row["status"],
                geqdsk="yes" if row["has_public_geqdsk"] else "no",
                aeqdsk="yes" if row["has_aeqdsk"] else "no",
                profiles="yes" if row["has_profile_file"] else "no",
                coils="yes" if row["has_coil_file"] else "no",
                diagnostics="yes" if row["has_experimental_diagnostics"] else "no",
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This package adds a real public DIII-D EFIT/GEQDSK anchor from the CaMaLabs M3DC1 public template set.",
            "NSTX-U and ITER currently have M3D-C1 machine templates and coil/current material, but no public EFIT GEQDSK was found in the local public package during this scan.",
            "No raw experimental diagnostic archive is packaged here; the DIII-D material is an EFIT/profile anchor, not a diagnostic validation set.",
            "Therefore the experimental-equilibrium gate is only partially satisfied: DIII-D is ready for EFIT-backed follow-up, while NSTX-U and ITER remain template-only until real equilibrium files are added.",
            "",
            "## M3D-C1 Integration Points",
            "",
            "- `idevice = 2`: NSTX family",
            "- `idevice = 3`: ITER",
            "- `idevice = 4`: DIII-D",
            "- `iread_eqdsk = 1`: read EFIT g-file named `geqdsk`",
            "- `icalc_scalars = 1`: scalar diagnostics enabled",
            "",
        ]
    )
    (run_dir / "machine_equilibrium_readiness_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m3dc1-repo", type=Path, default=DEFAULT_M3DC1_REPO)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()

    if args.input_dir.exists():
        shutil.rmtree(args.input_dir)
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.input_dir.mkdir(parents=True, exist_ok=True)
    args.run_dir.mkdir(parents=True, exist_ok=True)

    rows, geqdsk_summaries = _build_package(args.m3dc1_repo, args.input_dir)
    ready = [row for row in rows if row["status"] == "ready_with_public_efit"]
    blocked = [row for row in rows if row["status"].startswith("blocked") or row["status"].startswith("template_only")]
    overall = "PARTIAL_MACHINE_EQUILIBRIUM_READY" if ready and blocked else "READY" if ready else "BLOCKED"
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "m3dc1_repo": str(args.m3dc1_repo),
        "input_dir": str(args.input_dir),
        "overall_status": overall,
        "machines": rows,
        "geqdsk_summaries": geqdsk_summaries,
    }

    (args.run_dir / "machine_equilibrium_readiness_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    with (args.run_dir / "machine_equilibrium_readiness.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "machine",
                "status",
                "m3dc1_idevice",
                "has_public_geqdsk",
                "has_aeqdsk",
                "has_profile_file",
                "has_coil_file",
                "has_experimental_diagnostics",
                "requires_real_efit",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in writer.fieldnames})
    _write_report(args.run_dir, summary)
    print(json.dumps({"run_dir": str(args.run_dir), "input_dir": str(args.input_dir), "overall_status": overall}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Ubuntu orchestration for the current A/D validation gaps.

A (actuator-physics gap): run the Fiflis/Ruzic surface-retention gate and report
that it constrains safe liquid-metal/PFC forcing but does not create a measured
liquid-current -> plasma-edge transfer function.

D (engineering blanket gap): inventory the existing be_outer_kill/OpenMC path,
optionally run the existing OpenMC ordering study, and explicitly report the
engineering features still absent from the current geometry model.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = REPO / "validation_runs" / "ubuntu_ad_audit_default"


def run(cmd: list[str], cwd: Path, log_path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")
    return {"command": cmd, "returncode": proc.returncode, "log": str(log_path)}


def contains(path: Path, *needles: str) -> dict[str, bool]:
    if not path.exists():
        return {needle: False for needle in needles}
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return {needle: needle.lower() in text for needle in needles}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--with-openmc", action="store_true")
    parser.add_argument("--with-pytest", action="store_true")
    parser.add_argument("--strict", action="store_true", help="fail if an optional requested stage fails")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    evidence: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repo": str(REPO),
        "python": sys.version,
        "platform": sys.platform,
    }

    # A audit: existing Dedalus bias is prescribed; Ruzic gate adds a physical
    # PFC surface-retention constraint without pretending to close edge coupling.
    dedalus = REPO / "validation_models" / "dedalus_current_sheet" / "run_surface_stabilized_bias_matrix.py"
    dedalus_terms = contains(
        dedalus,
        "bias-strength",
        "prescribed",
        "capillary_stabilized",
        "magnetic_stiffened",
    )
    a_status = {
        "status": "PARTIAL_PHYSICS_CONSTRAINT_ONLY",
        "dedalus_surface_bias_file_exists": dedalus.exists(),
        "dedalus_terms": dedalus_terms,
        "missing": [
            "measured liquid-current -> plasma-edge transfer function",
            "machine-specific sheath/current closure",
            "experimentally identified actuator gain/phase/latency",
        ],
    }

    ruzic_dir = run_dir / "A_ruzic_surface_gate"
    a_run = run(
        [
            sys.executable,
            str(REPO / "scripts" / "run_ruzic_li_surface_gate.py"),
            "--run-dir",
            str(ruzic_dir),
            "--check",
        ],
        REPO,
        run_dir / "A_ruzic_surface_gate.log",
    )
    a_status["ruzic_gate_run"] = a_run
    evidence["A"] = a_status

    # D audit: inspect current OpenMC stack for engineering features.
    geom = REPO / "fusion_engine_v5" / "blanket" / "geometry_builder.py"
    geom_terms = contains(
        geom,
        "port",
        "coolant",
        "structural",
        "shield",
        "uncertainty",
        "zcylinder",
    )
    missing_features = [
        label
        for token, label in [
            ("port", "explicit penetrations/ports in neutronics geometry"),
            ("coolant", "explicit coolant channels/material regions"),
            ("structural", "explicit structural material fraction/regions"),
            ("shield", "explicit external shielding region"),
            ("uncertainty", "geometry/material uncertainty propagation inside the OpenMC case"),
        ]
        if not geom_terms[token]
    ]
    d_status: dict[str, Any] = {
        "status": "SIMPLIFIED_OPENMC_STACK_PRESENT_ENGINEERING_CASE_INCOMPLETE",
        "geometry_builder_exists": geom.exists(),
        "geometry_terms": geom_terms,
        "missing": missing_features,
        "openmc_python_importable": False,
        "openmc_executable": shutil.which("openmc"),
    }
    try:
        import openmc  # type: ignore  # noqa: F401

        d_status["openmc_python_importable"] = True
    except Exception as exc:
        d_status["openmc_import_error"] = repr(exc)

    if args.with_openmc:
        openmc_script = REPO / "scripts" / "run_openmc_ordering_ab_fast.py"
        if not openmc_script.exists():
            d_status["openmc_run"] = {"returncode": 127, "error": "script_missing"}
        elif not d_status["openmc_python_importable"] or not d_status["openmc_executable"]:
            d_status["openmc_run"] = {
                "returncode": 127,
                "error": "openmc_not_available",
                "note": "Install OpenMC plus a compatible cross-section library, then rerun --with-openmc.",
            }
        else:
            d_status["openmc_run"] = run(
                [sys.executable, str(openmc_script)],
                REPO,
                run_dir / "D_openmc_ordering_ab_fast.log",
            )
    evidence["D"] = d_status

    if args.with_pytest:
        evidence["pytest"] = run(
            [sys.executable, "-m", "pytest", "-q", "tests/test_ruzic_fiflis_2016.py"],
            REPO,
            run_dir / "pytest_ruzic.log",
        )

    evidence["overall"] = {
        "A_closed": False,
        "D_closed": False,
        "A_note": "Ruzic adds a defensible liquid-surface forcing/retention gate, not edge-plasma actuator validation.",
        "D_note": "Current repo has OpenMC capability, but the main geometry remains a simplified cylindrical stack.",
    }

    out_json = run_dir / "ubuntu_ad_audit_summary.json"
    out_json.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    report = f"""# Ubuntu A/D Validation Audit

Generated: {evidence['generated_utc']}

## A - lithium current / edge-plasma actuation

Status: `{a_status['status']}`

The repository already has prescribed Dedalus bias and surface-stabilization
proxies. This run adds the Fiflis/Ruzic 2016 Eq. 22/23 surface-retention gate so
current density, magnetic field, plasma tangential velocity, channel width, and
J-B orientation can be screened before a bias case is treated as physically
plausible. It **does not** manufacture the missing measured actuator transfer
function.

Ruzic stage return code: {a_run['returncode']}

## D - be_outer_kill engineering neutronics

Status: `{d_status['status']}`

Current geometry builder engineering omissions detected:
{chr(10).join('- ' + item for item in missing_features) if missing_features else '- none detected by token audit'}

OpenMC Python importable: {d_status['openmc_python_importable']}
OpenMC executable: {d_status['openmc_executable']}

## Result

A closed: **no**
D closed: **no**

This runner narrows A with an experimentally anchored surface-stability gate and
makes D's remaining geometry work machine-checkable on Ubuntu. It intentionally
does not relabel either gap as validated.
"""
    (run_dir / "UBUNTU_AD_AUDIT_REPORT.md").write_text(report, encoding="utf-8")

    print(json.dumps(evidence["overall"], indent=2))
    print(f"Wrote {out_json}")

    requested_failures = [a_run["returncode"]]
    if args.with_openmc and isinstance(d_status.get("openmc_run"), dict):
        requested_failures.append(int(d_status["openmc_run"].get("returncode", 1)))
    if args.with_pytest:
        requested_failures.append(int(evidence["pytest"]["returncode"]))
    if args.strict and any(code != 0 for code in requested_failures):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

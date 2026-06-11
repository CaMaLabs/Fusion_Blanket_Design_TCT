#!/usr/bin/env python3
"""Check provisional GEQDSK Jpar0 ingestion and finite elm-pb response."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from diiid_bout_elm_mesh_smoke import write_serial_topology_grid
from diiid_bout_elm_solution_convergence import run_case, summarize, write_input


REPO = Path(__file__).resolve().parent
DEFAULT_EXE = Path("/tmp/bout-build/examples/elm-pb/elm_pb")
DEFAULT_RUN_DIR = REPO / "validation_runs" / "diiid_jpar0_elm_response_default"
RECONSTRUCTION = REPO / "diiid_jpar0_reconstruction.py"


def write_report(run_dir: Path, summary: dict) -> None:
    lines = [
        "# DIII-D Provisional Jpar0 elm-pb Response",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated: `{summary['generated_at']}`",
        "",
        "| Case | Final U L2 | Final P L2 | Final Psi L2 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, case in summary["cases"].items():
        lines.append(
            f"| `{name}` | {case['fields']['U']['final_l2']:.6e} | "
            f"{case['fields']['P']['final_l2']:.6e} | {case['fields']['Psi']['final_l2']:.6e} |"
        )
    lines += [
        "",
        f"- All histories finite: `{summary['all_finite']}`",
        f"- Maximum final-norm relative response: `{summary['maximum_relative_response']:.6e}`",
        "",
        "## Claim boundary",
        "",
        "This confirms that the provisional GEQDSK-derived Jpar0 field is ingested and",
        "produces a finite, distinguishable short linear response. It does not establish",
        "that the reconstructed Jpar0 is experimentally correct, validate an ELM growth",
        "rate, or replace exact-X-point and diagnostic-referenced comparisons.",
        "",
    ]
    (run_dir / "diiid_jpar0_elm_response_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="diiid_jpar0_response_") as temp:
        temp_dir = Path(temp)
        reconstruction_dir = temp_dir / "reconstruction"
        subprocess.run(
            [
                "/root/.venvs/hypnotoad/bin/python",
                str(RECONSTRUCTION),
                "--run-dir",
                str(reconstruction_dir),
                "--keep-grid",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        serial_grid = temp_dir / "serial_jpar0.grd.nc"
        write_serial_topology_grid(
            reconstruction_dir / "diii_d_158103_03796_with_jpar0.grd.nc", serial_grid
        )
        cases = {}
        for name, include in (("without_jpar0", False), ("with_jpar0", True)):
            case_dir = args.run_dir / name
            write_input(case_dir, serial_grid, 8, 1e-4)
            input_path = case_dir / "BOUT.inp"
            text = input_path.read_text(encoding="utf-8").replace(
                "include_jpar0 = false", f"include_jpar0 = {str(include).lower()}"
            )
            input_path.write_text(text, encoding="utf-8")
            run_case(args.executable, case_dir)
            cases[name] = summarize(case_dir, "base", 8, 1e-4)

    differences = {}
    for field in ("U", "P", "Psi"):
        without = cases["without_jpar0"]["fields"][field]["final_l2"]
        with_jpar = cases["with_jpar0"]["fields"][field]["final_l2"]
        differences[field] = abs(with_jpar - without) / max(abs(with_jpar), abs(without), 1e-300)
    all_finite = all(field["finite"] for case in cases.values() for field in case["fields"].values())
    maximum = max(differences.values())
    passed = all_finite and maximum > 1e-8
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "DIIID_PROVISIONAL_JPAR0_ELM_RESPONSE_SUPPORTED" if passed else "DIIID_PROVISIONAL_JPAR0_ELM_RESPONSE_FAILED",
        "cases": cases,
        "final_norm_relative_responses": differences,
        "maximum_relative_response": maximum,
        "all_finite": all_finite,
    }
    (args.run_dir / "diiid_jpar0_elm_response_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps({"status": summary["status"], "maximum_relative_response": maximum}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

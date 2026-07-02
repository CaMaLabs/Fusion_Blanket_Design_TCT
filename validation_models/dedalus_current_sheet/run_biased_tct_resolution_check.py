#!/usr/bin/env python3
"""Run first-resolution sanity checks for the biased TCT Dedalus toy matrix."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
BENCHMARK = Path(__file__).resolve().with_name("dedalus_current_sheet_benchmark.py")

BASE_ARGS = [
    "--eta", "2e-4", "--nu", "2e-4",
    "--delta0", "0.16",
    "--perturbation-amplitude", "0.001",
    "--perturbation-kx", "1",
    "--drive-enabled",
    "--drive-start-time", "0.5",
    "--drive-end-time", "0.7",
    "--drive-strength", "0.002",
    "--drive-kx", "4",
    "--drive-width", "0.45",
    "--control-aspect-threshold", "80",
    "--control-strength", "0.008",
    "--control-width", "0.70",
    "--stop-time", "2.0",
    "--timestep", "0.001",
    "--diagnostic-cadence", "50",
    "--snapshot-cadence", "250",
    "--onset-island-count-threshold", "2",
    "--island-o-point-prominence", "1e-5",
]

RESOLUTIONS = ((64, 64), (96, 96))
CASES = [
    {"resolution_case": "baseline", "benchmark_case": "baseline", "description": "finite-pulse driven island-onset stress test without TCT proxy", "extra_args": []},
    {"resolution_case": "smoothing_only", "benchmark_case": "perturbed", "description": "aspect-triggered localized smoothing proxy", "extra_args": []},
    {
        "resolution_case": "smoothing_plus_bias_positive",
        "benchmark_case": "perturbed",
        "description": "aspect-triggered smoothing plus positive biased wall-current proxy",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0015", "--bias-polarity", "1"],
    },
]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["UCX_TLS"] = env.get("UCX_TLS", "self")
    env["OMP_NUM_THREADS"] = env.get("OMP_NUM_THREADS", "1")
    mpich_lib = "/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu"
    env["LD_LIBRARY_PATH"] = f"{mpich_lib}:{env.get('LD_LIBRARY_PATH', '')}"
    return env


def _run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, env=_env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        sys.stderr.write(result.stdout[-6000:])
        raise subprocess.CalledProcessError(result.returncode, cmd)


def _output_case_name(benchmark_case: str) -> str:
    return "baseline" if benchmark_case == "baseline" else "tct_style_perturbed"


def _load_summary(case_dir: Path, row: dict[str, Any]) -> dict[str, Any]:
    output_case = _output_case_name(str(row["benchmark_case"]))
    summary = json.loads((case_dir / output_case / "summary.json").read_text(encoding="utf-8"))
    summary.pop("case", None)
    return {**row, "benchmark_output_case": output_case, **summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=REPO / "validation_runs" / "dedalus_current_sheet_biased_tct_resolution_check")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    if args.run_dir.exists() and not args.keep_existing:
        shutil.rmtree(args.run_dir)
    args.run_dir = args.run_dir.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for nx, nz in RESOLUTIONS:
        for case in CASES:
            row = {"resolution": f"{nx}x{nz}", "nx": nx, "nz": nz, **case}
            print(f"running {row['resolution']} {row['resolution_case']}", flush=True)
            case_dir = args.run_dir / str(row["resolution"]) / str(row["resolution_case"])
            cmd = [
                args.python,
                str(BENCHMARK),
                "--run-dir", str(case_dir),
                "--case", str(case["benchmark_case"]),
                "--nx", str(nx),
                "--nz", str(nz),
                *BASE_ARGS,
                *case["extra_args"],
            ]
            _run(cmd, REPO)
            rows.append(_load_summary(case_dir, row))

    for resolution in {row["resolution"] for row in rows}:
        baseline = next(row for row in rows if row["resolution"] == resolution and row["resolution_case"] == "baseline")
        base_islands = float(baseline["final_island_count_proxy"])
        base_energy = float(baseline["final_magnetic_energy"])
        for row in rows:
            if row["resolution"] != resolution:
                continue
            row["final_island_count_reduction_vs_resolution_baseline"] = 1.0 - float(row["final_island_count_proxy"]) / base_islands
            row["final_magnetic_energy_delta_vs_resolution_baseline"] = float(row["final_magnetic_energy"]) - base_energy

    with (args.run_dir / "biased_tct_resolution_check_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    positive_rows = [row for row in rows if row["resolution_case"] == "smoothing_plus_bias_positive"]
    qualitative_reduction_persists = all(float(row["final_island_count_reduction_vs_resolution_baseline"]) > 0.0 for row in positive_rows)
    summary = {
        "artifact_type": "dedalus_biased_tct_resolution_check",
        "schema_version": "1.0",
        "not_reactor_claim": True,
        "not_tokamak_validation": True,
        "not_liquid_lithium_physics": True,
        "resolutions": [f"{nx}x{nz}" for nx, nz in RESOLUTIONS],
        "cases_checked": [case["resolution_case"] for case in CASES],
        "qualitative_positive_bias_reduction_persists": qualitative_reduction_persists,
        "cases": rows,
    }
    (args.run_dir / "biased_tct_resolution_check_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

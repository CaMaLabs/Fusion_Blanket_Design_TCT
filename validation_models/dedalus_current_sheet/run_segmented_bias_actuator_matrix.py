#!/usr/bin/env python3
"""Compare smooth, rib, and mesh edge-current bias proxies in the Dedalus toy model."""

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
    "--nx", "64", "--nz", "64",
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

CASES = [
    {
        "actuator_case": "baseline",
        "benchmark_case": "baseline",
        "actuator_family": "none",
        "description": "finite-pulse island-onset stress test without bias or smoothing",
        "extra_args": [],
    },
    {
        "actuator_case": "smoothing_only",
        "benchmark_case": "perturbed",
        "actuator_family": "smoothing",
        "description": "aspect-triggered localized smoothing only",
        "extra_args": [],
    },
    {
        "actuator_case": "smooth_standing_bias_positive",
        "benchmark_case": "baseline",
        "actuator_family": "smooth_bias",
        "description": "smooth standing wall-current source used by prior liquid-wall proxy",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0015", "--bias-polarity", "1"],
    },
    {
        "actuator_case": "rib8_bias_positive",
        "benchmark_case": "baseline",
        "actuator_family": "segmented_rib",
        "description": "eight-rib positive segmented edge-current source",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "rib_matrix", "--bias-strength", "0.0015", "--bias-polarity", "1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35",
        ],
    },
    {
        "actuator_case": "rib8_bias_negative",
        "benchmark_case": "baseline",
        "actuator_family": "segmented_rib",
        "description": "eight-rib negative segmented edge-current source",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "rib_matrix", "--bias-strength", "0.0015", "--bias-polarity", "-1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35",
        ],
    },
    {
        "actuator_case": "rib4_bias_positive",
        "benchmark_case": "baseline",
        "actuator_family": "segmented_rib",
        "description": "four-rib positive segmented edge-current source",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "rib_matrix", "--bias-strength", "0.0015", "--bias-polarity", "1",
            "--bias-rib-count", "4", "--bias-rib-duty", "0.35",
        ],
    },
    {
        "actuator_case": "rib8_bias_positive_low_strength",
        "benchmark_case": "baseline",
        "actuator_family": "segmented_rib",
        "description": "eight-rib positive segmented edge-current source at one-third strength",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "rib_matrix", "--bias-strength", "0.0005", "--bias-polarity", "1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35",
        ],
    },
    {
        "actuator_case": "mesh8_bias_positive",
        "benchmark_case": "baseline",
        "actuator_family": "segmented_mesh",
        "description": "eight-rib crossed mesh-like positive edge-current source",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "mesh", "--bias-strength", "0.0015", "--bias-polarity", "1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35",
        ],
    },
    {
        "actuator_case": "mesh8_bias_positive_low_strength",
        "benchmark_case": "baseline",
        "actuator_family": "segmented_mesh",
        "description": "eight-rib crossed mesh-like positive source at one-third strength",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "mesh", "--bias-strength", "0.0005", "--bias-polarity", "1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35",
        ],
    },
    {
        "actuator_case": "phase_locked_rib8_positive",
        "benchmark_case": "baseline",
        "actuator_family": "phase_locked_rib",
        "description": "phase-shifted eight-rib positive source",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "phase_locked_rib", "--bias-strength", "0.0015", "--bias-polarity", "1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35", "--bias-phase", "0.7853981633974483",
        ],
    },
    {
        "actuator_case": "smoothing_plus_smooth_standing_bias",
        "benchmark_case": "perturbed",
        "actuator_family": "smoothing_plus_smooth_bias",
        "description": "smoothing plus smooth standing wall-current source",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0015", "--bias-polarity", "1"],
    },
    {
        "actuator_case": "smoothing_plus_rib8_bias_positive",
        "benchmark_case": "perturbed",
        "actuator_family": "smoothing_plus_segmented_rib",
        "description": "smoothing plus eight-rib positive segmented edge-current source",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "rib_matrix", "--bias-strength", "0.0015", "--bias-polarity", "1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35",
        ],
    },
    {
        "actuator_case": "smoothing_plus_rib8_bias_positive_low_strength",
        "benchmark_case": "perturbed",
        "actuator_family": "smoothing_plus_segmented_rib",
        "description": "smoothing plus eight-rib positive segmented source at one-third strength",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "rib_matrix", "--bias-strength", "0.0005", "--bias-polarity", "1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35",
        ],
    },
    {
        "actuator_case": "smoothing_plus_mesh8_bias_positive",
        "benchmark_case": "perturbed",
        "actuator_family": "smoothing_plus_segmented_mesh",
        "description": "smoothing plus eight-rib crossed mesh-like positive edge-current source",
        "extra_args": [
            "--bias-enabled", "--bias-mode", "mesh", "--bias-strength", "0.0015", "--bias-polarity", "1",
            "--bias-rib-count", "8", "--bias-rib-duty", "0.35",
        ],
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


def _load_summary(case_dir: Path, case: dict[str, Any]) -> dict[str, Any]:
    output_case = _output_case_name(str(case["benchmark_case"]))
    summary = json.loads((case_dir / output_case / "summary.json").read_text(encoding="utf-8"))
    summary.pop("case", None)
    return {**case, "benchmark_output_case": output_case, **summary}


def _add_reductions(rows: list[dict[str, Any]]) -> None:
    baseline = next(row for row in rows if row["actuator_case"] == "baseline")
    base_islands = float(baseline["final_island_count_proxy"])
    base_components = float(baseline["final_component_count_proxy"])
    base_energy = float(baseline["final_magnetic_energy"])
    base_j = float(baseline["max_abs_J"])
    for row in rows:
        row["final_island_count_reduction_vs_baseline"] = 1.0 - float(row["final_island_count_proxy"]) / base_islands
        row["final_component_count_reduction_vs_baseline"] = (
            1.0 - float(row["final_component_count_proxy"]) / base_components if base_components else None
        )
        row["final_magnetic_energy_delta_vs_baseline"] = float(row["final_magnetic_energy"]) - base_energy
        row["max_abs_J_delta_vs_baseline"] = float(row["max_abs_J"]) - base_j


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=REPO / "validation_runs" / "dedalus_segmented_bias_actuator_matrix_default",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    if args.run_dir.exists() and not args.keep_existing:
        shutil.rmtree(args.run_dir)
    args.run_dir = args.run_dir.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for case in CASES:
        print(f"running {case['actuator_case']}", flush=True)
        case_dir = args.run_dir / str(case["actuator_case"])
        cmd = [
            args.python,
            str(BENCHMARK),
            "--run-dir", str(case_dir),
            "--case", str(case["benchmark_case"]),
            *BASE_ARGS,
            *case["extra_args"],
        ]
        _run(cmd, REPO)
        rows.append(_load_summary(case_dir, case))

    _add_reductions(rows)
    with (args.run_dir / "segmented_bias_actuator_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    best_island = min(rows, key=lambda row: int(row["final_island_count_proxy"]))
    best_component = min(rows, key=lambda row: int(row["final_component_count_proxy"]))
    summary = {
        "artifact_type": "dedalus_segmented_edge_current_bias_actuator_matrix",
        "schema_version": "1.0",
        "not_reactor_claim": True,
        "not_tokamak_validation": True,
        "not_liquid_lithium_physics": True,
        "not_electrode_engineering": True,
        "interpretation": (
            "Reduced-MHD toy comparison of smooth standing, segmented rib, and mesh-like prescribed "
            "edge-current source terms. These are actuator-geometry proxies, not physical electrode models."
        ),
        "best_case_by_final_island_proxy": best_island["actuator_case"],
        "best_case_by_final_component_proxy": best_component["actuator_case"],
        "cases": rows,
    }
    (args.run_dir / "segmented_bias_actuator_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

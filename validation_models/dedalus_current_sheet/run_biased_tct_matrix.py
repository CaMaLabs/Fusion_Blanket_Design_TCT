#!/usr/bin/env python3
"""Run a finite-pulse Dedalus island-onset matrix with biased TCT proxies."""

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
PLOTTER = Path(__file__).resolve().with_name("plot_dedalus_current_sheet_diagnostics.py")


BASE_ARGS = [
    "--nx",
    "64",
    "--nz",
    "64",
    "--eta",
    "2e-4",
    "--nu",
    "2e-4",
    "--delta0",
    "0.16",
    "--perturbation-amplitude",
    "0.001",
    "--perturbation-kx",
    "1",
    "--drive-enabled",
    "--drive-start-time",
    "0.5",
    "--drive-end-time",
    "0.7",
    "--drive-strength",
    "0.002",
    "--drive-kx",
    "4",
    "--drive-width",
    "0.45",
    "--control-aspect-threshold",
    "80",
    "--control-strength",
    "0.008",
    "--control-width",
    "0.70",
    "--stop-time",
    "2.0",
    "--timestep",
    "0.001",
    "--diagnostic-cadence",
    "50",
    "--snapshot-cadence",
    "250",
    "--onset-island-count-threshold",
    "2",
    "--island-o-point-prominence",
    "1e-5",
]


CASES = [
    {
        "case": "baseline",
        "description": "finite-pulse island-onset stress test without TCT proxy",
        "benchmark_case": "baseline",
        "extra_args": [],
    },
    {
        "case": "smoothing_only",
        "description": "aspect-triggered localized smoothing proxy",
        "benchmark_case": "perturbed",
        "extra_args": [],
    },
    {
        "case": "bias_positive_standing",
        "description": "standing positive biased wall-current proxy only",
        "benchmark_case": "baseline",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0015", "--bias-polarity", "1"],
    },
    {
        "case": "bias_negative_standing",
        "description": "standing negative biased wall-current proxy only",
        "benchmark_case": "baseline",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0015", "--bias-polarity", "-1"],
    },
    {
        "case": "smoothing_plus_bias_positive",
        "description": "aspect-triggered smoothing plus positive biased wall-current proxy",
        "benchmark_case": "perturbed",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0015", "--bias-polarity", "1"],
    },
    {
        "case": "smoothing_plus_bias_negative",
        "description": "aspect-triggered smoothing plus negative biased wall-current proxy",
        "benchmark_case": "perturbed",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0015", "--bias-polarity", "-1"],
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


def _case_output_name(benchmark_case: str) -> str:
    return "baseline" if benchmark_case == "baseline" else "tct_style_perturbed"


def _load_summary(case_dir: Path, case: dict[str, Any]) -> dict[str, Any]:
    output_case = _case_output_name(str(case["benchmark_case"]))
    summary = json.loads((case_dir / output_case / "summary.json").read_text(encoding="utf-8"))
    return {
        "case": case["case"],
        "description": case["description"],
        **summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=REPO / "validation_runs" / "dedalus_current_sheet_biased_tct_matrix")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    if args.run_dir.exists() and not args.keep_existing:
        shutil.rmtree(args.run_dir)
    args.run_dir = args.run_dir.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for case in CASES:
        case_dir = args.run_dir / str(case["case"])
        cmd = [
            args.python,
            str(BENCHMARK),
            "--run-dir",
            str(case_dir),
            "--case",
            str(case["benchmark_case"]),
            *BASE_ARGS,
            *case["extra_args"],
        ]
        _run(cmd, REPO)
        _run([args.python, str(PLOTTER), "--run-dir", str(case_dir)], REPO)
        rows.append(_load_summary(case_dir, case))

    baseline = next(row for row in rows if row["case"] == "baseline")
    for row in rows:
        base_islands = float(baseline["final_island_count_proxy"])
        base_energy = float(baseline["final_magnetic_energy"])
        row["final_island_count_reduction_vs_baseline"] = (
            1.0 - float(row["final_island_count_proxy"]) / base_islands if base_islands else None
        )
        row["final_magnetic_energy_delta_vs_baseline"] = float(row["final_magnetic_energy"]) - base_energy
        row["onset_delay_vs_baseline"] = (
            None
            if row["time_to_secondary_island_proxy"] is None or baseline["time_to_secondary_island_proxy"] is None
            else float(row["time_to_secondary_island_proxy"]) - float(baseline["time_to_secondary_island_proxy"])
        )

    with (args.run_dir / "biased_tct_matrix_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "artifact_type": "dedalus_biased_tct_wall_current_proxy_matrix",
        "not_reactor_claim": True,
        "not_liquid_lithium_physics": True,
        "interpretation": (
            "Finite-pulse driven island-onset stress test with biased wall-current proxy variants. "
            "Bias terms are prescribed reduced-MHD flux sources, not liquid-lithium wall currents."
        ),
        "cases": rows,
    }
    (args.run_dir / "biased_tct_matrix_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

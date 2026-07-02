#!/usr/bin/env python3
"""Run a compact biased TCT proxy parameter sweep for the Dedalus toy model."""

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

BIAS_STRENGTHS = (0.0005, 0.0010, 0.0015, 0.0020)
BIAS_POLARITIES = (1, -1)
CONTROL_FLAGS = (False, True)


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


def _case_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "sweep_case": "reference_unbiased_baseline",
            "benchmark_case": "baseline",
            "control_enabled_input": False,
            "bias_enabled_input": False,
            "bias_strength_input": 0.0,
            "bias_polarity_input": 0,
        }
    ]
    for control_enabled in CONTROL_FLAGS:
        for polarity in BIAS_POLARITIES:
            for strength in BIAS_STRENGTHS:
                control_label = "control" if control_enabled else "no_control"
                polarity_label = "positive" if polarity > 0 else "negative"
                rows.append(
                    {
                        "sweep_case": f"{control_label}_bias_{polarity_label}_{strength:.4f}",
                        "benchmark_case": "perturbed" if control_enabled else "baseline",
                        "control_enabled_input": control_enabled,
                        "bias_enabled_input": True,
                        "bias_strength_input": strength,
                        "bias_polarity_input": polarity,
                    }
                )
    return rows


def _args_for_row(row: dict[str, Any]) -> list[str]:
    if not row["bias_enabled_input"]:
        return []
    return [
        "--bias-enabled",
        "--bias-mode", "standing",
        "--bias-strength", str(row["bias_strength_input"]),
        "--bias-polarity", str(row["bias_polarity_input"]),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=REPO / "validation_runs" / "dedalus_current_sheet_biased_tct_parameter_sweep")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    if args.run_dir.exists() and not args.keep_existing:
        shutil.rmtree(args.run_dir)
    args.run_dir = args.run_dir.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for row in _case_rows():
        print(f"running {row['sweep_case']}", flush=True)
        case_dir = args.run_dir / str(row["sweep_case"])
        cmd = [
            args.python,
            str(BENCHMARK),
            "--run-dir", str(case_dir),
            "--case", str(row["benchmark_case"]),
            *BASE_ARGS,
            *_args_for_row(row),
        ]
        _run(cmd, REPO)
        rows.append(_load_summary(case_dir, row))

    baseline = next(row for row in rows if row["sweep_case"] == "reference_unbiased_baseline")
    base_islands = float(baseline["final_island_count_proxy"])
    base_energy = float(baseline["final_magnetic_energy"])
    for row in rows:
        row["final_island_count_reduction_vs_reference_baseline"] = 1.0 - float(row["final_island_count_proxy"]) / base_islands
        row["final_magnetic_energy_delta_vs_reference_baseline"] = float(row["final_magnetic_energy"]) - base_energy
        row["onset_delay_vs_reference_baseline"] = (
            None
            if row["time_to_secondary_island_proxy"] is None or baseline["time_to_secondary_island_proxy"] is None
            else float(row["time_to_secondary_island_proxy"]) - float(baseline["time_to_secondary_island_proxy"])
        )

    with (args.run_dir / "biased_tct_parameter_sweep_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    controlled_rows = [row for row in rows if row["control_enabled_input"] is True]
    best = min(controlled_rows, key=lambda row: int(row["final_island_count_proxy"]))
    summary = {
        "artifact_type": "dedalus_biased_tct_parameter_sweep",
        "schema_version": "1.0",
        "not_reactor_claim": True,
        "not_tokamak_validation": True,
        "not_liquid_lithium_physics": True,
        "reference_case": "reference_unbiased_baseline",
        "sweep_grid": {
            "bias_strength": list(BIAS_STRENGTHS),
            "bias_polarity": list(BIAS_POLARITIES),
            "control_enabled": list(CONTROL_FLAGS),
        },
        "best_controlled_case_by_final_island_proxy": best["sweep_case"],
        "cases": rows,
    }
    (args.run_dir / "biased_tct_parameter_sweep_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run compact numerical falsification checks for the biased Dedalus toy model."""

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
    "--eta", "2e-4",
    "--nu", "2e-4",
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
    "--diagnostic-cadence", "50",
    "--snapshot-cadence", "250",
    "--onset-island-count-threshold", "2",
]

CASES = [
    {
        "study_case": "baseline",
        "benchmark_case": "baseline",
        "description": "finite-pulse driven island-onset stress test without proxy control",
        "extra_args": [],
    },
    {
        "study_case": "smoothing_only",
        "benchmark_case": "perturbed",
        "description": "aspect-triggered localized smoothing proxy",
        "extra_args": [],
    },
    {
        "study_case": "smoothing_plus_bias_positive_0.0015",
        "benchmark_case": "perturbed",
        "description": "smoothing proxy plus positive standing biased flux source",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0015", "--bias-polarity", "1"],
    },
    {
        "study_case": "smoothing_plus_bias_negative_0.0020",
        "benchmark_case": "perturbed",
        "description": "smoothing proxy plus stronger negative standing biased flux source",
        "extra_args": ["--bias-enabled", "--bias-mode", "standing", "--bias-strength", "0.0020", "--bias-polarity", "-1"],
    },
]

# Compact grid:
# - 64x64 and 96x96 at the nominal timestep/prominence.
# - 64x64 nominal grid at a half timestep.
# - 64x64 nominal timestep with low/high local-extrema prominence.
CONDITIONS = [
    {"condition": "resolution_64_dt_0.001_prom_1e-5", "nx": 64, "nz": 64, "timestep": 0.001, "prominence": 1e-5},
    {"condition": "resolution_96_dt_0.001_prom_1e-5", "nx": 96, "nz": 96, "timestep": 0.001, "prominence": 1e-5},
    {"condition": "timestep_64_dt_0.0005_prom_1e-5", "nx": 64, "nz": 64, "timestep": 0.0005, "prominence": 1e-5},
    {"condition": "prominence_64_dt_0.001_prom_5e-6", "nx": 64, "nz": 64, "timestep": 0.001, "prominence": 5e-6},
    {"condition": "prominence_64_dt_0.001_prom_2e-5", "nx": 64, "nz": 64, "timestep": 0.001, "prominence": 2e-5},
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


def _load_summary(case_dir: Path, condition: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    output_case = _output_case_name(str(case["benchmark_case"]))
    summary = json.loads((case_dir / output_case / "summary.json").read_text(encoding="utf-8"))
    summary.pop("case", None)
    return {
        **condition,
        "study_case": case["study_case"],
        "benchmark_output_case": output_case,
        "description": case["description"],
        **summary,
    }


def _case_dir_name(condition: dict[str, Any], case: dict[str, Any]) -> str:
    return f"{condition['condition']}__{case['study_case']}"


def _add_reductions(rows: list[dict[str, Any]]) -> None:
    for condition in {row["condition"] for row in rows}:
        baseline = next(row for row in rows if row["condition"] == condition and row["study_case"] == "baseline")
        base_islands = float(baseline["final_island_count_proxy"])
        base_components = float(baseline["final_component_count_proxy"])
        base_energy = float(baseline["final_magnetic_energy"])
        base_max_j = float(baseline.get("max_abs_J", 0.0) or 0.0)
        for row in rows:
            if row["condition"] != condition:
                continue
            row["final_island_count_reduction_vs_condition_baseline"] = (
                1.0 - float(row["final_island_count_proxy"]) / base_islands if base_islands else None
            )
            row["final_component_count_reduction_vs_condition_baseline"] = (
                1.0 - float(row["final_component_count_proxy"]) / base_components if base_components else None
            )
            row["final_magnetic_energy_delta_vs_condition_baseline"] = float(row["final_magnetic_energy"]) - base_energy
            row["magnetic_energy_decay_fraction_delta_vs_condition_baseline"] = float(row["magnetic_energy_decay_fraction"]) - float(
                baseline["magnetic_energy_decay_fraction"]
            )
            row["max_abs_J_delta_vs_condition_baseline"] = float(row.get("max_abs_J", 0.0) or 0.0) - base_max_j


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cases = [case["study_case"] for case in CASES if case["study_case"] != "baseline"]
    per_case: dict[str, Any] = {}
    for case in cases:
        case_rows = [row for row in rows if row["study_case"] == case]
        island_reductions = [float(row["final_island_count_reduction_vs_condition_baseline"]) for row in case_rows]
        component_reductions = [float(row["final_component_count_reduction_vs_condition_baseline"]) for row in case_rows]
        per_case[case] = {
            "all_island_reductions_positive": all(value > 0.0 for value in island_reductions),
            "all_component_reductions_nonnegative": all(value >= 0.0 for value in component_reductions),
            "min_island_reduction": min(island_reductions),
            "max_island_reduction": max(island_reductions),
            "min_component_reduction": min(component_reductions),
            "max_component_reduction": max(component_reductions),
            "max_energy_decay_fraction_penalty": max(
                float(row["magnetic_energy_decay_fraction_delta_vs_condition_baseline"]) for row in case_rows
            ),
        }
    best = min((row for row in rows if row["study_case"] != "baseline"), key=lambda row: int(row["final_island_count_proxy"]))
    return {
        "per_case": per_case,
        "best_row_by_final_island_proxy": {
            "condition": best["condition"],
            "study_case": best["study_case"],
            "final_island_count_proxy": best["final_island_count_proxy"],
            "final_component_count_proxy": best["final_component_count_proxy"],
            "island_reduction": best["final_island_count_reduction_vs_condition_baseline"],
            "component_reduction": best["final_component_count_reduction_vs_condition_baseline"],
        },
        "falsification_readout": (
            "A candidate is numerically stronger only if island-proxy reduction, component-proxy direction, "
            "timestep sensitivity, and resolution sensitivity remain favorable without large energy/current penalties."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=REPO / "validation_runs" / "dedalus_current_sheet_biased_tct_falsification_study",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    if args.run_dir.exists() and not args.keep_existing:
        shutil.rmtree(args.run_dir)
    args.run_dir = args.run_dir.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for condition in CONDITIONS:
        for case in CASES:
            case_name = _case_dir_name(condition, case)
            print(f"running {case_name}", flush=True)
            case_dir = args.run_dir / case_name
            cmd = [
                args.python,
                str(BENCHMARK),
                "--run-dir",
                str(case_dir),
                "--case",
                str(case["benchmark_case"]),
                "--nx",
                str(condition["nx"]),
                "--nz",
                str(condition["nz"]),
                "--timestep",
                str(condition["timestep"]),
                "--island-o-point-prominence",
                str(condition["prominence"]),
                *BASE_ARGS,
                *case["extra_args"],
            ]
            _run(cmd, REPO)
            rows.append(_load_summary(case_dir, condition, case))

    _add_reductions(rows)
    with (args.run_dir / "biased_tct_falsification_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "artifact_type": "dedalus_biased_tct_numerical_falsification_study",
        "schema_version": "1.0",
        "not_reactor_claim": True,
        "not_tokamak_validation": True,
        "not_liquid_lithium_physics": True,
        "not_tct_validation": True,
        "conditions": CONDITIONS,
        "cases": rows,
        "summary": _summarize(rows),
    }
    (args.run_dir / "biased_tct_falsification_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

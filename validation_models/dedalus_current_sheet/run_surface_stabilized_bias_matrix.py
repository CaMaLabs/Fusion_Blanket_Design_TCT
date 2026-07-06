#!/usr/bin/env python3
"""Run non-acoustic surface-stabilized bias proxy cases in the Dedalus toy model."""

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

BIAS_BASE = ["--bias-enabled", "--bias-strength", "0.0015", "--bias-polarity", "1"]

CASES = [
    {
        "surface_case": "baseline",
        "benchmark_case": "baseline",
        "surface_strategy": "none",
        "description": "finite-pulse island-onset stress test without smoothing or bias",
        "extra_args": [],
    },
    {
        "surface_case": "smooth_standing_bias_positive",
        "benchmark_case": "baseline",
        "surface_strategy": "smooth_reference",
        "description": "smooth standing prescribed bias source; source-risk reference",
        "extra_args": [*BIAS_BASE, "--bias-mode", "standing"],
    },
    {
        "surface_case": "smooth_rib_bias_positive",
        "benchmark_case": "baseline",
        "surface_strategy": "segmented_smooth_envelope",
        "description": "smooth rib-like source envelope with reduced sharp transitions",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "smooth_rib_matrix",
            "--bias-rib-count", "8", "--bias-smoothness", "2.0",
        ],
    },
    {
        "surface_case": "smooth_mesh_bias_positive",
        "benchmark_case": "baseline",
        "surface_strategy": "mesh_smooth_envelope",
        "description": "smooth crossed mesh-like source envelope",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "smooth_mesh",
            "--bias-rib-count", "8", "--bias-smoothness", "2.0", "--surface-channel-count", "4",
        ],
    },
    {
        "surface_case": "capillary_stabilized_bias",
        "benchmark_case": "baseline",
        "surface_strategy": "capillary_porous_substrate_proxy",
        "description": "standing source with high-spatial-frequency attenuation and capillary risk damping",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "capillary_stabilized",
            "--surface-capillary-damping", "0.65",
        ],
    },
    {
        "surface_case": "magnetic_stiffened_bias",
        "benchmark_case": "baseline",
        "surface_strategy": "magnetic_pressure_shaping_proxy",
        "description": "standing source attenuated by a magnetic-stiffening proxy",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "magnetic_stiffened",
            "--surface-magnetic-stiffening", "1.0",
        ],
    },
    {
        "surface_case": "channelized_bias",
        "benchmark_case": "baseline",
        "surface_strategy": "flow_channel_geometry_proxy",
        "description": "low-frequency channelized source divided across four nominal channels",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "channelized",
            "--surface-channel-count", "4",
        ],
    },
    {
        "surface_case": "prebiased_smooth_pulse",
        "benchmark_case": "baseline",
        "surface_strategy": "prebias_plus_small_pulse_proxy",
        "description": "smooth standing source applied as a finite smooth pulse around the island drive",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "standing",
            "--bias-time-profile", "smooth_pulse",
            "--bias-start-time", "0.35", "--bias-end-time", "1.15", "--bias-ramp-time", "0.20",
        ],
    },
    {
        "surface_case": "smoothing_only",
        "benchmark_case": "perturbed",
        "surface_strategy": "localized_smoothing_reference",
        "description": "aspect-triggered localized smoothing proxy only",
        "extra_args": [],
    },
    {
        "surface_case": "smoothing_plus_capillary_stabilized",
        "benchmark_case": "perturbed",
        "surface_strategy": "smoothing_plus_capillary_proxy",
        "description": "localized smoothing plus capillary-stabilized source proxy",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "capillary_stabilized",
            "--surface-capillary-damping", "0.65",
        ],
    },
    {
        "surface_case": "smoothing_plus_magnetic_stiffened",
        "benchmark_case": "perturbed",
        "surface_strategy": "smoothing_plus_magnetic_pressure_proxy",
        "description": "localized smoothing plus magnetic-stiffening source proxy",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "magnetic_stiffened",
            "--surface-magnetic-stiffening", "1.0",
        ],
    },
    {
        "surface_case": "smoothing_plus_channelized",
        "benchmark_case": "perturbed",
        "surface_strategy": "smoothing_plus_channel_geometry_proxy",
        "description": "localized smoothing plus four-channel source proxy",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "channelized",
            "--surface-channel-count", "4",
        ],
    },
    {
        "surface_case": "smoothing_plus_smooth_rib",
        "benchmark_case": "perturbed",
        "surface_strategy": "smoothing_plus_smooth_segmented_envelope",
        "description": "localized smoothing plus smoothed rib source envelope",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "smooth_rib_matrix",
            "--bias-rib-count", "8", "--bias-smoothness", "2.0",
        ],
    },
    {
        "surface_case": "smoothing_plus_prebiased_smooth_pulse",
        "benchmark_case": "perturbed",
        "surface_strategy": "smoothing_plus_prebias_pulse_proxy",
        "description": "localized smoothing plus finite smooth pulse bias source",
        "extra_args": [
            *BIAS_BASE, "--bias-mode", "standing",
            "--bias-time-profile", "smooth_pulse",
            "--bias-start-time", "0.35", "--bias-end-time", "1.15", "--bias-ramp-time", "0.20",
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


def _ratio(value: float, reference: float) -> float | None:
    return value / reference if reference else None


def _add_comparisons(rows: list[dict[str, Any]]) -> None:
    baseline = next(row for row in rows if row["surface_case"] == "baseline")
    smooth = next(row for row in rows if row["surface_case"] == "smooth_standing_bias_positive")
    base_islands = float(baseline["final_island_count_proxy"])
    base_components = float(baseline["final_component_count_proxy"])
    base_energy = float(baseline["final_magnetic_energy"])
    base_j = float(baseline["max_abs_J"])
    smooth_risk = float(smooth["max_surface_displacement_risk_proxy"])
    for row in rows:
        row["final_island_count_reduction_vs_baseline"] = 1.0 - float(row["final_island_count_proxy"]) / base_islands
        row["final_component_count_reduction_vs_baseline"] = (
            1.0 - float(row["final_component_count_proxy"]) / base_components if base_components else None
        )
        row["final_magnetic_energy_delta_vs_baseline"] = float(row["final_magnetic_energy"]) - base_energy
        row["max_abs_J_delta_vs_baseline"] = float(row["max_abs_J"]) - base_j
        row["surface_risk_ratio_vs_smooth_standing"] = _ratio(
            float(row["max_surface_displacement_risk_proxy"]), smooth_risk
        )
        row["surface_risk_delta_vs_smooth_standing"] = (
            float(row["max_surface_displacement_risk_proxy"]) - smooth_risk
        )


def _write_artifact_notes(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    best_island = min(rows, key=lambda row: int(row["final_island_count_proxy"]))
    best_risk_nonzero = min(
        [row for row in rows if float(row["max_surface_displacement_risk_proxy"]) > 0.0],
        key=lambda row: float(row["max_surface_displacement_risk_proxy"]),
    )
    text = f"""# Surface-Stabilized Bias Matrix Notes

## Purpose

This matrix tests non-acoustic ways to make a prescribed biased TCT-style source
less sharp in a reduced-MHD Dedalus current-sheet toy benchmark. It covers
capillary/porous-substrate damping proxies, smooth segmented envelopes,
channelized source geometry, magnetic-stiffening attenuation, and pulse shaping.

Acoustic damping and active surface-wave cancellation were intentionally excluded
from this run.

## Strongest Island-Proxy Result

- Best final island proxy case: `{best_island["surface_case"]}`
- Final island proxy: `{best_island["final_island_count_proxy"]}`
- Reduction vs no-bias baseline: `{best_island["final_island_count_reduction_vs_baseline"]:.6g}`

## Lowest Nonzero Surface-Risk Proxy

- Lowest nonzero source-risk case: `{best_risk_nonzero["surface_case"]}`
- Max surface displacement risk proxy: `{best_risk_nonzero["max_surface_displacement_risk_proxy"]:.6g}`
- Ratio vs smooth standing source: `{best_risk_nonzero["surface_risk_ratio_vs_smooth_standing"]:.6g}`

## Caveats

- Reduced-MHD toy benchmark only.
- Prescribed flux-source terms only.
- No free-surface MHD.
- No liquid-lithium material physics.
- No capillary-wave, wetting, electrode, sheath, contact-resistance, or wall model.
- No tokamak geometry and no TCT validation claim.
- The surface-risk metric is a source-gradient/laplacian proxy, not a fluid
  displacement calculation.

## Next Work

- Replace source-risk proxies with a real free-surface or shallow-liquid model.
- Sweep source strength, pulse timing, smoothness, and channel count.
- Repeat at higher resolution and with independent topology diagnostics.
- Review the prescribed-source equations with Dedalus/reconnection experts.
"""
    (run_dir / "ARTIFACT_NOTES.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=REPO / "validation_runs" / "dedalus_surface_stabilized_bias_matrix_default",
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
        print(f"running {case['surface_case']}", flush=True)
        case_dir = args.run_dir / str(case["surface_case"])
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

    _add_comparisons(rows)
    results_path = args.run_dir / "surface_stabilized_bias_results.csv"
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    best_island = min(rows, key=lambda row: int(row["final_island_count_proxy"]))
    best_component = min(rows, key=lambda row: int(row["final_component_count_proxy"]))
    best_risk_nonzero = min(
        [row for row in rows if float(row["max_surface_displacement_risk_proxy"]) > 0.0],
        key=lambda row: float(row["max_surface_displacement_risk_proxy"]),
    )
    summary = {
        "artifact_type": "dedalus_non_acoustic_surface_stabilized_bias_matrix",
        "schema_version": "1.0",
        "not_reactor_claim": True,
        "not_tokamak_validation": True,
        "not_tct_validation": True,
        "not_liquid_lithium_physics": True,
        "not_free_surface_mhd": True,
        "excluded_strategy": "acoustic_damping_or_active_surface_wave_cancellation",
        "interpretation": (
            "Reduced-MHD toy comparison of prescribed source-shaping proxies intended to reduce "
            "bias-source sharpness while preserving island/morphology diagnostic benefit."
        ),
        "best_case_by_final_island_proxy": best_island["surface_case"],
        "best_case_by_final_component_proxy": best_component["surface_case"],
        "lowest_nonzero_surface_risk_proxy_case": best_risk_nonzero["surface_case"],
        "cases": rows,
    }
    (args.run_dir / "surface_stabilized_bias_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_artifact_notes(args.run_dir, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

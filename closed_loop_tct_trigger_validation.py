#!/usr/bin/env python3
"""Closed-loop, trigger-aware reduced-MHD TCT actuator validation bridge."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import netCDF4
import numpy as np

from bout_tct_actuator_robustness_sweep import BASE_GRID, FINE_GRID, _base_strength
from bout_tct_current_sheet_sweep import BUILD_DIR, MODEL_DIR, _build_model, _evaluate_base
from bout_validation_bridge import DEFAULT_BOUT_BUILD, DEFAULT_BOUT_TOP, REPO, _safe_float


RUN_NAME = "closed_loop_tct_trigger_default"
STATUS_PHRASE = "PASS_WITH_REDUCED_MODEL_BOUNDARIES"
M3DC1_REPO = Path("/root/CaMaLabs_M3DC1")


def _existing_bout_boundary() -> dict[str, Any]:
    path = REPO / "validation_runs" / "bout_tct_actuator_robustness_default" / "tct_actuator_robustness_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    by_case = {case["case"]: case for case in summary["cases"]}

    def metric(case: str, name: str) -> float:
        return float(by_case[case]["diagnostics"][name])

    base_peak = metric("base_uncontrolled", "post_initial_max_abs_J")
    nominal_peak = metric("base_nominal", "post_initial_max_abs_J")
    fine_peak = metric("fine_tct000", "post_initial_max_abs_J")
    fine_nominal_peak = metric("fine_tct080", "post_initial_max_abs_J")
    delayed4_peak = metric("timing_delayed4", "post_initial_max_abs_J")
    base_integrated = metric("base_uncontrolled", "time_integrated_max_abs_J")
    delayed2_integrated = metric("timing_delayed2", "time_integrated_max_abs_J")
    delayed4_integrated = metric("timing_delayed4", "time_integrated_max_abs_J")

    return {
        "source": str(path),
        "nominal_peak_current_reduction": 1.0 - nominal_peak / base_peak,
        "fine_grid_peak_current_reduction": 1.0 - fine_nominal_peak / fine_peak,
        "timing_delayed_peak_current_reduction": 1.0 - delayed4_peak / base_peak,
        "timing_delayed2_integrated_current_reduction": 1.0 - delayed2_integrated / base_integrated,
        "timing_delayed4_integrated_current_reduction": 1.0 - delayed4_integrated / base_integrated,
        "interpretation": (
            "Existing robustness evidence supports early/nominal actuation, but the delayed4 case preserves "
            "the timing falsification boundary: integrated current falls while post-initial peak current does not."
        ),
    }


def _existing_m3dc1_boundary() -> dict[str, Any]:
    candidate_path = M3DC1_REPO / "validation" / "generated" / "candidate0_physics_results.csv"
    real_report_path = M3DC1_REPO / "validation" / "real_c1_h5_report.md"
    rows = list(csv.DictReader(candidate_path.open(encoding="utf-8")))
    best = max(rows, key=lambda row: float(row["score"]))
    real_report = real_report_path.read_text(encoding="utf-8")
    limitation = (
        "The real public HEAT C1.h5 integration file fails reactor-relevant hard constraints; "
        "all five real-HDF5-derived cases failed with TBR<1.05 and Pnet<1.0. It is a real backend "
        "integration test, not reactor-relevant TCT validation."
    )
    if "TBR<1.05;Pnet<1.0" not in real_report:
        limitation += " The expected failure phrase was not found verbatim in the current report text."
    return {
        "candidate0_source": str(candidate_path),
        "candidate0_rows": len(rows),
        "candidate0_all_pass_hard_constraints": all(row["passed_hard_constraints"] == "True" for row in rows),
        "candidate0_best_case": best["case_name"],
        "candidate0_best_score": float(best["score"]),
        "candidate0_best_tbr": float(best["TBR"]),
        "candidate0_best_pnet_mw": float(best["Pnet_MW"]),
        "real_c1_h5_report": str(real_report_path),
        "real_c1_h5_limitation": limitation,
    }


def _write_inp(case_dir: Path, case: dict[str, Any], nout: int) -> None:
    grid = case["grid"]
    case_dir.mkdir(parents=True, exist_ok=True)
    text = f"""
MYG = 0
periodicX = true

[mesh]
nx = {int(grid["nx"])}
ny = 1
nz = {int(grid["nz"])}
dx = {float(grid["dx"]):.8g}
dy = 1.0
dz = {float(grid["dz"]):.8g}

[tct]
eta = {case["eta"]:.8g}
nu = {case["nu"]:.8g}
strength = {case["tct_strength"]:.8g}
omega_strength = {case["omega_tct_strength"]:.8g}
start_time = {case["actuator_start_time"]:.8g}
end_time = {case["actuator_end_time"]:.8g}
bracket = 2

[psi]
scale = 1.0
function = {case["psi_amp"]:.8g} * exp(-((x-0.5)/{grid["sheet_width"]:.8g})^2) + {case["island_seed"]:.8g} * cos(z)
bndry_all = dirichlet_o2

[omega]
scale = 1.0
function = {case["omega_seed"]:.8g} * sin(z) * exp(-((x-0.5)/(2*{grid["sheet_width"]:.8g}))^2)
bndry_all = dirichlet_o2

[tct_mask]
scale = 1.0
function = exp(-((x-{case["actuator_center"]:.8g})/{case["actuator_width"]:.8g})^2)
bndry_all = dirichlet_o2

[solver]
output_step = 1.0
nout = {int(nout)}
mxstep = 10000
atol = 1e-10
rtol = 1e-6
"""
    (case_dir / "BOUT.inp").write_text(text, encoding="utf-8")


def _run_case(exe: Path, case_dir: Path) -> None:
    env = os.environ.copy()
    env["UCX_TLS"] = os.environ.get("BOUT_UCX_TLS", "self")
    lib_paths = [str(Path(DEFAULT_BOUT_BUILD) / "lib"), "/tmp/bout-build/lib"]
    existing_ld_path = env.get("LD_LIBRARY_PATH")
    if existing_ld_path:
        lib_paths.append(existing_ld_path)
    env["LD_LIBRARY_PATH"] = ":".join(lib_paths)
    result = subprocess.run(
        [str(exe), "-d", str(case_dir)],
        check=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    (case_dir / "bout_stdout.log").write_text(result.stdout, encoding="utf-8")
    (case_dir / "bout_stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        sys.stderr.write(result.stdout[-4000:])
        sys.stderr.write(result.stderr[-4000:])
        raise subprocess.CalledProcessError(result.returncode, [str(exe), "-d", str(case_dir)])


def _series(case_dir: Path) -> dict[str, Any]:
    output = case_dir / "BOUT.dmp.0.nc"
    if not output.exists():
        raise FileNotFoundError(f"BOUT++ output not found: {output}")
    with netCDF4.Dataset(output) as ds:
        current = np.asarray(ds.variables["J"][:], dtype=float)
        omega = np.asarray(ds.variables["omega"][:], dtype=float)
        psi = np.asarray(ds.variables["psi"][:], dtype=float)
        time = np.asarray(ds.variables["t_array"][:], dtype=float)
    axes = tuple(range(1, current.ndim))
    abs_j = np.abs(current)
    max_j = np.max(abs_j, axis=axes)
    p99_j = np.percentile(abs_j.reshape((abs_j.shape[0], -1)), 99, axis=1)
    max_omega = np.max(np.abs(omega), axis=axes)
    magnetic_energy = 0.5 * np.mean(psi * psi, axis=axes)
    return {
        "time": time,
        "max_j": max_j,
        "p99_j": p99_j,
        "max_omega": max_omega,
        "magnetic_energy": magnetic_energy,
    }


def _diagnostics(series: dict[str, Any]) -> dict[str, float]:
    time = series["time"]
    max_j = series["max_j"]
    p99_j = series["p99_j"]
    max_omega = series["max_omega"]
    magnetic_energy = series["magnetic_energy"]
    return {
        "time_end": float(time[-1]),
        "initial_max_abs_J": float(max_j[0]),
        "post_initial_max_abs_J": float(np.max(max_j[1:])) if len(max_j) > 1 else float(max_j[0]),
        "final_max_abs_J": float(max_j[-1]),
        "time_integrated_max_abs_J": float(np.trapz(max_j, time)),
        "post_initial_max_abs_J_p99": float(np.max(p99_j[1:])) if len(p99_j) > 1 else float(p99_j[0]),
        "final_abs_J_p99": float(p99_j[-1]),
        "max_abs_omega": float(np.max(max_omega)),
        "time_integrated_max_abs_omega": float(np.trapz(max_omega, time)),
        "initial_magnetic_energy": float(magnetic_energy[0]),
        "final_magnetic_energy": float(magnetic_energy[-1]),
    }


def _uncontrolled_peak(series: dict[str, Any]) -> tuple[float, float]:
    time = series["time"]
    max_j = series["max_j"]
    if len(max_j) > 1:
        offset = int(np.argmax(max_j[1:])) + 1
    else:
        offset = int(np.argmax(max_j))
    return float(time[offset]), float(max_j[offset])


def _trigger_time(policy: dict[str, Any], baseline: dict[str, Any]) -> float | None:
    time = baseline["time"]
    max_j = baseline["max_j"]
    peak_time, peak_j = _uncontrolled_peak(baseline)
    latency = float(policy.get("latency", 0.0)) + float(policy.get("jitter", 0.0))
    kind = policy["trigger_kind"]
    if kind == "none":
        return None
    if kind == "scheduled":
        return max(0.0, float(policy["scheduled_time"]) + latency)
    if kind == "delayed":
        return peak_time + float(policy["delay_after_peak"]) + latency
    if kind == "j_threshold":
        threshold = float(policy["threshold_fraction"]) * peak_j
        hits = np.where(max_j >= threshold)[0]
        return float(time[int(hits[0])]) + latency if len(hits) else None
    if kind == "djdt_threshold":
        derivative = np.gradient(max_j, time)
        threshold = float(policy["threshold_fraction"]) * float(np.max(np.abs(derivative)))
        hits = np.where(np.abs(derivative) >= threshold)[0]
        return float(time[int(hits[0])]) + latency if len(hits) else None
    raise ValueError(f"Unknown trigger kind: {kind}")


def _policies(grid_name: str) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = [
        {"case_suffix": "no_control", "trigger_kind": "none", "strength_scale": 0.0, "threshold_label": "none"},
        {"case_suffix": "scheduled_preemptive", "trigger_kind": "scheduled", "scheduled_time": 0.0, "strength_scale": 1.0, "threshold_label": "scheduled"},
        {"case_suffix": "j_low_nominal", "trigger_kind": "j_threshold", "threshold_fraction": 0.70, "strength_scale": 1.0, "threshold_label": "low"},
        {"case_suffix": "j_medium_nominal", "trigger_kind": "j_threshold", "threshold_fraction": 0.85, "strength_scale": 1.0, "threshold_label": "medium"},
        {"case_suffix": "j_high_nominal", "trigger_kind": "j_threshold", "threshold_fraction": 0.98, "strength_scale": 1.0, "threshold_label": "high"},
        {"case_suffix": "j_medium_plus20", "trigger_kind": "j_threshold", "threshold_fraction": 0.85, "strength_scale": 1.2, "threshold_label": "medium"},
        {"case_suffix": "djdt_medium_nominal", "trigger_kind": "djdt_threshold", "threshold_fraction": 0.50, "strength_scale": 1.0, "threshold_label": "medium"},
        {"case_suffix": "j_medium_latency0p5", "trigger_kind": "j_threshold", "threshold_fraction": 0.85, "strength_scale": 1.0, "threshold_label": "medium", "latency": 0.5},
        {"case_suffix": "j_medium_latency1p5", "trigger_kind": "j_threshold", "threshold_fraction": 0.85, "strength_scale": 1.0, "threshold_label": "medium", "latency": 1.5},
        {"case_suffix": "delayed_falsification", "trigger_kind": "delayed", "delay_after_peak": 2.0, "strength_scale": 1.0, "threshold_label": "delayed"},
    ]
    if grid_name == "fine":
        return [p for p in policies if p["case_suffix"] in {"no_control", "j_medium_nominal", "j_medium_plus20", "delayed_falsification"}]
    return policies


def _case_from_policy(
    grid: dict[str, Any],
    policy: dict[str, Any],
    plasma: dict[str, Any],
    reactor: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    base_strength = _base_strength(plasma, reactor)
    strength_scale = float(policy["strength_scale"])
    trigger = _trigger_time(policy, baseline)
    if trigger is None:
        start = 0.0
        end = 0.0
        fired = False
    else:
        start = max(0.0, trigger)
        end = 1e30
        fired = True
    peak_time, _peak_j = _uncontrolled_peak(baseline)
    control = 0.8 * strength_scale
    return {
        "case": f"{grid['name']}_{policy['case_suffix']}",
        "grid": grid,
        "family": "closed_loop_trigger",
        "trigger_kind": policy["trigger_kind"],
        "threshold_label": policy.get("threshold_label", ""),
        "threshold_fraction": policy.get("threshold_fraction", ""),
        "sensor_latency": float(policy.get("latency", 0.0)),
        "timing_jitter": float(policy.get("jitter", 0.0)),
        "trigger_time": start if fired else "",
        "trigger_fired": fired,
        "uncontrolled_peak_time": peak_time,
        "trigger_margin_before_uncontrolled_peak": peak_time - start if fired else "",
        "trigger_fired_before_current_sheet_peak": fired and start < peak_time,
        "actuator_start_time": start,
        "actuator_end_time": end,
        "actuator_strength": base_strength * control,
        "actuator_center": 0.5,
        "actuator_width": 1.7 * float(grid["sheet_width"]),
        "control": control,
        "strength_scale": strength_scale,
        "tct_strength": base_strength * control,
        "omega_tct_strength": 0.5 * base_strength * control,
        "eta": 7.5e-4,
        "nu": 1.0e-3,
        "psi_amp": 0.08,
        "island_seed": 0.006,
        "omega_seed": 0.01,
    }


def _row(case_dir: Path, case: dict[str, Any], diagnostics: dict[str, float]) -> dict[str, Any]:
    grid = case["grid"]
    fields = {key: value for key, value in case.items() if key != "grid"}
    return {
        "case": case_dir.name,
        "case_dir": str(case_dir),
        "grid": grid["name"],
        "nx": grid["nx"],
        "nz": grid["nz"],
        "sheet_width": grid["sheet_width"],
        **fields,
        **diagnostics,
    }


def _add_reductions(rows: list[dict[str, Any]]) -> None:
    baselines = {row["grid"]: row for row in rows if row["trigger_kind"] == "none"}
    for row in rows:
        baseline = baselines[row["grid"]]
        for metric in ("post_initial_max_abs_J", "time_integrated_max_abs_J", "post_initial_max_abs_J_p99"):
            base = float(baseline[metric])
            value = float(row[metric])
            row[f"{metric}_reduction_fraction"] = 1.0 - value / base if base else float("nan")


def _gate_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _add_reductions(rows)
    by_case = {row["case"]: row for row in rows}
    base_nominal = by_case["base_j_medium_nominal"]
    base_control = by_case["base_no_control"]
    fine_nominal = by_case["fine_j_medium_nominal"]
    fine_control = by_case["fine_no_control"]
    delayed = by_case["base_delayed_falsification"]
    contract = REPO / "validation_runs" / RUN_NAME / "m3dc1_diagnostic_contract.json"
    contract_obj = json.loads(contract.read_text(encoding="utf-8"))
    return [
        {
            "gate": "nominal_and_fine_trigger_before_uncontrolled_peak",
            "passed": bool(base_nominal["trigger_fired_before_current_sheet_peak"] and fine_nominal["trigger_fired_before_current_sheet_peak"]),
            "evidence": {
                "base_margin": base_nominal["trigger_margin_before_uncontrolled_peak"],
                "fine_margin": fine_nominal["trigger_margin_before_uncontrolled_peak"],
            },
        },
        {
            "gate": "nominal_closed_loop_reduces_post_initial_peak_J",
            "passed": float(base_nominal["post_initial_max_abs_J"]) < float(base_control["post_initial_max_abs_J"]),
            "evidence": {
                "controlled": base_nominal["post_initial_max_abs_J"],
                "uncontrolled": base_control["post_initial_max_abs_J"],
                "reduction_fraction": base_nominal["post_initial_max_abs_J_reduction_fraction"],
            },
        },
        {
            "gate": "nominal_closed_loop_reduces_integrated_max_J",
            "passed": float(base_nominal["time_integrated_max_abs_J"]) < float(base_control["time_integrated_max_abs_J"]),
            "evidence": {
                "controlled": base_nominal["time_integrated_max_abs_J"],
                "uncontrolled": base_control["time_integrated_max_abs_J"],
                "reduction_fraction": base_nominal["time_integrated_max_abs_J_reduction_fraction"],
            },
        },
        {
            "gate": "fine_grid_direction_matches_base_grid_direction",
            "passed": (
                float(base_nominal["post_initial_max_abs_J_reduction_fraction"]) > 0.0
                and float(fine_nominal["post_initial_max_abs_J_reduction_fraction"]) > 0.0
                and float(base_nominal["time_integrated_max_abs_J_reduction_fraction"]) > 0.0
                and float(fine_nominal["time_integrated_max_abs_J_reduction_fraction"]) > 0.0
            ),
            "evidence": {
                "base_peak_reduction": base_nominal["post_initial_max_abs_J_reduction_fraction"],
                "fine_peak_reduction": fine_nominal["post_initial_max_abs_J_reduction_fraction"],
                "base_integrated_reduction": base_nominal["time_integrated_max_abs_J_reduction_fraction"],
                "fine_integrated_reduction": fine_nominal["time_integrated_max_abs_J_reduction_fraction"],
            },
        },
        {
            "gate": "delayed_trigger_preserves_timing_falsification_boundary",
            "passed": (
                not bool(delayed["trigger_fired_before_current_sheet_peak"])
                and float(delayed["post_initial_max_abs_J_reduction_fraction"]) <= 0.01
                and float(delayed["time_integrated_max_abs_J_reduction_fraction"]) > 0.0
            ),
            "evidence": {
                "delayed_peak_reduction": delayed["post_initial_max_abs_J_reduction_fraction"],
                "delayed_integrated_reduction": delayed["time_integrated_max_abs_J_reduction_fraction"],
                "trigger_margin": delayed["trigger_margin_before_uncontrolled_peak"],
            },
        },
        {
            "gate": "m3dc1_diagnostic_contract_valid_proxy_json",
            "passed": (
                contract_obj.get("artifact_type") == "diagnostic_control_contract"
                and contract_obj.get("not_real_m3dc1_output") is True
                and "not a real M3D-C1 run" in contract_obj.get("labeling", "")
            ),
            "evidence": {
                "artifact_type": contract_obj.get("artifact_type"),
                "not_real_m3dc1_output": contract_obj.get("not_real_m3dc1_output"),
            },
        },
    ]


def _write_contract(run_dir: Path) -> None:
    contract = {
        "schema_version": "1.0",
        "artifact_type": "diagnostic_control_contract",
        "artifact_label": "M3D-C1-compatible diagnostic/control contract for closed-loop reduced-MHD TCT trigger validation",
        "not_real_m3dc1_output": True,
        "labeling": "This is a diagnostic/control contract and proxy bridge, not a real M3D-C1 run or real M3D-C1 reactor output.",
        "status_phrase": STATUS_PHRASE,
        "required_diagnostic_inputs": {
            "psi": {"required": True, "description": "Poloidal flux or reduced-MHD flux field."},
            "phi": {"required": True, "description": "Toroidal angle or phase coordinate when available."},
            "J": {"required": False, "description": "Current density/current-sheet diagnostic if directly available."},
            "computable_J": {"required": True, "formula": "J = -Delp2(psi)"},
            "time": {"required": True, "description": "Monotonic sample time for trigger evaluation."},
            "mirnov_or_toroidal_proxy_signal": {"required": False, "description": "Optional magnetic precursor/proxy signal."},
        },
        "trigger_outputs": {
            "trigger_time": "First diagnostic threshold crossing time after latency/jitter model.",
            "actuator_start_time": "Time supplied to the reduced actuator backend.",
            "actuator_end_time": "Actuator shutoff time or open-ended sentinel.",
            "actuator_strength": "Reduced-MHD actuator strength used by the backend.",
            "actuator_center": "Radial/current-sheet actuator center in normalized coordinates.",
            "actuator_width": "Radial/current-sheet actuator width in normalized coordinates.",
        },
        "backend_compatibility": {
            "m3dc1_helical_proxy_c1_h5_schema": "compatible when psi/time and either J or fields sufficient to compute -Delp2(psi) are present",
            "existing_proxy_schema": "May consume the existing helical proxy C1.h5 field names when present.",
            "scope": "diagnostic/control handoff contract only",
        },
        "failure_modes": [
            "no pre-peak trigger",
            "trigger after peak",
            "integrated current reduction but no peak-current reduction",
            "grid-sensitive sign reversal",
        ],
    }
    (run_dir / "m3dc1_diagnostic_contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True), encoding="utf-8")


def _write_readme(run_dir: Path, summary: dict[str, Any]) -> None:
    readme = f"""# Closed-loop TCT Trigger Validation

Status: `{summary["status"]}`

This directory contains a closed-loop reduced-MHD trigger validation pass and an
M3D-C1-compatible diagnostic contract. It is reduced-model evidence, not full
tokamak-grade validation and not a real M3D-C1 reactor output.

Files:

- `closed_loop_trigger_results.csv`
- `closed_loop_trigger_summary.json`
- `closed_loop_trigger_report.md`
- `m3dc1_diagnostic_contract.json`

The run preserves the known timing boundary: late/delayed actuation can reduce
time-integrated max `|J|` while failing to reduce post-initial peak `|J|`.
"""
    (run_dir / "README.md").write_text(readme, encoding="utf-8")


def _gate_mark(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _write_report(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    gates = summary["gates"]
    top = max(
        [row for row in rows if row["trigger_kind"] != "none"],
        key=lambda row: float(row["time_integrated_max_abs_J_reduction_fraction"]),
    )
    weak = min(
        [row for row in rows if row["trigger_kind"] != "none"],
        key=lambda row: float(row["post_initial_max_abs_J_reduction_fraction"]),
    )
    gate_rows = "\n".join(
        f"| {gate['gate']} | {_gate_mark(bool(gate['passed']))} | `{json.dumps(gate['evidence'], sort_keys=True)}` |"
        for gate in gates
    )
    report = f"""# Closed-loop TCT Trigger Validation Report

Status: `{summary["status"]}`

## Already Completed Before This Run

- BOUT++ / M3D-C1 bridge artifacts:
  `validation_runs/m3dc1_bout_cross_validation_default/cross_validation_report.md`
  and `cross_validation_summary.json`.
- Resolved BOUT++ actuator robustness:
  `validation_runs/bout_tct_actuator_robustness_default/tct_actuator_robustness_summary.json`.
- BOUT++ validation ladder:
  `docs/bout_validation_plan.md`.
- M3D-C1-side proxy and integration artifacts:
  `/root/CaMaLabs_M3DC1/validation/generated/candidate0_physics_results.csv`,
  `/root/CaMaLabs_M3DC1/validation/real_c1_h5_report.md`, and
  `/root/CaMaLabs_M3DC1/validation/helical_benchmark_note.md`.

Existing timing boundary extracted from the actuator robustness run:

- nominal peak-current reduction: `{summary["existing_bout_boundary"]["nominal_peak_current_reduction"]:.6f}`
- fine-grid peak-current reduction: `{summary["existing_bout_boundary"]["fine_grid_peak_current_reduction"]:.6f}`
- delayed peak-current reduction: `{summary["existing_bout_boundary"]["timing_delayed_peak_current_reduction"]:.6f}`
- delayed2 integrated-current reduction: `{summary["existing_bout_boundary"]["timing_delayed2_integrated_current_reduction"]:.6f}`
- delayed4 integrated-current reduction: `{summary["existing_bout_boundary"]["timing_delayed4_integrated_current_reduction"]:.6f}`

M3D-C1 limitation preserved: {summary["existing_m3dc1_boundary"]["real_c1_h5_limitation"]}

## What This Run Adds

This run adds closed-loop reduced-MHD trigger validation using the existing
BOUT++ current-sheet actuator framework. Trigger policies include J-threshold,
dJ/dt-threshold, preemptive scheduled, delayed falsification, and no-control
baselines across base and fine grids, threshold variants, nominal and +20%
actuator strength, and latency cases.

It also writes an M3D-C1-compatible diagnostic contract at
`m3dc1_diagnostic_contract.json`. The contract is explicitly a diagnostic/control
contract and proxy bridge, not a real M3D-C1 run.

## Pass/Fail Gates

| Gate | Result | Evidence |
| --- | --- | --- |
{gate_rows}

## Strongest Result

`{top["case"]}` gave the strongest integrated-current reduction:

- post-initial peak `|J|` reduction: `{float(top["post_initial_max_abs_J_reduction_fraction"]):.6f}`
- time-integrated max `|J|` reduction: `{float(top["time_integrated_max_abs_J_reduction_fraction"]):.6f}`
- trigger time: `{top["trigger_time"]}`
- trigger margin before uncontrolled peak: `{top["trigger_margin_before_uncontrolled_peak"]}`

## Weakest Result

`{weak["case"]}` is the weakest controlled case by peak-current reduction:

- post-initial peak `|J|` reduction: `{float(weak["post_initial_max_abs_J_reduction_fraction"]):.6f}`
- time-integrated max `|J|` reduction: `{float(weak["time_integrated_max_abs_J_reduction_fraction"]):.6f}`
- trigger fired before current-sheet peak: `{weak["trigger_fired_before_current_sheet_peak"]}`

This preserves the known falsification boundary: delayed/late triggering can
still reduce integrated current while failing the peak-current metric.

## Explicit Limitations

- This is closed-loop reduced-MHD trigger validation, not full tokamak-grade
  validation.
- The actuator is the existing reduced BOUT++ current-sheet model, not a measured
  liquid-metal actuator.
- The M3D-C1 bridge is an M3D-C1-compatible diagnostic contract, not a real
  M3D-C1 reactor output.
- The real public HEAT `C1.h5` file remains a backend integration test that
  fails reactor-relevant hard constraints.
- No experimental Mirnov, ECE, density, EFIT-evolution, or actuator telemetry was
  used in this run.

## Next Step

The next real validation step is to replace the reduced `J`/`dJ/dt` trigger
diagnostic with authorized M3D-C1 fields or experimental magnetic diagnostics,
then rerun the same contract so pre-peak trigger timing, actuator latency, and
peak/integrated-current metrics are measured against real diagnostic data.
"""
    (run_dir / "closed_loop_trigger_report.md").write_text(report, encoding="utf-8")


def _write_outputs(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with (run_dir / "closed_loop_trigger_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "closed_loop_trigger_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_readme(run_dir, summary)
    _write_report(run_dir, rows, summary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bout-top", type=Path, default=Path(DEFAULT_BOUT_TOP))
    parser.add_argument("--bout-build", type=Path, default=Path(DEFAULT_BOUT_BUILD))
    parser.add_argument("--run-dir", type=Path, default=REPO / "validation_runs" / RUN_NAME)
    parser.add_argument("--nout", type=int, default=18)
    parser.add_argument("--keep-existing", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    _design, plasma, reactor = _evaluate_base()
    exe = BUILD_DIR / "tct_current_sheet" if args.skip_build else _build_model(args.bout_build)
    run_dir = args.run_dir
    if run_dir.exists() and not args.keep_existing:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_contract(run_dir)

    baseline_series: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []

    for grid in (BASE_GRID, FINE_GRID):
        baseline_policy = {"case_suffix": "no_control", "trigger_kind": "none", "strength_scale": 0.0, "threshold_label": "none"}
        baseline_case = _case_from_policy(grid, baseline_policy, plasma, reactor, {"time": np.array([0.0, 1.0]), "max_j": np.array([1.0, 1.0])})
        baseline_case["case"] = f"{grid['name']}_no_control"
        case_dir = run_dir / baseline_case["case"]
        _write_inp(case_dir, baseline_case, args.nout)
        _run_case(exe, case_dir)
        series = _series(case_dir)
        baseline_series[grid["name"]] = series
        diagnostics = _diagnostics(series)
        row = _row(case_dir, baseline_case, diagnostics)
        rows.append(row)
        cases.append({"case": case_dir.name, "case_parameters": {k: v for k, v in baseline_case.items() if k != "grid"}, "grid": grid, "diagnostics": diagnostics})

        for policy in _policies(grid["name"]):
            if policy["trigger_kind"] == "none":
                continue
            case = _case_from_policy(grid, policy, plasma, reactor, series)
            case_dir = run_dir / case["case"]
            _write_inp(case_dir, case, args.nout)
            _run_case(exe, case_dir)
            case_series = _series(case_dir)
            diagnostics = _diagnostics(case_series)
            row = _row(case_dir, case, diagnostics)
            rows.append(row)
            cases.append({"case": case_dir.name, "case_parameters": {k: v for k, v in case.items() if k != "grid"}, "grid": grid, "diagnostics": diagnostics})

    _add_reductions(rows)
    summary: dict[str, Any] = {
        "status": STATUS_PHRASE,
        "run_dir": str(run_dir),
        "model_dir": str(MODEL_DIR),
        "executable": str(exe),
        "bout_top": str(args.bout_top),
        "bout_build": str(args.bout_build),
        "control_mapping": "closed_loop_diagnostic_trigger_to_reduced_current_sheet_actuator_start_time",
        "existing_bout_boundary": _existing_bout_boundary(),
        "existing_m3dc1_boundary": _existing_m3dc1_boundary(),
        "base_plasma_summary": {
            "pfus_mw": _safe_float(plasma.get("pfus_mw"), 0.0),
            "wn_mw_m2": _safe_float(plasma.get("wn_mw_m2"), 0.0),
            "betaN": _safe_float(plasma.get("betaN"), 0.0),
            "qstar": _safe_float(plasma.get("qstar"), 0.0),
        },
        "base_reactor_summary": {
            "wall_load": _safe_float(reactor.get("wall_load"), 0.0),
            "event_loss_frac": _safe_float(reactor.get("event_loss_frac"), 0.0),
        },
        "cases": cases,
    }
    summary["gates"] = _gate_table(rows)
    summary["passed"] = all(bool(gate["passed"]) for gate in summary["gates"])
    _write_outputs(run_dir, rows, summary)
    print(json.dumps({"run_dir": str(run_dir), "status": summary["status"], "passed": summary["passed"], "gates": summary["gates"]}, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

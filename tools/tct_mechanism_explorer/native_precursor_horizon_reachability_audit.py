#!/usr/bin/env python3
"""Cost/reachability audit for the physically calibrated native precursor window.

This does not alter M3D-C1 physics or claim controller efficacy. It answers the
narrow question exposed by job 015: how far the current native horizon would
have to extend before the measured Mirnov/toroidal precursor can causally fit,
and what that implies for runtime at the demonstrated native cadence.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_precursor_horizon_reachability"
PARENT = REPO / "agent_pipeline/results/20260917-015-native-live-normalization-precursor-controller.json"
RUNTIME_REF = REPO / "agent_pipeline/results/20260914-008-h006-delta0295-confirmation.json"

CURRENT_HORIZON = 0.30
CURRENT_DT = 0.01
CURRENT_START = 0.05
N_ARMS = 6  # zero-equivalence pair plus required controller/falsification matrix is at least this order.


def dump(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "native_precursor_horizon_reachability_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


def main() -> int:
    parent_receipt = json.loads(PARENT.read_text())
    parent = parent_receipt["summary"]
    if parent.get("classification") != "M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_TIMESCALE_WINDOW_MISMATCH":
        raise RuntimeError("parent classification changed; refuse stale reachability audit")
    if parent.get("pipeline_failure") is not False:
        raise RuntimeError("parent was not a scientific prerequisite result")

    scale = float(parent["physical_time_calibration"]["physical_ms_per_solver_time_unit"])
    lead_ms = float(parent["precursor_lead_ms"])
    required_response_ms = float(parent["supervisor_decision"]["required_lead_ms"])
    if not all(math.isfinite(x) and x > 0 for x in (scale, lead_ms, required_response_ms)):
        raise RuntimeError("invalid calibrated timing inputs")

    lead_native = lead_ms / scale
    response_native = required_response_ms / scale
    minimum_event_native = CURRENT_START + lead_native
    minimum_event_ms = minimum_event_native * scale
    minimum_boost_native = CURRENT_START + response_native

    runtime_ref = json.loads(RUNTIME_REF.read_text())
    baseline_exec = runtime_ref["summary"]["baseline"]["execution"]
    baseline_seconds = float(baseline_exec["elapsed_seconds"])
    ref_horizon = float(runtime_ref["summary"]["audit"]["horizon"])
    ref_dt = float(runtime_ref["summary"]["audit"]["dt"])
    if ref_horizon != CURRENT_HORIZON or ref_dt != CURRENT_DT:
        raise RuntimeError("runtime reference no longer matches the current native cadence")

    horizon_multiplier = minimum_event_native / CURRENT_HORIZON
    minimum_steps = math.ceil(minimum_event_native / CURRENT_DT)
    projected_seconds_per_arm_linear = baseline_seconds * horizon_multiplier
    projected_days_per_arm_linear = projected_seconds_per_arm_linear / 86400.0
    projected_days_six_arm_linear = projected_days_per_arm_linear * N_ARMS

    # This is deliberately a planning bound, not a solver-performance promise.
    # The extrapolation assumes approximately linear cost with step count and
    # therefore must be validated by a shorter scaling benchmark before any
    # long native run is authorized.
    practical_direct_extension = projected_days_per_arm_linear <= 1.0
    classification = (
        "M3DC1_TCT_NATIVE_PRECURSOR_HORIZON_DIRECT_EXTENSION_PRACTICAL"
        if practical_direct_extension
        else "M3DC1_TCT_NATIVE_PRECURSOR_HORIZON_DIRECT_EXTENSION_IMPRACTICAL"
    )

    dump({
        "classification": classification,
        "pipeline_failure": False,
        "scientific_interpretation_allowed": True,
        "claim_boundary": "Normalized native M3D-C1 planning/reachability only; no controller-efficacy, reactor-scale, or experimental stabilization claim.",
        "parent_job_id": parent_receipt["job_id"],
        "parent_classification": parent["classification"],
        "zero_equivalence_status": "NOT_EVALUATED_IN_PARENT_TIMESCALE_PREREQUISITE_EXIT",
        "frozen_gates": parent["frozen_gates"],
        "precursor_authority": parent["precursor_authority"],
        "calibrated_timing": {
            "physical_ms_per_solver_time_unit": scale,
            "precursor_lead_ms": lead_ms,
            "precursor_lead_native_units": lead_native,
            "required_response_ms": required_response_ms,
            "required_response_native_units": response_native,
            "current_control_window_start_native": CURRENT_START,
            "minimum_causal_event_time_native": minimum_event_native,
            "minimum_causal_event_time_ms_from_native_origin": minimum_event_ms,
            "earliest_boost_after_window_start_native": minimum_boost_native,
        },
        "current_native_cadence": {
            "horizon": CURRENT_HORIZON,
            "dt": CURRENT_DT,
            "steps": round(CURRENT_HORIZON / CURRENT_DT),
        },
        "reachability": {
            "minimum_steps_at_current_dt": minimum_steps,
            "horizon_multiplier_vs_0p30": horizon_multiplier,
            "direct_extension_practical_under_one_day_per_arm": practical_direct_extension,
        },
        "runtime_reference": {
            "job_id": runtime_ref["job_id"],
            "baseline_elapsed_seconds": baseline_seconds,
            "reference_horizon": ref_horizon,
            "reference_dt": ref_dt,
            "projection_model": "linear_in_native_step_count_planning_extrapolation",
            "projected_days_per_arm_linear": projected_days_per_arm_linear,
            "projected_days_for_six_arms_linear": projected_days_six_arm_linear,
            "warning": "Projection is a planning estimate only; validate scaling before authorizing a long native run.",
        },
        "decision": (
            "Do not launch the full physically timed controller matrix by brute-force horizon extension. "
            "First establish a physically relevant native event/window or a validated time-scaling/restart strategy; "
            "retain Mirnov/toroidal precursor authority and fail-closed NO ACTION meanwhile."
            if not practical_direct_extension else
            "A bounded horizon-extension benchmark is computationally plausible, but zero-equivalence and frozen gates remain mandatory before efficacy interpretation."
        ),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

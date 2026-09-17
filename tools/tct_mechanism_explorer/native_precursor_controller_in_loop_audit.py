#!/usr/bin/env python3
"""Native M3D-C1 TCT precursor-controller-in-loop audit.

This is intentionally fail-closed. It will not translate FAIR-MAST milliseconds
into normalized M3D-C1 time unless an explicit reviewed calibration is present.
When calibrated, it runs a common five-arm matrix: no control, standing bias,
precursor-conditioned bounded boost, oracle-conditioned boost, and late/wrong-
sign falsification controls. Frozen width/Jpk gates remain unchanged.
"""
from __future__ import annotations

import json, os
from pathlib import Path

import native_two_profile_handoff_audit as base
import native_two_window_sustained_refinement_audit as native
from tct_pacman_supervisor import DiagnosticFrame, ActuatorState, decide

REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_precursor_controller_in_loop"
CAL = REPO / "validation_inputs/m3dc1_physical_time_calibration.json"
BUDGET = REPO / "validation_runs/fair_mast_biased_actuator_response_budget_default/fair_mast_biased_actuator_response_budget_summary.json"
PRECURSOR = REPO / "validation_runs/fair_mast_multidiagnostic_precursor_fusion_default/fair_mast_multidiagnostic_precursor_fusion_summary.json"

WIDTH_GATE = 0.020
JPK_GATE = 0.10
EQ_TOL = 1e-12
BIAS_AMP = -0.015
BOOST_AMP = -0.01520
BOOST_PROFILE = dict(second_width=0.145, second_shoulder_width=0.40, second_delta=0.300)


def dump(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "precursor_controller_in_loop_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def calibration() -> dict | None:
    if not CAL.exists():
        return None
    c = json.loads(CAL.read_text())
    required = {"physical_ms_per_solver_time_unit", "provenance", "reviewed", "applies_to_native_deck"}
    if not required <= c.keys() or c["reviewed"] is not True or c["applies_to_native_deck"] is not True:
        return None
    scale = float(c["physical_ms_per_solver_time_unit"])
    return c if scale > 0 else None


def summarize(label, rows, baseline):
    s = native.summarize_case(label=label, second_start=0.0, second_amp=0.0,
                              rows=rows, baseline_rows=baseline)
    return {k: s.get(k) for k in (
        "case", "width_gate_pass_any", "current_gate_pass_every_step_t0p10_to_t0p30",
        "continuous_positive_width_t0p10_to_t0p30", "sustained_safe_authority",
        "peak_width_gain_pct", "minimum_width_gain_pct", "worst_Jpk_change_pct",
        "final_width_gain_pct", "final_Jpk_change_pct")}


def run(label, amp1, t1off, amp2=0.0, t2on=0.30, t2off=0.30, sign=1.0):
    d, rows, status = base.run_case(label, source=native.CURRENT_SOURCE,
        amp1=amp1 * sign, t1_on=base.START, t1_off=t1off,
        amp2=amp2 * sign, t2_on=t2on, t2_off=t2off, **BOOST_PROFILE)
    if status["return_code"] != 0:
        raise RuntimeError(f"{label} native run failed rc={status['return_code']}")
    return rows


def main() -> int:
    c = calibration()
    claim = "Normalized native M3D-C1 only; no reactor-scale or experimental stabilization claim."
    if c is None:
        dump({
            "classification": "M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_PHYSICAL_TIME_CALIBRATION_REQUIRED",
            "pipeline_failure": False,
            "scientific_interpretation_allowed": False,
            "claim_boundary": claim,
            "frozen_gates": {"width_gain_pct_gt": WIDTH_GATE, "Jpk_change_pct_le": JPK_GATE},
            "reason": "Fail-closed prerequisite: no reviewed physical-ms to native-solver-time calibration exists for this deck. No arbitrary conversion was performed.",
            "pacman_adaptation": "diagnostic validation -> precursor proposal -> latency/safety arbiter -> bounded boost or NO ACTION",
            "precursor_authority": "Mirnov/toroidal; reduced-model proxies are not substituted",
        })
        return 0

    scale = float(c["physical_ms_per_solver_time_unit"])
    budget = json.loads(BUDGET.read_text())
    fast = next(x for x in budget["scenario_rows"] if x["scenario"] == "prebiased_current_sheet_fast")
    lead_ms = float(budget["lead_distribution_ms"]["median"])
    actuator = ActuatorState(True, True, True, float(fast["total_response_ms"]), 0.25)
    frame = DiagnosticFrame(True, "mirnov_toroidal", 1.0, lead_ms, True)
    decision = decide(frame, actuator)

    # Convert only after reviewed calibration has passed.
    event_time = 0.14  # native characterization's repeatable Jpk excursion; not claimed as an experimental ELM time
    lead_native = lead_ms / scale
    response_native = decision.required_lead_ms / scale
    trigger = event_time - lead_native
    boost_on = trigger + response_native
    boost_on = max(base.START, boost_on)
    if not decision.bounded_boost or boost_on >= event_time:
        controller_boost = False
    else:
        controller_boost = True

    base.OUT = OUT
    native.OUT = OUT
    base.RUN_ROOT = Path("/tmp/m3dc1_tct_native_precursor_controller_in_loop_runs")
    native.RUN_ROOT = base.RUN_ROOT
    base.pta.install_operator(); base.install_two_profile_operator(); base.pta.build()

    # Common baseline and mandatory zero-equivalence.
    _, baseline, bs = base.run_case("no_control", source=0, amp1=0.0, t1_on=0.0, t1_off=0.30,
        amp2=0.0, t2_on=0.30, t2_off=0.30, **BOOST_PROFILE)
    _, zero, zs = base.run_case("source4_zero", source=native.CURRENT_SOURCE, amp1=0.0,
        t1_on=base.START, t1_off=0.30, amp2=0.0, t2_on=0.30, t2_off=0.30, **BOOST_PROFILE)
    zero_eq = native.zero_equivalence(baseline, zero)
    if not zero_eq["pass"]:
        dump({"classification":"M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_ZERO_EQUIVALENCE_FAILED",
              "zero_equivalence":zero_eq,"claim_boundary":claim}); return 0

    bias = run("standing_bias_only", BIAS_AMP, 0.30)
    if controller_boost:
        ctl = run("precursor_conditioned", BIAS_AMP, boost_on, BOOST_AMP, boost_on, 0.30)
    else:
        ctl = bias
    oracle_on = max(base.START, event_time - response_native)
    oracle = run("oracle_conditioned", BIAS_AMP, oracle_on, BOOST_AMP, oracle_on, 0.30)
    late = run("late_negative_control", BIAS_AMP, event_time, BOOST_AMP, event_time, 0.30)
    wrong = run("wrong_sign_negative_control", BIAS_AMP, boost_on if controller_boost else oracle_on,
                BOOST_AMP, boost_on if controller_boost else oracle_on, 0.30, sign=-1.0)

    arms = {"standing_bias_only":summarize("standing_bias_only",bias,baseline),
            "precursor_conditioned":summarize("precursor_conditioned",ctl,baseline),
            "oracle_conditioned":summarize("oracle_conditioned",oracle,baseline),
            "late_negative_control":summarize("late_negative_control",late,baseline),
            "wrong_sign_negative_control":summarize("wrong_sign_negative_control",wrong,baseline)}
    ctl_s = arms["precursor_conditioned"]
    passed = bool(ctl_s["width_gate_pass_any"] and ctl_s["current_gate_pass_every_step_t0p10_to_t0p30"])
    classification = ("M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_FROZEN_GATES_PASS" if passed else
                      "M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_FROZEN_GATES_NOT_MET")
    dump({"classification":classification,"pipeline_failure":False,"claim_boundary":claim,
          "physical_time_calibration":c,"precursor_lead_ms":lead_ms,"supervisor_decision":decision.as_dict(),
          "derived_native_times":{"event_characterization_time":event_time,"trigger_time":trigger,
                                  "boost_on":boost_on,"oracle_on":oracle_on},
          "zero_equivalence":zero_eq,"frozen_gates":{"width_gain_pct_gt":WIDTH_GATE,"Jpk_change_pct_le":JPK_GATE},
          "arms":arms,"pacman_adaptation":"modular predictor/controller proposals with fail-closed latency/safety arbitration; Mirnov/toroidal retained as TCT precursor"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

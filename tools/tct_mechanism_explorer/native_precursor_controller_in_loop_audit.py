#!/usr/bin/env python3
"""Native M3D-C1 TCT precursor-controller-in-loop audit.

This runner keeps the established TCT control architecture intact:
standing preventative bias -> Mirnov/toroidal precursor -> response-time/safety
arbiter -> bounded boost or NO ACTION.

Physical milliseconds are converted to native M3D-C1 time only after the
baseline deck normalization is verified against a reviewed calibration artifact.
If the experimental precursor/actuator timing does not fit inside the native
simulation window, the audit fails closed instead of clipping the trigger to an
arbitrary native time.
"""
from __future__ import annotations

import json
import math
import re
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

PROTON_MASS_CGS_G = 1.6726219e-24
CAL_REL_TOL = 1e-10
NORMALIZATION_KEYS = ("b0_norm", "n0_norm", "l0_norm", "ion_mass")


def dump(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "precursor_controller_in_loop_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


def _input_scalar(text: str, key: str) -> float:
    match = re.search(
        rf"(?im)^\s*{re.escape(key)}\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?)",
        text,
    )
    if not match:
        raise ValueError(f"missing {key} in native baseline C1input")
    return float(match.group(1).replace("D", "e").replace("d", "e"))


def derive_alfven_time_calibration(deck: Path) -> dict:
    """Derive native M3D-C1 time normalization from the actual run deck.

    M3D-C1 normalization:
      v0 = b0 / sqrt(4*pi*ion_mass*mp*n0) [cm/s]
      t0 = l0 / v0                       [s/native time unit]
    """
    text = deck.read_text()
    vals = {key: _input_scalar(text, key) for key in NORMALIZATION_KEYS}
    if any(not math.isfinite(v) or v <= 0.0 for v in vals.values()):
        raise ValueError(f"invalid M3D-C1 normalization values: {vals}")
    mi_g = vals["ion_mass"] * PROTON_MASS_CGS_G
    v0_cm_s = vals["b0_norm"] / math.sqrt(4.0 * math.pi * mi_g * vals["n0_norm"])
    t0_s = vals["l0_norm"] / v0_cm_s
    return {
        "normalization": {
            "b0_norm_G": vals["b0_norm"],
            "n0_norm_cm3": vals["n0_norm"],
            "l0_norm_cm": vals["l0_norm"],
            "ion_mass_mp": vals["ion_mass"],
        },
        "alfven_velocity_cm_s": v0_cm_s,
        "physical_ms_per_solver_time_unit": 1000.0 * t0_s,
        "deck_path": str(deck),
    }


def _close(a: float, b: float, rel_tol: float = CAL_REL_TOL) -> bool:
    return math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=0.0)


def calibration() -> tuple[dict | None, str | None]:
    """Load reviewed calibration and verify it against the actual baseline deck."""
    if not CAL.exists():
        return None, f"calibration artifact missing: {CAL}"
    try:
        c = json.loads(CAL.read_text())
    except Exception as exc:
        return None, f"cannot read calibration artifact: {exc}"

    required = {
        "physical_ms_per_solver_time_unit",
        "normalization",
        "provenance",
        "reviewed",
        "applies_to_native_deck",
    }
    if not required <= c.keys():
        return None, f"calibration artifact missing required keys: {sorted(required - c.keys())}"
    if c["reviewed"] is not True or c["applies_to_native_deck"] is not True:
        return None, "calibration artifact is not marked reviewed/applicable"

    deck = native.BASE / "C1input"
    if not deck.exists():
        return None, f"native baseline deck missing: {deck}"
    try:
        derived = derive_alfven_time_calibration(deck)
    except Exception as exc:
        return None, f"cannot derive calibration from native baseline deck: {exc}"

    expected = c["normalization"]
    actual = derived["normalization"]
    for key in ("b0_norm_G", "n0_norm_cm3", "l0_norm_cm", "ion_mass_mp"):
        if key not in expected or not _close(expected[key], actual[key]):
            return None, f"native deck normalization mismatch for {key}: expected={expected.get(key)!r}, actual={actual[key]!r}"

    stated_scale = float(c["physical_ms_per_solver_time_unit"])
    derived_scale = float(derived["physical_ms_per_solver_time_unit"])
    if stated_scale <= 0.0 or not _close(stated_scale, derived_scale):
        return None, (
            "physical time scale mismatch: "
            f"artifact={stated_scale:.17g}, derived={derived_scale:.17g} ms/native-unit"
        )

    verified = dict(c)
    verified["runtime_verification"] = {
        "pass": True,
        "deck_path": str(deck),
        "derived_physical_ms_per_solver_time_unit": derived_scale,
        "derived_alfven_velocity_cm_s": derived["alfven_velocity_cm_s"],
        "relative_tolerance": CAL_REL_TOL,
    }
    return verified, None


def summarize(label, rows, baseline):
    s = native.summarize_case(
        label=label,
        second_start=0.0,
        second_amp=0.0,
        rows=rows,
        baseline_rows=baseline,
    )
    return {
        k: s.get(k)
        for k in (
            "case",
            "width_gate_pass_any",
            "current_gate_pass_every_step_t0p10_to_t0p30",
            "continuous_positive_width_t0p10_to_t0p30",
            "sustained_safe_authority",
            "peak_width_gain_pct",
            "minimum_width_gain_pct",
            "worst_Jpk_change_pct",
            "final_width_gain_pct",
            "final_Jpk_change_pct",
        )
    }


def run(label, amp1, t1off, amp2=0.0, t2on=0.30, t2off=0.30, sign=1.0):
    _, rows, status = base.run_case(
        label,
        source=native.CURRENT_SOURCE,
        amp1=amp1 * sign,
        t1_on=base.START,
        t1_off=t1off,
        amp2=amp2 * sign,
        t2_on=t2on,
        t2_off=t2off,
        **BOOST_PROFILE,
    )
    if status["return_code"] != 0:
        raise RuntimeError(f"{label} native run failed rc={status['return_code']}")
    return rows


def main() -> int:
    c, calibration_error = calibration()
    claim = "Normalized native M3D-C1 only; no reactor-scale or experimental stabilization claim."
    if c is None:
        dump(
            {
                "classification": "M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_PHYSICAL_TIME_CALIBRATION_REQUIRED",
                "pipeline_failure": False,
                "scientific_interpretation_allowed": False,
                "claim_boundary": claim,
                "frozen_gates": {
                    "width_gain_pct_gt": WIDTH_GATE,
                    "Jpk_change_pct_le": JPK_GATE,
                },
                "reason": f"Fail-closed prerequisite: {calibration_error}",
                "physical_time_calibration": None,
                "pacman_adaptation": "diagnostic validation -> precursor proposal -> latency/safety arbiter -> bounded boost or NO ACTION",
                "precursor_authority": "Mirnov/toroidal; reduced-model proxies are not substituted",
            }
        )
        return 0

    scale = float(c["physical_ms_per_solver_time_unit"])
    budget = json.loads(BUDGET.read_text())
    fast = next(
        x for x in budget["scenario_rows"] if x["scenario"] == "prebiased_current_sheet_fast"
    )
    lead_ms = float(budget["lead_distribution_ms"]["median"])
    actuator = ActuatorState(
        True, True, True, float(fast["total_response_ms"]), 0.25
    )
    frame = DiagnosticFrame(True, "mirnov_toroidal", 1.0, lead_ms, True)
    decision = decide(frame, actuator)

    # The native characterization has a repeatable Jpk excursion near t=0.14.
    # It is NOT an experimental ELM timestamp. Physical timing is used only to
    # determine whether a causal precursor-conditioned command can exist inside
    # this native window.
    event_time = 0.14
    lead_native = lead_ms / scale
    response_native = decision.required_lead_ms / scale
    trigger = event_time - lead_native
    boost_on = trigger + response_native
    event_physical_ms = event_time * scale
    window_start_physical_ms = base.START * scale
    pre_event_window_ms = max(0.0, (event_time - base.START) * scale)
    timing = {
        "event_characterization_time": event_time,
        "event_characterization_physical_ms_from_native_origin": event_physical_ms,
        "native_control_window_start": base.START,
        "native_control_window_start_physical_ms_from_native_origin": window_start_physical_ms,
        "available_pre_event_native_window_ms": pre_event_window_ms,
        "precursor_lead_native_units": lead_native,
        "required_response_native_units": response_native,
        "trigger_time": trigger,
        "boost_on": boost_on,
    }

    # Do not turn a many-millisecond experimental lead into an arbitrary t=0.05
    # command by clipping it to the start of a sub-microsecond native window.
    # Such a run would be a static prebias experiment, not controller-in-loop
    # evidence. Report the scale mismatch and keep the boost fail-closed.
    timing_window_compatible = (
        decision.bounded_boost
        and trigger >= base.START
        and boost_on >= base.START
        and boost_on < event_time
    )
    if not timing_window_compatible:
        dump(
            {
                "classification": "M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_TIMESCALE_WINDOW_MISMATCH",
                "pipeline_failure": False,
                "scientific_interpretation_allowed": True,
                "claim_boundary": claim,
                "reason": (
                    "Reviewed M3D-C1 Alfvén-time calibration is valid, but the measured "
                    "Mirnov/toroidal precursor lead and bounded-boost response budget occur "
                    "far outside the current native characterization window. No trigger time "
                    "was clipped or invented; bounded boost remains NO ACTION."
                ),
                "physical_time_calibration": c,
                "precursor_lead_ms": lead_ms,
                "supervisor_decision": decision.as_dict(),
                "derived_native_times": timing,
                "timescale_compatibility": {
                    "pass": False,
                    "requires_trigger_at_or_after_native_time": base.START,
                    "requires_boost_before_native_event_time": event_time,
                    "controller_boost_executed": False,
                },
                "zero_equivalence": None,
                "arms": None,
                "frozen_gates": {
                    "width_gain_pct_gt": WIDTH_GATE,
                    "Jpk_change_pct_le": JPK_GATE,
                },
                "precursor_authority": "Mirnov/toroidal; reduced-model proxies are not substituted",
                "pacman_adaptation": "modular predictor/controller proposals with fail-closed latency/safety arbitration; Mirnov/toroidal retained as TCT precursor",
            }
        )
        return 0

    base.OUT = OUT
    native.OUT = OUT
    base.RUN_ROOT = Path("/tmp/m3dc1_tct_native_precursor_controller_in_loop_runs")
    native.RUN_ROOT = base.RUN_ROOT
    base.pta.install_operator()
    base.install_two_profile_operator()
    base.pta.build()

    # Common baseline and mandatory zero-equivalence.
    _, baseline, _ = base.run_case(
        "no_control",
        source=0,
        amp1=0.0,
        t1_on=0.0,
        t1_off=0.30,
        amp2=0.0,
        t2_on=0.30,
        t2_off=0.30,
        **BOOST_PROFILE,
    )
    _, zero, _ = base.run_case(
        "source4_zero",
        source=native.CURRENT_SOURCE,
        amp1=0.0,
        t1_on=base.START,
        t1_off=0.30,
        amp2=0.0,
        t2_on=0.30,
        t2_off=0.30,
        **BOOST_PROFILE,
    )
    zero_eq = native.zero_equivalence(baseline, zero)
    if not zero_eq["pass"]:
        dump(
            {
                "classification": "M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_ZERO_EQUIVALENCE_FAILED",
                "zero_equivalence": zero_eq,
                "claim_boundary": claim,
            }
        )
        return 0

    bias = run("standing_bias_only", BIAS_AMP, 0.30)
    ctl = run(
        "precursor_conditioned",
        BIAS_AMP,
        boost_on,
        BOOST_AMP,
        boost_on,
        0.30,
    )
    oracle_on = event_time - response_native
    oracle = run("oracle_conditioned", BIAS_AMP, oracle_on, BOOST_AMP, oracle_on, 0.30)
    late = run("late_negative_control", BIAS_AMP, event_time, BOOST_AMP, event_time, 0.30)
    wrong = run(
        "wrong_sign_negative_control",
        BIAS_AMP,
        boost_on,
        BOOST_AMP,
        boost_on,
        0.30,
        sign=-1.0,
    )

    arms = {
        "standing_bias_only": summarize("standing_bias_only", bias, baseline),
        "precursor_conditioned": summarize("precursor_conditioned", ctl, baseline),
        "oracle_conditioned": summarize("oracle_conditioned", oracle, baseline),
        "late_negative_control": summarize("late_negative_control", late, baseline),
        "wrong_sign_negative_control": summarize("wrong_sign_negative_control", wrong, baseline),
    }
    ctl_s = arms["precursor_conditioned"]
    passed = bool(
        ctl_s["width_gate_pass_any"]
        and ctl_s["current_gate_pass_every_step_t0p10_to_t0p30"]
    )
    classification = (
        "M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_FROZEN_GATES_PASS"
        if passed
        else "M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_FROZEN_GATES_NOT_MET"
    )
    dump(
        {
            "classification": classification,
            "pipeline_failure": False,
            "claim_boundary": claim,
            "physical_time_calibration": c,
            "precursor_lead_ms": lead_ms,
            "supervisor_decision": decision.as_dict(),
            "derived_native_times": {**timing, "oracle_on": oracle_on},
            "zero_equivalence": zero_eq,
            "frozen_gates": {
                "width_gain_pct_gt": WIDTH_GATE,
                "Jpk_change_pct_le": JPK_GATE,
            },
            "arms": arms,
            "pacman_adaptation": "modular predictor/controller proposals with fail-closed latency/safety arbitration; Mirnov/toroidal retained as TCT precursor",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

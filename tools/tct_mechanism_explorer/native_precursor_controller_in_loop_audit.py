#!/usr/bin/env python3
"""Native M3D-C1 TCT precursor-controller-in-loop audit.

This runner keeps the established TCT control architecture intact:
standing preventative bias -> Mirnov/toroidal precursor -> response-time/safety
arbiter -> bounded boost or NO ACTION.

Physical milliseconds are converted to native M3D-C1 time from the live
baseline normalization using a reviewed M3D-C1 Alfvén-time formula.
C1.h5 root attributes are authoritative for runtime normalization; C1input is
used only as an optional consistency cross-check because restart/baseline decks
may omit normalization values already persisted in HDF5.

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
ARTIFACT_KEYS = {
    "b0_norm": "b0_norm_G",
    "n0_norm": "n0_norm_cm3",
    "l0_norm": "l0_norm_cm",
    "ion_mass": "ion_mass_mp",
}


def dump(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "precursor_controller_in_loop_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


def _input_scalar_optional(text: str, key: str) -> float | None:
    match = re.search(
        rf"(?im)^\s*{re.escape(key)}\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?)",
        text,
    )
    if not match:
        return None
    return float(match.group(1).replace("D", "e").replace("d", "e"))


def _as_float(value, key: str) -> float:
    """Convert a scalar HDF5 attribute to float without assuming numpy shape."""
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"HDF5 attribute {key} is not scalar numeric: {value!r}") from exc
    if not math.isfinite(out) or out <= 0.0:
        raise ValueError(f"HDF5 attribute {key} must be finite and positive: {out!r}")
    return out


def _h5_normalization(h5_path: Path) -> dict[str, float]:
    """Read authoritative runtime normalization from the native baseline HDF5."""
    try:
        import h5py
    except Exception as exc:
        raise RuntimeError(f"h5py unavailable for runtime normalization verification: {exc}") from exc

    if not h5_path.exists():
        raise FileNotFoundError(h5_path)

    with h5py.File(h5_path, "r") as h5:
        missing = [key for key in NORMALIZATION_KEYS if key not in h5.attrs]
        if missing:
            available = sorted(str(k) for k in h5.attrs.keys())
            raise ValueError(
                f"missing HDF5 root normalization attributes {missing}; "
                f"available root attributes={available}"
            )
        return {key: _as_float(h5.attrs[key], key) for key in NORMALIZATION_KEYS}


def _derive_from_values(vals: dict[str, float], provenance: dict) -> dict:
    if any(not math.isfinite(v) or v <= 0.0 for v in vals.values()):
        raise ValueError(f"invalid M3D-C1 normalization values: {vals}")
    mi_g = vals["ion_mass"] * PROTON_MASS_CGS_G
    v0_cm_s = vals["b0_norm"] / math.sqrt(
        4.0 * math.pi * mi_g * vals["n0_norm"]
    )
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
        "runtime_source": provenance,
    }


def derive_alfven_time_calibration(baseline_dir: Path) -> dict:
    """Derive native time normalization from live C1.h5, cross-checking C1input.

    M3D-C1 normalization:
      v0 = b0 / sqrt(4*pi*ion_mass*mp*n0) [cm/s]
      t0 = l0 / v0                       [s/native time unit]

    The live HDF5 is authoritative because a copied/restart C1input can omit
    normalization entries after the values have been persisted in C1.h5.
    """
    h5_path = baseline_dir / "C1.h5"
    vals = _h5_normalization(h5_path)

    input_path = baseline_dir / "C1input"
    input_checks: dict[str, dict] = {}
    if input_path.exists():
        text = input_path.read_text(errors="replace")
        for key in NORMALIZATION_KEYS:
            input_value = _input_scalar_optional(text, key)
            if input_value is None:
                input_checks[key] = {"present": False, "match_h5": None}
                continue
            match = math.isclose(
                input_value, vals[key], rel_tol=CAL_REL_TOL, abs_tol=0.0
            )
            input_checks[key] = {
                "present": True,
                "value": input_value,
                "h5_value": vals[key],
                "match_h5": match,
            }
            if not match:
                raise ValueError(
                    f"C1input/HDF5 normalization mismatch for {key}: "
                    f"input={input_value!r}, h5={vals[key]!r}"
                )

    return _derive_from_values(
        vals,
        {
            "authoritative": "C1.h5 root attributes",
            "h5_path": str(h5_path),
            "c1input_path": str(input_path),
            "c1input_cross_checks": input_checks,
        },
    )


def _close(a: float, b: float, rel_tol: float = CAL_REL_TOL) -> bool:
    return math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=0.0)


def calibration() -> tuple[dict | None, str | None]:
    """Verify the reviewed formula, then derive scale from the live baseline.

    The calibration artifact reviews the conversion formula and preserves the
    committed DIII-D template normalization as a reference point.  Run-specific
    normalization comes from the actual C1.h5 root attributes, which M3D-C1's
    reader defines as the authoritative b0_norm/n0_norm/l0_norm/ion_mass values.
    A reference-template divergence is recorded, not treated as a physics error.
    An explicit C1input/HDF5 disagreement still fails inside
    derive_alfven_time_calibration().
    """
    if not CAL.exists():
        return None, f"calibration artifact missing: {CAL}"
    try:
        c = json.loads(CAL.read_text())
    except Exception as exc:
        return None, f"cannot read calibration artifact: {exc}"

    required = {
        "formula",
        "provenance",
        "reviewed",
        "applies_to_native_deck",
        "runtime_normalization_authority",
        "runtime_verification_required",
    }
    if not required <= c.keys():
        return None, f"calibration artifact missing required keys: {sorted(required - c.keys())}"
    if c["reviewed"] is not True or c["applies_to_native_deck"] is not True:
        return None, "calibration artifact is not marked reviewed/applicable"
    if c["runtime_verification_required"] is not True:
        return None, "calibration artifact does not require runtime verification"
    if c["runtime_normalization_authority"] != "live baseline C1.h5 root attributes":
        return None, (
            "unsupported runtime normalization authority: "
            f"{c['runtime_normalization_authority']!r}"
        )

    formula = c["formula"]
    if formula.get("id") != "m3dc1_alfven_time_cgs":
        return None, f"unsupported calibration formula id: {formula.get('id')!r}"
    artifact_mp = float(formula.get("proton_mass_g", float("nan")))
    if not math.isfinite(artifact_mp) or not _close(artifact_mp, PROTON_MASS_CGS_G):
        return None, (
            "calibration proton-mass constant mismatch: "
            f"artifact={artifact_mp!r}, code={PROTON_MASS_CGS_G!r}"
        )

    if not native.BASE.exists():
        return None, f"native baseline directory missing: {native.BASE}"
    try:
        derived = derive_alfven_time_calibration(native.BASE)
    except Exception as exc:
        return None, f"cannot derive calibration from live native baseline: {exc}"

    actual = derived["normalization"]
    derived_scale = float(derived["physical_ms_per_solver_time_unit"])
    if not math.isfinite(derived_scale) or derived_scale <= 0.0:
        return None, f"invalid live-derived physical time scale: {derived_scale!r}"

    reference = c.get("reference_normalization", c.get("normalization", {}))
    reference_comparison = {}
    for key in ("b0_norm_G", "n0_norm_cm3", "l0_norm_cm", "ion_mass_mp"):
        ref_value = reference.get(key)
        if ref_value is None:
            reference_comparison[key] = {
                "reference_present": False,
                "actual": actual[key],
                "match": None,
            }
        else:
            reference_comparison[key] = {
                "reference_present": True,
                "reference": float(ref_value),
                "actual": actual[key],
                "match": _close(float(ref_value), actual[key]),
            }

    reference_scale = c.get(
        "reference_physical_ms_per_solver_time_unit",
        c.get("physical_ms_per_solver_time_unit"),
    )
    if reference_scale is not None:
        reference_scale = float(reference_scale)

    verified = dict(c)
    # Downstream timing always consumes the live-run scale and normalization.
    verified["physical_ms_per_solver_time_unit"] = derived_scale
    verified["normalization"] = actual
    verified["runtime_verification"] = {
        "pass": True,
        "source": derived["runtime_source"],
        "derived_normalization": actual,
        "derived_physical_ms_per_solver_time_unit": derived_scale,
        "derived_alfven_velocity_cm_s": derived["alfven_velocity_cm_s"],
        "relative_tolerance": CAL_REL_TOL,
        "reference_template_is_hard_gate": False,
        "reference_normalization_comparison": reference_comparison,
        "reference_physical_ms_per_solver_time_unit": reference_scale,
        "reference_scale_match": (
            None
            if reference_scale is None
            else _close(reference_scale, derived_scale)
        ),
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

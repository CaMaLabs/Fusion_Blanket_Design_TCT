#!/usr/bin/env python3
"""Focused second-stage amplitude refinement at the validated t=0.09 handoff.

The parent preemptive handoff audit improved the t=0.14 Jpk excursion most at
handoff t=0.09 but missed the frozen +0.10% Jpk gate by only ~0.00853 percentage
points while peak width remained just below the frozen +0.020% width gate.
This audit holds timing and geometry fixed and varies only the post-handoff
(second-profile) amplitude around the parent -0.015 value.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import native_two_profile_handoff_audit as base

native = base.native
pta = base.pta
REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_preemptive_second_amplitude_refinement"
RUN_ROOT = Path("/tmp/m3dc1_tct_native_preemptive_second_amplitude_refinement_runs")

HANDOFF = 0.09
FIRST_AMP = -0.015
SECOND_AMPLITUDES = (-0.0145, -0.0150, -0.0155, -0.0160)
SECOND_SHOULDER_WIDTH = 0.40
SECOND_DELTA = 0.30


def remove(path: Path) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def amp_label(amp: float) -> str:
    return f"two_profile_h0p09_a2_{amp:+.4f}".replace("+", "p").replace("-", "m").replace(".", "p")


def summarize(label: str, amp2: float, rows, baseline_rows) -> dict:
    s = native.summarize_case(
        label=label,
        second_start=HANDOFF,
        second_amp=amp2,
        rows=rows,
        baseline_rows=baseline_rows,
    )
    s.update({
        "kind": "uninterrupted_native_preemptive_second_amplitude_refinement",
        "first_start": base.START,
        "first_stop": HANDOFF,
        "first_amp": FIRST_AMP,
        "first_profile_width": base.PROFILE_WIDTH,
        "first_shoulder_width": base.FIRST_SHOULDER_WIDTH,
        "first_shoulder_delta": base.FIRST_DELTA,
        "second_start": HANDOFF,
        "second_stop": base.HORIZON,
        "second_amp": amp2,
        "second_profile_width": base.PROFILE_WIDTH,
        "second_shoulder_width": SECOND_SHOULDER_WIDTH,
        "second_shoulder_delta": SECOND_DELTA,
    })
    by_time = {round(float(r["time"]), 8): r for r in s["all_step_samples"]}
    for t in (0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.20, 0.25, 0.30):
        r = by_time.get(round(t, 8))
        if r:
            p = f"t{t:.2f}".replace(".", "p")
            s[f"{p}_width_gain_pct"] = r["width_gain_pct"]
            s[f"{p}_Jpk_change_pct"] = r["Jpk_change_pct"]
            s[f"{p}_high_J_change_pct"] = r["high_J_change_pct"]
    return s


def main() -> int:
    if not native.BASE.exists():
        raise FileNotFoundError(native.BASE)
    if not native.EXE.exists():
        raise FileNotFoundError(native.EXE)

    base.OUT = OUT
    base.RUN_ROOT = RUN_ROOT
    native.OUT = OUT
    native.RUN_ROOT = RUN_ROOT
    native.PROFILE_WIDTH = base.PROFILE_WIDTH
    native.SHOULDER_WIDTH = base.FIRST_SHOULDER_WIDTH
    native.SHOULDER_DELTA = base.FIRST_DELTA
    native.SECOND_STOP = base.HORIZON

    remove(RUN_ROOT)
    remove(OUT)
    RUN_ROOT.mkdir(parents=True)
    OUT.mkdir(parents=True)

    pta.install_operator()
    base.install_two_profile_operator()
    pta.build()

    baseline_dir, baseline_rows, baseline_status = base.run_case(
        "baseline_source0", source=0,
        amp1=0.0, t1_on=0.0, t1_off=base.HORIZON,
        amp2=0.0, t2_on=base.HORIZON, t2_off=base.HORIZON,
        second_width=base.PROFILE_WIDTH,
        second_shoulder_width=base.FIRST_SHOULDER_WIDTH,
        second_delta=base.FIRST_DELTA,
    )

    zero_dir, zero_rows, zero_status = base.run_case(
        "source4_zero", source=native.CURRENT_SOURCE,
        amp1=0.0, t1_on=base.START, t1_off=HANDOFF,
        amp2=0.0, t2_on=HANDOFF, t2_off=base.HORIZON,
        second_width=base.PROFILE_WIDTH,
        second_shoulder_width=SECOND_SHOULDER_WIDTH,
        second_delta=SECOND_DELTA,
    )
    zero_check = native.zero_equivalence(baseline_rows, zero_rows)

    ref_dir, ref_rows, ref_status = base.run_case(
        "constant_profile_reference", source=native.CURRENT_SOURCE,
        amp1=FIRST_AMP, t1_on=base.START, t1_off=base.HORIZON,
        amp2=0.0, t2_on=base.HORIZON, t2_off=base.HORIZON,
        second_width=base.PROFILE_WIDTH,
        second_shoulder_width=base.FIRST_SHOULDER_WIDTH,
        second_delta=base.FIRST_DELTA,
    )
    eq_dir, eq_rows, eq_status = base.run_case(
        "same_profile_handoff_equivalence", source=native.CURRENT_SOURCE,
        amp1=FIRST_AMP, t1_on=base.START, t1_off=HANDOFF,
        amp2=FIRST_AMP, t2_on=HANDOFF, t2_off=base.HORIZON,
        second_width=base.PROFILE_WIDTH,
        second_shoulder_width=base.FIRST_SHOULDER_WIDTH,
        second_delta=base.FIRST_DELTA,
    )
    handoff_equivalence = base.trajectory_equivalence(ref_rows, eq_rows)

    summaries = []
    executions = []
    flat_rows = []
    for amp2 in SECOND_AMPLITUDES:
        label = amp_label(amp2)
        d, rows, status = base.run_case(
            label, source=native.CURRENT_SOURCE,
            amp1=FIRST_AMP, t1_on=base.START, t1_off=HANDOFF,
            amp2=amp2, t2_on=HANDOFF, t2_off=base.HORIZON,
            second_width=base.PROFILE_WIDTH,
            second_shoulder_width=SECOND_SHOULDER_WIDTH,
            second_delta=SECOND_DELTA,
        )
        s = summarize(label, amp2, rows, baseline_rows)
        s["directory"] = str(d)
        summaries.append(s)
        executions.append({
            "case": label,
            "second_amp": amp2,
            "directory": str(d),
            "return_code": status["return_code"],
        })
        flat_rows.extend({"case": label, "second_amp": amp2, **row}
                         for row in s["all_step_samples"])

    ranked = sorted(summaries, key=lambda s: (
        bool(s["sustained_safe_authority"]),
        bool(s["current_gate_pass_every_step_t0p10_to_t0p30"]),
        bool(s["continuous_positive_width_t0p10_to_t0p30"]),
        bool(s["width_gate_pass_any"]),
        float(s["minimum_width_gain_pct"]),
        -max(0.0, float(s["worst_Jpk_change_pct"]) - native.JPK_GATE_PCT),
        float(s["peak_width_gain_pct"]),
        float(s["final_width_gain_pct"]),
    ), reverse=True)
    sustained = [s["case"] for s in ranked if s["sustained_safe_authority"]]
    current_safe = [s["case"] for s in ranked
                    if s["current_gate_pass_every_step_t0p10_to_t0p30"]]

    if not zero_check["pass"]:
        classification = "M3DC1_TCT_NATIVE_PREEMPTIVE_SECOND_AMPLITUDE_ZERO_EQUIVALENCE_FAILED"
    elif not handoff_equivalence["pass"]:
        classification = "M3DC1_TCT_NATIVE_PREEMPTIVE_SECOND_AMPLITUDE_HANDOFF_EQUIVALENCE_FAILED"
    elif sustained:
        classification = "M3DC1_TCT_NATIVE_PREEMPTIVE_SECOND_AMPLITUDE_SUSTAINED_SAFE_AUTHORITY"
    elif current_safe:
        classification = "M3DC1_TCT_NATIVE_PREEMPTIVE_SECOND_AMPLITUDE_CURRENT_SAFE_TRANSIENT_AUTHORITY"
    elif any(s["width_gate_pass_any"] for s in ranked):
        classification = "M3DC1_TCT_NATIVE_PREEMPTIVE_SECOND_AMPLITUDE_TRANSIENT_SAFE_AUTHORITY"
    else:
        classification = "M3DC1_TCT_NATIVE_PREEMPTIVE_SECOND_AMPLITUDE_NO_SAFE_AUTHORITY_FOUND"

    report = {
        "classification": classification,
        "sustained_pass_count": len(sustained),
        "sustained_pass_cases": sustained,
        "current_safe_count": len(current_safe),
        "current_safe_cases": current_safe,
        "zero_equivalence": zero_check,
        "handoff_equivalence": handoff_equivalence,
        "claim_boundary": (
            "Normalized native M3D-C1 uninterrupted two-profile amplitude refinement only. "
            "Frozen +0.020% width and +0.10% Jpk gates are unchanged and evaluated at every "
            "dt=0.01 sample from t=0.10 through t=0.30. No restart is used. No reactor-scale "
            "or experimental stabilization claim is implied."
        ),
        "audit": {
            "type": "uninterrupted_native_preemptive_second_amplitude_refinement",
            "reason": (
                "parent t=0.09 handoff reduced the worst Jpk excursion to +0.10853% while "
                "peak width remained just below +0.020%; vary only post-handoff amplitude"
            ),
            "dt": native.DT,
            "horizon": base.HORIZON,
            "start": base.START,
            "handoff": HANDOFF,
            "first_amp": FIRST_AMP,
            "second_amplitudes": list(SECOND_AMPLITUDES),
            "first_profile": {
                "center_width": base.PROFILE_WIDTH,
                "shoulder_width": base.FIRST_SHOULDER_WIDTH,
                "shoulder_delta": base.FIRST_DELTA,
            },
            "second_profile": {
                "center_width": base.PROFILE_WIDTH,
                "shoulder_width": SECOND_SHOULDER_WIDTH,
                "shoulder_delta": SECOND_DELTA,
            },
            "frozen_gates": {
                "width_gain_pct_gt": native.WIDTH_GATE_PCT,
                "Jpk_change_pct_le": native.JPK_GATE_PCT,
            },
            "restart_used_for_switching": False,
        },
        "baseline": {"directory": str(baseline_dir), "execution": baseline_status},
        "source4_zero": {"directory": str(zero_dir), "execution": zero_status},
        "constant_profile_reference": {"directory": str(ref_dir), "execution": ref_status},
        "same_profile_handoff": {"directory": str(eq_dir), "execution": eq_status},
        "best_case": ranked[0] if ranked else None,
        "case_summaries": ranked,
        "executions": executions,
    }

    write_json(OUT / "preemptive_second_amplitude_refinement_summary.json", report)
    pta.write_csv(OUT / "preemptive_second_amplitude_refinement_samples.csv", flat_rows)
    pta.write_csv(OUT / "preemptive_second_amplitude_refinement_case_summary.csv", [
        {key: s[key] for key in (
            "case", "first_amp", "second_amp", "second_start",
            "sustained_safe_authority", "continuous_positive_width_t0p10_to_t0p30",
            "current_gate_pass_every_step_t0p10_to_t0p30", "width_gate_pass_any",
            "final_width_gate_pass", "minimum_width_gain_pct", "minimum_width_time",
            "peak_width_gain_pct", "peak_width_time", "worst_Jpk_change_pct",
            "worst_Jpk_time", "Jpk_guard_margin_pct", "final_width_gain_pct",
            "final_Jpk_change_pct", "max_high_J_change_pct", "max_high_J_time")}
        for s in ranked
    ])
    (OUT / "runtime_provenance.txt").write_text("\n".join([
        f"repo={REPO}", f"source={native.SRC}", f"baseline={native.BASE}",
        f"executable={native.EXE}", f"executable_sha256={pta.sha256_file(native.EXE)}",
        f"run_root={RUN_ROOT}", f"dt={native.DT}", f"horizon={base.HORIZON}",
        f"start={base.START}", f"handoff={HANDOFF}", f"first_amp={FIRST_AMP}",
        f"second_amplitudes={list(SECOND_AMPLITUDES)}",
        f"second_profile=({base.PROFILE_WIDTH},{SECOND_SHOULDER_WIDTH},{SECOND_DELTA})",
        f"zero_equivalence_tol={native.ZERO_ABS_TOL}",
        f"handoff_equivalence_tol={base.EQ_TOL}",
        f"width_gate_pct={native.WIDTH_GATE_PCT}", f"jpk_gate_pct={native.JPK_GATE_PCT}",
        "acceptance=every native step from 0.10 through 0.30",
        "switching=uninterrupted two spatial profiles; no restart boundaries", "",
    ]))

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if zero_check["pass"] and handoff_equivalence["pass"] else 5


if __name__ == "__main__":
    raise SystemExit(main())

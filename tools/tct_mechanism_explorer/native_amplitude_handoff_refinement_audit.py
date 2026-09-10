#!/usr/bin/env python3
"""Uninterrupted native TCT amplitude-handoff refinement audit.

The previous uninterrupted two-window audit proved the large paired-restart
collapse was mostly a restart artifact, but it also exposed a genuine failure
that begins before the second pulse: with -0.030 held through t=0.15, Jpk
exceeds the frozen +0.10% guard at t=0.14 and width becomes negative.

This audit keeps the validated source=4 spatial profile and removes all restart
switching.  It starts at -0.030 at t=0.05, then hands off at
t={0.12,0.13,0.14} to a weaker continuation amplitude
{0,-0.005,-0.010,-0.015,-0.020} through t=0.30.

Frozen acceptance is unchanged and is evaluated at every native dt=0.01 sample
from t=0.10 through t=0.30:
  * width_gain_pct > 0 continuously;
  * Jpk_change_pct <= +0.10 continuously;
  * width_gain_pct > +0.020 at least once;
  * final width_gain_pct > +0.020.

A source=4 zero-amplitude trajectory must remain equivalent to source=0 within
1e-12 before any control result can be accepted.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import native_two_window_sustained_refinement_audit as native
import native_two_window_sustained_refinement_repair as repair
import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_amplitude_handoff_refinement"
RUN_ROOT = Path("/tmp/m3dc1_tct_native_amplitude_handoff_refinement_runs")

HANDOFF_TIMES = (0.12, 0.13, 0.14)
CONTINUATION_AMPS = (0.0, -0.005, -0.010, -0.015, -0.020)
STRONG_START = 0.05
STRONG_AMP = -0.030
HORIZON = 0.30


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def remove(path: Path) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def configure_native() -> None:
    # Reuse the already-validated uninterrupted two-window runner/extractor,
    # but write all artifacts to a separate audit root.
    native.OUT = OUT
    native.RUN_ROOT = RUN_ROOT
    native.FIRST_START = STRONG_START
    native.FIRST_AMP = STRONG_AMP
    native.SECOND_STOP = HORIZON


def case_label(handoff: float, continuation_amp: float) -> str:
    h = f"{handoff:.2f}".replace(".", "p")
    a = f"{abs(continuation_amp):.3f}".replace(".", "p")
    return f"handoff_h{h}_a{a}"


def summarize_handoff(
    label: str,
    handoff: float,
    continuation_amp: float,
    rows: list[dict[str, float]],
    baseline_rows: list[dict[str, float]],
) -> dict:
    # native.summarize_case applies the same frozen every-step acceptance.
    s = native.summarize_case(
        label=label,
        second_start=handoff,
        second_amp=continuation_amp,
        rows=rows,
        baseline_rows=baseline_rows,
    )
    s["kind"] = "uninterrupted_native_amplitude_handoff_refinement"
    s["handoff_time"] = handoff
    s["strong_amp"] = STRONG_AMP
    s["continuation_amp"] = continuation_amp

    # Add explicit diagnostic margins around the previously observed failure.
    by_time = {round(float(r["time"]), 8): r for r in s["all_step_samples"]}
    for t in (0.12, 0.13, 0.14, 0.15, 0.16):
        key = round(t, 8)
        if key in by_time:
            s[f"t{t:.2f}_width_gain_pct".replace(".", "p")] = by_time[key]["width_gain_pct"]
            s[f"t{t:.2f}_Jpk_change_pct".replace(".", "p")] = by_time[key]["Jpk_change_pct"]
            s[f"t{t:.2f}_high_J_change_pct".replace(".", "p")] = by_time[key]["high_J_change_pct"]
    return s


def main() -> int:
    if not native.BASE.exists():
        raise FileNotFoundError(native.BASE)
    if not native.EXE.exists():
        raise FileNotFoundError(native.EXE)

    configure_native()
    remove(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)

    # pulse_train audit may install magnetic helper changes; the repaired native
    # installer then guarantees a structurally valid two-window current operator.
    pta.install_operator()
    repair.repaired_install_native_two_window_operator()
    pta.build()

    baseline_dir, baseline_rows, baseline_status = native.run_case(
        "baseline_source0",
        source=0,
        amp1=0.0,
        t1_on=0.0,
        t1_off=HORIZON,
        amp2=0.0,
        t2_on=HORIZON,
        t2_off=HORIZON,
    )
    zero_dir, zero_rows, zero_status = native.run_case(
        "source4_zero",
        source=native.CURRENT_SOURCE,
        amp1=0.0,
        t1_on=STRONG_START,
        t1_off=min(HANDOFF_TIMES),
        amp2=0.0,
        t2_on=min(HANDOFF_TIMES),
        t2_off=HORIZON,
    )
    zero_check = native.zero_equivalence(baseline_rows, zero_rows)

    summaries: list[dict] = []
    flat_rows: list[dict] = []
    executions: list[dict] = []

    for handoff in HANDOFF_TIMES:
        for continuation_amp in CONTINUATION_AMPS:
            label = case_label(handoff, continuation_amp)
            d, rows, status = native.run_case(
                label,
                source=native.CURRENT_SOURCE,
                amp1=STRONG_AMP,
                t1_on=STRONG_START,
                t1_off=handoff,
                amp2=continuation_amp,
                t2_on=handoff,
                t2_off=HORIZON,
            )
            summary = summarize_handoff(
                label, handoff, continuation_amp, rows, baseline_rows
            )
            summary["directory"] = str(d)
            summaries.append(summary)
            flat_rows.extend(
                {
                    "case": label,
                    "handoff_time": handoff,
                    "strong_amp": STRONG_AMP,
                    "continuation_amp": continuation_amp,
                    **row,
                }
                for row in summary["all_step_samples"]
            )
            executions.append(
                {
                    "case": label,
                    "directory": str(d),
                    "return_code": status["return_code"],
                }
            )

    ranked = sorted(
        summaries,
        key=lambda s: (
            bool(s["sustained_safe_authority"]),
            bool(s["current_gate_pass_every_step_t0p10_to_t0p30"]),
            bool(s["continuous_positive_width_t0p10_to_t0p30"]),
            bool(s["final_width_gate_pass"]),
            float(s["minimum_width_gain_pct"]),
            float(s["final_width_gain_pct"]),
            float(s["peak_width_gain_pct"]),
        ),
        reverse=True,
    )
    sustained = [s["case"] for s in ranked if s["sustained_safe_authority"]]

    if not zero_check["pass"]:
        classification = "M3DC1_TCT_NATIVE_HANDOFF_ZERO_EQUIVALENCE_FAILED"
    elif sustained:
        classification = "M3DC1_TCT_NATIVE_HANDOFF_SUSTAINED_SAFE_AUTHORITY"
    elif any(s["width_gate_pass_any"] for s in ranked):
        classification = "M3DC1_TCT_NATIVE_HANDOFF_TRANSIENT_SAFE_AUTHORITY"
    else:
        classification = "M3DC1_TCT_NATIVE_HANDOFF_NO_SAFE_AUTHORITY_FOUND"

    report = {
        "classification": classification,
        "sustained_pass_count": len(sustained),
        "sustained_pass_cases": sustained,
        "claim_boundary": (
            "Normalized native M3D-C1 uninterrupted amplitude-handoff audit only. "
            "The source=4 spatial profile and frozen +0.020% width / +0.10% Jpk "
            "gates are unchanged. No restart is used for actuator switching. "
            "Acceptance is evaluated at every dt=0.01 sample from t=0.10 through "
            "t=0.30. No reactor-scale or experimental stabilization claim is implied."
        ),
        "audit": {
            "type": "uninterrupted_native_amplitude_handoff_refinement",
            "reason": (
                "the prior uninterrupted two-window sweep showed its common "
                "limiting excursion at t=0.14 before any second window could act"
            ),
            "dt": native.DT,
            "horizon": HORIZON,
            "strong_start": STRONG_START,
            "strong_amp": STRONG_AMP,
            "handoff_times": list(HANDOFF_TIMES),
            "continuation_amps": list(CONTINUATION_AMPS),
            "profile_width": native.PROFILE_WIDTH,
            "frozen_gates": {
                "width_gain_pct_gt": native.WIDTH_GATE_PCT,
                "Jpk_change_pct_le": native.JPK_GATE_PCT,
            },
            "acceptance": {
                "continuous_positive_width_t0p10_to_t0p30": True,
                "current_gate_every_step_t0p10_to_t0p30": True,
                "width_gate_pass_any": True,
                "final_width_gate_pass": True,
            },
            "restart_used_for_switching": False,
        },
        "zero_equivalence": zero_check,
        "baseline": {
            "directory": str(baseline_dir),
            "execution": baseline_status,
        },
        "source4_zero": {
            "directory": str(zero_dir),
            "execution": zero_status,
        },
        "best_case": ranked[0] if ranked else None,
        "case_summaries": ranked,
        "executions": executions,
    }

    write_json(OUT / "native_handoff_refinement_summary.json", report)
    pta.write_csv(OUT / "native_handoff_samples.csv", flat_rows)
    pta.write_csv(
        OUT / "native_handoff_case_summary.csv",
        [
            {
                key: s[key]
                for key in (
                    "case",
                    "handoff_time",
                    "strong_amp",
                    "continuation_amp",
                    "sustained_safe_authority",
                    "continuous_positive_width_t0p10_to_t0p30",
                    "current_gate_pass_every_step_t0p10_to_t0p30",
                    "width_gate_pass_any",
                    "final_width_gate_pass",
                    "minimum_width_gain_pct",
                    "minimum_width_time",
                    "peak_width_gain_pct",
                    "peak_width_time",
                    "worst_Jpk_change_pct",
                    "worst_Jpk_time",
                    "Jpk_guard_margin_pct",
                    "final_width_gain_pct",
                    "final_Jpk_change_pct",
                    "max_high_J_change_pct",
                    "max_high_J_time",
                )
            }
            for s in ranked
        ],
    )
    (OUT / "runtime_provenance.txt").write_text(
        "\n".join(
            [
                f"repo={REPO}",
                f"source={native.SRC}",
                f"baseline={native.BASE}",
                f"executable={native.EXE}",
                f"executable_sha256={pta.sha256_file(native.EXE)}",
                f"run_root={RUN_ROOT}",
                f"dt={native.DT}",
                f"horizon={HORIZON}",
                f"profile_width={native.PROFILE_WIDTH}",
                f"strong_stage={STRONG_START}->handoff@{STRONG_AMP}",
                f"handoff_times={list(HANDOFF_TIMES)}",
                f"continuation_amps={list(CONTINUATION_AMPS)}",
                f"width_gate_pct={native.WIDTH_GATE_PCT}",
                f"jpk_gate_pct={native.JPK_GATE_PCT}",
                "acceptance=every native step from 0.10 through 0.30",
                "switching=uninterrupted native amplitude handoff; no restart boundaries",
                "",
            ]
        )
    )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if zero_check["pass"] else 5


if __name__ == "__main__":
    raise SystemExit(main())

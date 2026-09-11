#!/usr/bin/env python3
"""Uninterrupted native TCT amplitude/profile-width refinement audit."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import native_two_window_sustained_refinement_audit as native
import native_two_window_sustained_refinement_repair as repair
import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_amplitude_profile_refinement"
RUN_ROOT = Path("/tmp/m3dc1_tct_native_amplitude_profile_refinement_runs")

PROFILE_WIDTHS = (0.1300, 0.1375, 0.1450)
AMPLITUDES = (-0.0150, -0.0175, -0.0200, -0.0225, -0.0250)
START = 0.05
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


def case_label(width: float, amp: float) -> str:
    w = f"{width:.4f}".replace(".", "p")
    a = f"{abs(amp):.4f}".replace(".", "p")
    return f"profile_w{w}_a{a}"


def zero_label(width: float) -> str:
    return f"source4_zero_w{width:.4f}".replace(".", "p")


def summarize(label, width, amp, rows, baseline_rows):
    s = native.summarize_case(
        label=label,
        second_start=HORIZON,
        second_amp=0.0,
        rows=rows,
        baseline_rows=baseline_rows,
    )
    s["kind"] = "uninterrupted_native_amplitude_profile_refinement"
    s["profile_width"] = width
    s["drive_amp"] = amp
    s["first_start"] = START
    s["first_stop"] = HORIZON
    s["first_amp"] = amp
    s["second_start"] = HORIZON
    s["second_stop"] = HORIZON
    s["second_amp"] = 0.0

    by_time = {round(float(r["time"]), 8): r for r in s["all_step_samples"]}
    for t in (0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.20, 0.25, 0.30):
        key = round(t, 8)
        if key in by_time:
            prefix = f"t{t:.2f}".replace(".", "p")
            s[f"{prefix}_width_gain_pct"] = by_time[key]["width_gain_pct"]
            s[f"{prefix}_Jpk_change_pct"] = by_time[key]["Jpk_change_pct"]
            s[f"{prefix}_high_J_change_pct"] = by_time[key]["high_J_change_pct"]
    return s


def main() -> int:
    if not native.BASE.exists():
        raise FileNotFoundError(native.BASE)
    if not native.EXE.exists():
        raise FileNotFoundError(native.EXE)

    native.OUT = OUT
    native.RUN_ROOT = RUN_ROOT
    native.SECOND_STOP = HORIZON

    remove(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)

    pta.install_operator()
    repair.repaired_install_native_two_window_operator()
    pta.build()

    native.PROFILE_WIDTH = PROFILE_WIDTHS[0]
    baseline_dir, baseline_rows, baseline_status = native.run_case(
        "baseline_source0", source=0,
        amp1=0.0, t1_on=0.0, t1_off=HORIZON,
        amp2=0.0, t2_on=HORIZON, t2_off=HORIZON,
    )

    zero_checks = []
    zero_executions = []
    for width in PROFILE_WIDTHS:
        native.PROFILE_WIDTH = width
        label = zero_label(width)
        d, rows, status = native.run_case(
            label, source=native.CURRENT_SOURCE,
            amp1=0.0, t1_on=START, t1_off=HORIZON,
            amp2=0.0, t2_on=HORIZON, t2_off=HORIZON,
        )
        check = native.zero_equivalence(baseline_rows, rows)
        zero_checks.append({
            "profile_width": width,
            "case": label,
            "pass": check["pass"],
            "checks": check["checks"],
            "tolerance": check["tolerance"],
        })
        zero_executions.append({
            "case": label,
            "profile_width": width,
            "directory": str(d),
            "return_code": status["return_code"],
        })

    all_zero_pass = all(z["pass"] for z in zero_checks)

    summaries = []
    flat_rows = []
    executions = []
    for width in PROFILE_WIDTHS:
        native.PROFILE_WIDTH = width
        for amp in AMPLITUDES:
            label = case_label(width, amp)
            d, rows, status = native.run_case(
                label, source=native.CURRENT_SOURCE,
                amp1=amp, t1_on=START, t1_off=HORIZON,
                amp2=0.0, t2_on=HORIZON, t2_off=HORIZON,
            )
            s = summarize(label, width, amp, rows, baseline_rows)
            s["directory"] = str(d)
            summaries.append(s)
            flat_rows.extend({
                "case": label,
                "profile_width": width,
                "drive_amp": amp,
                **row,
            } for row in s["all_step_samples"])
            executions.append({
                "case": label,
                "profile_width": width,
                "drive_amp": amp,
                "directory": str(d),
                "return_code": status["return_code"],
            })

    ranked = sorted(
        summaries,
        key=lambda s: (
            bool(s["sustained_safe_authority"]),
            bool(s["current_gate_pass_every_step_t0p10_to_t0p30"]),
            bool(s["continuous_positive_width_t0p10_to_t0p30"]),
            bool(s["final_width_gate_pass"]),
            float(s["minimum_width_gain_pct"]),
            -max(0.0, float(s["worst_Jpk_change_pct"]) - native.JPK_GATE_PCT),
            float(s["final_width_gain_pct"]),
            float(s["peak_width_gain_pct"]),
        ),
        reverse=True,
    )
    sustained = [s["case"] for s in ranked if s["sustained_safe_authority"]]

    if not all_zero_pass:
        classification = "M3DC1_TCT_NATIVE_PROFILE_ZERO_EQUIVALENCE_FAILED"
    elif sustained:
        classification = "M3DC1_TCT_NATIVE_PROFILE_SUSTAINED_SAFE_AUTHORITY"
    elif any(s["width_gate_pass_any"] for s in ranked):
        classification = "M3DC1_TCT_NATIVE_PROFILE_TRANSIENT_SAFE_AUTHORITY"
    else:
        classification = "M3DC1_TCT_NATIVE_PROFILE_NO_SAFE_AUTHORITY_FOUND"

    report = {
        "classification": classification,
        "sustained_pass_count": len(sustained),
        "sustained_pass_cases": sustained,
        "claim_boundary": (
            "Normalized native M3D-C1 uninterrupted amplitude/profile-width audit only. "
            "Frozen +0.020% width and +0.10% Jpk gates are unchanged and evaluated "
            "at every dt=0.01 sample from t=0.10 through t=0.30. No restart is used "
            "for actuator switching. No reactor-scale or experimental stabilization "
            "claim is implied."
        ),
        "audit": {
            "type": "uninterrupted_native_amplitude_profile_refinement",
            "reason": (
                "preemptive timing reduced Jpk only by sacrificing width authority; "
                "this audit tests amplitude and spatial profile width directly"
            ),
            "dt": native.DT,
            "horizon": HORIZON,
            "start": START,
            "profile_widths": list(PROFILE_WIDTHS),
            "amplitudes": list(AMPLITUDES),
            "shoulder_width": native.SHOULDER_WIDTH,
            "shoulder_delta": native.SHOULDER_DELTA,
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
        "zero_equivalence_pass": all_zero_pass,
        "zero_equivalence_by_width": zero_checks,
        "baseline": {"directory": str(baseline_dir), "execution": baseline_status},
        "zero_executions": zero_executions,
        "best_case": ranked[0] if ranked else None,
        "case_summaries": ranked,
        "executions": executions,
    }

    write_json(OUT / "native_profile_refinement_summary.json", report)
    pta.write_csv(OUT / "native_profile_samples.csv", flat_rows)
    pta.write_csv(
        OUT / "native_profile_case_summary.csv",
        [{key: s[key] for key in (
            "case", "profile_width", "drive_amp",
            "sustained_safe_authority",
            "continuous_positive_width_t0p10_to_t0p30",
            "current_gate_pass_every_step_t0p10_to_t0p30",
            "width_gate_pass_any", "final_width_gate_pass",
            "minimum_width_gain_pct", "minimum_width_time",
            "peak_width_gain_pct", "peak_width_time",
            "worst_Jpk_change_pct", "worst_Jpk_time",
            "Jpk_guard_margin_pct", "final_width_gain_pct",
            "final_Jpk_change_pct", "max_high_J_change_pct",
            "max_high_J_time",
        )} for s in ranked],
    )
    (OUT / "runtime_provenance.txt").write_text("\n".join([
        f"repo={REPO}",
        f"source={native.SRC}",
        f"baseline={native.BASE}",
        f"executable={native.EXE}",
        f"executable_sha256={pta.sha256_file(native.EXE)}",
        f"run_root={RUN_ROOT}",
        f"dt={native.DT}",
        f"horizon={HORIZON}",
        f"start={START}",
        f"profile_widths={list(PROFILE_WIDTHS)}",
        f"amplitudes={list(AMPLITUDES)}",
        f"shoulder_width={native.SHOULDER_WIDTH}",
        f"shoulder_delta={native.SHOULDER_DELTA}",
        f"width_gate_pct={native.WIDTH_GATE_PCT}",
        f"jpk_gate_pct={native.JPK_GATE_PCT}",
        "acceptance=every native step from 0.10 through 0.30",
        "switching=single uninterrupted source=4 window; no restart boundaries",
        "",
    ]))

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if all_zero_pass else 5


if __name__ == "__main__":
    raise SystemExit(main())

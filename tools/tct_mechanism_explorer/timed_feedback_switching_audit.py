#!/usr/bin/env python3
"""Timed-window and state-switched native M3D-C1 audit for the TCT current actuator.

Uses the measured authority anchor W_cd=0.1375, J_0cd=-0.03 from the preceding
extended-horizon audit.  Frozen authority gates remain unchanged.

The audit separates:
  1) single native on/off windows using cd_t_on/cd_t_off;
  2) two-window open-loop schedules using native restart boundaries; and
  3) a one-step-cadence state-switched controller that turns the actuator on
     during thinning / insufficient width and releases it after recovery or
     a Jpk guard.

Absolute Jint_high values and deltas are recorded beside percentage diagnostics
to expose denominator artifacts when the baseline high-J integral is small.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

os.environ["TCT_FEEDBACK_DT"] = "0.01"
os.environ["TCT_FEEDBACK_SEGMENT_STEPS"] = "1"
os.environ["TCT_FEEDBACK_MAX_SEGMENTS"] = "30"

import native_feedback_controller_audit as nfc
import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
BUILD = SRC / "build-ubuntu-2d"
EXE = BUILD / "unstructured/m3dc1_2d"
OUT = REPO / "validation_runs/m3dc1_tct_timed_feedback_switching"
RUN_ROOT = Path("/tmp/m3dc1_tct_timed_feedback_switching_runs")

DT = 0.01
HORIZON_STEPS = 30
HORIZON_TIME = DT * HORIZON_STEPS
HORIZON_TIMES = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
SUSTAIN_TIMES = (0.10, 0.15, 0.20, 0.25, 0.30)

CURRENT_SOURCE = 4
PROFILE_WIDTH = 0.1375
ACTUATOR_AMP = -0.030
OFF_AMP = 0.0

SHOULDER_WIDTH = 0.2805
SHOULDER_DELTA = 0.561
R0 = 10.0
Z0 = 1.0

WIDTH_GATE_PCT = 0.02
JPK_GATE_PCT = 0.10
ZERO_ABS_TOL = 1e-12

# State-switching policy values are control-layer thresholds only.
# They do not alter M3D-C1 equations or rescale the actuator.
TURN_ON_WIDTH_PCT = 0.0
RELEASE_WIDTH_PCT = 0.020
RELEASE_DW_PCT_PER_TIME = 0.0
JPK_GUARD_PCT = 0.10
MIN_ON_STEPS = 1
MIN_OFF_STEPS = 1

SINGLE_WINDOWS = (
    (0.00, 0.10),
    (0.00, 0.15),
    (0.00, 0.20),
    (0.05, 0.15),
    (0.05, 0.20),
    (0.10, 0.20),
    (0.10, 0.25),
)

MULTI_WINDOWS = (
    ((0.00, 0.10), (0.15, 0.25)),
    ((0.00, 0.10), (0.20, 0.30)),
    ((0.05, 0.15), (0.20, 0.30)),
)


def write_json(path: Path, payload: object) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def configure_native() -> None:
    nfc.RUN_ROOT = RUN_ROOT
    nfc.OUT = OUT
    nfc.DT = DT
    nfc.SEGMENT_STEPS = 1
    nfc.SEGMENT_DURATION = DT
    nfc.PROFILE_WIDTH = PROFILE_WIDTH
    nfc.SHOULDER_WIDTH = SHOULDER_WIDTH
    nfc.SHOULDER_DELTA = SHOULDER_DELTA
    nfc.CURRENT_SOURCE = CURRENT_SOURCE
    nfc.R0 = R0
    nfc.Z0 = Z0


def nearest(rows: list[dict[str, float]], t: float) -> dict[str, float]:
    return min(rows, key=lambda row: abs(row["time"] - t))


def require_horizon(rows: list[dict[str, float]], label: str) -> None:
    if not rows:
        raise RuntimeError(f"{label}: no extracted rows")
    for t in HORIZON_TIMES:
        if min(abs(float(row["time"]) - t) for row in rows) > 1e-8:
            raise RuntimeError(f"{label}: equal-time sample missing at t={t}")


def metric_row(
    row: dict[str, float],
    baseline: dict[str, float],
    zero: dict[str, float],
) -> dict[str, float | bool]:
    width_gain = pta.pct(row["W_sheet"], baseline["W_sheet"])
    jpk_change = pta.pct(row["Jpk"], baseline["Jpk"])
    high_j_abs = row["Jint_high"] - baseline["Jint_high"]
    return {
        "time": row["time"],
        "width_gain_pct": width_gain,
        "Jpk_change_pct": jpk_change,
        "high_J_change_pct": pta.pct(row["Jint_high"], baseline["Jint_high"]),
        "baseline_Jint_high": baseline["Jint_high"],
        "controlled_Jint_high": row["Jint_high"],
        "delta_Jint_high_abs": high_j_abs,
        "center_change_pct": pta.pct(
            row["center_abs_current"], baseline["center_abs_current"]
        ),
        "shoulder_change_pct": pta.pct(
            row["shoulder_abs_current"], baseline["shoulder_abs_current"]
        ),
        "mode_width_gain_pct": pta.pct(row["W_sheet"], zero["W_sheet"]),
        "mode_Jpk_change_pct": pta.pct(row["Jpk"], zero["Jpk"]),
        "delta_Reconnected_Flux": row["Reconnected_Flux"] - baseline["Reconnected_Flux"],
        "delta_magnetic_energy": row["magnetic_energy"] - baseline["magnetic_energy"],
        "width_gate_pass": width_gain > WIDTH_GATE_PCT,
        "current_gate_pass": jpk_change <= JPK_GATE_PCT,
    }


def sampled_metrics(
    rows: list[dict[str, float]],
    baseline_rows: list[dict[str, float]],
    zero_rows: list[dict[str, float]],
) -> list[dict[str, float | bool]]:
    require_horizon(rows, "controlled")
    return [
        metric_row(
            nearest(rows, t),
            nearest(baseline_rows, t),
            nearest(zero_rows, t),
        )
        for t in HORIZON_TIMES
    ]


def summarize_case(
    name: str,
    kind: str,
    windows: tuple[tuple[float, float], ...],
    metrics: list[dict[str, float | bool]],
    command_history: list[dict] | None = None,
) -> dict:
    peak = max(metrics, key=lambda r: float(r["width_gain_pct"]))
    late = [r for r in metrics if float(r["time"]) >= 0.10 - 1e-12]
    gate_rows = [r for r in metrics if bool(r["width_gate_pass"]) and bool(r["current_gate_pass"])]
    positive_late = all(float(r["width_gain_pct"]) > 0.0 for r in late)
    current_safe_late = all(bool(r["current_gate_pass"]) for r in late)
    final = max(metrics, key=lambda r: float(r["time"]))
    once_positive = False
    late_reversal = False
    for r in late:
        w = float(r["width_gain_pct"])
        if w > 0.0:
            once_positive = True
        elif once_positive and w <= 0.0:
            late_reversal = True
    return {
        "case": name,
        "kind": kind,
        "windows": [list(w) for w in windows],
        "peak_width_gain_pct": peak["width_gain_pct"],
        "peak_time": peak["time"],
        "best_gate_row": max(gate_rows, key=lambda r: float(r["width_gain_pct"]), default=None),
        "width_gate_pass_any": bool(gate_rows),
        "sustained_positive_from_t0p10": positive_late,
        "current_gate_pass_late": current_safe_late,
        "late_reversal_detected": late_reversal,
        "final_width_gain_pct": final["width_gain_pct"],
        "final_Jpk_change_pct": final["Jpk_change_pct"],
        "final_width_gate_pass": bool(final["width_gate_pass"]),
        "final_current_gate_pass": bool(final["current_gate_pass"]),
        "final_safe_authority": (
            bool(final["width_gate_pass"]) and bool(final["current_gate_pass"])
        ),
        "samples": metrics,
        "command_history": command_history or [],
    }


def run_continuous(
    name: str,
    amp: float,
    t_on: float,
    t_off: float,
    source: int = CURRENT_SOURCE,
) -> tuple[Path, list[dict[str, float]]]:
    d = nfc.write_input(
        name, source, amp, 0, t_on, t_off,
        nmax_steps=HORIZON_STEPS,
    )
    print(f"[timed-feedback] running {name}", flush=True)
    nfc.execute(d)
    rows = nfc.safe_extract(d)
    require_horizon(rows, name)
    return d, rows


def active_at(t: float, windows: tuple[tuple[float, float], ...]) -> bool:
    return any(start <= t < stop for start, stop in windows)


def run_segmented_schedule(
    name: str,
    windows: tuple[tuple[float, float], ...],
) -> tuple[list[dict[str, float]], list[dict]]:
    boundaries = sorted(
        {0.0, HORIZON_TIME}
        | {float(v) for pair in windows for v in pair}
    )
    control_rows: list[dict[str, float]] = []
    history: list[dict] = []
    previous_dir: Path | None = None

    for idx, (start, stop) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        midpoint = 0.5 * (start + stop)
        amp = ACTUATOR_AMP if active_at(midpoint, windows) else OFF_AMP
        d = nfc.write_input(
            f"{name}_seg_{idx:02d}",
            CURRENT_SOURCE,
            amp,
            0 if idx == 0 else 1,
            start,
            stop,
            nmax_steps=int(round(stop / DT)),
        )
        if previous_dir is not None:
            nfc.copy_restart_state(previous_dir, d)
        print(
            f"[timed-feedback] running {name} segment={idx} "
            f"t={start:.2f}->{stop:.2f} amp={amp:.4f}",
            flush=True,
        )
        nfc.execute(d)
        rows = nfc.safe_extract(d)
        if idx:
            rows = [r for r in rows if float(r["time"]) > start + 1e-8]
        if not rows:
            raise RuntimeError(f"{name}: segment {idx} did not advance")
        control_rows.extend(rows)
        history.append({
            "segment": idx,
            "start": start,
            "stop": stop,
            "amp": amp,
            "restart": 0 if idx == 0 else 1,
            "directory": str(d),
        })
        previous_dir = d

    require_horizon(control_rows, name)
    return control_rows, history


def feedback_decision(
    previous_metric: dict[str, float | bool] | None,
    current_metric: dict[str, float | bool],
    actuator_on: bool,
    dwell_steps: int,
) -> tuple[bool, str]:
    width = float(current_metric["width_gain_pct"])
    jpk = float(current_metric["Jpk_change_pct"])

    # Never keep negative drive active after the frozen positive Jpk guard.
    if jpk > JPK_GUARD_PCT:
        return False, "jpk_guard_release"

    if previous_metric is None:
        return True, "initial_probe"

    dt = max(
        float(current_metric["time"]) - float(previous_metric["time"]),
        DT,
    )
    dw_pct_dt = (
        width - float(previous_metric["width_gain_pct"])
    ) / dt

    if actuator_on:
        if dwell_steps < MIN_ON_STEPS:
            return True, "minimum_on_dwell"
        if width >= RELEASE_WIDTH_PCT and dw_pct_dt >= RELEASE_DW_PCT_PER_TIME:
            return False, "width_target_recovered"
        if dw_pct_dt < 0.0 and width > 0.0:
            return False, "positive_width_turning_down"
        return True, "continue_drive"

    if dwell_steps < MIN_OFF_STEPS:
        return False, "minimum_off_dwell"
    if width <= TURN_ON_WIDTH_PCT or dw_pct_dt < 0.0:
        return True, "thinning_or_nonpositive_width"
    return False, "hold_off_while_recovering"


def run_feedback(
    baseline_rows: list[dict[str, float]],
    zero_rows: list[dict[str, float]],
) -> tuple[list[dict[str, float]], list[dict]]:
    name = "feedback_switch"
    previous_dir: Path | None = None
    control_rows: list[dict[str, float]] = []
    history: list[dict] = []

    actuator_on = True
    dwell_steps = 0
    previous_metric: dict[str, float | bool] | None = None

    for step in range(HORIZON_STEPS):
        start = step * DT
        stop = (step + 1) * DT
        amp = ACTUATOR_AMP if actuator_on else OFF_AMP
        d = nfc.write_input(
            f"{name}_seg_{step:03d}",
            CURRENT_SOURCE,
            amp,
            0 if step == 0 else 1,
            start,
            stop,
            nmax_steps=step + 1,
        )
        if previous_dir is not None:
            nfc.copy_restart_state(previous_dir, d)
        print(
            f"[timed-feedback] running feedback step={step:02d} "
            f"state={'ON' if actuator_on else 'OFF'} amp={amp:.4f}",
            flush=True,
        )
        nfc.execute(d)
        rows = nfc.safe_extract(d)
        if step:
            rows = [r for r in rows if float(r["time"]) > start + 1e-8]
        if not rows:
            raise RuntimeError(f"feedback step {step} did not advance")
        control_rows.extend(rows)
        current = rows[-1]
        current_metric = metric_row(
            current,
            nearest(baseline_rows, float(current["time"])),
            nearest(zero_rows, float(current["time"])),
        )
        next_on, reason = feedback_decision(
            previous_metric, current_metric, actuator_on, dwell_steps
        )
        history.append({
            "step": step,
            "start": start,
            "stop": stop,
            "amp": amp,
            "state": "ON" if actuator_on else "OFF",
            "reason_for_next_state": reason,
            "next_state": "ON" if next_on else "OFF",
            "width_gain_pct": current_metric["width_gain_pct"],
            "Jpk_change_pct": current_metric["Jpk_change_pct"],
            "baseline_Jint_high": current_metric["baseline_Jint_high"],
            "controlled_Jint_high": current_metric["controlled_Jint_high"],
            "delta_Jint_high_abs": current_metric["delta_Jint_high_abs"],
            "high_J_change_pct": current_metric["high_J_change_pct"],
            "directory": str(d),
        })

        dwell_steps = dwell_steps + 1 if next_on == actuator_on else 0
        actuator_on = next_on
        previous_metric = current_metric
        previous_dir = d

    require_horizon(control_rows, name)
    return control_rows, history


def zero_equivalence(
    baseline_rows: list[dict[str, float]],
    zero_rows: list[dict[str, float]],
) -> dict:
    maximum = 0.0
    by_metric: dict[str, float] = {}
    for key in (
        "W_sheet",
        "Jpk",
        "Jint_high",
        "center_abs_current",
        "shoulder_abs_current",
        "Reconnected_Flux",
        "magnetic_energy",
    ):
        delta = max(
            abs(
                float(nearest(zero_rows, t)[key])
                - float(nearest(baseline_rows, t)[key])
            )
            for t in HORIZON_TIMES
        )
        by_metric[key] = delta
        maximum = max(maximum, delta)
    return {
        "max_abs_metric_delta": maximum,
        "by_metric": by_metric,
        "tolerance": ZERO_ABS_TOL,
        "pass": maximum <= ZERO_ABS_TOL,
    }


def main() -> int:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if not EXE.exists():
        raise FileNotFoundError(EXE)

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    configure_native()

    pta.install_operator()
    nfc.install_current_redistribution_operator()
    pta.build()

    _, baseline_rows = run_continuous(
        "baseline", 0.0, 0.0, HORIZON_TIME, source=0
    )
    _, zero_rows = run_continuous(
        "source4_zero", 0.0, 0.0, HORIZON_TIME
    )
    zero_check = zero_equivalence(baseline_rows, zero_rows)

    summaries: list[dict] = []
    flat_rows: list[dict] = []

    for start, stop in SINGLE_WINDOWS:
        label = f"single_{start:.2f}_{stop:.2f}".replace(".", "p")
        _, rows = run_continuous(label, ACTUATOR_AMP, start, stop)
        metrics = sampled_metrics(rows, baseline_rows, zero_rows)
        summary = summarize_case(
            label, "single_native_gate", ((start, stop),), metrics
        )
        summaries.append(summary)
        flat_rows.extend({"case": label, **r} for r in metrics)

    for idx, windows in enumerate(MULTI_WINDOWS):
        label = f"multi_{idx:02d}"
        rows, history = run_segmented_schedule(label, windows)
        metrics = sampled_metrics(rows, baseline_rows, zero_rows)
        summary = summarize_case(
            label, "multi_restart_schedule", windows, metrics, history
        )
        summaries.append(summary)
        flat_rows.extend({"case": label, **r} for r in metrics)

    feedback_rows, feedback_history = run_feedback(baseline_rows, zero_rows)
    feedback_metrics = sampled_metrics(feedback_rows, baseline_rows, zero_rows)
    feedback_summary = summarize_case(
        "feedback_switch",
        "state_switched_feedback",
        tuple(),
        feedback_metrics,
        feedback_history,
    )
    summaries.append(feedback_summary)
    flat_rows.extend({"case": "feedback_switch", **r} for r in feedback_metrics)

    ranked = sorted(
        summaries,
        key=lambda s: (
            bool(s["final_safe_authority"]),
            bool(s["sustained_positive_from_t0p10"]),
            float(s["final_width_gain_pct"]),
            float(s["peak_width_gain_pct"]),
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None

    feedback_success = (
        feedback_summary["sustained_positive_from_t0p10"]
        and feedback_summary["current_gate_pass_late"]
        and feedback_summary["final_safe_authority"]
        and not feedback_summary["late_reversal_detected"]
    )
    timed_success = any(
        s["sustained_positive_from_t0p10"]
        and s["current_gate_pass_late"]
        and s["final_safe_authority"]
        and not s["late_reversal_detected"]
        for s in summaries
        if s["kind"] != "state_switched_feedback"
    )
    any_point = any(bool(s["width_gate_pass_any"]) for s in summaries)

    if feedback_success:
        classification = "M3DC1_TCT_STATE_SWITCHED_SUSTAINED_SAFE_AUTHORITY"
    elif timed_success:
        classification = "M3DC1_TCT_TIMED_WINDOW_SUSTAINED_SAFE_AUTHORITY"
    elif any_point:
        classification = "M3DC1_TCT_TIMED_FEEDBACK_TRANSIENT_SAFE_AUTHORITY"
    else:
        classification = "M3DC1_TCT_TIMED_FEEDBACK_NO_SAFE_AUTHORITY_FOUND"

    report = {
        "classification": classification,
        "claim_boundary": (
            "Native normalized M3D-C1 timing/feedback audit only. Frozen 0.02% "
            "width and 0.10% Jpk gates are unchanged. No reactor-scale, RF-wave, "
            "lithium dimensional-transfer, or experimental claim is implied."
        ),
        "audit": {
            "type": "timed_window_plus_state_switched_current_redistribution",
            "dt": DT,
            "horizon_time": HORIZON_TIME,
            "horizon_times": list(HORIZON_TIMES),
            "profile_width": PROFILE_WIDTH,
            "shoulder_width": SHOULDER_WIDTH,
            "shoulder_separation": SHOULDER_DELTA,
            "actuator_amp": ACTUATOR_AMP,
            "source": CURRENT_SOURCE,
            "gates": {
                "width_threshold_pct": WIDTH_GATE_PCT,
                "Jpk_threshold_pct": JPK_GATE_PCT,
                "zero_equivalence_tolerance": ZERO_ABS_TOL,
            },
            "feedback_policy": {
                "turn_on_width_pct": TURN_ON_WIDTH_PCT,
                "release_width_pct": RELEASE_WIDTH_PCT,
                "release_dW_pct_per_time": RELEASE_DW_PCT_PER_TIME,
                "jpk_guard_pct": JPK_GUARD_PCT,
                "minimum_on_steps": MIN_ON_STEPS,
                "minimum_off_steps": MIN_OFF_STEPS,
            },
            "single_windows": [list(w) for w in SINGLE_WINDOWS],
            "multi_windows": [[list(w) for w in windows] for windows in MULTI_WINDOWS],
        },
        "zero_equivalence": zero_check,
        "best_case": best,
        "feedback_case": feedback_summary,
        "case_summaries": ranked,
    }

    pta.write_csv(OUT / "timed_feedback_samples.csv", flat_rows)
    pta.write_csv(
        OUT / "timed_feedback_case_summary.csv",
        [
            {
                "case": s["case"],
                "kind": s["kind"],
                "peak_width_gain_pct": s["peak_width_gain_pct"],
                "peak_time": s["peak_time"],
                "width_gate_pass_any": s["width_gate_pass_any"],
                "sustained_positive_from_t0p10": s["sustained_positive_from_t0p10"],
                "current_gate_pass_late": s["current_gate_pass_late"],
                "late_reversal_detected": s["late_reversal_detected"],
                "final_width_gain_pct": s["final_width_gain_pct"],
                "final_Jpk_change_pct": s["final_Jpk_change_pct"],
                "final_safe_authority": s["final_safe_authority"],
            }
            for s in ranked
        ],
    )
    pta.write_csv(OUT / "feedback_command_history.csv", feedback_history)
    write_json(OUT / "timed_feedback_summary.json", report)
    write_json(OUT / "feedback_command_history.json", feedback_history)
    (OUT / "runtime_provenance.txt").write_text(
        "repo={}\nsource={}\nbaseline={}\nexecutable={}\n"
        "executable_sha256={}\nrun_root={}\n"
        "dt={}\nhorizon_steps={}\nhorizon_time={}\n"
        "source={}\nprofile_width={}\nactuator_amp={}\n"
        "shoulder_width={}\nshoulder_separation={}\n".format(
            REPO,
            SRC,
            BASE,
            EXE,
            pta.sha256_file(EXE),
            RUN_ROOT,
            DT,
            HORIZON_STEPS,
            HORIZON_TIME,
            CURRENT_SOURCE,
            PROFILE_WIDTH,
            ACTUATOR_AMP,
            SHOULDER_WIDTH,
            SHOULDER_DELTA,
        )
    )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

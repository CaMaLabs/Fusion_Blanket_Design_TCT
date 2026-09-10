#!/usr/bin/env python3
"""Paired-restart differential TCT control audit.

Every restart-based controlled trajectory is paired with a source=0 null
trajectory using the identical restart boundaries and documented HDF5 restart
payload. Physics gates are evaluated only on control-minus-paired-null
differences. An uninterrupted source=0 run is retained only to quantify restart
bias and is never used as the control baseline.
"""
from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path

import native_feedback_controller_audit as nfc
import pulse_train_audit as pta
import restart_transport_audit as rta
import restart_transport_hdf5_repair as h5r

REPO = Path("/home/ubuntu/work/openmc/sweep")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
EXE = SRC / "build-ubuntu-2d/unstructured/m3dc1_2d"
OUT = REPO / "validation_runs/m3dc1_tct_paired_restart_differential"
RUN_ROOT = Path("/tmp/m3dc1_tct_paired_restart_differential_runs")

DT = 0.01
HORIZON = 0.30
HORIZON_STEPS = 30
HORIZON_TIMES = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
SUSTAIN_TIMES = (0.10, 0.15, 0.20, 0.25, 0.30)

CURRENT_SOURCE = 4
ACTUATOR_AMP = -0.030
PROFILE_WIDTH = 0.1375
SHOULDER_WIDTH = 0.2805
SHOULDER_DELTA = 0.561
R0 = 10.0
Z0 = 1.0

WIDTH_GATE_PCT = 0.020
JPK_GATE_PCT = 0.10

TURN_ON_WIDTH_PCT = 0.0
RELEASE_WIDTH_PCT = 0.020
RELEASE_DW_PCT_PER_TIME = 0.0
JPK_GUARD_PCT = 0.10
MIN_ON_STEPS = 1
MIN_OFF_STEPS = 1

SINGLE_WINDOWS = (
    (0.00, 0.20),
    (0.05, 0.20),
    (0.10, 0.20),
)
MULTI_WINDOWS = (
    ((0.00, 0.10), (0.15, 0.25)),
    ((0.00, 0.10), (0.20, 0.30)),
    ((0.05, 0.15), (0.20, 0.30)),
)

METRICS = (
    "W_sheet",
    "Jpk",
    "Jint_high",
    "center_abs_current",
    "shoulder_abs_current",
    "Reconnected_Flux",
    "magnetic_energy",
)
TIME_TOL = 1e-8


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


def prepare_dir(
    name: str,
    source: int,
    amp: float,
    restart: bool,
    start: float,
    stop: float,
) -> Path:
    """Write one native segment without relying on the old f-string launcher."""
    d = RUN_ROOT / name
    remove(d)
    d.mkdir(parents=True)

    for item in pta.COPY_NAMES:
        src = BASE / item
        if src.is_symlink():
            (d / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, d / item)

    text = (BASE / "C1input").read_text()
    updates = {
        "dt": f"{DT:.10g}",
        "ntimemax": str(int(round(stop / DT))),
        "ntimepr": "1",
        "irestart": "1" if restart else "0",
        "irestart_slice": "-1",
        "iwrite_restart": "1",
        "imag_control": "0",
        "mag_ctrl_amp": "0.0",
        "icd_source": str(source),
        "J_0cd": f"{amp:.10g}",
        "R_0cd": f"{R0:.10g}",
        "Z_0cd": f"{Z0:.10g}",
        "W_cd": f"{PROFILE_WIDTH:.10g}",
        "W_cd_shoulder": f"{SHOULDER_WIDTH:.10g}",
        "delta_cd": f"{SHOULDER_DELTA:.10g}",
        "cd_t_on": f"{start:.10g}",
        "cd_t_ramp": "0.0",
        "cd_t_off": f"{stop:.10g}",
    }
    for key, value in updates.items():
        text = pta.replace_or_add(text, key, value)
    (d / "C1input").write_text(text)

    launcher = f"""#!/usr/bin/env bash
set -euo pipefail
export TMPDIR="${{TMPDIR:-/tmp/tct-$USER}}"
export OMPI_MCA_orte_tmpdir_base="${{OMPI_MCA_orte_tmpdir_base:-$TMPDIR}}"
mkdir -p "$TMPDIR" "$OMPI_MCA_orte_tmpdir_base"
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "{d}"
set +e
timeout 1200s mpirun --oversubscribe -n 1 "{EXE}" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
rc=$?
set -e
printf 'return_code=%s\\n' "$rc" > run_status.txt
exit "$rc"
"""
    (d / "launch_command.sh").write_text(launcher)
    (d / "launch_command.sh").chmod(0o755)
    return d


def execute(d: Path) -> dict:
    t0 = time.time()
    p = pta.sh(["bash", "launch_command.sh"], cwd=d)
    status = {
        "return_code": p.returncode,
        "elapsed_seconds": time.time() - t0,
        "wrapper_tail": p.stdout[-3000:],
        "C1stdout_tail": (
            (d / "C1stdout").read_text(errors="replace")[-5000:]
            if (d / "C1stdout").exists() else ""
        ),
        "launcher_stderr_tail": (
            (d / "launcher.stderr").read_text(errors="replace")[-5000:]
            if (d / "launcher.stderr").exists() else ""
        ),
    }
    write_json(d / "segment_result.json", status)
    return status


def nearest(rows: list[dict[str, float]], t: float) -> dict[str, float]:
    if not rows:
        raise RuntimeError("nearest() called with no rows")
    row = min(rows, key=lambda r: abs(float(r["time"]) - t))
    if abs(float(row["time"]) - t) > TIME_TOL:
        raise RuntimeError(f"missing sample at t={t}; nearest={row['time']}")
    return row


def require_times(rows: list[dict[str, float]], times: tuple[float, ...], label: str) -> None:
    for t in times:
        nearest(rows, t)


def pct(control: float, null: float) -> float:
    return 100.0 * (control / null - 1.0) if abs(null) > 1e-300 else math.nan


def differential_row(
    control: dict[str, float],
    null: dict[str, float],
    uninterrupted: dict[str, float] | None = None,
) -> dict:
    width = pct(float(control["W_sheet"]), float(null["W_sheet"]))
    jpk = pct(float(control["Jpk"]), float(null["Jpk"]))
    row = {
        "time": float(control["time"]),
        "width_gain_pct": width,
        "Jpk_change_pct": jpk,
        "high_J_change_pct": pct(float(control["Jint_high"]), float(null["Jint_high"])),
        "paired_null_Jint_high": float(null["Jint_high"]),
        "controlled_Jint_high": float(control["Jint_high"]),
        "delta_Jint_high_abs": float(control["Jint_high"]) - float(null["Jint_high"]),
        "center_change_pct": pct(
            float(control["center_abs_current"]), float(null["center_abs_current"])
        ),
        "shoulder_change_pct": pct(
            float(control["shoulder_abs_current"]), float(null["shoulder_abs_current"])
        ),
        "delta_Reconnected_Flux": (
            float(control["Reconnected_Flux"]) - float(null["Reconnected_Flux"])
        ),
        "delta_magnetic_energy": (
            float(control["magnetic_energy"]) - float(null["magnetic_energy"])
        ),
        "width_gate_pass": width > WIDTH_GATE_PCT,
        "current_gate_pass": jpk <= JPK_GATE_PCT,
    }
    if uninterrupted is not None:
        row["paired_null_restart_bias_width_pct"] = pct(
            float(null["W_sheet"]), float(uninterrupted["W_sheet"])
        )
        row["paired_null_restart_bias_Jpk_pct"] = pct(
            float(null["Jpk"]), float(uninterrupted["Jpk"])
        )
    return row


def sample_differential(
    control_rows: list[dict[str, float]],
    null_rows: list[dict[str, float]],
    uninterrupted_rows: list[dict[str, float]],
) -> list[dict]:
    require_times(control_rows, HORIZON_TIMES, "control")
    require_times(null_rows, HORIZON_TIMES, "paired-null")
    require_times(uninterrupted_rows, HORIZON_TIMES, "uninterrupted")
    return [
        differential_row(
            nearest(control_rows, t),
            nearest(null_rows, t),
            nearest(uninterrupted_rows, t),
        )
        for t in HORIZON_TIMES
    ]


def active_at(t: float, windows: tuple[tuple[float, float], ...]) -> bool:
    return any(start <= t < stop for start, stop in windows)


def schedule_boundaries(windows: tuple[tuple[float, float], ...]) -> list[float]:
    return sorted(
        {0.0, HORIZON}
        | {float(v) for pair in windows for v in pair}
    )


def run_pair_schedule(
    label: str,
    windows: tuple[tuple[float, float], ...],
) -> tuple[list[dict[str, float]], list[dict[str, float]], list[dict]]:
    boundaries = schedule_boundaries(windows)
    control_rows: list[dict[str, float]] = []
    null_rows: list[dict[str, float]] = []
    history: list[dict] = []
    previous_control: Path | None = None
    previous_null: Path | None = None

    for idx, (start, stop) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        midpoint = 0.5 * (start + stop)
        amp = ACTUATOR_AMP if active_at(midpoint, windows) else 0.0
        restart = idx > 0

        control_dir = prepare_dir(
            f"{label}_control_seg_{idx:02d}",
            CURRENT_SOURCE, amp, restart, start, stop,
        )
        null_dir = prepare_dir(
            f"{label}_null_seg_{idx:02d}",
            0, 0.0, restart, start, stop,
        )
        control_manifest = null_manifest = None
        if restart:
            assert previous_control is not None and previous_null is not None
            control_manifest = h5r.copy_restart(previous_control, control_dir)
            null_manifest = h5r.copy_restart(previous_null, null_dir)

        print(
            f"[paired] {label} seg={idx} {start:.2f}->{stop:.2f} "
            f"control_amp={amp:.4f} restart={int(restart)}",
            flush=True,
        )
        control_status = execute(control_dir)
        null_status = execute(null_dir)
        entry = {
            "segment": idx,
            "start": start,
            "stop": stop,
            "restart": restart,
            "control_amp": amp,
            "control_directory": str(control_dir),
            "null_directory": str(null_dir),
            "control_execution": control_status,
            "null_execution": null_status,
            "control_seed_manifest": control_manifest,
            "null_seed_manifest": null_manifest,
        }
        if control_status["return_code"] or null_status["return_code"]:
            entry["pass"] = False
            history.append(entry)
            raise RuntimeError(
                f"{label} segment {idx} failed: "
                f"control_rc={control_status['return_code']} "
                f"null_rc={null_status['return_code']}"
            )

        crows = h5r.extract(control_dir)
        nrows = h5r.extract(null_dir)
        if restart:
            crows = [r for r in crows if float(r["time"]) > start + TIME_TOL]
            nrows = [r for r in nrows if float(r["time"]) > start + TIME_TOL]
        if not crows or not nrows:
            entry["pass"] = False
            history.append(entry)
            raise RuntimeError(f"{label} segment {idx}: twin did not advance")
        if abs(max(r["time"] for r in crows) - stop) > TIME_TOL:
            raise RuntimeError(f"{label} control segment {idx} did not reach {stop}")
        if abs(max(r["time"] for r in nrows) - stop) > TIME_TOL:
            raise RuntimeError(f"{label} null segment {idx} did not reach {stop}")

        entry["pass"] = True
        entry["control_final_C1_sha256"] = rta.sha256(control_dir / "C1.h5")
        entry["null_final_C1_sha256"] = rta.sha256(null_dir / "C1.h5")
        history.append(entry)
        control_rows.extend(crows)
        null_rows.extend(nrows)
        previous_control, previous_null = control_dir, null_dir

    require_times(control_rows, HORIZON_TIMES, f"{label}-control")
    require_times(null_rows, HORIZON_TIMES, f"{label}-null")
    return control_rows, null_rows, history


def feedback_decision(
    previous_metric: dict | None,
    current_metric: dict,
    actuator_on: bool,
    dwell_steps: int,
) -> tuple[bool, str]:
    width = float(current_metric["width_gain_pct"])
    jpk = float(current_metric["Jpk_change_pct"])
    if jpk > JPK_GUARD_PCT:
        return False, "jpk_guard_release"
    if previous_metric is None:
        return True, "initial_probe"

    dt = max(float(current_metric["time"]) - float(previous_metric["time"]), DT)
    dw_dt = (width - float(previous_metric["width_gain_pct"])) / dt
    if actuator_on:
        if dwell_steps < MIN_ON_STEPS:
            return True, "minimum_on_dwell"
        if width >= RELEASE_WIDTH_PCT and dw_dt >= RELEASE_DW_PCT_PER_TIME:
            return False, "width_target_recovered"
        if dw_dt < 0.0 and width > 0.0:
            return False, "positive_width_turning_down"
        return True, "continue_drive"

    if dwell_steps < MIN_OFF_STEPS:
        return False, "minimum_off_dwell"
    if width <= TURN_ON_WIDTH_PCT or dw_dt < 0.0:
        return True, "thinning_or_nonpositive_width"
    return False, "hold_off_while_recovering"


def run_feedback_pair(
    uninterrupted_rows: list[dict[str, float]],
) -> tuple[list[dict[str, float]], list[dict[str, float]], list[dict]]:
    control_rows: list[dict[str, float]] = []
    null_rows: list[dict[str, float]] = []
    history: list[dict] = []
    previous_control: Path | None = None
    previous_null: Path | None = None
    actuator_on = True
    dwell_steps = 0
    previous_metric: dict | None = None

    for step in range(HORIZON_STEPS):
        start, stop = step * DT, (step + 1) * DT
        amp = ACTUATOR_AMP if actuator_on else 0.0
        restart = step > 0
        control_dir = prepare_dir(
            f"feedback_control_seg_{step:03d}",
            CURRENT_SOURCE, amp, restart, start, stop,
        )
        null_dir = prepare_dir(
            f"feedback_null_seg_{step:03d}",
            0, 0.0, restart, start, stop,
        )
        cmanifest = nmanifest = None
        if restart:
            assert previous_control is not None and previous_null is not None
            cmanifest = h5r.copy_restart(previous_control, control_dir)
            nmanifest = h5r.copy_restart(previous_null, null_dir)

        print(
            f"[paired-feedback] step={step:02d} {start:.2f}->{stop:.2f} "
            f"state={'ON' if actuator_on else 'OFF'} amp={amp:.4f}",
            flush=True,
        )
        cs = execute(control_dir)
        ns = execute(null_dir)
        if cs["return_code"] or ns["return_code"]:
            raise RuntimeError(
                f"feedback step {step} failed control_rc={cs['return_code']} "
                f"null_rc={ns['return_code']}"
            )

        crows = h5r.extract(control_dir)
        nrows = h5r.extract(null_dir)
        if restart:
            crows = [r for r in crows if float(r["time"]) > start + TIME_TOL]
            nrows = [r for r in nrows if float(r["time"]) > start + TIME_TOL]
        if not crows or not nrows:
            raise RuntimeError(f"feedback step {step}: no advanced twin output")
        current_control = max(crows, key=lambda r: float(r["time"]))
        current_null = max(nrows, key=lambda r: float(r["time"]))
        if abs(float(current_control["time"]) - stop) > TIME_TOL:
            raise RuntimeError(f"feedback control step {step} did not reach {stop}")
        if abs(float(current_null["time"]) - stop) > TIME_TOL:
            raise RuntimeError(f"feedback null step {step} did not reach {stop}")

        uninterrupted = nearest(uninterrupted_rows, stop)
        metric = differential_row(current_control, current_null, uninterrupted)
        next_on, reason = feedback_decision(
            previous_metric, metric, actuator_on, dwell_steps
        )
        history.append({
            "step": step,
            "start": start,
            "stop": stop,
            "state": "ON" if actuator_on else "OFF",
            "amp": amp,
            "next_state": "ON" if next_on else "OFF",
            "reason_for_next_state": reason,
            "width_gain_pct": metric["width_gain_pct"],
            "Jpk_change_pct": metric["Jpk_change_pct"],
            "high_J_change_pct": metric["high_J_change_pct"],
            "delta_Jint_high_abs": metric["delta_Jint_high_abs"],
            "paired_null_restart_bias_width_pct": metric.get(
                "paired_null_restart_bias_width_pct"
            ),
            "control_directory": str(control_dir),
            "null_directory": str(null_dir),
            "control_seed_plot": (
                cmanifest.get("selected_plot_file") if cmanifest else None
            ),
            "null_seed_plot": (
                nmanifest.get("selected_plot_file") if nmanifest else None
            ),
        })

        control_rows.extend(crows)
        null_rows.extend(nrows)
        dwell_steps = dwell_steps + 1 if next_on == actuator_on else 0
        actuator_on = next_on
        previous_metric = metric
        previous_control, previous_null = control_dir, null_dir

    require_times(control_rows, HORIZON_TIMES, "feedback-control")
    require_times(null_rows, HORIZON_TIMES, "feedback-null")
    return control_rows, null_rows, history


def summarize(
    label: str,
    kind: str,
    windows: tuple[tuple[float, float], ...],
    metrics: list[dict],
    history: list[dict],
) -> dict:
    peak = max(metrics, key=lambda r: float(r["width_gain_pct"]))
    late = [r for r in metrics if float(r["time"]) >= 0.10 - TIME_TOL]
    gate_rows = [
        r for r in metrics
        if bool(r["width_gate_pass"]) and bool(r["current_gate_pass"])
    ]
    positive_late = all(float(r["width_gain_pct"]) > 0.0 for r in late)
    current_safe_late = all(bool(r["current_gate_pass"]) for r in late)
    final = max(metrics, key=lambda r: float(r["time"]))
    once_positive = False
    late_reversal = False
    for row in late:
        width = float(row["width_gain_pct"])
        if width > 0:
            once_positive = True
        elif once_positive:
            late_reversal = True
    max_restart_bias = max(
        abs(float(r.get("paired_null_restart_bias_width_pct", 0.0)))
        for r in metrics
    )
    return {
        "case": label,
        "kind": kind,
        "windows": [list(w) for w in windows],
        "peak_width_gain_pct": peak["width_gain_pct"],
        "peak_time": peak["time"],
        "safe_gate_pass_any": bool(gate_rows),
        "best_gate_row": max(
            gate_rows, key=lambda r: float(r["width_gain_pct"]), default=None
        ),
        "sustained_positive_from_t0p10": positive_late,
        "current_gate_pass_late": current_safe_late,
        "late_reversal_detected": late_reversal,
        "final_width_gain_pct": final["width_gain_pct"],
        "final_Jpk_change_pct": final["Jpk_change_pct"],
        "final_safe_authority": (
            bool(final["width_gate_pass"]) and bool(final["current_gate_pass"])
        ),
        "max_abs_paired_null_restart_bias_width_pct": max_restart_bias,
        "samples": metrics,
        "command_history": history,
    }


def run_uninterrupted_null() -> list[dict[str, float]]:
    d = prepare_dir(
        "uninterrupted_source0",
        source=0,
        amp=0.0,
        restart=False,
        start=0.0,
        stop=HORIZON,
    )
    print("[paired] uninterrupted source=0 restart-bias reference", flush=True)
    status = execute(d)
    if status["return_code"]:
        raise RuntimeError(
            f"uninterrupted source=0 failed rc={status['return_code']}\n"
            f"{status['C1stdout_tail']}\n{status['launcher_stderr_tail']}"
        )
    rows = h5r.extract(d)
    require_times(rows, HORIZON_TIMES, "uninterrupted-null")
    return rows


def main() -> int:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if not EXE.exists():
        raise FileNotFoundError(EXE)

    remove(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)

    pta.install_operator()
    nfc.install_current_redistribution_operator()
    pta.build()

    uninterrupted = run_uninterrupted_null()
    summaries: list[dict] = []
    flat_rows: list[dict] = []

    for start, stop in SINGLE_WINDOWS:
        label = f"single_{start:.2f}_{stop:.2f}".replace(".", "p")
        windows = ((start, stop),)
        crows, nrows, history = run_pair_schedule(label, windows)
        metrics = sample_differential(crows, nrows, uninterrupted)
        summary = summarize(label, "paired_restart_single_window", windows, metrics, history)
        summaries.append(summary)
        flat_rows.extend({"case": label, **r} for r in metrics)

    for idx, windows in enumerate(MULTI_WINDOWS):
        label = f"multi_{idx:02d}"
        crows, nrows, history = run_pair_schedule(label, windows)
        metrics = sample_differential(crows, nrows, uninterrupted)
        summary = summarize(label, "paired_restart_multi_window", windows, metrics, history)
        summaries.append(summary)
        flat_rows.extend({"case": label, **r} for r in metrics)

    fcrows, fnrows, fhistory = run_feedback_pair(uninterrupted)
    fmetrics = sample_differential(fcrows, fnrows, uninterrupted)
    feedback = summarize(
        "feedback_switch",
        "paired_restart_state_switched_feedback",
        tuple(),
        fmetrics,
        fhistory,
    )
    summaries.append(feedback)
    flat_rows.extend({"case": "feedback_switch", **r} for r in fmetrics)

    ranked = sorted(
        summaries,
        key=lambda s: (
            bool(s["final_safe_authority"]),
            bool(s["sustained_positive_from_t0p10"]),
            bool(s["current_gate_pass_late"]),
            float(s["final_width_gain_pct"]),
            float(s["peak_width_gain_pct"]),
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None

    feedback_success = (
        feedback["sustained_positive_from_t0p10"]
        and feedback["current_gate_pass_late"]
        and feedback["final_safe_authority"]
        and not feedback["late_reversal_detected"]
    )
    timed_success = any(
        s["sustained_positive_from_t0p10"]
        and s["current_gate_pass_late"]
        and s["final_safe_authority"]
        and not s["late_reversal_detected"]
        for s in summaries
        if s["kind"] != "paired_restart_state_switched_feedback"
    )
    any_safe_point = any(bool(s["safe_gate_pass_any"]) for s in summaries)

    if feedback_success:
        classification = "M3DC1_TCT_PAIRED_RESTART_STATE_SWITCHED_SUSTAINED_SAFE_AUTHORITY"
    elif timed_success:
        classification = "M3DC1_TCT_PAIRED_RESTART_TIMED_WINDOW_SUSTAINED_SAFE_AUTHORITY"
    elif any_safe_point:
        classification = "M3DC1_TCT_PAIRED_RESTART_TRANSIENT_SAFE_AUTHORITY"
    else:
        classification = "M3DC1_TCT_PAIRED_RESTART_NO_SAFE_AUTHORITY_FOUND"

    report = {
        "classification": classification,
        "claim_boundary": (
            "Normalized native M3D-C1 paired-restart differential audit only. "
            "Frozen 0.020% width and 0.10% Jpk gates are unchanged. Controlled "
            "cases are scored only against source=0 twins with identical restart "
            "boundaries. No reactor-scale or experimental claim is implied."
        ),
        "audit": {
            "type": "paired_restart_common_mode_subtracted_tct_control",
            "dt": DT,
            "horizon": HORIZON,
            "horizon_times": list(HORIZON_TIMES),
            "current_source": CURRENT_SOURCE,
            "actuator_amp": ACTUATOR_AMP,
            "profile_width": PROFILE_WIDTH,
            "shoulder_width": SHOULDER_WIDTH,
            "shoulder_separation": SHOULDER_DELTA,
            "frozen_gates": {
                "width_gain_pct_gt": WIDTH_GATE_PCT,
                "Jpk_change_pct_le": JPK_GATE_PCT,
            },
            "differential_definition": (
                "100*(controlled_restarted/paired_source0_restarted - 1) for "
                "relative observables; absolute subtraction for flux/energy."
            ),
            "uninterrupted_source0_role": (
                "restart-bias diagnostic only; never the control acceptance baseline"
            ),
            "restart_transport": (
                "C1.h5 + exactly selected time_nnn.h5; explicit irestart_slice"
            ),
            "single_windows": [list(w) for w in SINGLE_WINDOWS],
            "multi_windows": [[list(w) for w in ws] for ws in MULTI_WINDOWS],
            "feedback_policy": {
                "turn_on_width_pct": TURN_ON_WIDTH_PCT,
                "release_width_pct": RELEASE_WIDTH_PCT,
                "release_dW_pct_per_time": RELEASE_DW_PCT_PER_TIME,
                "jpk_guard_pct": JPK_GUARD_PCT,
                "minimum_on_steps": MIN_ON_STEPS,
                "minimum_off_steps": MIN_OFF_STEPS,
            },
        },
        "best_case": best,
        "feedback_case": feedback,
        "case_summaries": ranked,
    }

    pta.write_csv(OUT / "paired_restart_samples.csv", flat_rows)
    pta.write_csv(
        OUT / "paired_restart_case_summary.csv",
        [{
            "case": s["case"],
            "kind": s["kind"],
            "peak_width_gain_pct": s["peak_width_gain_pct"],
            "peak_time": s["peak_time"],
            "safe_gate_pass_any": s["safe_gate_pass_any"],
            "sustained_positive_from_t0p10": s["sustained_positive_from_t0p10"],
            "current_gate_pass_late": s["current_gate_pass_late"],
            "late_reversal_detected": s["late_reversal_detected"],
            "final_width_gain_pct": s["final_width_gain_pct"],
            "final_Jpk_change_pct": s["final_Jpk_change_pct"],
            "final_safe_authority": s["final_safe_authority"],
            "max_abs_paired_null_restart_bias_width_pct":
                s["max_abs_paired_null_restart_bias_width_pct"],
        } for s in ranked],
    )
    pta.write_csv(OUT / "feedback_command_history.csv", fhistory)
    write_json(OUT / "paired_restart_summary.json", report)
    write_json(OUT / "feedback_command_history.json", fhistory)
    (OUT / "runtime_provenance.txt").write_text(
        f"repo={REPO}\nsource={SRC}\nbaseline={BASE}\nexecutable={EXE}\n"
        f"executable_sha256={pta.sha256_file(EXE)}\nrun_root={RUN_ROOT}\n"
        f"dt={DT}\nhorizon={HORIZON}\ncurrent_source={CURRENT_SOURCE}\n"
        f"profile_width={PROFILE_WIDTH}\nactuator_amp={ACTUATOR_AMP}\n"
        f"width_gate_pct={WIDTH_GATE_PCT}\njpk_gate_pct={JPK_GATE_PCT}\n"
        "comparison=controlled_restart_minus_identically_restarted_source0_twin\n"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

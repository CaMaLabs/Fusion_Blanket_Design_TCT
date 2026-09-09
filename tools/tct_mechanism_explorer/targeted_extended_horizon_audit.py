#!/usr/bin/env python3
"""Targeted extended-horizon native M3D-C1 audit around the W_cd ~= 0.14 optimum.

This audit follows the center-width refinement result without changing its frozen
pass/fail thresholds.  It narrows the center-width grid, extends the physical
horizon to t=0.30, and probes stronger negative center-plus-shoulder current
redistribution amplitudes.

Classification distinguishes:
  * point authority: the frozen width/current gate is crossed at any sample;
  * sustained authority: the width response stays positive from t=0.10 through
    the late horizon while Jpk remains within the frozen current gate;
  * late reversal: an initially positive response becomes non-positive later.

No actuator rescaling, solver-equation change, RF-wave physics, or reactor-scale
claim is introduced by this audit.
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
OUT = REPO / "validation_runs/m3dc1_tct_targeted_extended_horizon"
RUN_ROOT = Path("/tmp/m3dc1_tct_targeted_extended_horizon_runs")

DT = 0.01
HORIZON_STEPS = 30
HORIZON_TIMES = (0.05, 0.10, 0.15, 0.20, 0.30)
SUSTAIN_TIMES = (0.10, 0.15, 0.20, 0.30)
CURRENT_SOURCE = 4

# Frozen around the W_cd=0.14 response found by center_width_refinement_audit.
CENTER_WIDTHS = (0.130, 0.135, 0.1375, 0.140, 0.1425, 0.145, 0.150)
AMPLITUDES = (-0.030, -0.025, -0.0225, -0.020, -0.015, 0.000)

SHOULDER_WIDTH = 0.2805
SHOULDER_DELTA = 0.561
R0 = 10.0
Z0 = 1.0

# Keep the previous audit gates frozen.
WIDTH_GATE_PCT = 0.02
JPK_GATE_PCT = 0.10
ZERO_ABS_TOL = 1e-12

# Repeat the strongest current-safe nonzero case twice from the same frozen
# initial condition.  This is a deterministic repeatability check, not a new
# statistical uncertainty model.
CONFIRMATION_REPEATS = 2


def write_json(path: Path, payload: object) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def amplitude_label(amp: float) -> str:
    if amp > 0:
        return "amp_p" + f"{abs(amp):.4f}".replace(".", "")
    if amp < 0:
        return "amp_m" + f"{abs(amp):.4f}".replace(".", "")
    return "amp_zero"


def width_label(width: float) -> str:
    return "wc_" + f"{width:.4f}".replace(".", "p")


def case_label(width: float, amp: float) -> str:
    return f"{width_label(width)}_{amplitude_label(amp)}"


def set_profile(width: float) -> None:
    nfc.PROFILE_WIDTH = width
    nfc.SHOULDER_WIDTH = SHOULDER_WIDTH
    nfc.SHOULDER_DELTA = SHOULDER_DELTA
    nfc.R0 = R0
    nfc.Z0 = Z0
    nfc.CURRENT_SOURCE = CURRENT_SOURCE


def rows_at(directory: Path) -> list[dict[str, float]]:
    rows = nfc.safe_extract(directory)
    if not rows:
        raise RuntimeError("no extracted rows in " + str(directory))
    for t in HORIZON_TIMES:
        if min(abs(row["time"] - t) for row in rows) > 1e-8:
            raise RuntimeError(
                f"equal-time sample missing in {directory} at t={t}"
            )
    return rows


def zero_delta(
    baseline_rows: list[dict[str, float]],
    zero_rows: list[dict[str, float]],
) -> float:
    maximum = 0.0
    for t in HORIZON_TIMES:
        baseline = nfc.nearest(baseline_rows, t)
        zero = nfc.nearest(zero_rows, t)
        for key in (
            "W_sheet",
            "Jpk",
            "Jint_high",
            "center_abs_current",
            "shoulder_abs_current",
            "Reconnected_Flux",
            "magnetic_energy",
        ):
            maximum = max(maximum, abs(zero[key] - baseline[key]))
    return maximum


def metric_row(
    width: float,
    amp: float,
    t: float,
    row: dict[str, float],
    baseline: dict[str, float],
    zero: dict[str, float],
) -> dict[str, float | str | bool]:
    width_gain = pta.pct(row["W_sheet"], baseline["W_sheet"])
    jpk_change = pta.pct(row["Jpk"], baseline["Jpk"])
    high_j_change = pta.pct(row["Jint_high"], baseline["Jint_high"])
    center_change = pta.pct(
        row["center_abs_current"], baseline["center_abs_current"]
    )
    shoulder_change = pta.pct(
        row["shoulder_abs_current"], baseline["shoulder_abs_current"]
    )
    return {
        "profile": width_label(width),
        "W_cd": width,
        "W_cd_shoulder": SHOULDER_WIDTH,
        "delta_cd": SHOULDER_DELTA,
        "case": case_label(width, amp),
        "source": CURRENT_SOURCE,
        "amp": amp,
        "time": t,
        "width_gain_pct": width_gain,
        "Jpk_change_pct": jpk_change,
        "high_J_change_pct": high_j_change,
        "center_change_pct": center_change,
        "shoulder_change_pct": shoulder_change,
        "mode_width_gain_pct": pta.pct(row["W_sheet"], zero["W_sheet"]),
        "mode_Jpk_change_pct": pta.pct(row["Jpk"], zero["Jpk"]),
        "width_gain_per_amp_pct": width_gain / amp if amp else 0.0,
        "Jpk_change_per_amp_pct": jpk_change / amp if amp else 0.0,
        "delta_Reconnected_Flux": (
            row["Reconnected_Flux"] - baseline["Reconnected_Flux"]
        ),
        "delta_magnetic_energy": (
            row["magnetic_energy"] - baseline["magnetic_energy"]
        ),
        "width_gate_pass": width_gain > WIDTH_GATE_PCT,
        "current_gate_pass": jpk_change <= JPK_GATE_PCT,
        "desired_redistribution_signature": (
            center_change < 0.0
            and shoulder_change > 0.0
            and high_j_change <= 0.0
            and jpk_change <= JPK_GATE_PCT
        ),
        "safe_authority_candidate": (
            width_gain > WIDTH_GATE_PCT and jpk_change <= JPK_GATE_PCT
        ),
    }


def summarize_case(rows: list[dict[str, float | str | bool]]) -> dict:
    rows = sorted(rows, key=lambda r: float(r["time"]))
    peak = max(rows, key=lambda r: float(r["width_gain_pct"]))
    late_rows = [
        r for r in rows
        if any(abs(float(r["time"]) - t) < 1e-12 for t in SUSTAIN_TIMES)
    ]
    early_positive = any(
        float(r["time"]) <= 0.10 + 1e-12
        and float(r["width_gain_pct"]) > 0.0
        for r in rows
    )
    later_nonpositive = any(
        float(r["time"]) >= 0.15 - 1e-12
        and float(r["width_gain_pct"]) <= 0.0
        for r in rows
    )
    current_gate_all = all(bool(r["current_gate_pass"]) for r in rows)
    width_positive_sustained = (
        len(late_rows) == len(SUSTAIN_TIMES)
        and all(float(r["width_gain_pct"]) > 0.0 for r in late_rows)
    )
    width_gate_any = any(bool(r["width_gate_pass"]) for r in rows)
    desired_signature_at_peak = bool(
        peak.get("desired_redistribution_signature", False)
    )
    sustained_safe_authority = (
        width_gate_any
        and width_positive_sustained
        and current_gate_all
        and desired_signature_at_peak
    )
    return {
        "case": rows[0]["case"],
        "profile": rows[0]["profile"],
        "W_cd": rows[0]["W_cd"],
        "amp": rows[0]["amp"],
        "peak": peak,
        "peak_width_gain_pct": float(peak["width_gain_pct"]),
        "peak_time": float(peak["time"]),
        "width_gate_pass_any": width_gate_any,
        "current_gate_pass_all": current_gate_all,
        "desired_redistribution_signature_at_peak": desired_signature_at_peak,
        "sustained_positive_from_t0p10": width_positive_sustained,
        "late_reversal_detected": early_positive and later_nonpositive,
        "sustained_safe_authority": sustained_safe_authority,
        "late_samples": late_rows,
    }


def max_repeat_delta(
    reference_rows: list[dict[str, float | str | bool]],
    repeat_rows: list[dict[str, float | str | bool]],
) -> dict[str, float]:
    keys = (
        "width_gain_pct",
        "Jpk_change_pct",
        "high_J_change_pct",
        "center_change_pct",
        "shoulder_change_pct",
    )
    maxima = {key: 0.0 for key in keys}
    for ref in reference_rows:
        t = float(ref["time"])
        match = min(repeat_rows, key=lambda r: abs(float(r["time"]) - t))
        for key in keys:
            maxima[key] = max(
                maxima[key],
                abs(float(match[key]) - float(ref[key])),
            )
    return maxima


def main() -> int:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if not EXE.exists():
        raise FileNotFoundError(EXE)

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    nfc.RUN_ROOT = RUN_ROOT
    nfc.OUT = OUT
    nfc.DT = DT
    nfc.SEGMENT_STEPS = 1
    nfc.SEGMENT_DURATION = DT

    pta.install_operator()
    nfc.install_current_redistribution_operator()
    pta.build()

    baseline_dir = nfc.write_input(
        "baseline",
        0,
        0.0,
        0,
        0.0,
        DT * HORIZON_STEPS,
        nmax_steps=HORIZON_STEPS,
    )
    print("[targeted-extended] running baseline", flush=True)
    nfc.execute(baseline_dir)
    baseline_rows = rows_at(baseline_dir)

    all_rows: list[dict[str, float | str | bool]] = []
    raw_rows: list[dict[str, float | str]] = []
    zero_results: dict[str, dict] = {}

    for width in CENTER_WIDTHS:
        set_profile(width)
        profile = width_label(width)

        zero_dir = nfc.write_input(
            f"{profile}_zero",
            CURRENT_SOURCE,
            0.0,
            0,
            0.0,
            DT * HORIZON_STEPS,
            nmax_steps=HORIZON_STEPS,
        )
        print(f"[targeted-extended] running {profile}_zero", flush=True)
        nfc.execute(zero_dir)
        zero_rows = rows_at(zero_dir)

        null_max = zero_delta(baseline_rows, zero_rows)
        zero_results[profile] = {
            "max_abs_metric_delta": null_max,
            "tolerance": ZERO_ABS_TOL,
            "pass": null_max <= ZERO_ABS_TOL,
        }

        for amp in AMPLITUDES:
            label = case_label(width, amp)
            case_dir = nfc.write_input(
                label,
                CURRENT_SOURCE,
                amp,
                0,
                0.0,
                DT * HORIZON_STEPS,
                nmax_steps=HORIZON_STEPS,
            )
            print(f"[targeted-extended] running {label}", flush=True)
            nfc.execute(case_dir)
            case_rows = rows_at(case_dir)

            for t in HORIZON_TIMES:
                row = nfc.nearest(case_rows, t)
                baseline = nfc.nearest(baseline_rows, t)
                zero = nfc.nearest(zero_rows, t)
                metrics = metric_row(width, amp, t, row, baseline, zero)
                all_rows.append(metrics)
                raw_rows.append({
                    "profile": profile,
                    "W_cd": width,
                    "W_cd_shoulder": SHOULDER_WIDTH,
                    "delta_cd": SHOULDER_DELTA,
                    "amp": amp,
                    "time": t,
                    "W_sheet": row["W_sheet"],
                    "Jpk": row["Jpk"],
                    "Jint_high": row["Jint_high"],
                    "center_abs_current": row["center_abs_current"],
                    "shoulder_abs_current": row["shoulder_abs_current"],
                    "Reconnected_Flux": row["Reconnected_Flux"],
                    "magnetic_energy": row["magnetic_energy"],
                })

    grouped: dict[str, list[dict[str, float | str | bool]]] = {}
    for row in all_rows:
        grouped.setdefault(str(row["case"]), []).append(row)

    case_summaries = [
        summarize_case(rows)
        for rows in grouped.values()
        if abs(float(rows[0]["amp"])) > 1e-15
    ]
    case_summaries.sort(
        key=lambda r: (
            bool(r["sustained_safe_authority"]),
            bool(r["width_gate_pass_any"]),
            float(r["peak_width_gain_pct"]),
        ),
        reverse=True,
    )

    point_candidates = [
        r for r in all_rows
        if abs(float(r["amp"])) > 1e-15
        and bool(r["safe_authority_candidate"])
        and zero_results[str(r["profile"])]["pass"]
    ]
    best_point = max(
        point_candidates,
        key=lambda r: float(r["width_gain_pct"]),
        default=None,
    )

    sustained_candidates = [
        r for r in case_summaries
        if bool(r["sustained_safe_authority"])
        and zero_results[str(r["profile"])]["pass"]
    ]
    best_sustained = max(
        sustained_candidates,
        key=lambda r: float(r["peak_width_gain_pct"]),
        default=None,
    )

    # Strongest current-safe nonzero case is re-run from the frozen initial
    # condition even when it narrowly misses the width gate.
    confirmation_target = max(
        (
            r for r in case_summaries
            if bool(r["current_gate_pass_all"])
            and zero_results[str(r["profile"])]["pass"]
        ),
        key=lambda r: float(r["peak_width_gain_pct"]),
        default=None,
    )
    confirmation = {
        "target": confirmation_target,
        "repeat_count": 0,
        "repeats": [],
        "max_abs_repeat_delta": None,
    }

    if confirmation_target is not None:
        width = float(confirmation_target["W_cd"])
        amp = float(confirmation_target["amp"])
        set_profile(width)
        profile = width_label(width)

        zero_dir = RUN_ROOT / f"{profile}_zero"
        zero_rows = rows_at(zero_dir)
        reference_rows = grouped[str(confirmation_target["case"])]

        overall = {
            "width_gain_pct": 0.0,
            "Jpk_change_pct": 0.0,
            "high_J_change_pct": 0.0,
            "center_change_pct": 0.0,
            "shoulder_change_pct": 0.0,
        }
        for repeat in range(1, CONFIRMATION_REPEATS + 1):
            name = f"confirm_{repeat:02d}_{case_label(width, amp)}"
            repeat_dir = nfc.write_input(
                name,
                CURRENT_SOURCE,
                amp,
                0,
                0.0,
                DT * HORIZON_STEPS,
                nmax_steps=HORIZON_STEPS,
            )
            print(f"[targeted-extended] running {name}", flush=True)
            nfc.execute(repeat_dir)
            run_rows = rows_at(repeat_dir)
            metrics_rows = []
            for t in HORIZON_TIMES:
                row = nfc.nearest(run_rows, t)
                baseline = nfc.nearest(baseline_rows, t)
                zero = nfc.nearest(zero_rows, t)
                metrics_rows.append(
                    metric_row(width, amp, t, row, baseline, zero)
                )
            delta = max_repeat_delta(reference_rows, metrics_rows)
            for key, value in delta.items():
                overall[key] = max(overall[key], value)
            confirmation["repeats"].append({
                "repeat": repeat,
                "directory": str(repeat_dir),
                "max_abs_delta_vs_grid_run": delta,
                "summary": summarize_case(metrics_rows),
            })

        confirmation["repeat_count"] = CONFIRMATION_REPEATS
        confirmation["max_abs_repeat_delta"] = overall

    if best_sustained is not None:
        classification = (
            "M3DC1_TCT_TARGETED_EXTENDED_SUSTAINED_SAFE_AUTHORITY"
        )
    elif best_point is not None:
        classification = (
            "M3DC1_TCT_TARGETED_EXTENDED_TRANSIENT_SAFE_AUTHORITY"
        )
    else:
        classification = (
            "M3DC1_TCT_TARGETED_EXTENDED_NO_SAFE_AUTHORITY_FOUND"
        )

    report = {
        "classification": classification,
        "claim_boundary": (
            "Native normalized M3D-C1 targeted center-width/amplitude audit "
            "only. The frozen 0.02% width and 0.10% Jpk gates are unchanged. "
            "No reactor stabilization, RF wave physics, lithium dimensional "
            "transfer, or experimental validation is implied."
        ),
        "audit": {
            "type": (
                "equal_time_targeted_center_width_amplitude_extended_horizon"
            ),
            "dt": DT,
            "ntimemax": HORIZON_STEPS,
            "ntimepr": 1,
            "source": CURRENT_SOURCE,
            "center_widths": list(CENTER_WIDTHS),
            "amplitudes": list(AMPLITUDES),
            "horizon_times": list(HORIZON_TIMES),
            "sustain_times": list(SUSTAIN_TIMES),
            "fixed_profile": {
                "R_0cd": R0,
                "Z_0cd": Z0,
                "W_cd_shoulder": SHOULDER_WIDTH,
                "delta_cd": SHOULDER_DELTA,
            },
            "gates": {
                "width_threshold_pct": WIDTH_GATE_PCT,
                "Jpk_threshold_pct": JPK_GATE_PCT,
                "zero_equivalence_tolerance": ZERO_ABS_TOL,
            },
            "sustained_definition": (
                "A nonzero case must cross the frozen width gate at least "
                "once, remain width-positive at t=0.10,0.15,0.20,0.30, keep "
                "Jpk <= +0.10% at every sampled time, show the desired "
                "center-down/shoulder-up/high-J-nonincreasing signature at "
                "its width peak, and pass its same-profile zero null."
            ),
        },
        "zero_equivalence": zero_results,
        "best_point_candidate": best_point,
        "best_sustained_candidate": best_sustained,
        "case_summaries": case_summaries,
        "confirmation": confirmation,
        "cases": all_rows,
    }

    pta.write_csv(OUT / "targeted_extended_horizon.csv", all_rows)
    pta.write_csv(OUT / "targeted_extended_horizon_raw.csv", raw_rows)

    summary_rows = []
    for item in case_summaries:
        summary_rows.append({
            "case": item["case"],
            "W_cd": item["W_cd"],
            "amp": item["amp"],
            "peak_width_gain_pct": item["peak_width_gain_pct"],
            "peak_time": item["peak_time"],
            "width_gate_pass_any": item["width_gate_pass_any"],
            "current_gate_pass_all": item["current_gate_pass_all"],
            "desired_redistribution_signature_at_peak": (
                item["desired_redistribution_signature_at_peak"]
            ),
            "sustained_positive_from_t0p10": (
                item["sustained_positive_from_t0p10"]
            ),
            "late_reversal_detected": item["late_reversal_detected"],
            "sustained_safe_authority": item["sustained_safe_authority"],
        })
    pta.write_csv(OUT / "targeted_case_summary.csv", summary_rows)

    write_json(OUT / "targeted_extended_horizon_summary.json", report)
    (OUT / "runtime_provenance.txt").write_text(
        "repo={}\nsource={}\nbaseline={}\nexecutable={}\n"
        "executable_sha256={}\nrun_root={}\n"
        "dt={}\nntimemax={}\nntimepr=1\nsource={}\n"
        "center_widths={}\namplitudes={}\nhorizon_times={}\n"
        "sustain_times={}\nwidth_gate_pct={}\njpk_gate_pct={}\n"
        "shoulder_width={}\nshoulder_separation={}\n"
        "confirmation_repeats={}\n".format(
            REPO,
            SRC,
            BASE,
            EXE,
            pta.sha256_file(EXE),
            RUN_ROOT,
            DT,
            HORIZON_STEPS,
            CURRENT_SOURCE,
            list(CENTER_WIDTHS),
            list(AMPLITUDES),
            list(HORIZON_TIMES),
            list(SUSTAIN_TIMES),
            WIDTH_GATE_PCT,
            JPK_GATE_PCT,
            SHOULDER_WIDTH,
            SHOULDER_DELTA,
            CONFIRMATION_REPEATS,
        )
    )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

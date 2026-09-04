#!/usr/bin/env python3
"""Multi-horizon signed transfer audit for the native TCT current operator.

The same frozen initial condition and signed amplitude set are run to a common
0.10-time-unit horizon.  Metrics are sampled at 0.01, 0.02, 0.05, and 0.10
to separate immediate profile shaping from delayed Jpk dynamics.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Keep this audit independent of the longer feedback-controller defaults.
os.environ["TCT_FEEDBACK_DT"] = "0.01"
os.environ["TCT_FEEDBACK_SEGMENT_STEPS"] = "1"
os.environ["TCT_FEEDBACK_MAX_SEGMENTS"] = "10"

import native_feedback_controller_audit as nfc
import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
BUILD = SRC / "build-ubuntu-2d"
EXE = BUILD / "unstructured/m3dc1_2d"
OUT = REPO / "validation_runs/m3dc1_tct_signed_current_transfer_multi_horizon"
RUN_ROOT = Path("/tmp/m3dc1_tct_signed_current_transfer_multi_horizon_runs")

DT = 0.01
HORIZON_STEPS = 10
HORIZON_TIMES = (0.01, 0.02, 0.05, 0.10)
CURRENT_SOURCE = 4
AMPLITUDES = (-0.010, -0.005, -0.002, 0.000, 0.002, 0.005)
R0 = 10.0
Z0 = 1.0
PROFILE_WIDTH = 0.2805
SHOULDER_WIDTH = 0.2805
SHOULDER_DELTA = 0.561
WIDTH_GATE_PCT = 0.02
JPK_GATE_PCT = 0.10
JPK_NOISE_PCT = 1e-6


def write_json(path: Path, payload: object) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def amplitude_label(amp: float) -> str:
    if amp > 0:
        return "amp_p" + f"{abs(amp):.3f}".replace(".", "")
    if amp < 0:
        return "amp_m" + f"{abs(amp):.3f}".replace(".", "")
    return "amp_zero"


def rows_at(d: Path) -> list[dict[str, float]]:
    rows = nfc.safe_extract(d)
    if not rows:
        raise RuntimeError("no extracted rows in " + str(d))
    for t in HORIZON_TIMES:
        if min(abs(row["time"] - t) for row in rows) > 1e-8:
            raise RuntimeError(
                "equal-time sample missing in {} at t={}".format(d, t)
            )
    return rows


def metric_row(
    label: str,
    amp: float,
    t: float,
    row: dict[str, float],
    baseline: dict[str, float],
    zero: dict[str, float],
) -> dict[str, float | str | bool]:
    width = pta.pct(row["W_sheet"], baseline["W_sheet"])
    jpk = pta.pct(row["Jpk"], baseline["Jpk"])
    mode_width = pta.pct(row["W_sheet"], zero["W_sheet"])
    mode_jpk = pta.pct(row["Jpk"], zero["Jpk"])
    return {
        "case": label,
        "source": CURRENT_SOURCE,
        "amp": amp,
        "time": t,
        "width_gain_pct": width,
        "Jpk_change_pct": jpk,
        "high_J_change_pct": pta.pct(
            row["Jint_high"], baseline["Jint_high"]
        ),
        "center_change_pct": pta.pct(
            row["center_abs_current"], baseline["center_abs_current"]
        ),
        "shoulder_change_pct": pta.pct(
            row["shoulder_abs_current"], baseline["shoulder_abs_current"]
        ),
        "mode_width_gain_pct": mode_width,
        "mode_Jpk_change_pct": mode_jpk,
        "delta_Reconnected_Flux": (
            row["Reconnected_Flux"] - baseline["Reconnected_Flux"]
        ),
        "delta_magnetic_energy": (
            row["magnetic_energy"] - baseline["magnetic_energy"]
        ),
        "width_gate_pass": width > WIDTH_GATE_PCT,
        "current_gate_pass": jpk <= JPK_GATE_PCT,
        "safe_authority_candidate": (
            width > WIDTH_GATE_PCT and jpk <= JPK_GATE_PCT
        ),
    }


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
        "baseline", 0, 0.0, 0, 0.0, DT * HORIZON_STEPS,
        nmax_steps=HORIZON_STEPS,
    )
    print("[multi-horizon] running baseline", flush=True)
    nfc.execute(baseline_dir)
    baseline_rows = rows_at(baseline_dir)

    zero_dir = nfc.write_input(
        "zero_source4", CURRENT_SOURCE, 0.0, 0, 0.0, DT * HORIZON_STEPS,
        nmax_steps=HORIZON_STEPS,
    )
    print("[multi-horizon] running zero_source4", flush=True)
    nfc.execute(zero_dir)
    zero_rows = rows_at(zero_dir)

    zero_max = 0.0
    for t in HORIZON_TIMES:
        b = nfc.nearest(baseline_rows, t)
        z = nfc.nearest(zero_rows, t)
        for key in (
            "W_sheet", "Jpk", "Jint_high", "center_abs_current",
            "shoulder_abs_current", "Reconnected_Flux", "magnetic_energy",
        ):
            zero_max = max(zero_max, abs(z[key] - b[key]))

    all_rows: list[dict[str, float | str | bool]] = []
    raw_rows: list[dict[str, float | str]] = []
    latency: dict[str, float | None] = {}
    per_case: dict[str, list[dict[str, float | str | bool]]] = {}

    for amp in AMPLITUDES:
        label = amplitude_label(amp)
        d = nfc.write_input(
            label, CURRENT_SOURCE, amp, 0, 0.0, DT * HORIZON_STEPS,
            nmax_steps=HORIZON_STEPS,
        )
        print("[multi-horizon] running " + label, flush=True)
        nfc.execute(d)
        case_rows = rows_at(d)
        case_metrics = []
        for t in HORIZON_TIMES:
            row = nfc.nearest(case_rows, t)
            baseline = nfc.nearest(baseline_rows, t)
            zero = nfc.nearest(zero_rows, t)
            metrics = metric_row(label, amp, t, row, baseline, zero)
            all_rows.append(metrics)
            case_metrics.append(metrics)
            raw_rows.append({
                "case": label,
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
        per_case[label] = case_metrics
        responsive = [
            float(r["time"]) for r in case_metrics
            if abs(float(r["Jpk_change_pct"])) > JPK_NOISE_PCT
        ]
        latency[label] = min(responsive) if responsive else None

    candidates = [
        r for r in all_rows if bool(r["safe_authority_candidate"])
    ]
    best = max(
        candidates,
        key=lambda r: float(r["width_gain_pct"]),
        default=None,
    )
    classification = (
        "M3DC1_SIGNED_CURRENT_TRANSFER_MULTI_HORIZON_SAFE_CANDIDATE"
        if best is not None
        else "M3DC1_SIGNED_CURRENT_TRANSFER_MULTI_HORIZON_NO_SAFE_SIGN_FOUND"
    )

    peak_by_case = {}
    for label, case_metrics in per_case.items():
        peak_width = max(case_metrics, key=lambda r: float(r["width_gain_pct"]))
        peak_jpk = max(case_metrics, key=lambda r: float(r["Jpk_change_pct"]))
        peak_by_case[label] = {
            "amp": peak_width["amp"],
            "peak_width_gain_pct": peak_width["width_gain_pct"],
            "peak_width_time": peak_width["time"],
            "max_Jpk_change_pct": peak_jpk["Jpk_change_pct"],
            "max_Jpk_time": peak_jpk["time"],
            "Jpk_response_latency": latency[label],
        }

    report = {
        "classification": classification,
        "claim_boundary": (
            "Native normalized M3D-C1 multi-horizon signed current-transfer "
            "audit only; no reactor stabilization, RF wave physics, lithium "
            "dimensional transfer, or experimental validation is implied."
        ),
        "audit": {
            "type": "multi_horizon_equal_time_signed_current_transfer",
            "dt": DT,
            "ntimemax": HORIZON_STEPS,
            "ntimepr": 1,
            "source": CURRENT_SOURCE,
            "amplitudes": list(AMPLITUDES),
            "horizon_times": list(HORIZON_TIMES),
            "geometry": {
                "R_0cd": R0,
                "Z_0cd": Z0,
                "W_cd": PROFILE_WIDTH,
                "W_cd_shoulder": SHOULDER_WIDTH,
                "delta_cd": SHOULDER_DELTA,
            },
            "gates": {
                "width_threshold_pct": WIDTH_GATE_PCT,
                "Jpk_threshold_pct": JPK_GATE_PCT,
                "Jpk_noise_pct": JPK_NOISE_PCT,
            },
            "comparison": (
                "Every amplitude starts from the same frozen initial condition "
                "and is compared at equal physical times against native source=0 "
                "and source=4, amp=0 trajectories."
            ),
        },
        "zero_equivalence": {
            "comparison": "source=4, amp=0 versus source=0 baseline",
            "max_abs_metric_delta": zero_max,
            "tolerance": 1e-12,
            "pass": zero_max <= 1e-12,
        },
        "best_candidate": best,
        "response_latency_by_case": latency,
        "peak_by_case": peak_by_case,
        "cases": all_rows,
    }

    pta.write_csv(OUT / "signed_current_transfer_multi_horizon.csv", all_rows)
    pta.write_csv(OUT / "signed_current_transfer_multi_horizon_raw.csv", raw_rows)
    write_json(OUT / "signed_current_transfer_multi_horizon_summary.json", report)
    (OUT / "runtime_provenance.txt").write_text(
        "repo={}\nsource={}\nbaseline={}\nexecutable={}\n"
        "executable_sha256={}\nrun_root={}\n"
        "dt={}\nntimemax={}\nntimepr=1\n"
        "icd_source={}\namplitudes={}\nhorizon_times={}\n"
        "profile_width={}\nshoulder_width={}\nshoulder_separation={}\n".format(
            REPO, SRC, BASE, EXE, pta.sha256_file(EXE), RUN_ROOT,
            DT, HORIZON_STEPS, CURRENT_SOURCE, list(AMPLITUDES),
            list(HORIZON_TIMES), PROFILE_WIDTH, SHOULDER_WIDTH,
            SHOULDER_DELTA,
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

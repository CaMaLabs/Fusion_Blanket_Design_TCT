#!/usr/bin/env python3
"""Equal-time signed transfer-function audit for the native TCT current operator.

Each amplitude starts from the same frozen baseline and runs for one native
output step.  This maps sign and magnitude before another closed-loop policy
is attempted.  It does not modify eta, nu, GEM epsilon, mesh, equilibrium,
solver physics, or arbitrary Fortran terms.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

# Force a fixed one-step audit before importing the shared native runner.
os.environ["TCT_FEEDBACK_DT"] = "0.01"
os.environ["TCT_FEEDBACK_SEGMENT_STEPS"] = "1"
os.environ["TCT_FEEDBACK_MAX_SEGMENTS"] = "1"

import native_feedback_controller_audit as nfc
import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
BUILD = SRC / "build-ubuntu-2d"
EXE = BUILD / "unstructured/m3dc1_2d"
OUT = REPO / "validation_runs/m3dc1_tct_signed_current_transfer"
RUN_ROOT = Path("/tmp/m3dc1_tct_signed_current_transfer_runs")

DT = 0.01
NMAX_STEPS = 1
CURRENT_SOURCE = 4
AMPLITUDES = (-0.010, -0.005, -0.002, 0.000, 0.002, 0.005)
R0 = 10.0
Z0 = 1.0
PROFILE_WIDTH = 0.2805
SHOULDER_WIDTH = 0.2805
SHOULDER_DELTA = 0.561
AUTHORITY_WIDTH_THRESHOLD_PCT = 0.02
AUTHORITY_JPK_THRESHOLD_PCT = 0.10


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


def extract_at(d: Path, target_time: float) -> dict[str, float]:
    rows = nfc.safe_extract(d)
    if not rows:
        raise RuntimeError("no extracted rows in " + str(d))
    row = nfc.nearest(rows, target_time)
    if abs(row["time"] - target_time) > 1e-8:
        raise RuntimeError(
            "equal-time sample missing in {}: requested {}, got {}".format(
                d, target_time, row["time"]
            )
        )
    return row


def metric_row(
    label: str,
    amp: float,
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
        "time": row["time"],
        "width_gain_pct": width,
        "Jpk_change_pct": jpk,
        "high_J_change_pct": pta.pct(row["Jint_high"], baseline["Jint_high"]),
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
        "width_gate_pass": width > AUTHORITY_WIDTH_THRESHOLD_PCT,
        "current_gate_pass": jpk <= AUTHORITY_JPK_THRESHOLD_PCT,
        "safe_authority_candidate": (
            width > AUTHORITY_WIDTH_THRESHOLD_PCT
            and jpk <= AUTHORITY_JPK_THRESHOLD_PCT
        ),
    }


def main() -> int:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if not EXE.exists():
        raise FileNotFoundError(EXE)

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    # Point shared helpers at this audit's isolated artifacts.
    nfc.RUN_ROOT = RUN_ROOT
    nfc.OUT = OUT
    nfc.DT = DT
    nfc.SEGMENT_STEPS = 1
    nfc.SEGMENT_DURATION = DT

    pta.install_operator()
    nfc.install_current_redistribution_operator()
    pta.build()

    baseline_dir = nfc.write_input(
        "baseline", 0, 0.0, 0, 0.0, DT, nmax_steps=NMAX_STEPS
    )
    print("[signed-transfer] running baseline", flush=True)
    nfc.execute(baseline_dir)
    baseline = extract_at(baseline_dir, DT)

    zero_dir = nfc.write_input(
        "zero_source4", CURRENT_SOURCE, 0.0, 0, 0.0, DT, nmax_steps=NMAX_STEPS
    )
    print("[signed-transfer] running zero_source4", flush=True)
    nfc.execute(zero_dir)
    zero = extract_at(zero_dir, DT)

    zero_max = 0.0
    for key in (
        "W_sheet", "Jpk", "Jint_high", "center_abs_current",
        "shoulder_abs_current", "Reconnected_Flux", "magnetic_energy",
    ):
        zero_max = max(zero_max, abs(zero[key] - baseline[key]))

    rows: list[dict[str, float | str | bool]] = []
    raw_rows: list[dict[str, float | str]] = []
    for amp in AMPLITUDES:
        label = amplitude_label(amp)
        d = nfc.write_input(
            label, CURRENT_SOURCE, amp, 0, 0.0, DT, nmax_steps=NMAX_STEPS
        )
        print("[signed-transfer] running " + label, flush=True)
        nfc.execute(d)
        row = extract_at(d, DT)
        rows.append(metric_row(label, amp, row, baseline, zero))
        raw_rows.append({
            "case": label,
            "amp": amp,
            "time": row["time"],
            "W_sheet": row["W_sheet"],
            "Jpk": row["Jpk"],
            "Jint_high": row["Jint_high"],
            "center_abs_current": row["center_abs_current"],
            "shoulder_abs_current": row["shoulder_abs_current"],
            "Reconnected_Flux": row["Reconnected_Flux"],
            "magnetic_energy": row["magnetic_energy"],
        })

    candidates = [
        r for r in rows if bool(r["safe_authority_candidate"])
    ]
    best = max(
        candidates,
        key=lambda r: float(r["width_gain_pct"]),
        default=None,
    )
    classification = (
        "M3DC1_SIGNED_CURRENT_TRANSFER_SAFE_AUTHORITY_CANDIDATE"
        if best is not None
        else "M3DC1_SIGNED_CURRENT_TRANSFER_NO_SAFE_SIGN_FOUND"
    )
    report = {
        "classification": classification,
        "claim_boundary": (
            "Native normalized M3D-C1 equal-time signed current-transfer "
            "audit only; no reactor stabilization, RF wave physics, lithium "
            "dimensional transfer, or experimental validation is implied."
        ),
        "audit": {
            "type": "equal_time_signed_current_transfer",
            "dt": DT,
            "ntimemax": NMAX_STEPS,
            "ntimepr": 1,
            "source": CURRENT_SOURCE,
            "amplitudes": list(AMPLITUDES),
            "geometry": {
                "R_0cd": R0,
                "Z_0cd": Z0,
                "W_cd": PROFILE_WIDTH,
                "W_cd_shoulder": SHOULDER_WIDTH,
                "delta_cd": SHOULDER_DELTA,
            },
            "gates": {
                "width_threshold_pct": AUTHORITY_WIDTH_THRESHOLD_PCT,
                "Jpk_threshold_pct": AUTHORITY_JPK_THRESHOLD_PCT,
            },
            "comparison": (
                "Each case starts from the same frozen initial condition and "
                "is compared at physical time t=0.01 against native source=0 "
                "baseline and source=4, amp=0 null."
            ),
        },
        "zero_equivalence": {
            "comparison": "source=4, amp=0 versus source=0 baseline at t=0.01",
            "max_abs_metric_delta": zero_max,
            "tolerance": 1e-12,
            "pass": zero_max <= 1e-12,
        },
        "best_candidate": best,
        "cases": rows,
    }
    pta.write_csv(OUT / "signed_current_transfer.csv", rows)
    pta.write_csv(OUT / "signed_current_transfer_raw.csv", raw_rows)
    write_json(OUT / "signed_current_transfer_summary.json", report)
    (OUT / "runtime_provenance.txt").write_text(
        "repo={}\nsource={}\nbaseline={}\nexecutable={}\n"
        "executable_sha256={}\nrun_root={}\n"
        "dt={}\nntimemax={}\nntimepr=1\n"
        "icd_source={}\n"
        "amplitudes={}\n"
        "profile_width={}\nshoulder_width={}\nshoulder_separation={}\n".format(
            REPO, SRC, BASE, EXE, pta.sha256_file(EXE), RUN_ROOT,
            DT, NMAX_STEPS, CURRENT_SOURCE, list(AMPLITUDES),
            PROFILE_WIDTH, SHOULDER_WIDTH, SHOULDER_DELTA,
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Bounded normalized-native M3D-C1 signed amplitude-response audit.

Tests the unvalidated assumption that observable changes scale with the
icd_source=4 command. This does not establish delivered physical current,
controller authority, segmented-electrode fidelity or TCT stabilization.
"""
import datetime
import json
import math
import pathlib
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0, str(repo / "tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta

out = repo / "validation_runs/m3dc1_tct_native_amplitude_response_127"
native.OUT = out
native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_amplitude_response_127_runs")
out.mkdir(parents=True, exist_ok=True)
metrics = ("W_sheet", "Jpk", "Jint_high", "Reconnected_Flux",
           "magnetic_energy", "center_abs_current", "shoulder_abs_current")
report = {
    "schema_version": 1,
    "parent_result_job_id": "20261029-126-native-current-drive-inwindow-gate-contrast",
    "classification": "M3DC1_NATIVE_CURRENT_DRIVE_AMPLITUDE_RESPONSE_UNRESOLVED",
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1",
    "shot_ids": [],
    "dt": 0.01,
    "steps": 3,
    "source_mode": 4,
    "gate_window": [0.0, 0.04],
    "amplitudes": [-0.005, -0.0025, 0.0, 0.0025, 0.005],
    "zero_equivalence_tolerance": 1e-12,
    "source_profile_and_physics_unchanged": True,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Normalized-native M3D-C1 command-response diagnostic only; no validated source-current calibration, shot handoff, causal segmented-TCT control, p-B11 or net-power claim.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
try:
    if abs(native.DT - 0.01) > 1e-12:
        raise RuntimeError("DT_PREREQUISITE_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    configs = (
        ("baseline", 0, 0.0),
        ("same_mode_zero", 4, 0.0),
        ("half_negative", 4, -0.0025),
        ("half_positive", 4, 0.0025),
        ("full_negative", 4, -0.005),
        ("full_positive", 4, 0.005),
    )
    runs = {}
    for name, source, amp in configs:
        directory = native.write_input(name, source, amp, 0, 0.0, 0.04, nmax_steps=3)
        print("[amplitude-response] running " + name, flush=True)
        native.execute(directory)
        rows = native.safe_extract(directory)
        if len(rows) < 4:
            raise RuntimeError("INSUFFICIENT_OUTPUT_FRAMES: " + name)
        runs[name] = rows
    base = runs["baseline"]
    zero = runs["same_mode_zero"]
    for name, rows in runs.items():
        if len(rows) != len(base):
            raise RuntimeError("FRAME_COUNT_MISMATCH: " + name)
        for a, b in zip(rows, base):
            if abs(float(a["time"]) - float(b["time"])) > 1e-8:
                raise RuntimeError("TIME_GRID_MISMATCH: " + name)
            if not all(math.isfinite(float(a[k])) for k in metrics):
                raise RuntimeError("NONFINITE_OBSERVABLE: " + name)
    report["observed_time_samples"] = [float(row["time"]) for row in base]
    report["run_frames"] = {name: len(rows) for name, rows in runs.items()}
    zero_delta = max(abs(float(a[k]) - float(b[k]))
                     for a, b in zip(zero, base) for k in metrics)
    report["zero_equivalence"] = {
        "max_abs_metric_delta": zero_delta,
        "pass": zero_delta <= 1e-12,
    }
    cases = ("half_negative", "half_positive", "full_negative", "full_positive")
    signed = {
        name: {
            k: [float(a[k]) - float(z[k]) for a, z in zip(runs[name], zero)]
            for k in metrics
        }
        for name in cases
    }
    report["signed_deltas_vs_same_mode_zero"] = signed
    report["max_abs_delta_vs_zero"] = {
        name: {k: max(abs(v) for v in signed[name][k]) for k in metrics}
        for name in cases
    }
    response = any(
        report["max_abs_delta_vs_zero"][name][k] > 1e-12
        for name in cases for k in metrics
    )
    report["source_response_observed"] = response
    report["scaling_diagnostics"] = {}
    for k in metrics:
        hpos, fpos = signed["half_positive"][k], signed["full_positive"][k]
        hneg, fneg = signed["half_negative"][k], signed["full_negative"][k]
        hp, fp = max(map(abs, hpos)), max(map(abs, fpos))
        hn, fn = max(map(abs, hneg)), max(map(abs, fneg))
        report["scaling_diagnostics"][k] = {
            "full_to_half_max_envelope_ratio_positive": fp / hp if hp > 1e-10 else None,
            "full_to_half_max_envelope_ratio_negative": fn / hn if hn > 1e-10 else None,
            "max_abs_full_odd_symmetry_residual": max(abs(a+b) for a,b in zip(fpos, fneg)),
            "max_abs_half_odd_symmetry_residual": max(abs(a+b) for a,b in zip(hpos, hneg)),
            "max_abs_full_positive_minus_twice_half": max(abs(a-2*b) for a,b in zip(fpos,hpos)),
            "max_abs_full_negative_minus_twice_half": max(abs(a-2*b) for a,b in zip(fneg,hneg)),
        }
    if not report["zero_equivalence"]["pass"]:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_ZERO_EQUIVALENCE_FAILED"
    elif response:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_AMPLITUDE_RESPONSE_DIAGNOSTIC_COMPLETE"
    else:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_AMPLITUDE_NO_RESPONSE"
    report["interpretation"] = (
        "Matched signed half/full command test over an unchanged three-step native horizon. "
        "Ratios are maxima of potentially different frames and are not linearity proof; "
        "rounding of extracted observables and absence of a directly measured injected source "
        "prevent quantitative actuator calibration. No physical TCT stabilization claim."
    )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_AMPLITUDE_DIAGNOSTIC_PIPELINE_BLOCKED"
path = out / "native_amplitude_summary.json"
tmp = out / "native_amplitude_summary.json.tmp"
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(path)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

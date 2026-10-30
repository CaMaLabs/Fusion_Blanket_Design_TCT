#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Native solver observable audit after fixed-fine-dt jphi scaling test 138.

Replace one jphi/e[2]-only response surrogate with solver-native W_sheet,
Jpk, high-J, reconnection and energy observables. No controller-in-loop,
physical-current calibration, source change, or solver-physics modification.
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

job_id = "20261030-139-native-current-drive-fine-dt-native-observables"
parent_id = "20261030-138-native-current-drive-fine-dt-amplitude-linearity"
out = repo / "validation_runs/m3dc1_tct_native_observables_139"
out.mkdir(parents=True, exist_ok=True)
metrics = ("W_sheet", "Jpk", "Jint_high", "Reconnected_Flux",
           "magnetic_energy", "center_abs_current", "shoulder_abs_current")
report = {
    "schema_version": 1, "job_id": job_id, "parent_result_job_id": parent_id,
    "classification": "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_NATIVE_OBSERVABLES_UNRESOLVED",
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "dt": 0.000625, "steps": 48,
    "matched_times": [0.01, 0.02, 0.03],
    "source_mode": 4, "source_gate": [0.0, 0.04],
    "amplitudes": [-0.01, -0.005, 0.0, 0.005, 0.01],
    "zero_equivalence_tolerance": 1e-12,
    "expected_parent_summary_sha256": "c4e61b347b974db6fa379ca70abc0a50bdf6d3ee188dc9361ccf4611c673bd46",
    "expected_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Fixed-dt normalized-native M3D-C1 native observable changes under open-loop source commands. Extraction precision is limited. Frozen width/Jpk comparisons are diagnostic, not controller-in-loop pass. No temporal convergence, calibrated physical injected current, segmented-electrode authority, experimental shot handoff, causal TCT stabilization, p-B11 fidelity, ignition or net power.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    parent_path = repo / "validation_runs/m3dc1_tct_native_amplitude_138/fine_dt_amplitude_linearity_summary.json"
    if not parent_path.is_file() or pta.sha256_file(parent_path) != report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("classification") != "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_AMPLITUDE_LINEARITY_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_CHANGED")
    if parent.get("zero_equivalence", {}).get("pass") is not True:
        raise RuntimeError("PARENT_ZERO_EQUIVALENCE_NOT_PASSED")
    if parent.get("amplitude_linearity_established") is not False:
        raise RuntimeError("PARENT_AMPLITUDE_LINEARITY_STATUS_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_executable_sha256"]:
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")

    native.DT = report["dt"]
    native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_observables_139")
    native.OUT = out
    configs = [
        ("baseline", 0, 0.0), ("same_mode_zero", 4, 0.0),
        ("neg_nominal", 4, -0.005), ("neg_double", 4, -0.01),
        ("pos_nominal", 4, 0.005), ("pos_double", 4, 0.01),
    ]
    runs = {}
    for name, mode, amp in configs:
        d = native.write_input(name, mode, amp, 0, 0.0, 0.04, nmax_steps=48)
        print("[fine-dt-native-observables] " + name, flush=True)
        native.execute(d)
        runs[name] = native.safe_extract(d)

    expected_times = [i * report["dt"] for i in range(49)]
    for name, rows in runs.items():
        if len(rows) != 49:
            raise RuntimeError("FRAME_COUNT_MISMATCH:" + name)
        if any(abs(float(r["time"]) - t) > 1e-8 for r, t in zip(rows, expected_times)):
            raise RuntimeError("TIME_GRID_MISMATCH:" + name)
        if any(not math.isfinite(float(r[k])) for r in rows for k in metrics):
            raise RuntimeError("NONFINITE_NATIVE_OBSERVABLE:" + name)

    zero_max = max(abs(float(a[k]) - float(b[k]))
                   for a,b in zip(runs["same_mode_zero"], runs["baseline"]) for k in metrics)
    report["zero_equivalence"] = {"max_abs_metric_delta": zero_max, "pass": zero_max <= 1e-12}
    report["matched_frames"] = []
    for time in report["matched_times"]:
        hits = [i for i,t in enumerate(expected_times) if abs(t-time) < 1e-8]
        if len(hits) != 1:
            raise RuntimeError("MATCHED_TIME_NOT_FOUND")
        i = hits[0]
        zero = runs["same_mode_zero"][i]
        frame = {"time": time, "cases": {}}
        for name in ("neg_nominal", "neg_double", "pos_nominal", "pos_double"):
            row = runs[name][i]
            delta = {k: float(row[k]) - float(zero[k]) for k in metrics}
            width = 100.0 * delta["W_sheet"] / max(abs(float(zero["W_sheet"])), 1e-300)
            jpk = 100.0 * delta["Jpk"] / max(abs(float(zero["Jpk"])), 1e-300)
            frame["cases"][name] = {
                "native_metric_deltas": delta,
                "width_gain_pct": width, "Jpk_change_pct": jpk,
                "frozen_open_loop_metric_comparison": {
                    "width_gt_0p020_pct": width > 0.02,
                    "Jpk_le_0p10_pct": jpk <= 0.10,
                    "both": width > 0.02 and jpk <= 0.10
                }
            }
        report["matched_frames"].append(frame)
    report["native_observable_response_detected"] = any(
        abs(v) > 1e-12 for f in report["matched_frames"] for c in f["cases"].values()
        for v in c["native_metric_deltas"].values()
    )
    report["temporal_convergence_established"] = False
    report["controller_in_loop_authority_established"] = False
    if not report["zero_equivalence"]["pass"]:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_NATIVE_OBSERVABLES_ZERO_EQUIVALENCE_FAILED"
    elif report["native_observable_response_detected"]:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_NATIVE_OBSERVABLES_DIAGNOSTIC_COMPLETE"
    else:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_NATIVE_OBSERVABLES_NO_RESPONSE"
    report["interpretation"] = "Replace jphi-only spatial-response proxy with extracted native W_sheet/Jpk/high-J/reconnection/energy diagnostics at the same fixed dt and signed amplitudes. Preserve zero control and frozen gates; do not equate an open-loop metric crossing with closed-loop stabilization or physical current calibration."
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_NATIVE_OBSERVABLES_PIPELINE_BLOCKED"
target = out / "fine_dt_native_observables_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

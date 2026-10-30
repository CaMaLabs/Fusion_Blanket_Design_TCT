#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Audit the ROI dependence of small native current-sheet width responses.

No solver-physics, actuator-profile, controller, threshold, or source change.
W_sheet here is a diagnostic derived from native HDF5 jphi, not a calibrated
physical sheet-width measurement. All frozen-gate comparisons are open-loop.
"""
import datetime
import json
import math
import pathlib
import sys
import h5py
import numpy as np

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0, str(repo / "tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta

job_id = "20261030-140-native-current-drive-width-roi-sensitivity"
parent_id = "20261030-139-native-current-drive-fine-dt-native-observables"
out = repo / "validation_runs/m3dc1_tct_native_width_roi_140"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1,
    "job_id": job_id, "parent_result_job_id": parent_id,
    "classification": "M3DC1_NATIVE_CURRENT_DRIVE_WIDTH_ROI_SENSITIVITY_UNRESOLVED",
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1", "shot_ids": [],
    "dt": 0.000625, "steps": 48,
    "source_mode": 4, "source_gate": [0.0, 0.04],
    "amplitudes": [-0.01, -0.005, 0.0, 0.005, 0.01],
    "matched_times": [0.01, 0.02, 0.03],
    "radial_roi_half_widths": [0.20, 0.25, 0.30],
    "radial_roi_center": 10.0,
    "zero_equivalence_tolerance": 1e-12,
    "expected_parent_summary_sha256": "605b0788369ab968a02787a0b725a3cd628f8a2dc60ebd0c533709380c6054e3",
    "expected_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Normalized-native M3D-C1 open-loop source response and ROI-derived HDF5 width diagnostic only. Mesh e[2] weights and ROI definition are not validated physical current/width integrals. No temporal convergence, calibrated source current, segmented controller-in-loop authority, experimental shot handoff, causal TCT stabilization, p-B11 fidelity, ignition or reactor net power.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    parent_path = repo / "validation_runs/m3dc1_tct_native_observables_139/fine_dt_native_observables_summary.json"
    if not parent_path.is_file() or pta.sha256_file(parent_path) != report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("classification") != "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_NATIVE_OBSERVABLES_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_CHANGED")
    if parent.get("zero_equivalence", {}).get("pass") is not True:
        raise RuntimeError("PARENT_ZERO_EQUIVALENCE_NOT_PASSED")
    if any(c["frozen_open_loop_metric_comparison"]["both"]
           for f in parent["matched_frames"] for c in f["cases"].values()):
        raise RuntimeError("PARENT_FROZEN_OPEN_LOOP_GATE_STATUS_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_executable_sha256"]:
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")
    native.DT = report["dt"]
    native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_width_roi_140")
    native.OUT = out
    configs = [
        ("baseline", 0, 0.0), ("same_mode_zero", 4, 0.0),
        ("neg_nominal", 4, -0.005), ("neg_double", 4, -0.01),
        ("pos_nominal", 4, 0.005), ("pos_double", 4, 0.01)
    ]
    dirs = {}
    for name, mode, amp in configs:
        d = native.write_input(name, mode, amp, 0, 0.0, 0.04, nmax_steps=48)
        print("[native-width-roi] " + name, flush=True)
        native.execute(d)
        dirs[name] = d
    expected_times = [i * report["dt"] for i in range(49)]
    for name, d in dirs.items():
        rows = pta.c1ke(d)
        if len(rows) != 49 or any(abs(float(r["time"]) - t) > 1e-8
                                  for r, t in zip(rows, expected_times)):
            raise RuntimeError("TIME_GRID_MISMATCH:" + name)

    def read_frame(d, i):
        with h5py.File(d / ("time_%03d.h5" % i), "r") as h:
            elements = np.asarray(h["/mesh/elements"][:], dtype=float)
            field = np.asarray(h["/fields/jphi"][:], dtype=float)
        if (elements.ndim != 2 or elements.shape[1] < 6 or
                field.ndim != 2 or len(elements) != len(field) or len(elements) != 1004):
            raise RuntimeError("NATIVE_MESH_OR_FIELD_SCHEMA_MISMATCH")
        if not np.isfinite(elements).all() or not np.isfinite(field).all():
            raise RuntimeError("NONFINITE_NATIVE_MESH_OR_FIELD")
        return elements, field[:, 0]

    def diagnostic(elements, j, band):
        mask = (np.abs(elements[:, 4] - report["radial_roi_center"]) <= band) & (elements[:, 2] > 0)
        z = elements[mask, 5]
        w = elements[mask, 2]
        a = np.abs(j[mask])
        if len(a) < 3 or float(np.sum(w*a)) <= 0:
            raise RuntimeError("INSUFFICIENT_ROI_SUPPORT")
        mass = float(np.sum(w*a))
        centroid = float(np.sum(z*w*a) / mass)
        variance = float(np.sum((z-centroid)**2*w*a) / mass)
        return {"W_sheet": 2.354820045 * math.sqrt(max(variance, 0.0)),
                "Jpk": float(np.max(a)), "roi_elements": int(len(a))}

    report["matched_frames"] = []
    zero_max = 0.0
    for time in report["matched_times"]:
        hits = [i for i, t in enumerate(expected_times) if abs(t-time) < 1e-8]
        if len(hits) != 1:
            raise RuntimeError("MATCHED_TIME_NOT_FOUND")
        arrays = {name: read_frame(d, hits[0]) for name, d in dirs.items()}
        mesh, baseline = arrays["baseline"]
        for m, _ in arrays.values():
            if not np.allclose(mesh, m, atol=1e-10, rtol=0):
                raise RuntimeError("MESH_MISMATCH")
        zero = arrays["same_mode_zero"][1]
        zero_max = max(zero_max, float(np.max(np.abs(baseline-zero))))
        frame = {"time": time, "roi_comparisons": []}
        for band in report["radial_roi_half_widths"]:
            reference = diagnostic(mesh, zero, band)
            cases = {}
            for name in ("neg_nominal", "neg_double", "pos_nominal", "pos_double"):
                m = diagnostic(mesh, arrays[name][1], band)
                width = 100.0 * (m["W_sheet"]/reference["W_sheet"]-1.0)
                jpk = 100.0 * (m["Jpk"]/reference["Jpk"]-1.0)
                cases[name] = {
                    "width_gain_pct": width, "Jpk_change_pct": jpk,
                    "width_gt_0p020_pct": width > 0.02,
                    "Jpk_le_0p10_pct": jpk <= 0.10,
                    "both_frozen_open_loop_metrics": width > 0.02 and jpk <= 0.10
                }
            frame["roi_comparisons"].append({
                "radial_half_width": band, "roi_elements": reference["roi_elements"],
                "cases": cases
            })
        report["matched_frames"].append(frame)
    report["zero_equivalence"] = {
        "max_abs_field_delta": zero_max,
        "pass": zero_max <= report["zero_equivalence_tolerance"]
    }
    report["open_loop_width_gate_crossed_any"] = any(
        c["width_gt_0p020_pct"]
        for f in report["matched_frames"] for r in f["roi_comparisons"]
        for c in r["cases"].values()
    )
    report["open_loop_both_frozen_metrics_any"] = any(
        c["both_frozen_open_loop_metrics"]
        for f in report["matched_frames"] for r in f["roi_comparisons"]
        for c in r["cases"].values()
    )
    report["controller_in_loop_authority_established"] = False
    report["temporal_convergence_established"] = False
    report["classification"] = (
        "M3DC1_NATIVE_CURRENT_DRIVE_WIDTH_ROI_SENSITIVITY_DIAGNOSTIC_COMPLETE"
        if report["zero_equivalence"]["pass"]
        else "M3DC1_NATIVE_CURRENT_DRIVE_WIDTH_ROI_SENSITIVITY_ZERO_EQUIVALENCE_FAILED"
    )
    report["interpretation"] = (
        "Test sensitivity of small native jphi-derived sheet-width gains to radial ROI "
        "selection while holding solver physics, source profile, time grid and frozen "
        "thresholds fixed. Open-loop diagnostic crossings are not controller passes."
    )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_WIDTH_ROI_SENSITIVITY_PIPELINE_BLOCKED"
target = out / "width_roi_sensitivity_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

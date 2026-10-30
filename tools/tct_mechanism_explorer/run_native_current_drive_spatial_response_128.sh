#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Matched native field-level command response audit; not a source-current calibration."""
import datetime
import json
import math
import pathlib
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0, str(repo / "tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta

out = repo / "validation_runs/m3dc1_tct_native_spatial_response_128"
native.OUT = out
native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_spatial_response_128_runs")
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1,
    "parent_result_job_id": "20261029-127-native-current-drive-amplitude-response-audit",
    "classification": "M3DC1_NATIVE_CURRENT_DRIVE_SPATIAL_RESPONSE_UNRESOLVED",
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1",
    "shot_ids": [],
    "dt": 0.01, "steps": 3, "source_mode": 4,
    "gate_window": [0.0, 0.04],
    "amplitudes": [-0.005, -0.0025, 0.0, 0.0025, 0.005],
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Field-level normalized-native M3D-C1 diagnostic only. No directly measured injected source, physical current calibration, shot handoff, segmented-electrode authority, p-B11 or causal TCT stabilization.",
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
        ("baseline", 0, 0.0), ("same_mode_zero", 4, 0.0),
        ("half_negative", 4, -0.0025), ("half_positive", 4, 0.0025),
        ("full_negative", 4, -0.005), ("full_positive", 4, 0.005),
    )
    directories = {}
    for name, mode, amp in configs:
        d = native.write_input(name, mode, amp, 0, 0.0, 0.04, nmax_steps=3)
        print("[spatial-response] running " + name, flush=True)
        native.execute(d)
        directories[name] = d

    try:
        import h5py
        report["field_read_backend"] = "h5py_native_dataset"
    except ImportError:
        h5py = None
        report["field_read_backend"] = "h5dump_text_precision_limited"
        h5 = pta.H5()

    def read_frame(d, index):
        path = d / ("time_%03d.h5" % index)
        if h5py is not None:
            with h5py.File(path, "r") as f:
                elems = f["/mesh/elements"][:]
                jphi = f["/fields/jphi"][:]
                mesh = [(float(e[4]), float(e[5]), max(0.0, float(e[2]))) for e in elems]
                vals = [float(v[0]) for v in jphi]
        else:
            elems = h5.matrix(path, "/mesh/elements")
            jphi = h5.matrix(path, "/fields/jphi")
            mesh = [(float(e[4]), float(e[5]), max(0.0, float(e[2]))) for e in elems]
            vals = [float(v[0]) for v in jphi]
        if len(mesh) != len(vals) or not mesh:
            raise RuntimeError("MESH_FIELD_SIZE_MISMATCH")
        if not all(math.isfinite(v) for v in vals):
            raise RuntimeError("NONFINITE_JPHI")
        return mesh, vals

    samples = {name: pta.c1ke(d) for name, d in directories.items()}
    base_times = [float(row["time"]) for row in samples["baseline"]]
    if len(base_times) != 4:
        raise RuntimeError("EXPECTED_FOUR_FRAMES")
    for name, rows in samples.items():
        if len(rows) != 4 or any(abs(float(r["time"]) - t) > 1e-8 for r,t in zip(rows,base_times)):
            raise RuntimeError("TIME_GRID_MISMATCH: " + name)
    report["observed_time_samples"] = base_times
    report["frame_diagnostics"] = []
    mismatch = False
    max_zero = 0.0
    for frame in range(4):
        fields = {name: read_frame(d, frame) for name,d in directories.items()}
        mesh, baseline = fields["baseline"]
        for name,(other,_) in fields.items():
            if len(other) != len(mesh) or any(
                abs(a-b) > 1e-10 for m,n in zip(mesh,other) for a,b in zip(m,n)
            ):
                mismatch = True
        if mismatch:
            report["mesh_correspondence_verified"] = False
            break
        zero = fields["same_mode_zero"][1]
        max_zero = max(max_zero, max(abs(a-b) for a,b in zip(baseline,zero)))
        roi = [i for i,(r,z,w) in enumerate(mesh) if abs(r-pta.R_CENTER) <= pta.R_BAND and w > 0]
        if not roi:
            raise RuntimeError("EMPTY_WEIGHTED_SHEET_ROI")
        def delta(name):
            return [fields[name][1][i] - zero[i] for i in roi]
        weights = [mesh[i][2] for i in roi]
        coords = [mesh[i][1] for i in roi]
        cases = ("half_negative","half_positive","full_negative","full_positive")
        differences = {name: delta(name) for name in cases}
        def weighted_abs(values):
            return sum(abs(v)*w for v,w in zip(values,weights))
        def weighted_signed(values):
            return sum(v*w for v,w in zip(values,weights))
        def residual(a,b,factor=1.0):
            return weighted_abs([x-factor*y for x,y in zip(a,b)])
        hp,hn = differences["half_positive"],differences["half_negative"]
        fp,fn = differences["full_positive"],differences["full_negative"]
        norm_full = weighted_abs(fp) + weighted_abs(fn)
        norm_half = weighted_abs(hp) + weighted_abs(hn)
        frame_result = {
            "frame": frame, "time": base_times[frame],
            "mesh_elements": len(mesh), "weighted_roi_elements": len(roi),
            "max_abs_zero_vs_baseline_jphi": max(abs(a-b) for a,b in zip(baseline,zero)),
            "cases": {},
            "full_odd_symmetry_residual_fraction": weighted_abs([a+b for a,b in zip(fp,fn)])/max(norm_full,1e-300),
            "half_odd_symmetry_residual_fraction": weighted_abs([a+b for a,b in zip(hp,hn)])/max(norm_half,1e-300),
            "full_positive_twice_half_residual_fraction": residual(fp,hp,2)/max(weighted_abs(fp)+2*weighted_abs(hp),1e-300),
            "full_negative_twice_half_residual_fraction": residual(fn,hn,2)/max(weighted_abs(fn)+2*weighted_abs(hn),1e-300),
        }
        for name,values in differences.items():
            frame_result["cases"][name] = {
                "max_abs_delta_jphi": max(map(abs,values)),
                "weighted_abs_delta_jphi": weighted_abs(values),
                "weighted_signed_delta_jphi": weighted_signed(values),
                "center_signed_delta_jphi": sum(v*w for v,w,z in zip(values,weights,coords) if abs(z-pta.Z_CENTER)<=pta.CENTER_HW),
                "shoulder_signed_delta_jphi": sum(v*w for v,w,z in zip(values,weights,coords) if abs(abs(z-pta.Z_CENTER)-pta.Z_SHOULDER)<=pta.SHOULDER_HW),
            }
        report["frame_diagnostics"].append(frame_result)
    report["mesh_correspondence_verified"] = not mismatch
    report["zero_equivalence"] = {"max_abs_field_delta": max_zero, "pass": (not mismatch and max_zero <= 1e-12)}
    response = any(
        case["weighted_abs_delta_jphi"] > 1e-12
        for frame in report["frame_diagnostics"] for case in frame["cases"].values()
    )
    report["field_response_observed"] = response
    if mismatch:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_MESH_CORRESPONDENCE_UNRESOLVED"
    elif not report["zero_equivalence"]["pass"]:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_FIELD_ZERO_EQUIVALENCE_FAILED"
    elif response:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_SPATIAL_RESPONSE_DIAGNOSTIC_COMPLETE"
    else:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_SPATIAL_RESPONSE_NOT_OBSERVED"
    report["interpretation"] = (
        "Matched per-frame native jphi mesh response replaces reliance on aggregate Jpk "
        "envelopes. h5dump fallback is precision-limited if h5py is unavailable. "
        "Response geometry is not the injected source itself and does not calibrate physical "
        "actuator current, validate a segmented-electrode controller, or establish TCT stabilization."
    )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_SPATIAL_RESPONSE_PIPELINE_BLOCKED"
path = out / "native_spatial_summary.json"
tmp = path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(path)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

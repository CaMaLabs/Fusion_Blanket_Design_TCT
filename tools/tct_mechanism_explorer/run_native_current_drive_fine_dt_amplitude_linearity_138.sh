#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Fixed-fine-dt native M3D-C1 signed amplitude scaling diagnostic; no solver changes."""
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

job_id = "20261030-138-native-current-drive-fine-dt-amplitude-linearity"
parent_id = "20261030-137-native-current-drive-unforced-baseline-dt-audit"
out = repo / "validation_runs/m3dc1_tct_native_amplitude_138"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job_id, "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "classification": "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_AMPLITUDE_LINEARITY_UNRESOLVED",
    "dt": 0.000625, "steps": 48, "matched_times": [0.01, 0.02, 0.03],
    "source_mode": 4, "source_gate": [0.0, 0.04],
    "amplitude_magnitudes": [0.0025, 0.005, 0.01],
    "zero_equivalence_tolerance": 1e-12,
    "expected_parent_summary_sha256": "32ae1c43472fa2289d5372458cfed16e875039db75411d1d620a3854f182a451",
    "expected_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Amplitude scaling of normalized-native M3D-C1 jphi responses at one fixed fine dt only. e[2] is uncalibrated; no temporal convergence, physical current conservation, segmented-electrode authority, experimental shot handoff, causal TCT stabilization, p-B11 fidelity, ignition or reactor-net-power claim.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    parent_path = repo / "validation_runs/m3dc1_tct_native_unforced_dt_137/unforced_baseline_dt_summary.json"
    if not parent_path.is_file() or pta.sha256_file(parent_path) != report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("classification") != "M3DC1_NATIVE_UNFORCED_BASELINE_DT_SENSITIVITY_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_CHANGED")
    if parent.get("zero_equivalence", {}).get("pass") is not True:
        raise RuntimeError("PARENT_ZERO_EQUIVALENCE_NOT_PASSED")
    if parent.get("temporal_convergence_established") is not False:
        raise RuntimeError("PARENT_CONVERGENCE_STATUS_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_executable_sha256"]:
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")

    native.DT = report["dt"]
    native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_amplitude_138")
    native.OUT = out
    cases = [
        ("baseline", 0, 0.0), ("same_mode_zero", 4, 0.0),
        ("neg_half", 4, -0.0025), ("neg_nominal", 4, -0.005),
        ("neg_double", 4, -0.01), ("pos_half", 4, 0.0025),
        ("pos_nominal", 4, 0.005), ("pos_double", 4, 0.01)
    ]
    dirs = {}
    for name, mode, amplitude in cases:
        d = native.write_input(name, mode, amplitude, 0, 0.0, 0.04, nmax_steps=48)
        print("[fine-dt-amplitude] " + name, flush=True)
        native.execute(d)
        dirs[name] = d
    expected_times = [i * report["dt"] for i in range(49)]
    grids = {name: [float(row["time"]) for row in pta.c1ke(d)] for name, d in dirs.items()}
    if any(len(t) != 49 or any(abs(a-b) > 1e-8 for a,b in zip(t,expected_times))
           for t in grids.values()):
        raise RuntimeError("CASE_TIME_GRID_MISMATCH")

    def read(d, frame):
        with h5py.File(d / ("time_%03d.h5" % frame), "r") as h:
            e = np.asarray(h["/mesh/elements"][:], dtype=float)
            j = np.asarray(h["/fields/jphi"][:], dtype=float)
        if e.ndim != 2 or e.shape[1] < 6 or j.ndim != 2 or len(e) != len(j) or len(e) != 1004:
            raise RuntimeError("MESH_OR_FIELD_SCHEMA_MISMATCH")
        mesh, field = e[:, [4,5,2]], j[:,0]
        if not np.isfinite(mesh).all() or not np.isfinite(field).all() or np.any(mesh[:,2] <= 0):
            raise RuntimeError("NONFINITE_OR_INVALID_MESH_FIELD")
        return mesh, field

    report["matched_frames"] = []
    zero_max = 0.0
    for time in report["matched_times"]:
        hits = [i for i,t in enumerate(expected_times) if abs(t-time) < 1e-8]
        if len(hits) != 1:
            raise RuntimeError("MATCHED_FRAME_NOT_FOUND")
        arrays = {name: read(d, hits[0]) for name,d in dirs.items()}
        mesh, baseline = arrays["baseline"]
        if any(not np.allclose(mesh, m, atol=1e-10, rtol=0) for m,_ in arrays.values()):
            raise RuntimeError("WITHIN_CASE_MESH_MISMATCH")
        zero = arrays["same_mode_zero"][1]
        zero_max = max(zero_max, float(np.max(np.abs(zero-baseline))))
        w = mesh[:,2]
        def norm(x):
            return math.sqrt(float(np.sum(w*x*x)))
        def cosine(x,y):
            return float(np.sum(w*x*y)) / max(norm(x)*norm(y), 1e-300)
        response = {name:field-zero for name,(_,field) in arrays.items() if name not in ("baseline","same_mode_zero")}
        row = {"time":time,"mesh_elements":len(w),"response":{},"scaling":{},"odd_symmetry":{}}
        for name,x in response.items():
            row["response"][name] = {
                "weighted_l2":norm(x),
                "signed_e2_proxy":float(np.sum(w*x)),
                "max_abs":float(np.max(np.abs(x)))
            }
        for sign in ("neg","pos"):
            half,nominal,double = (response[sign+"_"+label] for label in ("half","nominal","double"))
            row["scaling"][sign] = {
                "nominal_vs_twice_half_relative_l2":norm(nominal-2*half)/max(norm(nominal),1e-300),
                "double_vs_twice_nominal_relative_l2":norm(double-2*nominal)/max(norm(double),1e-300),
                "half_nominal_cosine":cosine(half,nominal),
                "nominal_double_cosine":cosine(nominal,double),
                "nominal_over_half_norm_ratio":norm(nominal)/max(norm(half),1e-300),
                "double_over_nominal_norm_ratio":norm(double)/max(norm(nominal),1e-300)
            }
        for label in ("half","nominal","double"):
            neg,pos = response["neg_"+label],response["pos_"+label]
            row["odd_symmetry"][label] = float(np.sum(w*np.abs(neg+pos)))/max(float(np.sum(w*(np.abs(neg)+np.abs(pos)))),1e-300)
        report["matched_frames"].append(row)
    report["zero_equivalence"] = {"max_abs_field_delta":zero_max,"pass":zero_max<=1e-12}
    report["temporal_convergence_established"] = False
    report["amplitude_linearity_established"] = False
    report["classification"] = (
        "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_AMPLITUDE_LINEARITY_DIAGNOSTIC_COMPLETE"
        if report["zero_equivalence"]["pass"]
        else "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_AMPLITUDE_LINEARITY_ZERO_EQUIVALENCE_FAILED"
    )
    report["interpretation"] = "Compare fixed-dt response fields at three signed amplitudes. Scaling residuals and odd symmetry are diagnostic, not pre-approved linearity gates; baseline dt sensitivity and driven response dt sensitivity remain distinct."
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_AMPLITUDE_LINEARITY_PIPELINE_BLOCKED"
target = out / "fine_dt_amplitude_linearity_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
tmp.replace(target)
print(json.dumps(report,indent=2,sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

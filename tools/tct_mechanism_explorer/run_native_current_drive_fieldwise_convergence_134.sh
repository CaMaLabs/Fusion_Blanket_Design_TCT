#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Matched native-M3D-C1 fieldwise dt sensitivity; no physics or acceptance changes."""
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

job_id = "20261030-134-native-current-drive-fieldwise-convergence-audit"
parent_id = "20261030-133-native-current-drive-third-timestep-refinement"
out = repo / "validation_runs/m3dc1_tct_native_fieldwise_134"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job_id, "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "classification": "M3DC1_NATIVE_CURRENT_DRIVE_FIELDWISE_CONVERGENCE_UNRESOLVED",
    "dt_sequence": [0.0025, 0.00125], "matched_times": [0.01, 0.02, 0.03],
    "source_mode": 4, "amplitudes": [-0.005, 0.0, 0.005],
    "source_gate": [0.0, 0.04], "zero_equivalence_tolerance": 1e-12,
    "expected_parent_summary_sha256": "50257f670456fcac1733fbcdb0dd74f22b571b23f25cd757924158123860f7d1",
    "expected_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Fieldwise temporal sensitivity of normalized-native M3D-C1 jphi actuator response only. e[2] is an uncalibrated mesh weight. Two dt levels do not establish numerical convergence. No physical current conservation, segmented-electrode authority, experimental shot handoff, causal TCT stabilization, p-B11 fidelity or reactor-net-power claim.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    parent_path = repo / "validation_runs/m3dc1_tct_native_timestep_133/timestep_refinement_summary.json"
    if not parent_path.is_file() or pta.sha256_file(parent_path) != report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("classification") != "M3DC1_NATIVE_CURRENT_DRIVE_THIRD_TIMESTEP_REFINEMENT_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_CHANGED")
    if parent.get("zero_equivalence", {}).get("pass") is not True:
        raise RuntimeError("PARENT_ZERO_EQUIVALENCE_NOT_PASSED")
    if parent.get("timestep_convergence_trend", {}).get("numerical_convergence_established") is not False:
        raise RuntimeError("PARENT_CONVERGENCE_STATUS_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_executable_sha256"]:
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")

    cases = (("baseline", 0, 0.0), ("same_mode_zero", 4, 0.0),
             ("full_negative", 4, -0.005), ("full_positive", 4, 0.005))
    levels = {}
    for dt, steps, label in ((0.0025, 12, "coarse"), (0.00125, 24, "fine")):
        native.DT = dt
        native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_fieldwise_134_" + label)
        native.OUT = out
        dirs = {}
        for name, mode, amp in cases:
            d = native.write_input(name, mode, amp, 0, 0.0, 0.04, nmax_steps=steps)
            print("[fieldwise] " + label + " " + name, flush=True)
            native.execute(d)
            dirs[name] = d
        times = [float(row["time"]) for row in pta.c1ke(dirs["baseline"])]
        if len(times) != steps + 1 or any(abs(t-dt*i)>1e-8 for i,t in enumerate(times)):
            raise RuntimeError("TIME_GRID_MISMATCH: " + label)
        for name, d in dirs.items():
            t = [float(row["time"]) for row in pta.c1ke(d)]
            if len(t) != len(times) or any(abs(a-b)>1e-8 for a,b in zip(t,times)):
                raise RuntimeError("CASE_TIME_GRID_MISMATCH: " + label + "/" + name)
        levels[label] = {"dt":dt, "dirs":dirs, "times":times}

    def read(d, frame):
        with h5py.File(d / ("time_%03d.h5" % frame), "r") as h:
            e = np.asarray(h["/mesh/elements"][:], dtype=float)
            j = np.asarray(h["/fields/jphi"][:], dtype=float)
        if e.ndim != 2 or e.shape[1] < 6 or j.ndim != 2 or len(e) != len(j) or len(e) != 1004:
            raise RuntimeError("MESH_OR_FIELD_SCHEMA_MISMATCH")
        mesh = e[:,[4,5,2]]
        field = j[:,0]
        if not np.isfinite(mesh).all() or not np.isfinite(field).all() or np.any(mesh[:,0]<=0) or np.any(mesh[:,2]<=0):
            raise RuntimeError("NONFINITE_OR_INVALID_MESH_FIELD")
        return mesh,field

    report["matched_frames"] = []
    zero_max = 0.0
    for time in report["matched_times"]:
        pairs = {}
        for label, level in levels.items():
            hits = [i for i,t in enumerate(level["times"]) if abs(t-time)<1e-8]
            if len(hits) != 1:
                raise RuntimeError("MATCHED_FRAME_NOT_FOUND: " + label)
            arrays = {name:read(d,hits[0]) for name,d in level["dirs"].items()}
            mesh,baseline = arrays["baseline"]
            if any(not np.allclose(mesh,m,atol=1e-10,rtol=0) for m,_ in arrays.values()):
                raise RuntimeError("WITHIN_LEVEL_MESH_MISMATCH: " + label)
            zero = arrays["same_mode_zero"][1]
            zero_max = max(zero_max,float(np.max(np.abs(zero-baseline))))
            pairs[label] = {"mesh":mesh,"weights":mesh[:,2],
                "negative":arrays["full_negative"][1]-zero,
                "positive":arrays["full_positive"][1]-zero}
        coarse,fine=pairs["coarse"],pairs["fine"]
        if not np.allclose(coarse["mesh"],fine["mesh"],atol=1e-10,rtol=0):
            raise RuntimeError("CROSS_DT_MESH_MISMATCH")
        w=fine["weights"]
        def wnorm(x):
            return math.sqrt(float(np.sum(w*x*x)))
        row={"time":time,"mesh_elements":len(w),"commands":{}}
        for command in ("negative","positive"):
            a,b=coarse[command],fine[command]
            difference=b-a
            norm_a,norm_b=wnorm(a),wnorm(b)
            denom=max(norm_a*norm_b,1e-300)
            row["commands"][command]={
                "coarse_weighted_l2":norm_a,
                "fine_weighted_l2":norm_b,
                "difference_weighted_l2":wnorm(difference),
                "relative_difference_to_fine_l2":wnorm(difference)/max(norm_b,1e-300),
                "difference_linf":float(np.max(np.abs(difference))),
                "weighted_spatial_correlation":float(np.sum(w*a*b))/denom,
                "coarse_signed_e2_proxy":float(np.sum(w*a)),
                "fine_signed_e2_proxy":float(np.sum(w*b))
            }
        for label,pair in pairs.items():
            a,b=pair["negative"],pair["positive"]
            row[label+"_odd_symmetry_residual_e2"]=float(np.sum(w*np.abs(a+b)))/max(float(np.sum(w*(np.abs(a)+np.abs(b)))),1e-300)
        report["matched_frames"].append(row)
    report["zero_equivalence"]={"max_abs_field_delta":zero_max,"pass":zero_max<=1e-12}
    report["classification"]=(
        "M3DC1_NATIVE_CURRENT_DRIVE_FIELDWISE_CONVERGENCE_DIAGNOSTIC_COMPLETE"
        if report["zero_equivalence"]["pass"]
        else "M3DC1_NATIVE_CURRENT_DRIVE_FIELDWISE_CONVERGENCE_ZERO_EQUIVALENCE_FAILED")
    report["interpretation"]="Direct matched-mesh fieldwise response comparison of dt=0.0025 versus dt=0.00125 at three times; descriptive sensitivity only. No numerical convergence gate is passed from two resolutions."
except Exception as exc:
    report["pipeline_error"]=type(exc).__name__+": "+str(exc)
    report["classification"]="M3DC1_NATIVE_CURRENT_DRIVE_FIELDWISE_CONVERGENCE_PIPELINE_BLOCKED"
target=out/"fieldwise_convergence_summary.json"
tmp=target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
tmp.replace(target)
print(json.dumps(report,indent=2,sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Repeat matched native M3D-C1 cases at one fixed dt to separate run-to-run variability from dt sensitivity."""
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

job_id = "20261030-136-native-current-drive-fixed-dt-repeatability"
parent_id = "20261030-135-native-current-drive-three-level-fieldwise-convergence"
out = repo / "validation_runs/m3dc1_tct_native_repeatability_136"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job_id, "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "classification": "M3DC1_NATIVE_CURRENT_DRIVE_FIXED_DT_REPEATABILITY_UNRESOLVED",
    "dt": 0.000625, "steps": 48, "matched_times": [0.01, 0.02, 0.03],
    "source_mode": 4, "amplitudes": [-0.005, 0.0, 0.005],
    "source_gate": [0.0, 0.04], "zero_equivalence_tolerance": 1e-12,
    "repeatability_max_abs_field_tolerance": 1e-12,
    "expected_parent_summary_sha256": "75ff8d3ecfc1f2724cc3a32430361f94dacb52b4707a259dcefb4eea442da02b",
    "expected_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Two independent matched-case repeats at a single fixed dt test numerical repeatability, not temporal convergence. Normalized-native M3D-C1 jphi only; e[2] uncalibrated. No physical current conservation, segmented-electrode controller-in-loop authority, validated experimental handoff, causal TCT stabilization, p-B11 fidelity, ignition or net-power claim.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    parent_path = repo / "validation_runs/m3dc1_tct_native_fieldwise_135/three_level_fieldwise_summary.json"
    if not parent_path.is_file() or pta.sha256_file(parent_path) != report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("classification") != "M3DC1_NATIVE_CURRENT_DRIVE_THREE_LEVEL_FIELDWISE_CONVERGENCE_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_CHANGED")
    if parent.get("zero_equivalence", {}).get("pass") is not True:
        raise RuntimeError("PARENT_ZERO_EQUIVALENCE_NOT_PASSED")
    if parent.get("fieldwise_convergence_established") is not False:
        raise RuntimeError("PARENT_CONVERGENCE_STATUS_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_executable_sha256"]:
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")

    cases = (("baseline", 0, 0.0), ("same_mode_zero", 4, 0.0),
             ("full_negative", 4, -0.005), ("full_positive", 4, 0.005))
    native.DT = report["dt"]
    native.OUT = out
    repeats = {}
    for repeat in ("A", "B"):
        native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_repeatability_136_" + repeat)
        dirs = {}
        for name, mode, amp in cases:
            d = native.write_input(name, mode, amp, 0, 0.0, 0.04, nmax_steps=48)
            print("[fixed-dt-repeatability] " + repeat + " " + name, flush=True)
            native.execute(d)
            dirs[name] = d
        grids = {name:[float(row["time"]) for row in pta.c1ke(d)] for name,d in dirs.items()}
        expected = [i*report["dt"] for i in range(49)]
        if any(len(grid)!=49 or any(abs(a-b)>1e-8 for a,b in zip(grid,expected))
               for grid in grids.values()):
            raise RuntimeError("CASE_TIME_GRID_MISMATCH_" + repeat)
        repeats[repeat] = {"dirs":dirs,"times":grids["baseline"]}

    def read(d, frame):
        with h5py.File(d / ("time_%03d.h5" % frame), "r") as h:
            e = np.asarray(h["/mesh/elements"][:], dtype=float)
            j = np.asarray(h["/fields/jphi"][:], dtype=float)
        if e.ndim!=2 or e.shape[1]<6 or j.ndim!=2 or len(e)!=len(j) or len(e)!=1004:
            raise RuntimeError("MESH_OR_FIELD_SCHEMA_MISMATCH")
        mesh=e[:,[4,5,2]]
        field=j[:,0]
        if not np.isfinite(mesh).all() or not np.isfinite(field).all() or np.any(mesh[:,2]<=0):
            raise RuntimeError("NONFINITE_OR_INVALID_MESH_FIELD")
        return mesh,field

    report["matched_frames"] = []
    zero_max=0.0
    repeat_max=0.0
    for time in report["matched_times"]:
        fields={}
        for repeat,data in repeats.items():
            hits=[i for i,t in enumerate(data["times"]) if abs(t-time)<1e-8]
            if len(hits)!=1:
                raise RuntimeError("MATCHED_FRAME_NOT_FOUND_"+repeat)
            arrays={name:read(d,hits[0]) for name,d in data["dirs"].items()}
            mesh,baseline=arrays["baseline"]
            if any(not np.allclose(mesh,m,atol=1e-10,rtol=0) for m,_ in arrays.values()):
                raise RuntimeError("WITHIN_REPEAT_MESH_MISMATCH_"+repeat)
            zero=arrays["same_mode_zero"][1]
            zero_max=max(zero_max,float(np.max(np.abs(zero-baseline))))
            fields[repeat]={"mesh":mesh,"weights":mesh[:,2],
                            "raw":{name:field for name,(_,field) in arrays.items()},
                            "negative":arrays["full_negative"][1]-zero,
                            "positive":arrays["full_positive"][1]-zero}
        a,b=fields["A"],fields["B"]
        if not np.allclose(a["mesh"],b["mesh"],atol=1e-10,rtol=0):
            raise RuntimeError("CROSS_REPEAT_MESH_MISMATCH")
        w=a["weights"]
        def norm(x):
            return math.sqrt(float(np.sum(w*x*x)))
        row={"time":time,"mesh_elements":len(w),"raw_field_max_abs_differences":{},"response":{}}
        for name in a["raw"]:
            diff=float(np.max(np.abs(a["raw"][name]-b["raw"][name])))
            row["raw_field_max_abs_differences"][name]=diff
            repeat_max=max(repeat_max,diff)
        for command in ("negative","positive"):
            x,y=a[command],b[command]
            diff=y-x
            row["response"][command]={
                "max_abs_difference":float(np.max(np.abs(diff))),
                "relative_weighted_l2_difference":norm(diff)/max(norm(y),1e-300),
                "weighted_cosine":float(np.sum(w*x*y))/max(norm(x)*norm(y),1e-300)
            }
        report["matched_frames"].append(row)
    report["zero_equivalence"]={"max_abs_field_delta":zero_max,"pass":zero_max<=1e-12}
    report["fixed_dt_repeatability"]={"max_abs_raw_field_delta":repeat_max,
        "pass":repeat_max<=report["repeatability_max_abs_field_tolerance"]}
    report["temporal_convergence_established"]=False
    report["classification"]=(
        "M3DC1_NATIVE_CURRENT_DRIVE_FIXED_DT_REPEATABILITY_DIAGNOSTIC_COMPLETE"
        if report["zero_equivalence"]["pass"]
        else "M3DC1_NATIVE_CURRENT_DRIVE_FIXED_DT_REPEATABILITY_ZERO_EQUIVALENCE_FAILED")
    report["interpretation"]="Matched independent fixed-dt repeats isolate run-to-run field variability; passing repeatability cannot establish dt convergence. All jphi and e[2] metrics are normalized-native proxies."
except Exception as exc:
    report["pipeline_error"]=type(exc).__name__+": "+str(exc)
    report["classification"]="M3DC1_NATIVE_CURRENT_DRIVE_FIXED_DT_REPEATABILITY_PIPELINE_BLOCKED"
target=out/"fixed_dt_repeatability_summary.json"
tmp=target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
tmp.replace(target)
print(json.dumps(report,indent=2,sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-/home/ubuntu/work/openmc/sweep/.venv-dudson/bin/python}" - <<'PY'
"""Read-only recovery of job153's four attested native replays.
Do not rerun solver, modify source, infer absent diagnostics or claim int2 parity.
"""
import datetime as dt, hashlib, json, pathlib, sys
import h5py, numpy as np
repo=pathlib.Path("/home/ubuntu/work/openmc/sweep")
job="20261103-154-native-int2-hdf5-recovery"
parent="20261103-153-native-int2-attested-replay"
out=repo/"validation_runs/m3dc1_tct_native_int2_hdf5_recovery_154"
out.mkdir(parents=True,exist_ok=True)
runroot=pathlib.Path("/tmp/m3dc1_tct_native_int2_attested_replay_153_runs")
report={"schema_version":1,"job_id":job,"parent_result_job_id":parent,
"fuel_track":"fuel_agnostic_control","machine":"normalized-native-M3D-C1",
"shot_ids":[],"classification":"M3DC1_NATIVE_INT2_HDF5_RECOVERY_PREREQUISITE_BLOCKED",
"physics_solver_runs":0,"reused_parent_solver_runs":4,"zero_equivalence_tolerance":1e-12,
"frozen_gates_preserved":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.1},
"native_int2_operator_parity_validated":False,"physical_current_calibrated":False,
"causal_segmented_controller_authority_validated":False,"pb11_fidelity_validated":False,
"ignition_or_net_power_validated":False,"timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
"claim_boundary":"Attested native job153 replay artifacts only; no independent int2 quadrature parity, physical-current calibration, causal segmented TCT, shot handoff, p-B11 or net power."}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def datasets(f):
    paths=[]
    f.visititems(lambda name,obj: paths.append("/"+name) if isinstance(obj,h5py.Dataset) else None)
    return paths
def read_field(f,path):
    if path not in f:return None
    a=np.asarray(f[path][()],dtype=float).reshape(-1)
    if not a.size or not np.isfinite(a).all():raise ValueError("NONFINITE_OR_EMPTY_FIELD:"+path)
    return a
try:
    receipt=repo/"agent_pipeline/results"/(parent+".json")
    if not receipt.is_file():
        report["prerequisite_blocker"]="PARENT_RECEIPT_MISSING"
    else:
        prior=json.loads(receipt.read_text())
        if prior.get("summary",{}).get("classification")!="M3DC1_NATIVE_INT2_ATTESTED_REPLAY_PIPELINE_BLOCKED" or prior.get("summary",{}).get("physics_solver_runs")!=4:
            report["prerequisite_blocker"]="PARENT_RECEIPT_CHANGED"
        elif prior.get("summary",{}).get("executable_sha256")!="8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec":
            report["prerequisite_blocker"]="PARENT_EXECUTABLE_ATTESTATION_CHANGED"
        else:
            cases=("baseline","same_mode_zero","full_negative","full_positive")
            grids=prior["summary"]["time_grids"]
            report["parent_receipt_sha256"]=sha(receipt)
            report["parent_executable_sha256"]=prior["summary"]["executable_sha256"]
            report["dataset_inventories"]={}
            frames=[]
            maxzero=0.0
            missing=[]
            for i in range(4):
                data={}
                for case in cases:
                    d=runroot/case
                    frame=d/("time_%03d.h5"%i)
                    if not frame.is_file():
                        missing.append(str(frame));continue
                    with h5py.File(frame,"r") as f:
                        keys=datasets(f)
                        if i==0:report["dataset_inventories"][case]={"time_frame":keys}
                        j=read_field(f,"/fields/jphi")
                        if j is None:
                            missing.append(case+":/fields/jphi");continue
                        current=read_field(f,"/scalars/toroidal_current")
                    if current is None:
                        c1=d/"C1.h5"
                        if c1.is_file():
                            with h5py.File(c1,"r") as f:
                                if i==0:report["dataset_inventories"][case]["C1_h5"]=datasets(f)
                                arr=read_field(f,"/scalars/toroidal_current")
                                if arr is not None and arr.size>i:current=np.array([arr[i]])
                    data[case]={"jphi":j,"current":None if current is None else float(current[0])}
                if len(data)!=4:continue
                if any(data[c]["jphi"].shape!=data["baseline"]["jphi"].shape for c in cases):
                    missing.append("JPHI_SHAPE_MISMATCH_FRAME_"+str(i));continue
                maxzero=max(maxzero,float(np.max(np.abs(data["baseline"]["jphi"]-data["same_mode_zero"]["jphi"]))))
                frames.append({"time":grids["baseline"][i],
                               "native_toroidal_current":{c:data[c]["current"] for c in cases},
                               "signed_current_delta_from_zero":{c:(data[c]["current"]-data["same_mode_zero"]["current"] if data[c]["current"] is not None and data["same_mode_zero"]["current"] is not None else None) for c in ("full_negative","full_positive")}})
            report["frames"]=frames
            report["missing_diagnostics"]=missing
            if len(frames)==4:
                report["zero_equivalence"]={"max_abs_jphi_delta":maxzero,"pass":maxzero<=1e-12}
                report["classification"]="M3DC1_NATIVE_INT2_HDF5_RECOVERY_DIAGNOSTIC_COMPLETE" if maxzero<=1e-12 else "M3DC1_NATIVE_INT2_HDF5_RECOVERY_ZERO_EQUIVALENCE_FAILED"
                report["interpretation"]="Recovered four existing native jphi frames; missing current scalars are explicit nulls. Native outputs are not independent int2 parity."
            else:report["prerequisite_blocker"]="PARENT_NATIVE_HDF5_DATASET_OR_FRAME_UNAVAILABLE"
except Exception as exc:
    report["classification"]="M3DC1_NATIVE_INT2_HDF5_RECOVERY_PIPELINE_BLOCKED"
    report["pipeline_error"]=type(exc).__name__+": "+str(exc)
target=out/"native_int2_hdf5_recovery_summary.json"
temp=target.with_suffix(".json.tmp")
temp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
temp.replace(target)
print(json.dumps(report,sort_keys=True,indent=2))
if "pipeline_error" in report:sys.exit(1)
PY

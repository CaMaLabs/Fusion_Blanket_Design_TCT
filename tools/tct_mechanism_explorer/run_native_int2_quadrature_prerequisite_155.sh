#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-/home/ubuntu/work/openmc/sweep/.venv-dudson/bin/python}" - <<'PY'
"""Native HDF5 quadrature-input audit. Read only; no solver rerun or physics edits."""
import datetime as dt, hashlib, json, pathlib, sys
import h5py, numpy as np
repo=pathlib.Path("/home/ubuntu/work/openmc/sweep")
job="20261106-155-native-int2-quadrature-prerequisite"
parent="20261103-154-native-int2-hdf5-recovery"
out=repo/"validation_runs/m3dc1_tct_native_int2_quadrature_prerequisite_155"
out.mkdir(parents=True,exist_ok=True)
root=pathlib.Path("/tmp/m3dc1_tct_native_int2_attested_replay_153_runs")
cases=("baseline","same_mode_zero","full_negative","full_positive")
expected_exe="8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec"
source=pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
expected_sources={"M3Dmodules.f90":"bdf67e1267f177dd7c1826a23b5a0265f612e40c4347521e0642bb8a8e999011","m3dc1_nint.f90":"15556646264a010de8a416cedc07258b539e013ef6f507ca5e9b60d437e47693","diagnostics.f90":"0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655"}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r={"schema_version":1,"job_id":job,"parent_result_job_id":parent,"fuel_track":"fuel_agnostic_control","machine":"normalized-native-M3D-C1","shot_ids":[],"timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"classification":"M3DC1_NATIVE_INT2_QUADRATURE_PREREQUISITE_BLOCKED","physics_solver_runs":0,"zero_equivalence_tolerance":1e-12,"frozen_gates_preserved":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.1},"independent_int2_operator_parity_validated":False,"physical_current_calibrated":False,"causal_segmented_controller_authority_validated":False,"pb11_fidelity_validated":False,"ignition_or_net_power_validated":False,"expected_executable_sha256":expected_exe,"expected_source_sha256":expected_sources,"claim_boundary":"HDF5 mesh/field/current input availability and attested source only; not independent int2 quadrature parity, calibrated current, causal TCT, p-B11 or net power."}
def info(f,p):
    if p not in f:return None
    o=f[p]
    return {"shape":list(o.shape),"dtype":str(o.dtype),"attrs":{str(k):str(v)[:200] for k,v in o.attrs.items()},"sha256":hashlib.sha256(np.asarray(o[()]).tobytes()).hexdigest()}
try:
    receipt=repo/"agent_pipeline/results"/(parent+".json")
    if not receipt.is_file():raise RuntimeError("PARENT_154_RECEIPT_MISSING")
    prior=json.loads(receipt.read_text())
    if prior.get("summary",{}).get("classification")!="M3DC1_NATIVE_INT2_HDF5_RECOVERY_DIAGNOSTIC_COMPLETE":raise RuntimeError("PARENT_154_CLASSIFICATION_CHANGED")
    r["parent_receipt_sha256"]=sha(receipt)
    r["source_attestation"]={k:{"exists":(source/k).is_file(),"sha256":sha(source/k) if (source/k).is_file() else None,"matches_pin":(source/k).is_file() and sha(source/k)==v} for k,v in expected_sources.items()}
    if not all(v["matches_pin"] for v in r["source_attestation"].values()):raise RuntimeError("NATIVE_SOURCE_ATTESTATION_MISMATCH")
    r["frames"]={}
    jphi={}
    for case in cases:
        r["frames"][case]=[]
        jphi[case]=[]
        for i in range(4):
            p=root/case/("time_%03d.h5"%i)
            if not p.is_file():raise RuntimeError("SAVED_FRAME_MISSING:"+str(p))
            with h5py.File(p,"r") as f:
                d={key:info(f,key) for key in ("/mesh/elements","/mesh/adjacency","/fields/jphi","/fields/mesh_zone","/scalars/toroidal_current")}
                for key in ("/mesh/elements","/fields/jphi"):
                    if d[key] is None:raise RuntimeError("REQUIRED_DATASET_MISSING:"+case+":"+key)
                r["frames"][case].append({"frame":i,"file_sha256":sha(p),"datasets":d})
                jphi[case].append(np.asarray(f["/fields/jphi"][()],dtype=np.float64))
    zero=max(float(np.max(np.abs(a-b))) for a,b in zip(jphi["baseline"],jphi["same_mode_zero"]))
    r["zero_equivalence"]={"max_abs_jphi_delta":zero,"pass":zero<=1e-12}
    if zero>1e-12:r["classification"]="M3DC1_NATIVE_INT2_QUADRATURE_ZERO_EQUIVALENCE_FAILED"
    else:
        # HDF5 mesh connectivity is not itself the physical element map/Jacobian.
        # Explicitly require independently verified element coordinates, basis,
        # quadrature points/weights, ijacobian mode and unit normalization.
        r["required_for_independent_parity"]=["verified physical mesh coordinates and element mapping","native basis evaluation at int2 quadrature points","native quadrature weights and Jacobian determinant including ijacobian=1 behavior","toroidal-current diagnostic normalization and integration domain"]
        r["classification"]="M3DC1_NATIVE_INT2_QUADRATURE_INPUT_AUDIT_COMPLETE"
        r["parity_status"]="NOT_EVALUATED_UNTIL_NATIVE_WEIGHT_AND_GEOMETRY_MAPPING_ATTESTED"
        r["interpretation"]="Four attested replay frames inspected; HDF5 dataset shapes, hashes and attributes recorded. No unverified triangle-area proxy is promoted to native int2 parity."
except Exception as exc:
    r["classification"]="M3DC1_NATIVE_INT2_QUADRATURE_PREREQUISITE_BLOCKED"
    r["prerequisite_blocker"]=type(exc).__name__+": "+str(exc)
target=out/"native_int2_quadrature_prerequisite_summary.json"
temp=target.with_suffix(".json.tmp")
temp.write_text(json.dumps(r,indent=2,sort_keys=True,allow_nan=False)+"\n")
temp.replace(target)
print(json.dumps({"job_id":job,"classification":r["classification"],"zero_equivalence":r.get("zero_equivalence"),"prerequisite_blocker":r.get("prerequisite_blocker"),"parity_status":r.get("parity_status")},sort_keys=True))
PY

#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-/home/ubuntu/work/openmc/sweep/.venv-dudson/bin/python}" - <<'PY'
"""Bounded four-case native replay: binary/source attestation and current diagnostic.
No modification of M3D-C1 equations, solver thresholds, or source physics.
This is NOT independent int2 quadrature parity; the latter requires an
instrumented native int2 trace or a verified reconstruction of its inputs.
"""
import datetime as dt
import hashlib, json, math, pathlib, sys
repo=pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0,str(repo/"tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta
import h5py
job="20261103-153-native-int2-attested-replay"
out=repo/"validation_runs/m3dc1_tct_native_int2_attested_replay_153"
out.mkdir(parents=True,exist_ok=True)
native.OUT=out
native.RUN_ROOT=pathlib.Path("/tmp/m3dc1_tct_native_int2_attested_replay_153_runs")
expected_exe="8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec"
source=pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
expected_sources={"M3Dmodules.f90":"bdf67e1267f177dd7c1826a23b5a0265f612e40c4347521e0642bb8a8e999011","m3dc1_nint.f90":"15556646264a010de8a416cedc07258b539e013ef6f507ca5e9b60d437e47693","diagnostics.f90":"0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655"}
report={"schema_version":1,"job_id":job,"parent_result_job_id":"20261030-152-native-ijacobian-runtime-provenance","fuel_track":"fuel_agnostic_control","machine":"normalized-native-M3D-C1","shot_ids":[],"classification":"M3DC1_NATIVE_INT2_ATTESTED_REPLAY_PREREQUISITE_BLOCKED","timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"physics_solver_runs":0,"expected_executable_sha256":expected_exe,"expected_source_sha256":expected_sources,"native_int2_operator_parity_validated":False,"physical_current_calibrated":False,"causal_segmented_controller_authority_validated":False,"pb11_fidelity_validated":False,"ignition_or_net_power_validated":False,"zero_equivalence_tolerance":1e-12,"frozen_gates_preserved":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.10},"claim_boundary":"Native replay and HDF5 current scalar evidence only; no independently instrumented int2 quadrature, physical-current calibration, causal TCT, shot handoff, p-B11 or net power."}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
try:
    parent=repo/"validation_runs/m3dc1_tct_native_ijacobian_runtime_152/native_ijacobian_runtime_provenance_summary.json"
    if not parent.is_file() or sha(parent)!="600540b606a5aed693e818cf7f106bed2c62f520514228fb3201ebf2dc2bea4c":
        report["prerequisite_blocker"]="PARENT_152_SUMMARY_MISSING_OR_CHANGED"
    elif any(not (source/k).is_file() or sha(source/k)!=v for k,v in expected_sources.items()):
        report["prerequisite_blocker"]="PINNED_NATIVE_SOURCE_MISSING_OR_CHANGED"
    else:
        pta.install_operator()
        native.install_current_redistribution_operator()
        pta.build()
        report["executable_sha256"]=pta.sha256_file(native.EXE)
        if report["executable_sha256"]!=expected_exe:
            report["prerequisite_blocker"]="EXECUTABLE_HASH_DIFFERS_FROM_JOB130_PIN"
        else:
            cases=(("baseline",0,0.0),("same_mode_zero",4,0.0),("full_negative",4,-0.005),("full_positive",4,0.005))
            dirs={}
            for name,mode,amp in cases:
                d=native.write_input(name,mode,amp,0,0.0,0.04,nmax_steps=3)
                native.execute(d)
                dirs[name]=d
                report["physics_solver_runs"]+=1
            times={name:[float(row["time"]) for row in pta.c1ke(d)] for name,d in dirs.items()}
            report["time_grids"]=times
            if any(len(v)!=4 or any(abs(x-y)>1e-8 for x,y in zip(v,times["baseline"])) for v in times.values()):
                report["prerequisite_blocker"]="NATIVE_TIME_GRID_MISMATCH"
            else:
                frames=[]
                zero_max=0.0
                for i in range(4):
                    data={}
                    for name,d in dirs.items():
                        with h5py.File(d/("time_%03d.h5"%i),"r") as f:
                            j=f["/fields/jphi"][:]
                            scalar=f["/scalars/toroidal_current"][()]
                            import numpy as np
                            data[name]={"jphi":np.asarray(j,dtype=float).reshape(-1),"current":float(np.asarray(scalar).reshape(-1)[0])}
                    baseline=data["baseline"]["jphi"]
                    zero=data["same_mode_zero"]["jphi"]
                    if baseline.shape!=zero.shape or not all(data[n]["jphi"].shape==baseline.shape for n in data):
                        raise RuntimeError("JPHI_SHAPE_MISMATCH")
                    zero_max=max(zero_max,float(abs(baseline-zero).max()))
                    frames.append({"time":times["baseline"][i],"native_toroidal_current":{n:data[n]["current"] for n in data},"signed_current_delta_from_zero":{n:data[n]["current"]-data["same_mode_zero"]["current"] for n in ("full_negative","full_positive")}})
                report["frames"]=frames
                report["zero_equivalence"]={"max_abs_jphi_delta":zero_max,"pass":zero_max<=1e-12}
                report["classification"]=("M3DC1_NATIVE_INT2_ATTESTED_REPLAY_DIAGNOSTIC_COMPLETE" if zero_max<=1e-12 else "M3DC1_NATIVE_INT2_ATTESTED_REPLAY_ZERO_EQUIVALENCE_FAILED")
                report["interpretation"]="Four native cases replayed against a pinned executable/source hash, with zero-mode jphi equivalence and native current scalars compared. Native scalar output is not an independent int2 implementation; operator parity and physical-current calibration remain unvalidated."
except Exception as exc:
    report["classification"]="M3DC1_NATIVE_INT2_ATTESTED_REPLAY_PIPELINE_BLOCKED"
    report["pipeline_error"]=type(exc).__name__+": "+str(exc)
target=out/"native_int2_attested_replay_summary.json"
temp=target.with_suffix(".json.tmp")
temp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
temp.replace(target)
print(json.dumps(report,sort_keys=True,indent=2))
if "pipeline_error" in report:sys.exit(1)
PY

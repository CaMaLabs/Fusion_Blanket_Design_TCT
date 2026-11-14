#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
import json, math, pathlib, sys, hashlib
repo=pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0,str(repo/"tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta
out=repo/"validation_runs/m3dc1_tct_native_signed_ab_156"
out.mkdir(parents=True,exist_ok=True)
report={"schema_version":1,"job_id":"20261113-156-native-signed-current-redistribution-ab","classification":"M3DC1_NATIVE_SIGNED_AB_UNRESOLVED","fuel_track":"fuel_agnostic_control","machine":"normalized-native-M3D-C1","shot_ids":[],"physics_solver_runs":0,"dt":0.000625,"steps":48,"source_mode":4,"source_gate":[0,0.04],"amplitude":0.005,"matched_times":[0.01,0.02,0.03],"frozen_gates":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.10},"claim_boundary":"Native open-loop matched A/B simulation; no independent int2 parity, calibrated current, causal closed-loop TCT, experimental shot handoff, p-B11 fidelity or net power."}
try:
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    exe_hash=pta.sha256_file(native.EXE)
    report["executable_sha256"]=exe_hash
    if exe_hash!="8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec":
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")
    native.DT=report["dt"]
    native.RUN_ROOT=pathlib.Path("/tmp/m3dc1_tct_native_signed_ab_156")
    native.OUT=out
    metrics=("W_sheet","Jpk","Jint_high","Reconnected_Flux","magnetic_energy","center_abs_current","shoulder_abs_current")
    runs={}
    for name,mode,amp in [("baseline",0,0.0),("same_mode_zero",4,0.0),("positive",4,0.005),("negative",4,-0.005)]:
        d=native.write_input(name,mode,amp,0,0.0,0.04,nmax_steps=48)
        print("NATIVE_SOLVER_START",name,flush=True)
        native.execute(d)
        report["physics_solver_runs"]+=1
        runs[name]=native.safe_extract(d)
    for name,rows in runs.items():
        if len(rows)!=49: raise RuntimeError("FRAME_COUNT_MISMATCH:"+name)
        for i,row in enumerate(rows):
            if abs(float(row["time"])-i*report["dt"])>1e-8: raise RuntimeError("TIME_GRID_MISMATCH:"+name)
            if any(not math.isfinite(float(row[k])) for k in metrics): raise RuntimeError("NONFINITE_METRIC:"+name)
    z=max(abs(float(a[k])-float(c[k])) for a,c in zip(runs["baseline"],runs["same_mode_zero"]) for k in metrics)
    report["zero_equivalence"]={"max_abs_metric_delta":z,"pass":z<=1e-12}
    report["frames"]=[]
    for t in report["matched_times"]:
        i=round(t/report["dt"])
        ref=runs["same_mode_zero"][i]
        f={"time":t,"cases":{}}
        for name in ("positive","negative"):
            row=runs[name][i]
            w=100*(float(row["W_sheet"])-float(ref["W_sheet"]))/max(abs(float(ref["W_sheet"])),1e-300)
            j=100*(float(row["Jpk"])-float(ref["Jpk"]))/max(abs(float(ref["Jpk"])),1e-300)
            f["cases"][name]={"width_gain_pct":w,"Jpk_change_pct":j,"open_loop_frozen_gate_crossing":w>0.02 and j<=0.10,"native_metric_deltas":{k:float(row[k])-float(ref[k]) for k in metrics}}
        report["frames"].append(f)
    report["classification"]="M3DC1_NATIVE_SIGNED_AB_COMPLETE" if report["zero_equivalence"]["pass"] else "M3DC1_NATIVE_SIGNED_AB_ZERO_EQUIVALENCE_FAILED"
except Exception as exc:
    report["pipeline_error"]=type(exc).__name__+": "+str(exc)
    report["classification"]="M3DC1_NATIVE_SIGNED_AB_PIPELINE_BLOCKED"
p=out/"native_signed_ab_summary.json"
p.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
print(json.dumps(report,sort_keys=True),flush=True)
if "pipeline_error" in report: sys.exit(1)
PY

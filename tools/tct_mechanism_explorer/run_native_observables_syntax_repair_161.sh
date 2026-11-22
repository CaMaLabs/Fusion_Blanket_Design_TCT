#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Repair job160 literal backslash-n syntax error; preserve its intended time-precision audit and physics."""
import datetime, json, math, pathlib, sys
repo=pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0,str(repo/"tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta
job="20261122-161-native-observables-syntax-repair"
parent="20261122-160-native-observables-time-precision-repair"
out=repo/"validation_runs/m3dc1_tct_native_temporal_convergence_161"
out.mkdir(parents=True,exist_ok=True)
target=out/"native_temporal_convergence_syntax_repair_summary.json"
metrics=("W_sheet","Jpk","Jint_high","Reconnected_Flux","magnetic_energy","center_abs_current","shoulder_abs_current")
cases=(("baseline",0,0.0),("same_mode_zero",4,0.0),("neg_nominal",4,-0.005),("neg_double",4,-0.01),("pos_nominal",4,0.005),("pos_double",4,0.01))
report={"schema_version":1,"job_id":job,"parent_result_job_id":parent,"fuel_track":"fuel_agnostic_control","machine":"normalized-native-M3D-C1","shot_ids":[],"classification":"M3DC1_NATIVE_OBSERVABLES_TEMPORAL_CONVERGENCE_UNRESOLVED","dt_coarse":0.000625,"dt_fine":0.0003125,"steps_fine":96,"matched_times":[0.01,0.02,0.03],"source_mode":4,"source_gate":[0.0,0.04],"zero_equivalence_tolerance":1e-12,"expected_parent_summary_sha256":"130428a1245a2e87068456fef7df721b32ef4c7a8c20d41c9ac4712d1fc3b9e0","expected_executable_sha256":"8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec","frozen_gates_preserved":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.10},"convergence_rule":{"effect_relative_change_max":0.25,"effect_absolute_floor":1e-12,"requires_all_nontrivial_W_sheet_and_Jpk_effects":True},"temporal_convergence_established":False,"physical_current_calibrated":False,"independent_int2_parity_validated":False,"controller_in_loop_authority_established":False,"pb11_fidelity_validated":False,"ignition_or_net_power_validated":False,"claim_boundary":"Two-level temporal consistency of native open-loop normalized M3D-C1 observables only. Not continuum convergence proof, calibrated physical current, independent int2 parity, segmented closed-loop TCT authority, p-B11 fidelity, ignition or net power.","timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
try:
    parent_path=repo/"validation_runs/m3dc1_tct_native_observables_157/fine_dt_native_observables_summary.json"
    if not parent_path.is_file() or pta.sha256_file(parent_path)!=report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    coarse=json.loads(parent_path.read_text())
    blocked_path=repo/"validation_runs/m3dc1_tct_native_temporal_convergence_158/native_temporal_convergence_summary.json"
    if not blocked_path.is_file() or pta.sha256_file(blocked_path)!="b7e0fd02e623846db9c41dd75ae0c0d4a9f84b635b5b2a3baaf6f7602ccd50fc":
        raise RuntimeError("BLOCKED_PARENT_SUMMARY_MISSING_OR_CHANGED")
    report["repaired_result_job_id"]="20261122-160-native-observables-time-precision-repair"
    prior=repo/"validation_runs/m3dc1_tct_native_temporal_convergence_159/native_temporal_convergence_repair_summary.json"
    if not prior.is_file() or pta.sha256_file(prior)!="974002f291c64241dcf8539fd17d83940e06aee7b492eff350e5346d4e4d4434":
        raise RuntimeError("REPAIR_PARENT_SUMMARY_MISSING_OR_CHANGED")
    report["time_grid_tolerance"]=2e-6
    report["observed_parent_max_abs_grid_delta"]=5.000000000005e-7
    report["time_tolerance_basis"]="2e-6 bounded extraction timestamp precision, greater than measured 5e-7; no solver time-step changes"
    if coarse.get("job_id")!="20261121-157-native-edge-observables-replay" or coarse.get("classification")!="M3DC1_NATIVE_CURRENT_DRIVE_FINE_DT_NATIVE_OBSERVABLES_DIAGNOSTIC_COMPLETE" or coarse.get("zero_equivalence",{}).get("pass") is not True:
        raise RuntimeError("PARENT_CLASSIFICATION_OR_ZERO_GATE_INVALID")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"]=pta.sha256_file(native.EXE)
    if report["executable_sha256"]!=report["expected_executable_sha256"]:
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")
    native.DT=report["dt_fine"]
    native.RUN_ROOT=pathlib.Path("/tmp/m3dc1_tct_native_temporal_convergence_161")
    native.OUT=out
    runs={}
    for name,mode,amp in cases:
        d=native.write_input(name,mode,amp,0,0.0,0.04,nmax_steps=96)
        print("[native-temporal-convergence] "+name,flush=True)
        native.execute(d)
        runs[name]=native.safe_extract(d)
    times=[i*report["dt_fine"] for i in range(97)]
    for name,rows in runs.items():
        observed_times=[float(r["time"]) for r in rows]
        report.setdefault("time_grid_diagnostics",{})[name]={"observed_count":len(rows),"expected_count":97,"first_time":observed_times[0] if observed_times else None,"last_time":observed_times[-1] if observed_times else None,"max_abs_grid_delta":max((abs(a-b) for a,b in zip(observed_times,times)),default=None),"strictly_increasing":all(b>a for a,b in zip(observed_times,observed_times[1:]))}
        if len(rows)!=97 or not report["time_grid_diagnostics"][name]["strictly_increasing"] or report["time_grid_diagnostics"][name]["max_abs_grid_delta"]>report["time_grid_tolerance"]:
            raise RuntimeError("TIME_GRID_OR_FRAME_COUNT_MISMATCH:"+name+":"+json.dumps(report["time_grid_diagnostics"][name],sort_keys=True))
        if any(not math.isfinite(float(r[k])) for r in rows for k in metrics):
            raise RuntimeError("NONFINITE_OBSERVABLE:"+name)
    zero=max(abs(float(a[k])-float(b[k])) for a,b in zip(runs["baseline"],runs["same_mode_zero"]) for k in metrics)
    report["zero_equivalence"]={"max_abs_metric_delta":zero,"pass":zero<=1e-12}
    if not report["zero_equivalence"]["pass"]:
        report["classification"]="M3DC1_NATIVE_OBSERVABLES_TEMPORAL_CONVERGENCE_ZERO_EQUIVALENCE_FAILED"
    else:
        comparisons=[]
        for frame in coarse["matched_frames"]:
            t=float(frame["time"])
            idx=next((i for i,v in enumerate(times) if abs(v-t)<1e-8),None)
            if idx is None: raise RuntimeError("MATCHED_TIME_MISSING")
            baseline=runs["same_mode_zero"][idx]
            for name in ("neg_nominal","neg_double","pos_nominal","pos_double"):
                row=runs[name][idx]
                coarse_case=frame["cases"][name]
                fine_delta={k:float(row[k])-float(baseline[k]) for k in metrics}
                width=100*fine_delta["W_sheet"]/max(abs(float(baseline["W_sheet"])),1e-300)
                jpk=100*fine_delta["Jpk"]/max(abs(float(baseline["Jpk"])),1e-300)
                effect={}
                for key,old,new in (("width_gain_pct",float(coarse_case["width_gain_pct"]),width),("Jpk_change_pct",float(coarse_case["Jpk_change_pct"]),jpk)):
                    meaningful=max(abs(old),abs(new))>1e-12
                    rel=abs(new-old)/max(abs(old),abs(new),1e-12)
                    effect[key]={"coarse":old,"fine":new,"relative_change":rel,"meaningful":meaningful,"consistent":meaningful and rel<=0.25}
                comparisons.append({"time":t,"case":name,"effect":effect,"fine_native_metric_deltas":fine_delta,"frozen_open_loop_metric_comparison":{"width_gt_0p020_pct":width>0.02,"Jpk_le_0p10_pct":jpk<=0.10,"both":width>0.02 and jpk<=0.10}})
        report["comparisons"]=comparisons
        report["temporal_convergence_established"]=all(c["effect"][k]["consistent"] for c in comparisons for k in ("width_gain_pct","Jpk_change_pct"))
        report["classification"]="M3DC1_NATIVE_OBSERVABLES_TWO_LEVEL_TEMPORAL_CONSISTENCY_DIAGNOSTIC_COMPLETE"
        report["interpretation"]="Two-level fixed-output-time comparison; 25% relative-effect criterion is diagnostic and does not prove asymptotic convergence. No open-loop metric crossing implies controller authority."
except Exception as exc:
    report["pipeline_error"]=type(exc).__name__+": "+str(exc)
    report["classification"]="M3DC1_NATIVE_OBSERVABLES_TEMPORAL_CONVERGENCE_PIPELINE_BLOCKED"
tmp=target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
tmp.replace(target)
print(json.dumps(report,indent=2,sort_keys=True))
if "pipeline_error" in report: sys.exit(1)
PY

#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
python3 - <<'PY'
"""Bounded native int2 Jacobian/weight runtime-prerequisite audit; no solver runs."""
import datetime as dt, hashlib, json, pathlib, re, sys
repo=pathlib.Path("/home/ubuntu/work/openmc/sweep")
native=pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
parent="20261030-150-native-int2-input-producer-lineage"
parent_path=repo/"validation_runs/m3dc1_tct_native_int2_lineage_150/native_int2_input_producer_lineage_summary.json"
parent_sha="078ba1d5aba97e93bcec4935643b0b6015dee15d37b0e711b1ebd001bcf0da76"
source_sha={"diagnostics.f90":"0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655","nintegrate_mod.f90":"fd4be567e954d9df18e7ed83d3f622816a48c939832a4b7df700be3746471d00","m3dc1_nint.f90":"15556646264a010de8a416cedc07258b539e013ef6f507ca5e9b60d437e47693"}
out=repo/"validation_runs/m3dc1_tct_native_int2_weight_branch_151"
out.mkdir(parents=True,exist_ok=True)
report={"schema_version":1,"job_id":"20261030-151-native-int2-weight-jacobian-branch","parent_result_job_id":parent,"fuel_track":"fuel_agnostic_control","machine":"normalized-native-M3D-C1","shot_ids":[],"classification":"M3DC1_NATIVE_INT2_WEIGHT_JACOBIAN_BRANCH_PREREQUISITE_BLOCKED","expected_parent_summary_sha256":parent_sha,"expected_native_source_sha256":source_sha,"saved_run_origin_job_id":"20261029-130-native-current-drive-geometry-weight-sensitivity","physics_solver_runs":0,"native_int2_operator_parity_validated":False,"runtime_jacobian_branch_confirmed":False,"physical_current_calibrated":False,"causal_segmented_controller_authority_validated":False,"pb11_fidelity_validated":False,"ignition_or_net_power_validated":False,"zero_equivalence_tolerance":1e-12,"frozen_gates_preserved":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.10},"claim_boundary":"Read-only native source and existing run-input preflight; no independent int2 parity, physical current conservation/calibration, causal TCT, shot handoff, p-B11 or net power.","timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
try:
    if not parent_path.is_file() or sha(parent_path)!=parent_sha:
        report["prerequisite_blocker"]="PARENT_SUMMARY_MISSING_OR_CHANGED"
    else:
        p=json.loads(parent_path.read_text())
        if p.get("classification")!="M3DC1_NATIVE_INT2_INPUT_PRODUCER_LINEAGE_AUDIT_COMPLETE" or p.get("parent_value_time_parity_supported") is not True:
            report["prerequisite_blocker"]="PARENT_EVIDENCE_CHANGED"
        else:
            missing=[k for k,v in source_sha.items() if not (native/k).is_file() or sha(native/k)!=v]
            if missing:
                report["prerequisite_blocker"]="NATIVE_SOURCE_MISSING_OR_CHANGED"
                report["missing_or_changed_source"]=missing
            else:
                evidence={}
                for name in source_sha:
                    lines=(native/name).read_text(errors="replace").splitlines()
                    hits=[]
                    for i,line in enumerate(lines):
                        code=line.split("!",1)[0].strip()
                        if not code:continue
                        if (name=="diagnostics.f90" and "totcur" in code.lower() and "int2(" in code.lower()) or (name=="nintegrate_mod.f90" and ("weight_79" in code.lower() or re.search(r"\bfunction\s+int2\b",code,re.I))) or (name=="m3dc1_nint.f90" and ("ijacobian" in code.lower() or ("weight_79" in code.lower() and "=" in code))):
                            hits.append({"line":i+1,"code":code[:220]})
                    evidence[name]=hits[:80]
                report["source_path_evidence"]=evidence
                runroot=pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs")
                cases=("baseline","same_mode_zero","full_negative","full_positive")
                report["existing_run_input_evidence"]={}
                for case in cases:
                    d=runroot/case
                    found=[]
                    if d.is_dir():
                        for f in sorted(d.iterdir()):
                            if f.is_file() and f.stat().st_size<2000000 and f.suffix.lower() in ("",".in",".dat",".nml",".txt",".cfg"):
                                try:
                                    for n,line in enumerate(f.read_text(errors="replace").splitlines(),1):
                                        if re.search(r"\bijacobian\b",line,re.I):
                                            found.append({"file":f.name,"line":n,"text":line.strip()[:220]})
                                except OSError:pass
                    report["existing_run_input_evidence"][case]={"directory_present":d.is_dir(),"ijacobian_lines":found[:12]}
                source_ready=bool(evidence["diagnostics.f90"] and evidence["nintegrate_mod.f90"] and evidence["m3dc1_nint.f90"])
                report["source_weight_branch_traceable"]=source_ready
                report["runtime_jacobian_branch_confirmed"]=False
                if source_ready:
                    report["classification"]="M3DC1_NATIVE_INT2_WEIGHT_JACOBIAN_SOURCE_PATH_AUDIT_COMPLETE"
                    report["interpretation"]="Native int2 weight and conditional Jacobian source path traced. Runtime ijacobian setting is not inferred from source references or missing input overrides; exact quadrature operator parity remains unvalidated."
                else:report["prerequisite_blocker"]="SOURCE_WEIGHT_PATH_UNRESOLVED"
except Exception as exc:
    report["classification"]="M3DC1_NATIVE_INT2_WEIGHT_JACOBIAN_PIPELINE_BLOCKED"
    report["pipeline_error"]=type(exc).__name__+": "+str(exc)
target=out/"native_int2_weight_jacobian_branch_summary.json"
tmp=target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
tmp.replace(target)
print(json.dumps(report,sort_keys=True,indent=2))
if "pipeline_error" in report:sys.exit(1)
PY

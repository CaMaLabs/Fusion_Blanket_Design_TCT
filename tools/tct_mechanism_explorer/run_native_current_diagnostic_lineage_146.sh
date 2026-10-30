#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"$TCT_PYTHON" - <<'PY'
"""Source-guarded native toroidal-current diagnostic lineage; zero solver runs."""
import datetime, hashlib, json, pathlib, re, sys
repo=pathlib.Path("/home/ubuntu/work/openmc/sweep")
native=pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
job="20261030-146-native-current-diagnostic-lineage"
parent_id="20261030-145-native-poloidal-area-weighted-jphi-response"
parent_path=repo/"validation_runs/m3dc1_tct_native_area_jphi_145/poloidal_area_weighted_jphi_summary.json"
parent_sha="dbd5b0a8419fd2a5bc56721c562f98d393d4a792a648f9c366a99dd40a9135de"
out=repo/"validation_runs/m3dc1_tct_native_current_lineage_146"
out.mkdir(parents=True,exist_ok=True)
report={
 "schema_version":1,"job_id":job,"parent_result_job_id":parent_id,
 "expected_parent_summary_sha256":parent_sha,
 "classification":"M3DC1_NATIVE_CURRENT_DIAGNOSTIC_LINEAGE_UNRESOLVED",
 "fuel_track":"fuel_agnostic_control","machine":"normalized-native-M3D-C1",
 "shot_ids":[],"physics_solver_runs":0,"zero_equivalence_tolerance":1e-12,
 "frozen_gates_preserved":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.10},
 "native_int2_physical_current_parity_validated":False,
 "calibrated_physical_current_validated":False,
 "calibrated_physical_width_validated":False,
 "temporal_convergence_validated":False,
 "causal_segmented_controller_authority_validated":False,
 "shot_handoff_validated":False,"pb11_fidelity_validated":False,
 "claim_boundary":"Native M3D-C1 toroidal-current source callsite and saved 2-D jphi schema only; no int2 parity, physical current calibration, causal segmented TCT, shot handoff, p-B11, ignition or net power.",
 "timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def context(lines,i): return "\n".join(str(j+1)+": "+lines[j][:200] for j in range(max(0,i-3),min(len(lines),i+4)))
try:
 if not parent_path.is_file() or sha(parent_path)!=parent_sha:
  raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
 parent=json.loads(parent_path.read_text())
 if parent.get("job_id")!=parent_id or parent.get("classification")!="M3DC1_NATIVE_POLOIDAL_AREA_WEIGHTED_JPHI_RESPONSE_DIAGNOSTIC_COMPLETE":
  raise RuntimeError("PARENT_CLASSIFICATION_OR_ID_CHANGED")
 if parent.get("zero_equivalence",{}).get("pass") is not True or parent.get("physical_current_quadrature_validated") is not False:
  raise RuntimeError("PARENT_ZERO_OR_CURRENT_FIDELITY_GATE_CHANGED")
 report["parent_area_signed_t003"]={
  k:parent["frames"][-1]["cases"][k]["weighting"]["crosschecked_2d_poloidal_area"]["signed"]
  for k in ("full_negative","full_positive")}
 report["parent_zero_max_abs_field_delta"]=parent["zero_equivalence"]["max_abs_field_delta"]
 report["parent_cancellation_shift"]=parent["max_e2_vs_area_cancellation_fraction_shift"]
 diag=native/"diagnostics.f90"
 expected="0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655"
 if not diag.is_file() or sha(diag)!=expected:
  report["classification"]="M3DC1_NATIVE_CURRENT_DIAGNOSTIC_SOURCE_BLOCKED"
  report["prerequisite_blocker"]="NATIVE_DIAGNOSTICS_SOURCE_MISSING_OR_CHANGED"
 else:
  lines=diag.read_text(errors="replace").splitlines()
  report["diagnostics_source_sha256"]=expected
  report["native_totcur_callsites"]=[
   {"line":i+1,"context":context(lines,i)} for i,s in enumerate(lines)
   if re.search(r"\btotcur\s*=\s*totcur\s*-\s*int2\s*\(",s,re.I)]
  report["targeted_quadrature_definition_candidates"]=[]
  for p in sorted(native.iterdir()):
   if not p.is_file() or p.suffix.lower() not in (".f",".f90",".f95") or not any(t in p.name.lower() for t in ("integrat","nint","quad","matdef")):
    continue
   lines=p.read_text(errors="replace").splitlines()
   hits=[{"line":i+1,"context":context(lines,i)} for i,s in enumerate(lines)
         if re.search(r"\b(?:function|subroutine)\s+int[12]\b|\binterface\s+int[12]\b",s,re.I)]
   report["targeted_quadrature_definition_candidates"].append({"file":p.name,"sha256":sha(p),"hits":hits[:12]})
  saved=pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs/baseline/time_003.h5")
  report["saved_native_hdf5_path"]=str(saved)
  if not report["native_totcur_callsites"]:
   report["classification"]="M3DC1_NATIVE_CURRENT_DIAGNOSTIC_SOURCE_MAPPING_INCOMPLETE"
   report["prerequisite_blocker"]="NATIVE_TOTCUR_CALLSITE_NOT_MATCHED"
  elif not saved.is_file():
   report["classification"]="M3DC1_NATIVE_CURRENT_DIAGNOSTIC_DATA_ACCESS_BLOCKED"
   report["prerequisite_blocker"]="SAVED_NATIVE_JPHI_HDF5_MISSING"
  else:
   import h5py
   with h5py.File(saved,"r") as h:
    report["saved_hdf5_jphi_shape"]=list(h["/fields/jphi"].shape)
    report["saved_hdf5_mesh_shape"]=list(h["/mesh/elements"].shape)
    report["saved_hdf5_3d_flag"]=int(h["/mesh"].attrs.get("3D",0))
    found=[]
    def visit(name,obj):
     if isinstance(obj,h5py.Dataset) and re.search(r"cur|jphi|tot",name,re.I):
      found.append({"path":name,"shape":list(obj.shape)})
    h.visititems(visit)
    report["saved_hdf5_current_named_datasets"]=found[:30]
   if report["saved_hdf5_mesh_shape"]!=[1004,8] or report["saved_hdf5_3d_flag"]!=0:
    raise ValueError("UNEXPECTED_SAVED_NATIVE_2D_MESH")
   report["classification"]="M3DC1_NATIVE_CURRENT_DIAGNOSTIC_LINEAGE_COMPLETE"
  report["interpretation"]="The native totcur expression uses int2 with flux-derived fields, not the saved area*jphi proxy. This maps a prerequisite, not physical-current or controller authority."
except Exception as exc:
 report["pipeline_error"]=type(exc).__name__+": "+str(exc)
 report["classification"]="M3DC1_NATIVE_CURRENT_DIAGNOSTIC_LINEAGE_PIPELINE_BLOCKED"
target=out/"native_current_diagnostic_lineage_summary.json"
tmp=target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
tmp.replace(target)
print(json.dumps(report,indent=2,sort_keys=True))
if "pipeline_error" in report: sys.exit(1)
PY

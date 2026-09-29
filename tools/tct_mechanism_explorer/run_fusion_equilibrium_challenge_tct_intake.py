#!/usr/bin/env python3
import json, sys
from pathlib import Path

OUT=Path("validation_runs/fusion_equilibrium_challenge_tct_intake")
OUT.mkdir(parents=True, exist_ok=True)
summary={
 "schema_version":1,
 "classification":"TCT_EXPERIMENTAL_SHOT_FAMILY_ADAPTER_READY_DATA_FETCH_REQUIRED",
 "source":"Sophelio/fusion-equilibrium-challenge",
 "machine":"DIII-D",
 "dataset_config":"diii_d_train",
 "shot_identifier_policy":"dataset row index; upstream release does not expose original machine shot numbers",
 "planned_scope":{"rows":[0,63],"count":64},
 "claim_boundary":"Experimental observational actuator/equilibrium timing analog only; not causal TCT validation and not native M3D-C1.",
 "tests_planned":[
   "PF-coil-current to EFIT psi/axis/shape response lag and reachability",
   "pre-event equilibrium-change timing where an objective event marker can be derived from released signals",
   "shot-level cross-validation only; never split timesteps across train/test"
 ],
 "required_fields":["efit_times","efit_psirz","efit_q95","efit_beta_n","efit_li","efit_r_axis","efit_z_axis"],
 "status":"dependency_or_fetch_not_attempted"
}
try:
 from datasets import load_dataset
 import numpy as np
except Exception as e:
 summary["status"]="human_intervention_required"
 summary["error"]="Python dependencies unavailable: "+repr(e)
 (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 print(summary["classification"])
 sys.exit(0)

try:
 ds=load_dataset("Sophelio/fusion-equilibrium-challenge","diii_d_train",split="train",streaming=True)
 rows=[]
 for i,shot in enumerate(ds):
  if i>=64: break
  t=np.asarray(shot["efit_times"],dtype=float)
  psi=np.asarray(shot["efit_psirz"],dtype=float)
  rows.append({"dataset_row":i,"efit_frames":int(len(t)),"t_start_ms":float(t[0]) if len(t) else None,"t_end_ms":float(t[-1]) if len(t) else None,"psi_shape":list(psi.shape)})
 summary["status"]="adapter_smoke_pass"
 summary["classification"]="TCT_EXPERIMENTAL_SHOT_FAMILY_INGESTED"
 summary["rows_observed"]=rows
 summary["rows_observed_count"]=len(rows)
except Exception as e:
 summary["status"]="human_intervention_required"
 summary["error"]="Dataset streaming failed: "+repr(e)

(OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(summary["classification"])

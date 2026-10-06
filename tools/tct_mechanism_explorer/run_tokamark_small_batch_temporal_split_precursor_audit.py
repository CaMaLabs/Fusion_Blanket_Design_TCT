#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT=Path("validation_runs/tokamark_small_batch_temporal_split_precursor_audit")
OUT.mkdir(parents=True, exist_ok=True)

summary={
  "schema_version":1,
  "created_utc":datetime.now(timezone.utc).isoformat(),
  "classification":"TOKAMARK_MAST_SMALL_BATCH_TEMPORAL_SPLIT_PRECURSOR_AUDIT_STAGED",
  "machine":"MAST",
  "fuel_track":"fuel_agnostic_control",
  "source":"UKAEA-IBM-STFC/tokamark-v1",
  "evidence_class":"observational_prospective_split_design",
  "bulk_download_performed":False,
  "archive_size_gb_approx":565,
  "actuator_budgets_ms":{"prebiased_fast":2.75,"prebiased_nominal":5.25},
  "design":{
    "split":"frozen temporal train/test split using TokaMark task metadata",
    "selection":"smallest available public task batch sufficient to resolve shot IDs, timestamps/campaign ordering, Mirnov-like and event/target metadata before any large transfer",
    "trigger_retuning_permitted":False,
    "required_controls":["frozen temporal holdout","circular trigger-train shift null","shuffled-event null","per-shot reporting","aggregate reporting"],
    "diagnostic_targets":["Mirnov coils (500 kHz)","D-alpha (50 kHz)","soft X-ray (50 kHz)","magnetics/equilibrium context"]
  },
  "next_execution_gate":"Resolve machine-readable task metadata and smallest batch URLs/shot IDs; do not download bulk archive until split provenance is frozen.",
  "claim_boundary":"Prospective split/staging audit only on repackaged FAIR-MAST MAST data. No independent-machine evidence, causal TCT suppression, actuator efficacy, p-B11 physics, or reactor-scale claim."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2))

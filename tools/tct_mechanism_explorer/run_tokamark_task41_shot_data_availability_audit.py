#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path.cwd()
OUT=ROOT/"validation_runs/tokamark_task41_shot_data_availability_audit"
OUT.mkdir(parents=True,exist_ok=True)
split=ROOT/"src/tokamark/metadata/TokaMark_data_splits.csv"
candidates=[
 ROOT/"data/tokamark", ROOT/"data/MAST", ROOT/"data/mast",
 ROOT/"tokamark_data", ROOT/"validation_runs/tokamark_mast_intake"
]
existing=[str(p.relative_to(ROOT)) for p in candidates if p.exists()]
files=[]
for p in candidates:
    if p.exists() and p.is_dir():
        for f in p.rglob("*"):
            if f.is_file():
                files.append(str(f.relative_to(ROOT)))
                if len(files)>=200: break
    if len(files)>=200: break
summary={
 "schema_version":1,
 "created_utc":datetime.now(timezone.utc).isoformat(),
 "classification":"TOKAMARK_MAST_TASK41_SHOT_DATA_AVAILABILITY_AUDITED",
 "machine":"MAST",
 "fuel_track":"fuel_agnostic_control",
 "evidence_class":"pipeline_data_availability",
 "pipeline_failure":False,
 "parent_result_job_id":"20261006-093-tokamark-task41-frozen-reachability-design",
 "canonical_split_present":split.exists(),
 "candidate_data_roots_present":existing,
 "sample_local_files":files,
 "sample_local_file_count":len(files),
 "ready_for_frozen_shot_level_reachability":bool(existing and files and split.exists()),
 "no_network_fetch_performed":True,
 "interpretation":"Availability/provenance audit only. No shot-level precursor statistic, causal TCT inference, M3D-C1 gate mapping, or p-B11 inference.",
 "next_gate":"If local Task-4.1-compatible shot data are present, run the frozen observational reachability design unchanged; otherwise repair/materialize data access only."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2))

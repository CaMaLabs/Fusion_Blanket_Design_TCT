#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT=Path("validation_runs/tokamark_canonical_path_metadata_audit")
OUT.mkdir(parents=True, exist_ok=True)
RAW="https://raw.githubusercontent.com/UKAEA-IBM-STFC-Fusion-FMs/tokamark/main"

CANDIDATES=[
 "src/tokamark/metadata/TokaMark_data_splits.csv",
 "src/tokamark/tasks_configs",
 "src/tokamark/tasks_configs/group4",
 "src/tokamark/tasks_configs/group_4",
]

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"tct-audit"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read().decode("utf-8")

files={}
errors={}
for rel in CANDIDATES:
    url=f"{RAW}/{rel}"
    try:
        files[rel]=get(url)
    except Exception as e:
        errors[rel]=f"{type(e).__name__}: {e}"

split_rel="src/tokamark/metadata/TokaMark_data_splits.csv"
shot_ids=[]
columns=[]
campaign_preview=[]
if split_rel in files:
    rows=list(csv.DictReader(io.StringIO(files[split_rel])))
    columns=list(rows[0].keys()) if rows else []
    for row in rows[:1000]:
        for k,v in row.items():
            if not v: continue
            lk=k.lower()
            if "shot" in lk:
                shot_ids.append(v)
            if any(x in lk for x in ("campaign","split","time","date")):
                campaign_preview.append({k:v})
shot_ids=list(dict.fromkeys(shot_ids))

summary={
 "schema_version":1,
 "created_utc":datetime.now(timezone.utc).isoformat(),
 "classification":"TOKAMARK_MAST_CANONICAL_PATH_METADATA_AUDIT",
 "machine":"MAST",
 "fuel_track":"fuel_agnostic_control",
 "evidence_class":"observational_source_metadata",
 "pipeline_failure":False,
 "bulk_download_performed":False,
 "actuator_budgets_ms":{"prebiased_fast":2.75,"prebiased_nominal":5.25},
 "fetched_paths":sorted(files),
 "fetch_errors":errors,
 "temporal_split_path":split_rel,
 "temporal_split_resolved":split_rel in files,
 "temporal_split_columns":columns,
 "resolved_shot_id_count_preview":len(shot_ids),
 "shot_id_preview":shot_ids[:100],
 "campaign_or_split_preview":campaign_preview[:100],
 "claim_boundary":"Canonical TokaMark source metadata only. Observational MAST provenance/timing staging; no causal TCT validation, no independent cross-machine claim, no segmented-electrode efficacy, no p-B11 inference.",
 "controls_preserved":["2.75 ms fast reachability budget","5.25 ms nominal reachability budget","frozen temporal holdout","circular-shift null","shuffled-event null","no retuning"],
 "next_gate":"Only if canonical split and shot identifiers resolve, inspect the smallest relevant Group-4 task YAML and its diagnostic sampling/timing semantics before precursor statistics."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
print(json.dumps(summary,indent=2))

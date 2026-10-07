#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT=Path("validation_runs/tokamark_group4_task41_metadata_audit")
OUT.mkdir(parents=True, exist_ok=True)

URL="https://raw.githubusercontent.com/UKAEA-IBM-STFC-Fusion-FMs/tokamark/main/src/tokamark/tasks_configs/group_4_mhd_activity/task_4-1.yaml"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"tct-audit"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read().decode("utf-8")

text=fetch(URL)
(OUT/"task_4-1.yaml").write_text(text,encoding="utf-8")

wanted=[
 "input_window","forecast_window","stride","mag","mirnov","saddle","plasma_current",
 "density","dalpha","d-alpha","sxr","soft x","nbi","gas","pf","solenoid","reference"
]
hits={k:[] for k in wanted}
for i,line in enumerate(text.splitlines(),1):
    lo=line.lower()
    for k in wanted:
        if k in lo:
            hits[k].append({"line":i,"text":line.strip()})

summary={
 "schema_version":1,
 "created_utc":datetime.now(timezone.utc).isoformat(),
 "classification":"TOKAMARK_MAST_GROUP4_TASK41_METADATA_AUDITED",
 "machine":"MAST",
 "fuel_track":"fuel_agnostic_control",
 "evidence_class":"observational_task_metadata",
 "pipeline_failure":False,
 "source_url":URL,
 "task_id":"4-1",
 "actuator_budgets_ms":{"prebiased_fast":2.75,"prebiased_nominal":5.25},
 "frozen_tct_gates":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.1},
 "task_yaml_bytes":len(text.encode("utf-8")),
 "keyword_hits":hits,
 "claim_boundary":"Task metadata/timing provenance only. No causal TCT validation, no independent cross-machine evidence, no segmented-electrode efficacy, no p-B11 inference.",
 "next_gate":"Parse exact timing-window values and channel names from task 4-1 metadata into a frozen observational precursor-reachability design before shot-level statistics."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
print(json.dumps(summary,indent=2))

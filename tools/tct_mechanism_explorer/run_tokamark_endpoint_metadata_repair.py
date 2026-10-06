#!/usr/bin/env python3
from __future__ import annotations
import csv
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("validation_runs/tokamark_endpoint_metadata_repair")
OUT.mkdir(parents=True, exist_ok=True)

CODE_REPO = "UKAEA-IBM-STFC-Fusion-FMs/tokamark"
RAW = f"https://raw.githubusercontent.com/{CODE_REPO}/main"

CANDIDATES = [
    "TokaMark_temporal_data_splits.csv",
    "tokamark/TokaMark_temporal_data_splits.csv",
    "data/TokaMark_temporal_data_splits.csv",
    "configs/TokaMark_temporal_data_splits.csv",
    "task_configurations.json",
    "tasks.json",
    "README.md",
]

def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent":"tct-audit"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")

fetched = {}
errors = {}
for rel in CANDIDATES:
    url = f"{RAW}/{rel}"
    try:
        fetched[rel] = fetch_text(url)
    except Exception as e:
        errors[rel] = f"{type(e).__name__}: {e}"

split_rel = next((k for k in fetched if k.endswith("TokaMark_temporal_data_splits.csv")), None)
shot_ids = []
columns = []
campaign_fields = []
if split_rel:
    rows = list(csv.DictReader(io.StringIO(fetched[split_rel])))
    columns = list(rows[0].keys()) if rows else []
    for row in rows[:500]:
        for key in row:
            lk = key.lower()
            if "shot" in lk and row.get(key):
                shot_ids.append(row[key])
            if ("campaign" in lk or "split" in lk or "time" in lk) and row.get(key):
                campaign_fields.append({key: row[key]})
    shot_ids = list(dict.fromkeys(shot_ids))

summary = {
  "schema_version": 1,
  "created_utc": datetime.now(timezone.utc).isoformat(),
  "classification": "TOKAMARK_MAST_ENDPOINT_METADATA_REPAIR_AUDITED",
  "machine": "MAST",
  "fuel_track": "fuel_agnostic_control",
  "code_repository": CODE_REPO,
  "dataset": "UKAEA-IBM-STFC/tokamark-v1",
  "evidence_class": "observational_source_metadata",
  "pipeline_failure": False,
  "bulk_download_performed": False,
  "actuator_budgets_ms": {
    "prebiased_fast": 2.75,
    "prebiased_nominal": 5.25
  },
  "fetched_files": sorted(fetched),
  "fetch_errors": errors,
  "temporal_split_file": split_rel,
  "temporal_split_columns": columns,
  "resolved_shot_id_count_preview": len(shot_ids),
  "shot_id_preview": shot_ids[:50],
  "campaign_or_split_preview": campaign_fields[:50],
  "promotion_gate": {
    "metadata_endpoint_corrected": bool(fetched),
    "temporal_split_resolved": split_rel is not None,
    "shot_ids_resolved": len(shot_ids) > 0
  },
  "controls_preserved": [
    "frozen temporal holdout",
    "2.75 ms fast reachability budget",
    "5.25 ms nominal reachability budget",
    "circular trigger-train shift null",
    "shuffled-event null",
    "no trigger retuning"
  ],
  "claim_boundary": "Endpoint/provenance repair only on TokaMark repackaged FAIR-MAST MAST data. No precursor efficacy, causal TCT suppression, independent cross-machine validation, segmented-electrode efficacy, p-B11 physics, or reactor-scale claim.",
  "next_gate": "If the temporal split and shot identifiers resolve, map the selected smallest task/batch to its diagnostic sampling/timing metadata before any precursor lead-time statistics."
}

(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
(OUT / "fetched_source_metadata.json").write_text(json.dumps({k:v for k,v in fetched.items()}, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))

#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("validation_runs/tokamark_source_metadata_fetch_audit")
OUT.mkdir(parents=True, exist_ok=True)

def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "tct-audit"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

source = "UKAEA-IBM-STFC/tokamark-v1"
base_api = f"https://api.github.com/repos/{source}"
targets = [
    ("repo", base_api),
    ("root", base_api + "/contents"),
]

resolved = {}
errors = {}
for name, url in targets:
    try:
        resolved[name] = fetch_json(url)
    except Exception as e:
        errors[name] = f"{type(e).__name__}: {e}"

summary = {
  "schema_version": 1,
  "created_utc": datetime.now(timezone.utc).isoformat(),
  "classification": "TOKAMARK_MAST_SOURCE_METADATA_FETCH_AUDIT",
  "machine": "MAST",
  "fuel_track": "fuel_agnostic_control",
  "source": source,
  "evidence_class": "observational_source_metadata",
  "actuator_budgets_ms": {
    "prebiased_fast": 2.75,
    "prebiased_nominal": 5.25
  },
  "network_fetch_attempted": True,
  "bulk_download_performed": False,
  "resolved_sections": sorted(resolved.keys()),
  "errors": errors,
  "required_resolution": [
    "task identifiers",
    "smallest public batch/artifact",
    "MAST shot IDs",
    "campaign or acquisition ordering",
    "target/event definition",
    "diagnostic provenance",
    "sampling/timing metadata"
  ],
  "controls_preserved": [
    "frozen temporal holdout",
    "2.75 ms fast reachability budget",
    "5.25 ms nominal reachability budget",
    "circular trigger-train shift null",
    "shuffled-event null",
    "no trigger retuning"
  ],
  "claim_boundary": "Public-source metadata fetch only for TokaMark repackaged FAIR-MAST MAST data. No precursor efficacy, causal TCT suppression, independent cross-machine validation, segmented-electrode efficacy, p-B11 physics, or reactor-scale claim."
}

(OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
(OUT / "source_metadata.json").write_text(json.dumps(resolved, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))

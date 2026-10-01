#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

OUT = pathlib.Path("validation_runs/tcabr_precursor_cache_audit")
OUT.mkdir(parents=True, exist_ok=True)
SUMMARY = OUT / "summary.json"

record_url = "https://zenodo.org/api/records/21843354"
try:
    with urllib.request.urlopen(record_url, timeout=30) as r:
        record = json.load(r)
except Exception as exc:
    SUMMARY.write_text(json.dumps({
        "classification": "TCABR_PRECURSOR_CACHE_PROVENANCE_UNAVAILABLE",
        "success": False,
        "pipeline_failure": True,
        "error": repr(exc),
        "fuel_track": "fuel_agnostic_control",
        "claim_boundary": "TCABR public-corpus provenance/cache audit only; no causal TCT efficacy claim."
    }, indent=2) + "\n")
    raise

files = []
for f in record.get("files", []):
    links = f.get("links", {}) or {}
    files.append({
        "key": f.get("key"),
        "size": f.get("size"),
        "checksum": f.get("checksum"),
        "download": links.get("content") or links.get("self")
    })

summary = {
    "classification": "TCABR_PRECURSOR_CACHE_PROVENANCE_AUDITED",
    "success": True,
    "pipeline_failure": False,
    "fuel_track": "fuel_agnostic_control",
    "machine": "TCABR",
    "source": "Zenodo 10.5281/zenodo.21843354",
    "record_id": record.get("id"),
    "title": (record.get("metadata") or {}).get("title"),
    "file_count": len(files),
    "files": files,
    "next_analysis": {
        "frozen_split": "stratified disruptive/non-disruptive split; exact split to be persisted before feature evaluation",
        "diagnostics": ["Mirnov", "H-alpha", "electrode voltage", "electrode current"],
        "actuator_budgets_ms": {"prebiased_fast": 2.75, "prebiased_nominal": 5.25},
        "null_controls": ["per-shot circular trigger-train shift", "shuffled event timing"],
        "retuning_permitted": False
    },
    "claim_boundary": "Experimental TCABR Ohmic L-mode corpus provenance/cache audit only. Electrode channels remain observational analogs. No causal TCT suppression, segmented-electrode efficacy, p-B11 physics, or reactor-scale claim."
}
SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))

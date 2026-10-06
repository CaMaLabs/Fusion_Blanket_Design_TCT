#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("validation_runs/tokamark_task_metadata_resolution_audit")
OUT.mkdir(parents=True, exist_ok=True)

summary = {
  "schema_version": 1,
  "created_utc": datetime.now(timezone.utc).isoformat(),
  "classification": "TOKAMARK_MAST_TASK_METADATA_RESOLUTION_AUDIT_STAGED",
  "machine": "MAST",
  "fuel_track": "fuel_agnostic_control",
  "source": "UKAEA-IBM-STFC/tokamark-v1",
  "evidence_class": "observational_metadata_resolution",
  "actuator_budgets_ms": {
    "prebiased_fast": 2.75,
    "prebiased_nominal": 5.25
  },
  "required_metadata": [
    "task identifiers",
    "smallest public batch/artifact",
    "MAST shot IDs",
    "campaign or acquisition ordering",
    "target/event definition",
    "diagnostic provenance",
    "sampling/timing metadata"
  ],
  "required_controls": [
    "freeze metadata before feature extraction",
    "preserve temporal holdout",
    "no trigger retuning",
    "circular trigger-train shift null",
    "shuffled-event null"
  ],
  "bulk_download_performed": False,
  "claim_boundary": "Metadata-resolution audit only on TokaMark repackaged FAIR-MAST MAST data. No precursor efficacy, causal TCT suppression, independent cross-machine validation, segmented-electrode efficacy, p-B11 physics, or reactor-scale claim.",
  "next_gate": "Only after shot IDs, task/target semantics, ordering, diagnostics, and timing metadata are resolved may shot-level precursor lead-time and 2.75/5.25 ms reachability statistics be computed."
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))

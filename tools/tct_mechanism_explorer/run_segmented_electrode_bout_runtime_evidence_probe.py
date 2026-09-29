#!/usr/bin/env python3
"""Prepare fail-closed compiled BOUT++ runtime evidence for the segmented-electrode handoff.

This runner does not claim efficacy. It attempts to locate an existing compiled BOUT++
current-sheet executable and, only if present, runs a minimal zero-equivalence / handoff
probe using the repository's electrode-enabled BOUT++ model inputs. Missing executable,
missing inputs, or missing runtime observables are reported as pipeline/data availability
failures rather than scientific negatives.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation_runs" / "tct_segmented_electrode_bout_runtime_evidence_probe"
OUT.mkdir(parents=True, exist_ok=True)

candidates = [
    ROOT / "tools" / "tct_mechanism_explorer" / "bout_current_sheet" / "build" / "tct_current_sheet",
    ROOT / "tools" / "tct_mechanism_explorer" / "bout_current_sheet" / "tct_current_sheet",
    ROOT / "validation_runs" / "bout_current_sheet" / "tct_current_sheet",
]
exe = next((p for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)
if exe is None:
    which = shutil.which("tct_current_sheet")
    if which:
        exe = Path(which)

summary = {
    "schema_version": 1,
    "classification": "TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EVIDENCE_UNAVAILABLE",
    "pipeline_failure": True,
    "runtime_executable_found": exe is not None,
    "runtime_executable": str(exe) if exe else None,
    "zero_equivalence_required": True,
    "zero_equivalence_pass": False,
    "handoff_equivalence_required": True,
    "handoff_equivalence_pass": False,
    "frozen_gates": {"width_gain_pct_min": 0.020, "jpk_improvement_pct_min": 0.10},
    "claim_boundary": "BOUT++ compiled-runtime evidence probe only; no segmented-electrode efficacy or native M3D-C1 electrode-efficacy claim.",
}

if exe is not None:
    # We intentionally do not invent model-specific CLI flags. Record executable provenance
    # and a harmless version/help probe; a subsequent job may perform the actual equivalence
    # runs once an executable-specific invocation contract is present in the repository.
    try:
        proc = subprocess.run([str(exe), "--help"], cwd=ROOT, text=True, capture_output=True, timeout=60)
        (OUT / "executable_probe.stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (OUT / "executable_probe.stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        summary["executable_probe_return_code"] = proc.returncode
        summary["pipeline_failure"] = False
        summary["classification"] = "TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EXECUTABLE_IDENTIFIED"
    except Exception as exc:  # fail closed; this is infrastructure evidence only
        summary["error"] = f"{type(exc).__name__}: {exc}"

(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))

#!/usr/bin/env python3
"""Fail-closed runtime-equivalence audit for segmented-electrode BOUT++ handoff.

This runner does not modify solver physics.  It records the evidence required before
any segmented-electrode efficacy claim is allowed: compiled-runtime zero-equivalence
and a declared handoff-equivalence result.  Missing runtime evidence fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation_runs" / "tct_segmented_electrode_bout_runtime_equivalence_audit"
OUT.mkdir(parents=True, exist_ok=True)

# Runtime evidence is intentionally explicit.  A worker may populate this file from
# compiled BOUT++ baseline/electrode runs; absence is not silently treated as pass.
evidence_path = OUT / "runtime_evidence.json"
evidence = {}
if evidence_path.exists():
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

zero = evidence.get("zero_equivalence")
handoff = evidence.get("handoff_equivalence")
zero_pass = bool(zero and zero.get("pass") is True)
handoff_pass = bool(handoff and handoff.get("pass") is True)

classification = (
    "TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EQUIVALENCE_ESTABLISHED"
    if zero_pass and handoff_pass
    else "TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EQUIVALENCE_NOT_ESTABLISHED"
)
summary = {
    "schema_version": 1,
    "classification": classification,
    "pipeline_failure": False,
    "zero_equivalence_required": True,
    "zero_equivalence_pass": zero_pass,
    "handoff_equivalence_required": True,
    "handoff_equivalence_pass": handoff_pass,
    "runtime_evidence_present": evidence_path.exists(),
    "frozen_gates": {"width_gain_pct_min": 0.020, "jpk_improvement_pct_min": 0.10},
    "claim_boundary": "BOUT++ compiled-runtime coupling/equivalence audit only; no segmented-electrode efficacy or native M3D-C1 electrode-efficacy claim.",
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))

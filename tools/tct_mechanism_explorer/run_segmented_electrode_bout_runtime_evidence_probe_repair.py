#!/usr/bin/env python3
"""Repair the BOUT++ runtime-evidence probe by discovering the worker's actual build/runtime layout.

Infrastructure-only: this does not alter solver physics or claim electrode efficacy.
"""
from __future__ import annotations
import json, os, shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"validation_runs"/"tct_segmented_electrode_bout_runtime_evidence_probe_repair"
OUT.mkdir(parents=True, exist_ok=True)

names={"tct_current_sheet","bout++","bout"}
roots=[ROOT, ROOT.parent, Path.home()/"BOUT-dev", Path.home()/"bout-dev", Path.home()/"bout++", Path("/usr/local/bin"), Path("/usr/bin")]
seen=set(); candidates=[]
for root in roots:
    try:
        root=root.resolve()
    except Exception:
        continue
    if root in seen or not root.exists(): continue
    seen.add(root)
    if root.is_file():
        paths=[root]
    elif str(root) in ("/usr/bin","/usr/local/bin"):
        paths=[p for p in root.iterdir() if p.name in names]
    else:
        paths=[]
        try:
            for p in root.rglob("*"):
                if p.is_file() and (p.name in names or "tct_current_sheet" in p.name):
                    paths.append(p)
                if len(paths)>=100: break
        except (PermissionError,OSError):
            pass
    for p in paths:
        try:
            if os.access(p,os.X_OK):
                candidates.append(str(p.resolve()))
        except OSError: pass
for n in names:
    w=shutil.which(n)
    if w: candidates.append(str(Path(w).resolve()))
candidates=sorted(set(candidates))
summary={
 "schema_version":1,
 "classification":"TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EXECUTABLE_IDENTIFIED" if candidates else "TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EVIDENCE_UNAVAILABLE",
 "pipeline_failure":not bool(candidates),
 "fuel_track":"fuel_agnostic_control",
 "runtime_executable_found":bool(candidates),
 "runtime_executable":candidates[0] if candidates else None,
 "runtime_executable_candidates":candidates,
 "zero_equivalence_required":True,"zero_equivalence_pass":False,
 "handoff_equivalence_required":True,"handoff_equivalence_pass":False,
 "frozen_gates":{"width_gain_pct_min":0.020,"jpk_improvement_pct_min":0.10},
 "claim_boundary":"BOUT++ compiled-runtime discovery only; no segmented-electrode efficacy, fuel-specific efficacy, or native M3D-C1 electrode-efficacy claim."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
print(json.dumps(summary,indent=2))

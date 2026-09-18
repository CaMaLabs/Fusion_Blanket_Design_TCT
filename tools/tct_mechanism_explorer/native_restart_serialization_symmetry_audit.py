#!/usr/bin/env python3
"""Audit native M3D-C1 restart read/write symmetry after first-postrestart divergence.

Source/provenance audit only: no solver-physics edits and no controller-efficacy run.
"""
from __future__ import annotations
import json, re
from pathlib import Path

SRC=Path('/home/ubuntu/M3DC1-official/unstructured')
OUT=Path('/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_restart_serialization_symmetry')
FILES=('restart_hdf5.f90','newpar.f90','hdf5_output.f90')
READ_RE=re.compile(r'\b(read_[A-Za-z0-9_]+|h5[adg][A-Za-z0-9_]*read[A-Za-z0-9_]*)\s*\(',re.I)
WRITE_RE=re.compile(r'\b(write_[A-Za-z0-9_]+|h5[adg][A-Za-z0-9_]*write[A-Za-z0-9_]*)\s*\(',re.I)
STRING_RE=re.compile(r'["\']([^"\']+)["\']')

def calls(path:Path):
    rows=[]
    if not path.exists(): return rows
    for n,line in enumerate(path.read_text(errors='replace').splitlines(),1):
        low=line.lower()
        if 'read_' not in low and 'write_' not in low and 'h5' not in low: continue
        kind='read' if READ_RE.search(line) else ('write' if WRITE_RE.search(line) else None)
        if not kind: continue
        names=STRING_RE.findall(line)
        rows.append({'path':path.name,'line':n,'kind':kind,'text':line.strip(),'dataset_literals':names})
    return rows

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name in FILES: rows += calls(SRC/name)
    read_names=set(); write_names=set()
    for r in rows:
        target=read_names if r['kind']=='read' else write_names
        target.update(x for x in r['dataset_literals'] if len(x)<120)
    read_only=sorted(read_names-write_names); write_only=sorted(write_names-read_names)
    # This audit identifies candidates, not proof of a missing state variable: dynamic handoff remains failed in parent.
    classification='M3DC1_TCT_NATIVE_RESTART_SERIALIZATION_ASYMMETRY_CANDIDATES_FOUND' if (read_only or write_only) else 'M3DC1_TCT_NATIVE_RESTART_SERIALIZATION_LITERAL_SYMMETRY_NO_OBVIOUS_GAP'
    report={
      'classification':classification,'pipeline_failure':False,
      'parent_job_id':'20260918-022-native-restart-state-path-audit',
      'parent_classification':'M3DC1_TCT_NATIVE_RESTART_STATE_PATH_SOURCE_AUDITED',
      'audit_scope':'Static native M3D-C1 restart read/write serialization symmetry audit; no solver execution and no controller efficacy run.',
      'files_scanned':[str(SRC/x) for x in FILES], 'call_count':len(rows),
      'read_dataset_literals':sorted(read_names),'write_dataset_literals':sorted(write_names),
      'read_only_literals':read_only,'write_only_literals':write_only,'calls':rows,
      'handoff_equivalence_status':'FAILED_AT_FIRST_POSTRESTART_STEP_IN_JOB_021',
      'zero_equivalence_status':'NOT_APPLICABLE_SOURCE_RESTART_CAPABILITY_AUDIT',
      'frozen_gates':{'width_gain_pct_gt':0.02,'Jpk_change_pct_le':0.1},
      'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.'}
    p=OUT/'native_restart_serialization_symmetry_summary.json'; p.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

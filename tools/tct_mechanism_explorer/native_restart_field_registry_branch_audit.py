#!/usr/bin/env python3
"""Narrow static audit of restart-vs-continuous field registry branch context.

No solver execution and no physics modification.  This follows job 030 by
asking whether the observed field-number shift can be tied to restart-gated
create/destroy lifecycle branches, rather than treating numeric IDs as field
identity.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
SRC=Path('/home/ubuntu/m3dc1')
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_field_registry_branch'
TERMS=('irestart','restart','create_field','destroy_field')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    hits=[]
    if SRC.exists():
        for p in SRC.rglob('*.f90'):
            try: lines=p.read_text(errors='replace').splitlines()
            except OSError: continue
            for i,line in enumerate(lines):
                lo=line.lower()
                if ('irestart' in lo or re.search(r'\brestart\b',lo)):
                    a=max(0,i-8); b=min(len(lines),i+9)
                    block='\n'.join(lines[a:b])
                    if 'create_field' in block.lower() or 'destroy_field' in block.lower():
                        hits.append({'path':str(p.relative_to(SRC)),'line':i+1,'restart_line':line.strip(),'context':block})
    classification=('M3DC1_TCT_NATIVE_RESTART_FIELD_REGISTRY_RESTART_GATED_LIFECYCLE_CONTEXT_FOUND' if hits
                    else 'M3DC1_TCT_NATIVE_RESTART_FIELD_REGISTRY_NO_RESTART_GATED_LIFECYCLE_CONTEXT_FOUND')
    report={
      'classification':classification,'pipeline_failure':False,
      'parent_job_id':'20260918-030-native-restart-field-registry-source-audit',
      'audit_scope':'Search native M3D-C1 source for restart-gated create/destroy field lifecycle context relevant to the observed registry shift; no solver execution or modification.',
      'restart_gated_lifecycle_hits':hits,
      'causation_status':'STATIC_BRANCH_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION',
      'handoff_equivalence':'INHERITED_FAILED_AT_1E-12_FROM_JOB_028',
      'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
      'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
      'finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_field_registry_branch_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

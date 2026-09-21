#!/usr/bin/env python3
"""Trace first post-restart unsplit matrix/RHS reconstruction without modifying M3D-C1."""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_unsplit_first_step_rebuild'
ROOTS=[Path('/home/ubuntu/M3DC1-official'),Path('/home/ubuntu/m3dc1')]
TOKENS=('calc_matrices','q4_vec','assemble','matrix','restart','step_unsplit','import_time_advance_vectors')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    root=next((p for p in ROOTS if p.exists()),None)
    if root is None:
        report={'classification':'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_FIRST_STEP_REBUILD_SOURCE_NOT_FOUND','pipeline_failure':True}
    else:
        hits=[]
        rx=re.compile('|'.join(re.escape(x) for x in TOKENS),re.I)
        for p in sorted(root.rglob('*.f90')):
            try: lines=p.read_text(errors='replace').splitlines()
            except OSError: continue
            for i,line in enumerate(lines):
                if rx.search(line):
                    lo=max(0,i-8); hi=min(len(lines),i+9)
                    hits.append({'path':str(p.relative_to(root)),'line':i+1,'text':line.strip(),'context':'\n'.join(lines[lo:hi])})
        report={
          'classification':'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_FIRST_STEP_REBUILD_CONTEXT_CAPTURED',
          'pipeline_failure':False,
          'parent_job_id':'20260921-044-native-restart-unsplit-import-export-audit',
          'audit_scope':'Static source trace of first post-restart unsplit calc_matrices/RHS/matrix reconstruction; no solver execution or modification.',
          'source_root':str(root),'matches':hits,
          'causation_status':'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION',
          'handoff_equivalence':'REQUIRED_REFERENCE_FAILURE_AT_1E-12_IN_JOB_041_WITH_DOUBLE_CHECKPOINT_FIELDS',
          'zero_equivalence':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
          'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
          'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
          'finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_unsplit_first_step_rebuild_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 1 if report.get('pipeline_failure') else 0
if __name__=='__main__': raise SystemExit(main())

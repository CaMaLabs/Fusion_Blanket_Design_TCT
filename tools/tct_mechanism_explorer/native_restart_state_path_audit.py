#!/usr/bin/env python3
"""Audit the native M3D-C1 restart read/write state path after a confirmed 5->6 discontinuity."""
from __future__ import annotations
import json,re
from pathlib import Path
SRC=Path('/home/ubuntu/M3DC1-official')
OUT=Path('/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_restart_state_path')
TOKENS=('irestart','irestart_slice','iwrite_restart','restart_hdf5','read_restart','write_restart','C1.h5')

def writej(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def main():
    hits=[]
    exts={'.f','.f90','.F','.F90','.c','.cc','.cpp','.h','.hpp'}
    for p in SRC.rglob('*'):
        if not p.is_file() or p.suffix not in exts: continue
        try: lines=p.read_text(errors='replace').splitlines()
        except Exception: continue
        for i,line in enumerate(lines):
            if any(t.lower() in line.lower() for t in TOKENS):
                lo=max(0,i-4); hi=min(len(lines),i+5)
                hits.append({'path':str(p.relative_to(SRC)),'line':i+1,'match':line.strip(),'context':'\n'.join(f'{j+1}: {lines[j]}' for j in range(lo,hi))})
    high=[h for h in hits if re.search(r'irestart|restart_hdf5|read_restart|write_restart',h['match'],re.I)]
    report={'classification':'M3DC1_TCT_NATIVE_RESTART_STATE_PATH_SOURCE_AUDITED',
      'pipeline_failure':False,'parent_job_id':'20260918-021-native-restart-boundary-discontinuity',
      'parent_classification':'M3DC1_TCT_NATIVE_RESTART_FIRST_POSTSTEP_DISCONTINUITY_CONFIRMED',
      'audit_scope':'Source-level audit of native M3D-C1 restart serialization/restoration path after precheckpoint equivalence and first-poststep divergence; no solver physics changes and no controller efficacy run.',
      'source_root':str(SRC),'match_count':len(hits),'high_signal_count':len(high),'high_signal_hits':high[:160],
      'handoff_equivalence_status':'FAILED_AT_FIRST_POSTRESTART_STEP_IN_PARENT_JOB',
      'zero_equivalence_status':'NOT_APPLICABLE_RESTART_CAPABILITY_AUDIT',
      'frozen_gates':{'width_gain_pct_gt':0.02,'Jpk_change_pct_le':0.1},
      'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.'}
    if not high:
        report['classification']='M3DC1_TCT_NATIVE_RESTART_STATE_PATH_SOURCE_NOT_RESOLVED'
    writej(OUT/'native_restart_state_path_summary.json',report); print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

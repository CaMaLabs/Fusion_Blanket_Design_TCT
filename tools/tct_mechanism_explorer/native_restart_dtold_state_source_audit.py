#!/usr/bin/env python3
"""Static audit of native M3D-C1 restart handling for dt/dtold state.

Source context only: does not execute or modify M3D-C1 and cannot establish causation.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_dtold_state_source'
SOURCES=[Path('/home/ubuntu/M3DC1-official'),Path('/home/ubuntu/m3dc1')]
RX=re.compile(r'\bdtold\b|\bdtsave\b|\brdrestart_hdf5\b|\binitialize_timestep\b',re.I)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    root=next((p for p in SOURCES if p.exists()),None)
    if root is None:
        report={'classification':'M3DC1_TCT_NATIVE_RESTART_DTOLD_STATE_SOURCE_AUDIT_SOURCE_NOT_FOUND','pipeline_failure':True,'source_candidates':[str(p) for p in SOURCES]}
    else:
        hits=[]
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in {'.f90','.f','.f95','.f03'}: continue
            try: lines=p.read_text(errors='replace').splitlines()
            except OSError: continue
            for i,line in enumerate(lines):
                if RX.search(line):
                    lo=max(0,i-10); hi=min(len(lines),i+11)
                    hits.append({'path':str(p.relative_to(root)),'line':i+1,'match':line.strip(),'context':'\n'.join(lines[lo:hi])})
        report={
          'classification':'M3DC1_TCT_NATIVE_RESTART_DTOLD_STATE_CONTEXT_CAPTURED' if hits else 'M3DC1_TCT_NATIVE_RESTART_DTOLD_STATE_CONTEXT_NOT_FOUND',
          'pipeline_failure':False,'parent_job_id':'20260918-034-native-restart-timestep-state-source-audit',
          'audit_scope':'Static source audit of dtold/dt state persistence and initialization across native restart; no M3D-C1 execution or physics modification.',
          'source_root':str(root),'hits':hits[:100],
          'causation_status':'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION',
          'handoff_equivalence':'INHERITED_FAILED_AT_1E-12_FROM_JOB_028','zero_equivalence':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
          'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
          'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
          'finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_dtold_state_source_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 1 if report.get('pipeline_failure') else 0
if __name__=='__main__': raise SystemExit(main())

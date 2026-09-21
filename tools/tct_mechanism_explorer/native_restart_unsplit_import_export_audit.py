#!/usr/bin/env python3
"""Audit native unsplit time-advance import/export call order across restart."""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_unsplit_import_export'
ROOTS=[Path('/home/ubuntu/M3DC1-official'),Path('/home/ubuntu/m3dc1')]
NAMES={'import_time_advance_vectors','export_time_advance_vectors','step_unsplit','advance_timestep'}

def routines(p:Path):
    try: lines=p.read_text(errors='replace').splitlines()
    except OSError: return []
    out=[]; i=0
    rx=re.compile(r'^\s*subroutine\s+([a-z0-9_]+)\b',re.I)
    while i<len(lines):
        m=rx.search(lines[i])
        if not m: i+=1; continue
        name=m.group(1).lower(); j=i+1
        while j<len(lines) and not re.search(r'^\s*end\s+subroutine\b',lines[j],re.I): j+=1
        if name in NAMES or 'time_advance' in name:
            out.append({'path':str(p),'name':name,'start_line':i+1,'end_line':min(j+1,len(lines)),'body':'\n'.join(lines[i:min(j+1,len(lines))])})
        i=max(j+1,i+1)
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    root=next((p for p in ROOTS if p.exists()),None)
    if root is None:
        report={'classification':'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_IMPORT_EXPORT_SOURCE_NOT_FOUND','pipeline_failure':True}
    else:
        rs=[]
        for p in sorted(root.rglob('*.f90')):
            if any(k in p.name.lower() for k in ('time_step','newpar','main','advance')): rs.extend(routines(p))
        calls=[]
        callrx=re.compile(r'\bcall\s+(import_time_advance_vectors|export_time_advance_vectors|step_unsplit|advance_timestep)\b',re.I)
        for p in sorted(root.rglob('*.f90')):
            try: lines=p.read_text(errors='replace').splitlines()
            except OSError: continue
            for i,line in enumerate(lines):
                m=callrx.search(line)
                if m:
                    lo=max(0,i-12); hi=min(len(lines),i+13)
                    calls.append({'path':str(p.relative_to(root)),'line':i+1,'callee':m.group(1).lower(),'context':'\n'.join(lines[lo:hi])})
        report={
          'classification':'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_IMPORT_EXPORT_CONTEXT_CAPTURED',
          'pipeline_failure':False,
          'parent_job_id':'20260921-043-native-restart-unsplit-work-vector-audit',
          'audit_scope':'Static source trace of native unsplit time-advance vector import/export and call order; no solver execution or modification.',
          'source_root':str(root),'routines':rs,'call_sites':calls,
          'causation_status':'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION',
          'handoff_equivalence':'FAILED_AT_1E-12_IN_JOB_041_WITH_DOUBLE_CHECKPOINT_FIELDS',
          'zero_equivalence':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
          'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
          'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
          'finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_unsplit_import_export_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 1 if report.get('pipeline_failure') else 0
if __name__=='__main__': raise SystemExit(main())

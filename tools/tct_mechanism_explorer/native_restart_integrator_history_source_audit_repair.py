#!/usr/bin/env python3
"""Static audit of native M3D-C1 restart handling for integrator/history state.

Repairs job 032's stale source-root assumption only. No solver execution or
physics modification.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
SOURCE_CANDIDATES=[Path('/home/ubuntu/M3DC1-official'),Path('/home/ubuntu/m3dc1')]
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_integrator_history_source_repair'
HISTORY=re.compile(r'\b(history|previous|prev|old|older|predict|correct|multistep|bdf|adams|timestep|time_step|dtime|dtold|dt_prev|deriv|rhs_old|nstep|istep)\b',re.I)
RESTART=re.compile(r'\b(irestart|restart|rdrestart|wrrestart)\b',re.I)
EXTS={'.f','.f90','.F','.F90','.c','.cc','.cpp','.h','.hpp'}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    src=next((p for p in SOURCE_CANDIDATES if p.exists()),None)
    if src is None:
        report={'classification':'M3DC1_TCT_NATIVE_RESTART_INTEGRATOR_HISTORY_SOURCE_AUDIT_SOURCE_NOT_FOUND','pipeline_failure':True,'error':'no known native M3D-C1 source root found','source_candidates':[str(p) for p in SOURCE_CANDIDATES]}
    else:
        hits=[]; files_scanned=0
        for p in src.rglob('*'):
            if not p.is_file() or p.suffix not in EXTS: continue
            files_scanned += 1
            try: lines=p.read_text(errors='replace').splitlines()
            except OSError: continue
            for i,line in enumerate(lines):
                if not RESTART.search(line): continue
                a=max(0,i-12); b=min(len(lines),i+13); block='\n'.join(lines[a:b])
                terms=sorted({m.group(0).lower() for m in HISTORY.finditer(block)})
                if terms: hits.append({'path':str(p.relative_to(src)),'line':i+1,'restart_line':line.strip(),'history_terms':terms,'context':block})
        classification='M3DC1_TCT_NATIVE_RESTART_INTEGRATOR_HISTORY_CONTEXT_FOUND' if hits else 'M3DC1_TCT_NATIVE_RESTART_INTEGRATOR_HISTORY_CONTEXT_NOT_FOUND'
        report={'classification':classification,'pipeline_failure':False,'parent_job_id':'20260918-032-native-restart-integrator-history-source-audit','repair_scope':'Correct stale native-source root from job 032 and repeat the same static source audit only.','source_root':str(src),'files_scanned':files_scanned,'restart_history_hits':hits,'causation_status':'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION','handoff_equivalence':'INHERITED_FAILED_AT_1E-12_FROM_JOB_028','zero_equivalence':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST','frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.','finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_integrator_history_source_repair_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 1 if report.get('pipeline_failure') else 0
if __name__=='__main__': raise SystemExit(main())

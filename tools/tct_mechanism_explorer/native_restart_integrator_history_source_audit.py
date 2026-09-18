#!/usr/bin/env python3
"""Static audit of native M3D-C1 restart handling for time-integrator/history state.

No solver execution or modification. This follows the negative field-registry
branch audit by testing a separate, physically relevant hypothesis for a
first-postrestart-only discontinuity: incomplete or restart-specific handling
of multistep/predictor/history/timestep state.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
SRC=Path('/home/ubuntu/m3dc1')
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_integrator_history_source'
HISTORY=re.compile(r'\b(history|previous|prev|old|older|predict|correct|multistep|bdf|adams|timestep|time_step|dtime|dtold|dt_prev|deriv|rhs_old|nstep|istep)\b',re.I)
RESTART=re.compile(r'\b(irestart|restart|rdrestart|wrrestart)\b',re.I)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    hits=[]; files_scanned=0
    if not SRC.exists():
        report={'classification':'M3DC1_TCT_NATIVE_RESTART_INTEGRATOR_HISTORY_SOURCE_AUDIT_SOURCE_NOT_FOUND','pipeline_failure':True,'error':f'{SRC} not found'}
    else:
        for p in SRC.rglob('*.f90'):
            files_scanned += 1
            try: lines=p.read_text(errors='replace').splitlines()
            except OSError: continue
            for i,line in enumerate(lines):
                if not RESTART.search(line): continue
                a=max(0,i-12); b=min(len(lines),i+13); block='\n'.join(lines[a:b])
                terms=sorted({m.group(0).lower() for m in HISTORY.finditer(block)})
                if terms:
                    hits.append({'path':str(p.relative_to(SRC)),'line':i+1,'restart_line':line.strip(),'history_terms':terms,'context':block})
        classification=('M3DC1_TCT_NATIVE_RESTART_INTEGRATOR_HISTORY_CONTEXT_FOUND' if hits else 'M3DC1_TCT_NATIVE_RESTART_INTEGRATOR_HISTORY_CONTEXT_NOT_FOUND')
        report={'classification':classification,'pipeline_failure':False,'parent_job_id':'20260918-031-native-restart-field-registry-branch-audit','audit_scope':'Search native M3D-C1 source for restart-adjacent time-integrator/history/timestep state handling relevant to the first-postrestart discontinuity; no solver execution or modification.','files_scanned':files_scanned,'restart_history_hits':hits,'causation_status':'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION','handoff_equivalence':'INHERITED_FAILED_AT_1E-12_FROM_JOB_028','frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.','finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_integrator_history_source_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 1 if report.get('pipeline_failure') else 0
if __name__=='__main__': raise SystemExit(main())

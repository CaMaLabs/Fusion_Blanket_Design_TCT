#!/usr/bin/env python3
import json, re
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path('/home/ubuntu/M3DC1-official')
OUT = Path('validation_runs/m3dc1_tct_native_restart_unsplit_solver_state')
OUT.mkdir(parents=True, exist_ok=True)
patterns = re.compile(r'\b(isolve_with_guess|iskippc|pskip|nskip|precondition|initial guess|calc_matrices|irestart)\b', re.I)
matches=[]
for p in SOURCE.rglob('*'):
    if not p.is_file() or p.suffix.lower() not in {'.f90','.f','.F90'.lower(),'.h','.inc'}:
        continue
    try: lines=p.read_text(errors='replace').splitlines()
    except OSError: continue
    for i,line in enumerate(lines,1):
        if patterns.search(line):
            lo=max(0,i-4); hi=min(len(lines),i+3)
            matches.append({'path':str(p.relative_to(SOURCE)),'line':i,'text':line.strip(),'context':'\n'.join(lines[lo:hi])})
summary={
 'classification':'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_SOLVER_STATE_CONTEXT_CAPTURED',
 'pipeline_failure':False,
 'parent_job_id':'20260921-046-native-restart-unsplit-first-step-rebuild-audit',
 'audit_scope':'Static source audit of restart-sensitive linear-solver initial-guess, matrix/preconditioner reuse, and rebuild state for the first unsplit post-restart step; no solver execution or modification.',
 'causation_status':'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION',
 'handoff_equivalence':'REQUIRED_REFERENCE_FAILURE_AT_1E-12_IN_JOB_041_WITH_DOUBLE_CHECKPOINT_FIELDS',
 'frozen_width_gate_pct_gt':0.020,
 'frozen_Jpk_gate_pct_le':0.10,
 'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
 'match_count':len(matches), 'matches':matches,
 'finished_utc':datetime.now(timezone.utc).isoformat()
}
(OUT/'native_restart_unsplit_solver_state_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

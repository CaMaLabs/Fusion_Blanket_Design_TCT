#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
SRC=Path('/home/ubuntu/M3DC1-official')
OUT=Path('/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_restart_field_registry_source')
TOKENS=('createfield','create_field','destroyfield','destroy_field','irestart','restart_hdf5')
def main():
    hits=[]
    exts={'.f','.f90','.F','.F90','.c','.cc','.cpp','.h','.hpp'}
    for p in SRC.rglob('*'):
        if not p.is_file() or p.suffix not in exts: continue
        try: lines=p.read_text(errors='replace').splitlines()
        except Exception: continue
        for i,line in enumerate(lines):
            if any(t.lower() in line.lower() for t in TOKENS):
                hits.append({'path':str(p.relative_to(SRC)),'line':i+1,'match':line.strip(),'context':'\n'.join(lines[max(0,i-3):min(len(lines),i+4)])})
    report={'classification':'M3DC1_TCT_NATIVE_RESTART_FIELD_REGISTRY_SOURCE_CONTEXT_CAPTURED' if hits else 'M3DC1_TCT_NATIVE_RESTART_FIELD_REGISTRY_SOURCE_CONTEXT_NOT_FOUND','pipeline_failure':False,'parent_job_id':'20260918-029-native-restart-field-registry-audit','audit_scope':'Map observed restart-vs-continuous field-registry differences to native M3D-C1 field lifecycle/restart source context; no solver execution.','observed_continuous_only_fields':[67,68,69,70],'observed_restart_only_fields':[50,51,52,53],'source_context_hits':hits[:240],'causation_status':'OBSERVATIONAL_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION','handoff_equivalence':'INHERITED_FAILED_AT_1E-12_FROM_JOB_028','zero_equivalence':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST','frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.'}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'native_restart_field_registry_source_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

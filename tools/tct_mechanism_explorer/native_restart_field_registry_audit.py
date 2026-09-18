#!/usr/bin/env python3
"""Audit job 028 logs for restart-vs-continuous native field-registry differences.

No M3D-C1 execution, controller efficacy run, or solver-physics modification.
"""
from __future__ import annotations
import json,re
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
SRC=REPO/'validation_runs/m3dc1_tct_native_restart_slice_selection/native_restart_slice_selection_summary.json'
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_field_registry'

def fields(text): return sorted({int(x) for x in re.findall(r'destroy field\s+(\d+)',text or '')})
def matrices(text): return sorted({int(x) for x in re.findall(r'mat%imatrix=\s*(\d+)',text or '')})
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    s=json.loads(SRC.read_text())
    cont=s['continuous_execution']['C1stdout_tail']
    runs=s['restart_runs']
    cf=fields(cont); cm=matrices(cont)
    arms={}
    for name,r in runs.items():
        text=r['execution']['C1stdout_tail']; rf=fields(text); rm=matrices(text)
        arms[name]={'destroy_fields':rf,'solver_matrix_ids':rm,'missing_vs_continuous':sorted(set(cf)-set(rf)),'extra_vs_continuous':sorted(set(rf)-set(cf))}
    same_restart_registry=arms['implicit_latest']['destroy_fields']==arms['explicit_latest']['destroy_fields']
    any_delta=any(v['missing_vs_continuous'] or v['extra_vs_continuous'] for v in arms.values())
    classification=('M3DC1_TCT_NATIVE_RESTART_FIELD_REGISTRY_DIFFERENCE_OBSERVED' if any_delta else 'M3DC1_TCT_NATIVE_RESTART_FIELD_REGISTRY_NO_DIFFERENCE_OBSERVED')
    report={'classification':classification,'pipeline_failure':False,'parent_job_id':'20260918-028-native-restart-slice-selection','audit_scope':'Parse job 028 native stdout tails for restart-vs-continuous field-registry and solver-matrix-ID differences; no M3D-C1 execution.','continuous':{'destroy_fields':cf,'solver_matrix_ids':cm},'restart_arms':arms,'restart_arms_same_registry':same_restart_registry,'causation_status':'OBSERVATIONAL_ONLY_NOT_DYNAMIC_CAUSATION','handoff_equivalence':'INHERITED_FAILED_AT_1E-12_FROM_JOB_028','handoff_equivalence_tolerance':1e-12,'zero_equivalence':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST','frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.'}
    (OUT/'native_restart_field_registry_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

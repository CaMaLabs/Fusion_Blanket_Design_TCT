#!/usr/bin/env python3
"""Test whether explicit latest-slice selection changes native M3D-C1 restart handoff.

Source=0 restart capability audit only. No controller efficacy run or solver-physics changes.
"""
from __future__ import annotations
import json, shutil
from pathlib import Path
import native_restart_boundary_discontinuity_audit as rb

OUT=rb.REPO/'validation_runs/m3dc1_tct_native_restart_slice_selection'
ROOT=Path('/tmp/m3dc1_tct_native_restart_slice_selection_runs')

def writej(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

def main():
    rb.rm(ROOT); ROOT.mkdir(parents=True); OUT.mkdir(parents=True,exist_ok=True)
    # Continuous source=0 reference through step 6.
    cont=rb.prep('continuous',rb.TARGET,write_restart=1,ntimers=rb.SPLIT); cst=rb.run(cont)
    # Generate the same bounded five-step checkpoint once.
    first=rb.prep('split_first',rb.SPLIT,write_restart=1,ntimers=rb.SPLIT); fst=rb.run(first)
    runs={}; comparisons={}; extraction_error=None
    try:
        cr=rb.pta.extract(cont); c6=cr[-1]
        for label,slice_value in [('implicit_latest',-1),('explicit_latest',rb.SPLIT)]:
            d=ROOT/label; shutil.copytree(first,d,symlinks=True)
            text=(d/'C1input').read_text()
            for k,v in {'ntimemax':str(rb.TARGET),'irestart':'1','irestart_slice':str(slice_value),'iwrite_restart':'0'}.items():
                text=rb.pta.replace_or_add(text,k,v)
            (d/'C1input').write_text(text)
            ex=rb.run(d); runs[label]={'irestart_slice':slice_value,'execution':ex}
            if ex['return_code']==0:
                rr=rb.pta.extract(d); comparisons[label]=rb.compare(c6,rr[-1])
    except Exception as e:
        extraction_error=repr(e)
    execution_ok=cst['return_code']==0 and fst['return_code']==0 and len(runs)==2 and all(v['execution']['return_code']==0 for v in runs.values())
    implicit_ok=comparisons.get('implicit_latest',{}).get('pass',False)
    explicit_ok=comparisons.get('explicit_latest',{}).get('pass',False)
    if not execution_ok or extraction_error:
        classification='M3DC1_TCT_NATIVE_RESTART_SLICE_SELECTION_AUDIT_EXECUTION_FAILED'
    elif explicit_ok:
        classification='M3DC1_TCT_NATIVE_RESTART_EXPLICIT_LATEST_SLICE_HANDOFF_EQUIVALENCE_PASSED'
    elif explicit_ok != implicit_ok:
        classification='M3DC1_TCT_NATIVE_RESTART_SLICE_SELECTION_CHANGES_HANDOFF_BUT_EQUIVALENCE_FAILED'
    else:
        classification='M3DC1_TCT_NATIVE_RESTART_SLICE_SELECTION_DOES_NOT_RESOLVE_HANDOFF_DISCONTINUITY'
    report={
      'classification':classification,'pipeline_failure':not execution_ok or extraction_error is not None,
      'parent_job_id':'20260918-027-native-restart-checkpoint-link-consistency',
      'audit_scope':'Source=0 bounded first-postrestart-step A/B test of irestart_slice=-1 versus explicit latest slice 5; no controller efficacy run.',
      'continuous_execution':cst,'checkpoint_execution':fst,'restart_runs':runs,'comparisons_to_continuous_step6':comparisons,
      'extraction_error':extraction_error,'handoff_equivalence_tolerance':rb.TOL,
      'handoff_equivalence':'PASSED_EXPLICIT_LATEST_SLICE' if explicit_ok else 'FAILED_AT_1E-12',
      'zero_equivalence':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
      'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
      'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.'}
    writej(OUT/'native_restart_slice_selection_summary.json',report); print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

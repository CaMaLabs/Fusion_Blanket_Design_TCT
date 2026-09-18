#!/usr/bin/env python3
"""Capture and inventory the actual bounded native M3D-C1 restart checkpoint."""
from __future__ import annotations
import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
import native_restart_boundary_discontinuity_audit as rb

OUT=rb.REPO/'validation_runs/m3dc1_tct_native_restart_checkpoint_capture'
CAP=OUT/'captured'

def inspect_h5(p: Path):
    rec={'name':p.name,'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'hdf5':False,'datasets':[],'attrs':{}}
    try:
        import h5py
        with h5py.File(p,'r') as f:
            rec['hdf5']=True
            rec['attrs']={str(k):str(v) for k,v in f.attrs.items()}
            def visit(name,obj):
                if isinstance(obj,h5py.Dataset): rec['datasets'].append({'path':name,'shape':list(obj.shape),'dtype':str(obj.dtype)})
            f.visititems(visit)
    except Exception as e: rec['hdf5_error']=repr(e)
    return rec

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if CAP.exists(): shutil.rmtree(CAP)
    CAP.mkdir(parents=True)
    d=rb.prep('checkpoint_capture',rb.SPLIT,write_restart=1,ntimers=rb.SPLIT)
    ex=rb.run(d)
    candidates=[]
    for p in sorted(d.iterdir()):
        if p.is_file() and (p.suffix.lower() in {'.h5','.hdf5'} or 'restart' in p.name.lower()):
            q=CAP/p.name; shutil.copy2(p,q); candidates.append(inspect_h5(q))
    execution_ok=ex['return_code']==0
    hdf5_ok=any(x['hdf5'] for x in candidates)
    classification=('M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_CAPTURED_FOR_SCHEMA_AUDIT' if execution_ok and hdf5_ok
                    else 'M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_CAPTURE_AUDIT_EXECUTION_FAILED' if not execution_ok
                    else 'M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_CAPTURED_BUT_HDF5_SCHEMA_UNREADABLE')
    report={'classification':classification,'pipeline_failure':not execution_ok,'parent_job_id':'20260918-024-native-restart-checkpoint-schema-audit',
      'audit_scope':'Regenerate one bounded source=0 five-step native checkpoint, persist its actual HDF5 artifacts, and inventory their schema; no controller efficacy run.',
      'execution':ex,'artifacts':candidates,'zero_equivalence':'NOT_EVALUATED_CAPTURE_AUDIT_ONLY','handoff_equivalence':'NOT_EVALUATED_CAPTURE_AUDIT_ONLY',
      'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
      'claim_boundary':'Normalized native M3D-C1 restart artifact/schema provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
      'finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_checkpoint_capture_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

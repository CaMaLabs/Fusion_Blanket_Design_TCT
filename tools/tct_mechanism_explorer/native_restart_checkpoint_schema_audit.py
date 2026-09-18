#!/usr/bin/env python3
import json, os, pathlib, re
from datetime import datetime, timezone

OUT=pathlib.Path('validation_runs/m3dc1_tct_native_restart_checkpoint_schema')
OUT.mkdir(parents=True, exist_ok=True)
roots=[pathlib.Path('validation_runs/m3dc1_tct_native_restart_boundary_discontinuity'), pathlib.Path('/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_restart_boundary_discontinuity')]
files=[]
for root in roots:
    if root.exists():
        for p in root.rglob('*'):
            if p.is_file() and (p.suffix.lower() in {'.h5','.hdf5'} or 'restart' in p.name.lower()):
                files.append(p)
files=sorted(set(files))
records=[]
try:
    import h5py
except Exception as e:
    h5py=None
    h5err=str(e)
for p in files:
    rec={'path':str(p),'size_bytes':p.stat().st_size,'hdf5':False,'datasets':[],'attrs':{}}
    if h5py:
        try:
            with h5py.File(p,'r') as f:
                rec['hdf5']=True
                rec['attrs']={str(k):str(v) for k,v in f.attrs.items()}
                def visit(name,obj):
                    if isinstance(obj,h5py.Dataset):
                        rec['datasets'].append({'path':name,'shape':list(obj.shape),'dtype':str(obj.dtype)})
                f.visititems(visit)
        except Exception as e: rec['hdf5_error']=str(e)
    records.append(rec)
classification='M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_SCHEMA_CAPTURED' if any(r['hdf5'] for r in records) else 'M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_ARTIFACT_NOT_FOUND'
summary={
 'classification':classification,
 'pipeline_failure':False,
 'parent_job_id':'20260918-023-native-restart-serialization-symmetry',
 'audit_scope':'Inventory actual native restart/checkpoint artifacts and HDF5 schema from the bounded restart validation; no solver/controller efficacy run.',
 'artifact_count':len(records),'artifacts':records,
 'h5py_available':h5py is not None,
 'h5py_error':None if h5py else h5err,
 'zero_equivalence':'NOT_EVALUATED_SCHEMA_AUDIT_ONLY',
 'handoff_equivalence':'NOT_EVALUATED_SCHEMA_AUDIT_ONLY',
 'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
 'claim_boundary':'Normalized native M3D-C1 restart artifact/schema provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
 'finished_utc':datetime.now(timezone.utc).isoformat()
}
(OUT/'native_restart_checkpoint_schema_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

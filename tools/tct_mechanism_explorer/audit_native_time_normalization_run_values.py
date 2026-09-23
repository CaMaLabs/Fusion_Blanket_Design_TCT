#!/usr/bin/env python3
from __future__ import annotations
import json, math, re
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
SRC=Path('/home/ubuntu/M3DC1-official')
RUN=REPO/'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run'
OUT=REPO/'validation_runs/m3dc1_tct_native_time_normalization_run_values_audit'
CLAIM='Normalized native M3D-C1 provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'


def fail(msg):
    r={'classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_RUN_VALUES_AUDIT_PIPELINE_FAILURE','pipeline_failure':True,'pipeline_error':msg,'physical_time_calibrated':False,'frozen_width_gate_pct_gt':0.020,'frozen_Jpk_gate_pct_le':0.10,'claim_boundary':CLAIM}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'summary.json').write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2)); return 96


def main():
    try: import h5py
    except Exception as e: return fail(f'h5py unavailable: {e}')
    h5p=RUN/'C1.h5'; srcp=SRC/'unstructured/input.f90'; inp=RUN/'C1input'
    if not h5p.is_file() or not srcp.is_file() or not inp.is_file(): return fail('required C1.h5, C1input, or official input.f90 missing')
    src=srcp.read_text(errors='replace')
    relation_ok=bool(re.search(r'v0_norm\s*=\s*b0_norm\s*/\s*sqrt\s*\(\s*4\.\*pi\*m0_norm\*n0_norm\s*\)',src,re.I) and re.search(r't0_norm\s*=\s*l0_norm\s*/\s*v0_norm',src,re.I))
    with h5py.File(h5p,'r') as h:
        paths=[]
        def visit(name,obj):
            low=name.lower()
            if any(k in low for k in ('b0_norm','n0_norm','l0_norm','normalization')): paths.append(name)
        h.visititems(visit)
        vals={}
        for name in paths:
            obj=h[name]
            if hasattr(obj,'shape') and getattr(obj,'shape',None) == ():
                try: vals[name]=float(obj[()])
                except Exception: pass
            elif hasattr(obj,'shape') and getattr(obj,'size',0)==1:
                try: vals[name]=float(obj[()].reshape(-1)[0])
                except Exception: pass
    txt=inp.read_text(errors='replace')
    m=re.search(r'\bion_mass\s*=\s*([0-9.eE+-]+)',txt,re.I); ion_mass=float(m.group(1)) if m else None
    # HDF5 writer registers these names with explicit native CGS-unit descriptions in official input.f90.
    def pick(key):
        for n,v in vals.items():
            if n.lower().endswith(key): return v
        return None
    b0,n0,l0=pick('b0_norm'),pick('n0_norm'),pick('l0_norm')
    usable=relation_ok and ion_mass is not None and all(v is not None and math.isfinite(v) and v>0 for v in (b0,n0,l0))
    derived={}
    if usable:
        mp=1.67262192369e-24 # g, CODATA proton mass; only used with source-declared CGS normalization quantities.
        m0=mp*ion_mass
        v0=b0/math.sqrt(4*math.pi*m0*n0)
        t0=l0/v0
        dtm=re.search(r'\bdt\s*=\s*([0-9.eE+-]+)',txt,re.I); dt=float(dtm.group(1)) if dtm else None
        derived={'m0_norm_g':m0,'v0_norm_cm_per_s':v0,'t0_norm_s':t0,'native_dt':dt,'dt_si_s':(dt*t0 if dt is not None else None)}
    r={'classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_RUN_VALUES_AUDITED','pipeline_failure':False,'diagnostic_only':True,'parent_classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_ASSIGNMENT_AUDITED','implemented_relations_verified':relation_ok,'hdf5_normalization_candidates':vals,'ion_mass_from_C1input':ion_mass,'derived_from_explicit_source_relation':derived,'physical_time_calibrated':bool(usable),'interpretation':('Official native source explicitly implements v0_norm=b0_norm/sqrt(4*pi*m0_norm*n0_norm) and t0_norm=l0_norm/v0_norm. Physical-time calibration is accepted only if the selected native run also exposes positive run-specific b0_norm/n0_norm/l0_norm values in C1.h5 and ion_mass in C1input; otherwise it remains fail-closed.'),'frozen_width_gate_pct_gt':0.020,'frozen_Jpk_gate_pct_le':0.10,'claim_boundary':CLAIM}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'summary.json').write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

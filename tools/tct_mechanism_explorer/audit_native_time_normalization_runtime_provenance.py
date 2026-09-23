#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
REPO=Path('/home/ubuntu/work/openmc/sweep')
SRC=Path('/home/ubuntu/M3DC1-official')
RUN=REPO/'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run'
OUT=REPO/'validation_runs/m3dc1_tct_native_time_normalization_runtime_provenance_audit'
CLAIM='Normalized native M3D-C1 provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
KEYS=('b0_norm','n0_norm','l0_norm','v0_norm','t0_norm')
def fail(msg):
 r={'classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_RUNTIME_PROVENANCE_AUDIT_PIPELINE_FAILURE','pipeline_failure':True,'pipeline_error':msg,'physical_time_calibrated':False,'frozen_width_gate_pct_gt':0.020,'frozen_Jpk_gate_pct_le':0.10,'claim_boundary':CLAIM}; OUT.mkdir(parents=True,exist_ok=True); (OUT/'summary.json').write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2)); return 96
def contexts(path):
 if not path.is_file(): return []
 lines=path.read_text(errors='replace').splitlines(); out=[]
 for i,line in enumerate(lines):
  if any(k in line.lower() for k in KEYS): out.append({'line':i+1,'text':line[:500]})
 return out
def main():
 inp=RUN/'C1input'; stdout=RUN/'C1stdout'; ke=RUN/'C1ke'; src=SRC/'unstructured/input.f90'
 if not inp.is_file() or not src.is_file(): return fail('required selected-run C1input or official input.f90 missing')
 evidence={'C1input':contexts(inp),'C1stdout':contexts(stdout),'C1ke':contexts(ke),'official_input_f90':contexts(src)}
 # Runtime calibration remains fail-closed: source declarations/defaults are not treated as run-specific values unless selected-run artifacts explicitly emit them.
 runtime_hits=evidence['C1input']+evidence['C1stdout']+evidence['C1ke']
 emitted={}
 for hit in runtime_hits:
  for k in ('b0_norm','n0_norm','l0_norm'):
   m=re.search(r'\b'+k+r'\s*[=:]\s*([0-9.eE+-]+)',hit['text'],re.I)
   if m:
    try: emitted[k]=float(m.group(1))
    except ValueError: pass
 calibrated=all(k in emitted and emitted[k]>0 for k in ('b0_norm','n0_norm','l0_norm'))
 r={'classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_RUNTIME_PROVENANCE_AUDITED','pipeline_failure':False,'diagnostic_only':True,'parent_classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_RUN_VALUES_AUDITED','selected_run_runtime_normalization_values':emitted,'runtime_and_source_contexts':evidence,'physical_time_calibrated':calibrated,'interpretation':'Audit selected-run C1input/C1stdout/C1ke for explicit runtime b0_norm/n0_norm/l0_norm values and retain official source contexts for provenance. Source declarations or defaults alone do not establish run-specific physical-time calibration.','frozen_width_gate_pct_gt':0.020,'frozen_Jpk_gate_pct_le':0.10,'claim_boundary':CLAIM}
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'summary.json').write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

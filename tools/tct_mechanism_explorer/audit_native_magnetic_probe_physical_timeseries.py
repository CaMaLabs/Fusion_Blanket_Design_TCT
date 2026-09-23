#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
VALUE = REPO/'validation_runs/m3dc1_tct_native_magnetic_probe_value_semantics_audit/summary.json'
TIME = REPO/'validation_runs/m3dc1_tct_native_magnetic_probe_time_metadata_audit/summary.json'
CAL = REPO/'validation_runs/m3dc1_tct_native_time_physical_conversion/summary.json'
OUT = REPO/'validation_runs/m3dc1_tct_native_magnetic_probe_physical_timeseries'

v=json.loads(VALUE.read_text()); t=json.loads(TIME.read_text()); c=json.loads(CAL.read_text())
if v.get('classification')!='M3DC1_TCT_NATIVE_MAGNETIC_PROBE_VALUE_SEMANTICS_AUDITED': raise SystemExit('unexpected value-semantics classification')
if t.get('classification')!='M3DC1_TCT_NATIVE_MAGNETIC_PROBE_TIME_METADATA_AUDITED': raise SystemExit('unexpected time-metadata classification')
if c.get('classification')!='M3DC1_TCT_NATIVE_TIME_PHYSICAL_CONVERSION_AUDITED' or not c.get('physical_time_calibrated'): raise SystemExit('physical-time calibration not established')
for src in (v,t):
    if float(src.get('frozen_width_gate_pct_gt',-1)) != 0.02 or float(src.get('frozen_Jpk_gate_pct_le',-1)) != 0.1:
        raise SystemExit('frozen gate mismatch')

times=None
for x in t.get('time_metadata_candidates',[]):
    if x.get('file')=='C1.h5' and x.get('source')=='object' and x.get('path')=='scalars/time':
        times=x.get('value'); break
values=[row[0] if isinstance(row,list) else row for row in v.get('values',[])]
if not isinstance(times,list) or len(times)!=len(values) or not times: raise SystemExit('time/value alignment unavailable')
t0=float(c['t0_norm_s'])
samples=[{'index':i,'time_native':float(nt),'time_s':float(nt)*t0,'time_us':float(nt)*t0*1e6,'probe_value_native':float(val)} for i,(nt,val) in enumerate(zip(times,values))]
summary={
 'classification':'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_PHYSICAL_TIMESERIES_AUDITED',
 'pipeline_failure':False,
 'diagnostic_only':True,
 'physical_time_calibrated':True,
 'observable_path':v.get('observable_path'),
 't0_norm_s':t0,
 'samples':samples,
 'sample_interval_s':(samples[1]['time_s']-samples[0]['time_s']) if len(samples)>1 else None,
 'sample_interval_us':(samples[1]['time_us']-samples[0]['time_us']) if len(samples)>1 else None,
 'mirnov_equivalence_established':False,
 'precursor_lead_time_established':False,
 'controller_efficacy_established':False,
 'solver_physics_modified':False,
 'frozen_width_gate_pct_gt':0.020,
 'frozen_Jpk_gate_pct_le':0.10,
 'interpretation':'The configured native magnetic-probe samples now have run-specific physical timestamps from verified M3D-C1 normalization provenance. This does not establish Mirnov equivalence or a precursor lead time.',
 'claim_boundary':'Run-specific native M3D-C1 magnetic diagnostic timing only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
}
OUT.mkdir(parents=True,exist_ok=True); (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2))

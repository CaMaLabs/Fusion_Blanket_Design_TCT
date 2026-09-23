#!/usr/bin/env python3
"""Derive run-specific native M3D-C1 physical-time conversion from established provenance.

Claim boundary: normalization audit only. This does not alter solver physics or validate controller efficacy.
"""
from __future__ import annotations
import json, math, re
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
RUN=REPO/'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run'
OUT=REPO/'validation_runs/m3dc1_tct_native_time_physical_conversion'
OUT.mkdir(parents=True, exist_ok=True)
stdout=(RUN/'C1stdout').read_text(errors='ignore')
c1input=(RUN/'C1input').read_text(errors='ignore')

def grab(text,key):
    m=re.search(rf'\b{re.escape(key)}\b\s*[=:]\s*([+\-0-9.eEdD]+)',text,re.I)
    return float(m.group(1).replace('D','E').replace('d','e')) if m else None
vals={k:grab(stdout,k) for k in ('b0_norm','l0_norm','n0_norm')}
ion_mass=grab(c1input,'ion_mass')
dt=grab(c1input,'dt')
missing=[k for k,v in {**vals,'ion_mass':ion_mass,'dt':dt}.items() if v is None]
summary={
 'classification':'M3DC1_TCT_NATIVE_TIME_PHYSICAL_CONVERSION_AUDITED',
 'pipeline_failure':False,
 'physical_time_calibrated':False,
 'provenance_relation':{
   'm0_norm':'m_p * ion_mass',
   'v0_norm':'b0_norm / sqrt(4*pi*m0_norm*n0_norm)',
   't0_norm':'l0_norm / v0_norm',
   'dt_si':'dt * t0_norm'
 },
 'run_values':{**vals,'ion_mass':ion_mass,'dt_native':dt},
 'missing':missing,
 'claim_boundary':'Normalized native M3D-C1 timing provenance only; no experimental, reactor-scale, Mirnov-equivalence, or controller-efficacy claim.'
}
if not missing:
    # Native source uses cgs normalization: B[G], L[cm], n[cm^-3], proton mass[g].
    mp_g=1.67262192369e-24
    m0=mp_g*ion_mass
    v0_cms=vals['b0_norm']/math.sqrt(4*math.pi*m0*vals['n0_norm'])
    t0_s=vals['l0_norm']/v0_cms
    dt_s=dt*t0_s
    summary.update({'m0_norm_g':m0,'v0_norm_cm_s':v0_cms,'t0_norm_s':t0_s,'dt_si_s':dt_s,'dt_si_ms':dt_s*1e3,'physical_time_calibrated':all(map(math.isfinite,(v0_cms,t0_s,dt_s))) and t0_s>0})
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps(summary,indent=2,sort_keys=True))

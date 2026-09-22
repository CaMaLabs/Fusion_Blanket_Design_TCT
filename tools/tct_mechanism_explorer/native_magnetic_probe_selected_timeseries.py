#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, shutil, subprocess
from pathlib import Path
REPO=Path('/home/ubuntu/work/openmc/sweep'); BASE=Path('/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE')
PARENT=REPO/'validation_runs/m3dc1_tct_native_magnetic_probe_in_domain_sweep/summary.json'
OUT=REPO/'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries'; RUN=OUT/'run'
BIN=Path(os.environ.get('M3DC1_BIN','/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d')); MPI=shutil.which('mpiexec.mpich') or shutil.which('mpirun')
parent=json.loads(PARENT.read_text())
if parent.get('classification')!='M3DC1_TCT_NATIVE_MAGNETIC_PROBE_IN_DOMAIN_CANDIDATE_FOUND': raise SystemExit('unexpected parent classification')
sel=parent.get('selected_in_domain_candidate')
if not sel: raise SystemExit('parent has no selected candidate')
if not BIN.exists() or not os.access(BIN,os.X_OK): raise SystemExit(f'missing executable: {BIN}')
if not MPI: raise SystemExit('missing MPI launcher')
if RUN.exists(): shutil.rmtree(RUN)
OUT.mkdir(parents=True,exist_ok=True); shutil.copytree(BASE,RUN)
for p in RUN.glob('*.h5'): p.unlink()
inp=RUN/'C1input'; text=inp.read_text()
def put(k,v):
 global text
 pat=re.compile(rf'^(\s*{re.escape(k)}\s*=\s*)(.*?)(\s*(?:!.*)?$)',re.M)
 text=pat.sub(rf'\g<1>{v}\g<3>',text,count=1) if pat.search(text) else text.replace('\n /',f'\n  {k} = {v}\n /',1)
put('imag_probes','1'); put('mag_probe_x(1)',f"{float(sel['r']):.8f}"); put('mag_probe_phi(1)','0.0'); put('mag_probe_z(1)',f"{float(sel['z']):.8f}"); put('mag_probe_nx(1)','1.0'); put('mag_probe_nz(1)','0.0'); inp.write_text(text)
log=RUN/'probe.log'
with log.open('w') as fh: proc=subprocess.run([MPI,'-np','1',str(BIN)],cwd=RUN,stdin=inp.open(),stdout=fh,stderr=subprocess.STDOUT,text=True)
lt=log.read_text(errors='replace'); fp=r'([+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)'; rejects=[tuple(map(float,m.groups())) for m in re.finditer(r'Point not found in domain:\s+'+fp+r'\s+'+fp+r'\s+'+fp,lt)]
r=float(sel['r']); z=float(sel['z']); rejected=any(abs(x-r)<=5e-4 and abs(zz-z)<=5e-4 for x,_phi,zz in rejects)
h5=[p.name for p in sorted(RUN.glob('*.h5'))]
summary={'classification':'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_SELECTED_TIMESERIES_CAPTURED' if proc.returncode==0 and not rejected and h5 else 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_SELECTED_TIMESERIES_NOT_CAPTURED','pipeline_failure':proc.returncode!=0,'diagnostic_only':True,'parent_classification':parent['classification'],'selected_probe':{'r':r,'z':z,'orientation':'BR/nx=1.0'},'requested_point_rejected':rejected,'return_code':proc.returncode,'hdf5_files':h5,'solver_physics_modified':False,'frozen_width_gate_pct_gt':0.020,'frozen_Jpk_gate_pct_le':0.10,'claim_boundary':'Normalized native M3D-C1 magnetic diagnostic capture only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.','next_step_contract':'Do not construct a precursor until the native magnetic-probe observable is positively identified in the captured output and shown to contain a usable time series.'}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2)); raise SystemExit(proc.returncode)

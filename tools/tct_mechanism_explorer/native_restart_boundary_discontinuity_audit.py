#!/usr/bin/env python3
"""Locate any native M3D-C1 restart discontinuity at the 5->6 step boundary.

Source=0 capability/provenance audit only. No TCT controller efficacy run.
"""
from __future__ import annotations
import hashlib, json, shutil, subprocess, time
from pathlib import Path
import pulse_train_audit as pta

REPO=Path('/home/ubuntu/work/openmc/sweep')
BASE=Path('/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE')
SRC=Path('/home/ubuntu/M3DC1-official')
EXE=SRC/'build-ubuntu-2d/unstructured/m3dc1_2d'
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_boundary_discontinuity'
ROOT=Path('/tmp/m3dc1_tct_native_restart_boundary_discontinuity_runs')
DT=0.01; SPLIT=5; TARGET=6; TOL=1e-12
METRICS=('W_sheet','Jpk','Jint_high','center_abs_current','shoulder_abs_current','Reconnected_Flux','magnetic_energy')

def rm(p):
    if p.exists(): shutil.rmtree(p) if p.is_dir() else p.unlink()
def writej(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def prep(name,steps,restart=0,restart_slice=-1,write_restart=0,ntimers=1):
    d=ROOT/name; rm(d); d.mkdir(parents=True)
    for item in pta.COPY_NAMES:
        s=BASE/item
        if s.is_symlink(): (d/item).symlink_to(s.readlink())
        elif s.exists(): shutil.copy2(s,d/item)
    text=(BASE/'C1input').read_text()
    for k,v in {'dt':f'{DT:.10g}','ntimemax':str(steps),'ntimepr':'1','irestart':str(restart),
                'irestart_slice':str(restart_slice),'iwrite_restart':str(write_restart),'ntimers':str(ntimers),
                'imag_control':'0','mag_ctrl_amp':'0.0','icd_source':'0','J_0cd':'0.0'}.items():
        text=pta.replace_or_add(text,k,v)
    (d/'C1input').write_text(text); return d
def run(d):
    env='source "$HOME/spack/share/spack/setup-env.sh" && spack env activate m3dc1-deps && '
    cmd=env+f'cd "{d}" && timeout 1200s mpirun --oversubscribe -n 1 "{EXE}" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr'
    t=time.time(); p=subprocess.run(['bash','-lc',cmd],text=True,capture_output=True)
    return {'return_code':p.returncode,'elapsed_seconds':time.time()-t,
            'C1stdout_tail':(d/'C1stdout').read_text(errors='replace')[-2500:] if (d/'C1stdout').exists() else '',
            'stderr_tail':p.stderr[-1000:]}
def compare(a,b):
    by={}; ok=True
    for m in METRICS:
        delta=float(b[m])-float(a[m]); p=abs(delta)<=TOL; ok=ok and p
        by[m]={'a':float(a[m]),'b':float(b[m]),'delta':delta,'pass':p}
    td=float(b['time'])-float(a['time']); tp=abs(td)<=TOL; ok=ok and tp
    return {'pass':ok,'time_a':float(a['time']),'time_b':float(b['time']),'time_delta':td,'time_pass':tp,'by_metric':by}
def inventory(d):
    out=[]
    for p in sorted(d.iterdir()):
        n=p.name.lower()
        if p.is_file() and ('restart' in n or n.startswith('c1.h5')):
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            out.append({'name':p.name,'size':p.stat().st_size,'sha256':h})
    return out

def main():
    if not BASE.exists(): raise FileNotFoundError(BASE)
    if not EXE.exists(): raise FileNotFoundError(EXE)
    rm(ROOT); ROOT.mkdir(parents=True); OUT.mkdir(parents=True,exist_ok=True)
    cont=prep('continuous',TARGET,write_restart=1,ntimers=SPLIT); cst=run(cont)
    first=prep('split_first',SPLIT,write_restart=1,ntimers=SPLIT); fst=run(first)
    restart_inventory=inventory(first)
    second=ROOT/'split_second'; shutil.copytree(first,second,symlinks=True)
    text=(second/'C1input').read_text()
    for k,v in {'ntimemax':str(TARGET),'irestart':'1','irestart_slice':'-1','iwrite_restart':'0'}.items(): text=pta.replace_or_add(text,k,v)
    (second/'C1input').write_text(text); sst=run(second)
    execution_ok=all(x['return_code']==0 for x in (cst,fst,sst))
    boundary=None; post=None; extraction_error=None
    try:
        cr=pta.extract(cont); fr=pta.extract(first); sr=pta.extract(second)
        c5=min(cr,key=lambda r:abs(float(r['time'])-SPLIT*DT)); c6=cr[-1]; f5=fr[-1]; s6=sr[-1]
        boundary=compare(c5,f5); post=compare(c6,s6)
    except Exception as e: extraction_error=repr(e)
    if not execution_ok: classification='M3DC1_TCT_NATIVE_RESTART_BOUNDARY_AUDIT_EXECUTION_FAILED'
    elif boundary and not boundary['pass']: classification='M3DC1_TCT_NATIVE_RESTART_PRECHECKPOINT_TRAJECTORY_NONDETERMINISTIC'
    elif post and post['pass']: classification='M3DC1_TCT_NATIVE_RESTART_FIRST_POSTSTEP_EQUIVALENCE_PASSED'
    else: classification='M3DC1_TCT_NATIVE_RESTART_FIRST_POSTSTEP_DISCONTINUITY_CONFIRMED'
    report={'classification':classification,'pipeline_failure':not execution_ok,
      'parent_job_id':'20260918-020-native-restart-split-equivalence-repair',
      'parent_classification':'M3DC1_TCT_NATIVE_RESTART_SPLIT_RUN_HANDOFF_EQUIVALENCE_FAILED',
      'audit_scope':'Source=0 native restart boundary localization at steps 5->6 only; no controller efficacy run.',
      'execution':{'continuous':cst,'split_first':fst,'split_second':sst},
      'precheckpoint_equivalence':boundary,'first_postrestart_step_equivalence':post,
      'restart_artifact_inventory':restart_inventory,'extraction_error':extraction_error,
      'handoff_equivalence_tolerance':TOL,'zero_equivalence_status':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
      'frozen_gates':{'width_gain_pct_gt':0.02,'Jpk_change_pct_le':0.1},
      'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.'}
    writej(OUT/'native_restart_boundary_discontinuity_summary.json',report)
    print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

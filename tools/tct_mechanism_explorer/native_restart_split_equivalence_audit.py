#!/usr/bin/env python3
"""Bounded native M3D-C1 continuous-vs-restart state-equivalence audit.

This validates the high-signal restart interface found by job 018. It does not
run the TCT controller or alter frozen controller acceptance gates.
"""
from __future__ import annotations
import json, shutil, subprocess, time
from pathlib import Path
import pulse_train_audit as pta

REPO=Path('/home/ubuntu/work/openmc/sweep')
BASE=Path('/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE')
SRC=Path('/home/ubuntu/M3DC1-official')
EXE=SRC/'build-ubuntu-2d/unstructured/m3dc1_2d'
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_split_equivalence'
ROOT=Path('/tmp/m3dc1_tct_native_restart_split_equivalence_runs')
DT=0.01; TOTAL_STEPS=10; SPLIT_STEPS=5; TOL=1e-12
METRICS=('W_sheet','Jpk','Jint_high','center_abs_current','shoulder_abs_current','Reconnected_Flux','magnetic_energy')

def rm(p):
    if p.exists(): shutil.rmtree(p) if p.is_dir() else p.unlink()

def writej(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

def prep(name, steps, restart=0, restart_slice=-1, write_restart=0, ntimers=1):
    d=ROOT/name; rm(d); d.mkdir(parents=True)
    for item in pta.COPY_NAMES:
        s=BASE/item
        if s.is_symlink(): (d/item).symlink_to(s.readlink())
        elif s.exists(): shutil.copy2(s,d/item)
    text=(BASE/'C1input').read_text()
    updates={'dt':f'{DT:.10g}','ntimemax':str(steps),'ntimepr':'1','irestart':str(restart),
             'irestart_slice':str(restart_slice),'iwrite_restart':str(write_restart),'ntimers':str(ntimers),
             'imag_control':'0','mag_ctrl_amp':'0.0','icd_source':'0','J_0cd':'0.0'}
    for k,v in updates.items(): text=pta.replace_or_add(text,k,v)
    (d/'C1input').write_text(text); return d

def run(d):
    env='source "$HOME/spack/share/spack/setup-env.sh" && spack env activate m3dc1-deps && '
    cmd=env+f'cd "{d}" && timeout 1200s mpirun --oversubscribe -n 1 "{EXE}" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr'
    t=time.time(); p=subprocess.run(['bash','-lc',cmd],text=True,capture_output=True)
    st={'return_code':p.returncode,'elapsed_seconds':time.time()-t,'stderr_tail':p.stderr[-2000:],
        'C1stdout_tail':(d/'C1stdout').read_text(errors='replace')[-4000:] if (d/'C1stdout').exists() else ''}
    writej(d/'run_status.json',st); return st

def main():
    if not BASE.exists(): raise FileNotFoundError(BASE)
    if not EXE.exists(): raise FileNotFoundError(EXE)
    rm(ROOT); ROOT.mkdir(parents=True); OUT.mkdir(parents=True,exist_ok=True)
    cont=prep('continuous',TOTAL_STEPS,write_restart=1,ntimers=SPLIT_STEPS)
    cst=run(cont)
    first=prep('split_first',SPLIT_STEPS,write_restart=1,ntimers=SPLIT_STEPS)
    fst=run(first)
    second=ROOT/'split_second'; shutil.copytree(first,second,symlinks=True)
    text=(second/'C1input').read_text()
    # ntimemax is the absolute target step on restart, not a count of additional
    # steps. Job 019 incorrectly reused SPLIT_STEPS here, so the resumed run
    # stopped at t=0.05 and could not constitute a handoff-equivalence test.
    for k,v in {'ntimemax':str(TOTAL_STEPS),'irestart':'1','irestart_slice':'-1','iwrite_restart':'0'}.items():
        text=pta.replace_or_add(text,k,v)
    (second/'C1input').write_text(text)
    sst=run(second)
    execution_ok=all(x['return_code']==0 for x in (cst,fst,sst))
    checks=[]; eq=False; extraction_error=None
    try:
        cr=pta.extract(cont); sr=pta.extract(second)
        if execution_ok and cr and sr:
            cf=cr[-1]; sf=sr[-1]; by={}; eq=True
            for m in METRICS:
                delta=float(sf[m])-float(cf[m]); ok=abs(delta)<=TOL; eq=eq and ok
                by[m]={'continuous':float(cf[m]),'split':float(sf[m]),'delta':delta,'pass':ok}
            time_ok=abs(float(sf['time'])-float(cf['time']))<=TOL
            eq=eq and time_ok
            checks=[{'continuous_time':float(cf['time']),'split_time':float(sf['time']),'time_pass':time_ok,'by_metric':by}]
    except Exception as e: extraction_error=repr(e)
    if not execution_ok:
        classification='M3DC1_TCT_NATIVE_RESTART_SPLIT_RUN_EXECUTION_FAILED'
    elif eq:
        classification='M3DC1_TCT_NATIVE_RESTART_SPLIT_RUN_HANDOFF_EQUIVALENCE_PASSED'
    else:
        classification='M3DC1_TCT_NATIVE_RESTART_SPLIT_RUN_HANDOFF_EQUIVALENCE_FAILED'
    report={'classification':classification,'pipeline_failure':False,
      'parent_job_id':'20260917-019-native-restart-split-equivalence',
      'parent_classification':'M3DC1_TCT_NATIVE_RESTART_SPLIT_RUN_HANDOFF_EQUIVALENCE_FAILED',
      'audit_scope':'Short source=0 continuous-versus-split native restart validation only; no controller efficacy run.',
      'continuous_steps':TOTAL_STEPS,'split_steps':[SPLIT_STEPS,SPLIT_STEPS],'dt_native':DT,
      'execution':{'continuous':cst,'split_first':fst,'split_second':sst},
      'handoff_equivalence':{'tolerance':TOL,'pass':eq,'checks':checks,'extraction_error':extraction_error},
      'zero_equivalence_status':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
      'frozen_gates':{'width_gain_pct_gt':0.02,'Jpk_change_pct_le':0.1},
      'precursor_authority':'Mirnov/toroidal; reduced-model proxies are not substituted',
      'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.'}
    writej(OUT/'native_restart_split_equivalence_summary.json',report)
    print(json.dumps({k:report[k] for k in ('classification','pipeline_failure','handoff_equivalence','zero_equivalence_status','frozen_gates','claim_boundary')},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())

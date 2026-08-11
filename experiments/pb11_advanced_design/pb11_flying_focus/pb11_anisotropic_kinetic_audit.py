#!/usr/bin/env python3
"""Anisotropic / directed electron phase-space audit for the 638-keV p-B11 FF channel.

Tests symmetric mirror loss cone, shifted-Maxwellian return current, and a
current-neutral skewed two-stream electron distribution. Reduced screening
model only; not a full 2V Landau or PIC solve.
"""
from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np
from scipy.special import roots_genlaguerre
from numpy.polynomial.legendre import leggauss
QE=1.602176634e-19; EPS0=8.8541878128e-12; ME=9.1093837015e-31; MP=1.67262192369e-27
C=299792458.; ZB=5.; LNL=15.; TE=16.67; TI=55.358; TARGET=638.; QMEV=8.7
NE=1.3368052430557294e20; FFAST=.20; NFAST=FFAST*NE; NB=(NE-NFAST)/ZB
VP=math.sqrt(2*TARGET*1e3*QE/MP); VTE=math.sqrt(2*TE*1e3*QE/ME)
BURN=.23033; PASSES=419246.468; BCOL=6.592e21
HAZ=-math.log(1-BURN)/PASSES; SP=HAZ/BCOL; SV=SP*VP; PF=NFAST*NB*SV*QMEV*1e6*QE
PE0=9.165124340522159; PB0=.8501419491515615; REPL=TARGET/1000/QMEV; PSELF=.20346630338955626
PB_CAP=.98; DT_RATIO=1.153375427999846; DT_ASSIST=.85; ETA=.90; DIRECT=.92
KC=QE*QE/(4*math.pi*EPS0)
def psi(x):
    y=math.sqrt(max(x,0)); return math.erf(y)-2/math.sqrt(math.pi)*y*math.exp(-x)
def slowing(v):
    if v<=1e-12:return 0.
    x=ME*v*v/(2*TE*1e3*QE); return (1+MP/ME)*psi(x)/v**3
S0=slowing(VP)
def drag_shift(u):
    vr=(1-u)*VP
    if abs(vr)<1e-9*VP:return 0.
    return math.copysign(1,vr)*slowing(abs(vr))*abs(vr)/(S0*VP)
def demand(df):
    c=PE0*df+PB0; return c,c+REPL
def alpha(d):
    gross=d/ETA; dt=min(DT_RATIO*DT_ASSIST,gross); rem=max(0,gross-dt); pb=min(PB_CAP,rem)
    closed=rem<=PB_CAP; left=max(0,PB_CAP-pb); return closed,left*DIRECT
def eta_spitzer():
    zeff=(NFAST+25*NB)/NE; return 1.03e-4*zeff*LNL/((TE*1e3)**1.5)
ETA_SP=eta_spitzer()
GX,GW=roots_genlaguerre(220,.5); WE=2/math.sqrt(math.pi)*GW
ECRIT=(ME/MP)*TARGET; QV=np.sqrt(TE*GX/ECRIT); MU,MUW=leggauss(240)
def lc_kernel(mumax):
    mu=mumax*MU; w=MUW/2; q=QV[:,None]; m=mu[None,:]
    k=(1-q*m)/(1+q*q-2*q*m)**1.5
    return float(np.sum(WE[:,None]*w[None,:]*k))
LC0=lc_kernel(1.)
def losscone(R):return lc_kernel(math.sqrt(max(0,1-1/R)))/LC0
def ee_nu(v,n):
    if v<=1e-12:return 0.
    x=ME*v*v/(2*TE*1e3*QE); nu0=4*math.pi*KC*KC*LNL*n/(ME*ME*v**3)
    return 2*psi(x)*nu0
def twostream(p,u1):
    p2=1-p; u2=(FFAST-p*u1)/p2; df=p*drag_shift(u1)+p2*drag_shift(u2)
    coll,d=demand(df); closed,direct=alpha(d); dv=abs(u1-u2)*VP
    Pstream=p*NE*ME*ee_nu(dv,p2*NE)*dv*dv/PF; total=Pstream+PSELF
    req=max(0,1-direct/total) if total else 0
    return dict(co_stream_fraction=p,co_stream_drift_over_vp=u1,counter_stream_fraction=p2,
      counter_stream_drift_over_vp=u2,counter_stream_speed_over_c=abs(u2)*VP/C,
      relative_stream_speed_over_vte=dv/VTE,mean_electron_drift_over_vp=FFAST,drag_factor=df,
      collision_over_Pfusion=coll,useful_proton_demand_over_Pfusion=d,proton_loop_closed=closed,
      stream_relaxation_over_Pfusion=Pstream,proton_self_shape_over_Pfusion=PSELF,
      total_phase_space_recirc_over_Pfusion=total,direct_electric_left_over_Pfusion=direct,
      required_phase_space_energy_recovery_fraction=req,electrostatic_beam_instability_risk=(dv/VTE)>=1,
      current_neutral_by_construction=True)
def main(outdir='anisotropic_kinetic'):
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    mirror=[]
    for R in (1.2,1.5,2.,3.,5.,10.,20.,100.):
        df=losscone(R); c,d=demand(df); closed,_=alpha(d)
        mirror.append(dict(mirror_ratio=R,drag_factor=df,collision_over_Pfusion=c,useful_proton_demand_over_Pfusion=d,proton_loop_closed=closed))
    single=[]
    for u in (0.,.1,.2,.4,.6,.8,.9):
        df=drag_shift(u); c,d=demand(df); closed,direct=alpha(d); je=QE*NE*u*VP
        Pres=ETA_SP*je*je/PF; total=Pres+PSELF; req=max(0,1-direct/total) if total else 0
        single.append(dict(electron_drift_over_vp=u,current_neutral=abs(u-FFAST)<1e-12,drag_factor=df,
          collision_over_Pfusion=c,useful_proton_demand_over_Pfusion=d,proton_loop_closed=closed,
          spitzer_drift_maintenance_over_Pfusion=Pres,direct_electric_left_over_Pfusion=direct,
          required_phase_space_energy_recovery_fraction=req))
    two=[]
    for p in np.arange(.70,.951,.01):
        for u1 in np.arange(.30,1.201,.02):
            r=twostream(float(p),float(u1))
            if r['counter_stream_speed_over_c']<=.45:two.append(r)
    closed=[r for r in two if r['proton_loop_closed']]
    best=min(closed,key=lambda r:(r['required_phase_space_energy_recovery_fraction'],r['stream_relaxation_over_Pfusion']))
    least=min(closed,key=lambda r:r['stream_relaxation_over_Pfusion'])
    def write(name,rows):
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write('mirror_loss_cone_sweep.csv',mirror);write('single_drift_sweep.csv',single);write('two_stream_sweep.csv',two)
    write('best_closed_two_stream_cases.csv',sorted(closed,key=lambda r:r['required_phase_space_energy_recovery_fraction'])[:25])
    neutral=next(r for r in single if r['current_neutral'])
    summary={'classification':'DIRECTED_ELECTRON_TWO_STREAM_FAILS_RECIRCULATION_AND_STABILITY_GATE','target_proton_lab_keV':TARGET,
      'current_neutral_single_drift':neutral,'mirror_minimum_drag_factor':min(r['drag_factor'] for r in mirror),
      'best_closed_two_stream_case':best,'least_stream_power_closed_case':least,
      'core_result':'Directional two-stream shaping can close the alpha-supported proton loop, but electron-electron stream relaxation costs hundreds of local p-B11 fusion-power units and the closed points are beam-instability-risk cases.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

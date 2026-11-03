#!/usr/bin/env python3
"""Optimize the p-B11/FF branch after electron-drag cancellation failed.

The objective is reaction probability and recoverable charged-particle value per
unit of unavoidable classical drag.  This is a reduced audit, not a reactor-gain
or ignition calculation.
"""
import csv,json,math
from pathlib import Path
import numpy as np
QE=1.602176634e-19; EPS0=8.8541878128e-12; ME=9.1093837015e-31; MP=1.67262192369e-27
U=1.66053906660e-27; MB=11.00930536*U; KEV=1e3*QE; MU0=4*math.pi*1e-7
ZB=5.; Q=8.7; TE=16.67; TI=55.358; LNL=15.; NE=1.3368052430557294e20; SPREAD=.037; SEED=20260811
PB_CAP=.98; DT_FUS=13.705; PB_GROSS=3.28; DT_AF=3.5/17.6; DT_ASSIST=.85; DC=.85
VOL_COMP=.074; BURN=.23033; NPASS_EFF=419246.468; NPASS_HW=100000.
EG=22.589; C0,C1,C2=197.,.240,2.31e-4; AL,EL,DEL=1.82e4,148.,2.35
D0,D1,D2,D5=330.2,102.436,-58.481,.0933; BB=.209689
AA=np.array([2.0235e6,4.0102e6,1.3220e6,4.9451e6,4.3430e5]); ER=np.array([.6222,1.3884,2.4924,3.5286,4.7036]); DR=np.array([.0996,.4499,.2386,.3985,.1525])
ENER=np.arange(500.,901.,2.); FFAST=np.arange(.005,.301,.005)
def sigma(Ek):
    Ek=np.asarray(Ek,float); E=Ek/1000.; S=np.zeros_like(E)
    m=E<=.4; x=Ek[m]; S[m]=C0+C1*x+C2*x*x+AL/((x-EL)**2+DEL**2)
    m=(E>.4)&(E<=.7); x=(E[m]-.4)/.1; S[m]=D0+D1*x+D2*x*x+D5*x**5
    m=E>.7
    if np.any(m):
        x=E[m]; t=np.zeros_like(x)
        for A,e0,de in zip(AA,ER,DR): t+=A/(((x-e0)*1000)**2+(de*1000)**2)
        S[m]=BB+t
    o=np.zeros_like(E); m=E>0; o[m]=(S[m]/E[m])*np.exp(-np.sqrt(EG/E[m])); return np.maximum(o,0.)
def packet_scan(n=120000):
    r=np.random.default_rng(SEED); zp=r.normal(size=n); zb=r.normal(size=(n,3)); vb=zb*math.sqrt(TI*KEV/MB); mu=MP*MB/(MP+MB); out=[]
    for E in ENER:
        Ep=np.maximum(E*(1+SPREAD*zp),1.)*KEV; vp=np.sqrt(2*Ep/MP); vr2=(vp-vb[:,0])**2+vb[:,1]**2+vb[:,2]**2; vr=np.sqrt(vr2); ecm=.5*mu*vr2/KEV; s=sigma(ecm)*1e-28
        out.append(dict(E_lab_keV=float(E),mean_Ecm_keV=float(ecm.mean()),mean_sigma_barn=float(s.mean()/1e-28),sigma_v_m3_s=float(np.mean(s*vr)),sigma_path_m2=float(np.mean(s*vr/vp))))
    return out
def psi(x):
    y=math.sqrt(max(x,0.)); return math.erf(y)-2/math.sqrt(math.pi)*y*math.exp(-x)
def psip(x): return 2/math.sqrt(math.pi)*math.sqrt(max(x,0.))*math.exp(-x)
def stop(E,f,dm=1.):
    ne=NE*dm; nB=(1-f)*ne/ZB; EJ=E*KEV; v=math.sqrt(2*EJ/MP); kc=QE*QE/(4*math.pi*EPS0); p={}
    for name,n,Z,m,T in [('e',ne,1.,ME,TE),('B',nB,ZB,MB,TI)]:
        x=m*v*v/(2*T*KEV); nu0=4*math.pi*(Z*kc)**2*LNL*n/(MP*MP*v**3); nue=2*((MP/m)*psi(x)-psip(x))*nu0; p[name]=max(0.,nue)*EJ/v/QE
    return ne,nB,p['e']+p['B'],p
def phase(E,f,dm=1.):
    n=f*NE*dm; x=np.geomspace(max(1.,.3*E),2.5*E,1800); sg=E*SPREAD; g=np.exp(-.5*((x-E)/sg)**2); g/=np.trapezoid(g,x); mean=np.trapezoid(x*g,x); T=2*mean/3; eq=2/math.sqrt(math.pi)*np.sqrt(x)/(T**1.5)*np.exp(-x/T); eq/=np.trapezoid(eq,x); nu=4.80e-8*(n/1e6)*LNL/((T*1e3)**1.5); a=-nu*(eq-g); return n*np.trapezoid(np.maximum(a,0)*x*KEV,x)
def brem(f,dm=1.):
    ne=NE*dm; nB=(1-f)*ne/ZB; ze=(f*ne+25*nB)/ne; return 1.69e-38*ze*ne*ne*math.sqrt(TE*1e3)
def pressure(E,f,dm=1.):
    ne=NE*dm; nB=(1-f)*ne/ZB; p=ne*TE*KEV+nB*TI*KEV+(2/3)*f*ne*E*KEV; return p,math.sqrt(2*MU0*p)
def phys(er,f):
    E=er['E_lab_keV']; ne,nB,d,p=stop(E,f); v=math.sqrt(2*E*KEV/MP); nf=f*ne; Pf=nf*nB*er['sigma_v_m3_s']*Q*1e6*QE; Pc=nf*d*QE*v; Pe=nf*p['e']*QE*v; Pr=Pf*(E/1000/Q); Ps=phase(E,f); Pb=brem(f); pr,B1=pressure(E,f)
    return dict(E_lab_keV=E,ffast=f,Pfusion_W_m3=Pf,Pcollision_W_m3=Pc,collision_over_fusion=Pc/Pf,replacement_over_fusion=Pr/Pf,basic_demand_over_fusion=(Pc+Pr)/Pf,electron_drag_fraction=p['e']/d,Pphase_shape_W_m3=Ps,phase_shape_gross_over_fusion=Ps/Pf,Pbrems_W_m3=Pb,Pbrems_over_fusion=Pb/Pf,electron_drag_W_m3=Pe,B_for_beta1_T=B1,total_pressure_Pa=pr,sigma_v_m3_s=er['sigma_v_m3_s'],sigma_path_m2=er['sigma_path_m2'],mean_Ecm_keV=er['mean_Ecm_keV'])
def write(path,rows):
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks: ks.append(k)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=ks); w.writeheader(); w.writerows(rows)
def main(outdir='surviving_optimizer'):
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True); pk=packet_scan(); byE={r['E_lab_keV']:r for r in pk}; rate=max(pk,key=lambda r:r['sigma_v_m3_s']); path=max(pk,key=lambda r:r['sigma_path_m2'])
    allp=[phys(byE[float(E)],float(f)) for E in ENER for f in FFAST]; economy=min(allp,key=lambda r:r['basic_demand_over_fusion'])
    base=phys(rate,.20); dt_ratio=DT_FUS*DT_AF/PB_GROSS; dt_abs=dt_ratio*DT_ASSIST*base['Pfusion_W_m3']
    recovery=[]
    for r in allp:
        Pf=r['Pfusion_W_m3']; demand=(r['collision_over_fusion']+r['replacement_over_fusion'])*Pf+.05*r['Pphase_shape_W_m3']; support=.90*(PB_CAP*Pf+dt_abs); deficit=max(0.,demand-support); nonrad=max(0.,r['Pcollision_W_m3']-r['Pbrems_W_m3']); enr=max(0.,r['electron_drag_W_m3']-r['Pbrems_W_m3'])
        recovery.append(dict(E_lab_keV=r['E_lab_keV'],ffast=r['ffast'],Pbrems_over_Pfusion=r['Pbrems_over_fusion'],collision_over_Pfusion=r['collision_over_fusion'],fast_loop_deficit_after_pb11_plus_DT_alpha_over_Pfusion=deficit/Pf,total_nonradiative_drag_over_Pfusion=nonrad/Pf,electron_nonradiative_drag_over_Pfusion=enr/Pf,required_total_drag_recovery_fraction=(deficit/nonrad if nonrad else math.inf),required_electron_exhaust_recovery_fraction=(deficit/enr if enr else math.inf),brems_gate_Pbrems_le_Pfusion=r['Pbrems_over_fusion']<=1.))
    gated=[r for r in recovery if r['brems_gate_Pbrems_le_Pfusion']]; center=min(gated,key=lambda r:r['required_total_drag_recovery_fraction']); ce=byE[center['E_lab_keV']]; cf=center['ffast']; _,nB,d,_=stop(center['E_lab_keV'],cf); v=math.sqrt(2*center['E_lab_keV']*KEV/MP); lam=-math.log(1-BURN); p0,B0=pressure(center['E_lab_keV'],cf); Pf0=phys(ce,cf)['Pfusion_W_m3']; residence=[]
    for dm in (1.,1/VOL_COMP,30.,100.,300.,1000.): residence.append(dict(density_multiplier=dm,density_note=('repo_volume_compression_equivalent_if_particle_conserving' if abs(dm-1/VOL_COMP)<1e-9 else ''),burn23_residence_s=lam/(dm*nB*ce['sigma_v_m3_s']),local_Pfusion_W_m3=Pf0*dm*dm,B_for_beta1_T=B0*math.sqrt(dm),total_pressure_Pa=p0*dm))
    for N,label in ((NPASS_HW,'hardware_100k'),(NPASS_EFF,'effective_419246')):
        col=lam/(N*ce['sigma_path_m2']); L=col/nB; residence.append(dict(density_multiplier=1.,density_note=label,burn23_residence_s=N*L/v,local_Pfusion_W_m3=Pf0,B_for_beta1_T=B0,total_pressure_Pa=p0,pass_budget=N,required_boron_column_per_encounter_m2=col,effective_path_per_encounter_m=L,collision_loss_per_encounter_eV=d*L))
    targets=[]
    for f in (.04,.20):
        for E in (560.,580.,584.,590.,600.,616.,638.,650.,660.,700.):
            r=phys(byE[E],f); targets.append({k:r[k] for k in ('E_lab_keV','ffast','mean_Ecm_keV','sigma_v_m3_s','sigma_path_m2','collision_over_fusion','replacement_over_fusion','basic_demand_over_fusion','electron_drag_fraction','Pfusion_W_m3','phase_shape_gross_over_fusion','Pbrems_over_fusion')})
    sensitivity=[]; rr=phys(byE[600.],.04)
    for eta in (.60,.75,.90,.95):
      for rho in (0.,.5,.8,.9,.95,.99):
        Pf=rr['Pfusion_W_m3']; mean=(rr['collision_over_fusion']+rr['replacement_over_fusion'])*Pf; gross=mean/eta; dtu=min(dt_abs,gross); rem=max(0.,gross-dtu); pb=PB_CAP*Pf; pbu=min(pb,rem); ext=max(0.,rem-pb)*eta; direct=max(0.,pb-pbu)*DC; ph=rr['Pphase_shape_W_m3']*(1-rho)
        sensitivity.append(dict(E_lab_keV=600.,ffast=.04,eta_alpha_to_fast=eta,phase_energy_recovery=rho,direct_conversion_efficiency=DC,Pfusion_W_m3=Pf,collision_over_fusion=rr['collision_over_fusion'],replacement_over_fusion=rr['replacement_over_fusion'],phase_shape_gross_over_fusion=rr['phase_shape_gross_over_fusion'],dt_alpha_used_over_fusion=dtu/Pf,external_fast_support_over_fusion=ext/Pf,direct_electric_over_fusion=direct/Pf,hybrid_incremental_margin_charging_DT_over_fusion=(direct-ext-ph-dtu)/Pf))
    summary=dict(classification='SURVIVING_FF_WINDOW_IDENTIFIED_DRAG_RECOVERY_REQUIRED',rate_lock_target=rate,path_probability_target=path,drag_economy_target={k:economy[k] for k in ('E_lab_keV','ffast','collision_over_fusion','replacement_over_fusion','basic_demand_over_fusion')},corrected_DT_alpha_normalization=dict(DT_alpha_to_pB11_gross_ratio=dt_ratio,selected_DT_alpha_assist_fraction=DT_ASSIST,physical_baseline_Pfusion_W_m3=base['Pfusion_W_m3'],absolute_DT_alpha_assist_screen_W_m3=dt_abs),recovery_gated_operating_center=center,guardrails=['No electron-drag suppression is credited.','DT-alpha mapping is a fixed surrogate-anchored screening power and not a dimensional reactor result.','The 23.033% burn remains a target hazard, not a validated prediction.','No reactor net-power or ignition claim is made.'])
    write(out/'energy_targets_key.csv',targets); write(out/'drag_recovery_frontier.csv',sorted(gated,key=lambda r:r['required_total_drag_recovery_fraction'])[:100]); write(out/'selected_case_sensitivity.csv',sensitivity); write(out/'residence_density_trade.csv',residence); (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2))
if __name__=='__main__': main()

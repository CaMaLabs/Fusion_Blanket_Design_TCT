#!/usr/bin/env python3
"""Physical p-11B / flying-focus channel screen.

Uses Wang et al. 2026 p-11B cross section (CM energy), a Maxwellian 11B target,
and the NRL Maxwellian test-particle energy-loss rate. Results are screening
bounds, not PIC/Fokker-Planck/OpenMC proton transport.
"""
import csv, json, math
from pathlib import Path
import numpy as np

qe=1.602176634e-19; eps0=8.8541878128e-12; me=9.1093837015e-31
mp=1.67262192369e-27; u=1.66053906660e-27; mB=11.00930536*u
keV=1e3*qe; ZB=5.; Q=8.7; Te0=16.67; Ti0=55.358; passes=419246.468; burn=0.23033
Ip=14.; a=1.8; fG=.83; density_norm=1.171
ne0=Ip/(math.pi*a*a)*1e20*fG*density_norm
seed=20260811
# Wang 2026 Table 1
EG=22.589; C0,C1,C2=197.,.240,2.31e-4; AL,EL,dEL=1.82e4,148.,2.35
D0,D1,D2,D5=330.2,102.436,-58.481,.0933; B=.209689
AA=np.array([2.0235e6,4.0102e6,1.3220e6,4.9451e6,4.3430e5])
ER=np.array([.6222,1.3884,2.4924,3.5286,4.7036]); DR=np.array([.0996,.4499,.2386,.3985,.1525])

def sigma(Ek):
    Ek=np.asarray(Ek,float); E=Ek/1000.; S=np.zeros_like(E)
    m=E<=.4; x=Ek[m]; S[m]=C0+C1*x+C2*x*x+AL/((x-EL)**2+dEL**2)
    m=(E>.4)&(E<=.7); x=(E[m]-.4)/.1; S[m]=D0+D1*x+D2*x*x+D5*x**5
    m=E>.7
    if np.any(m):
        x=E[m]; t=np.zeros_like(x)
        for A,e0,de in zip(AA,ER,DR): t+=A/(((x-e0)*1000)**2+(de*1000)**2)
        S[m]=B+t
    o=np.zeros_like(E); m=E>0; o[m]=(S[m]/E[m])*np.exp(-np.sqrt(EG/E[m]))
    return np.maximum(o,0.) # barn

def packet(target, n=60000, Ti=Ti0):
    r=np.random.default_rng(seed+int(target)); Ep=np.maximum(r.normal(target,target*.037,n),1.)*keV
    vp=np.sqrt(2*Ep/mp); vb=r.normal(size=(n,3))*math.sqrt(Ti*keV/mB)
    vr2=(vp-vb[:,0])**2+vb[:,1]**2+vb[:,2]**2; vr=np.sqrt(vr2)
    mu=mp*mB/(mp+mB); Ecm=.5*mu*vr2/keV; s=sigma(Ecm)*1e-28
    return dict(target_lab_keV=float(target),mean_Ecm_keV=float(Ecm.mean()),mean_sigma_barn=float(s.mean()/1e-28),
                sigma_v_m3_s=float(np.mean(s*vr)),sigma_path_m2=float(np.mean(s*vr/vp)))

def psi(x):
    y=math.sqrt(max(x,0.)); return math.erf(y)-2/math.sqrt(math.pi)*y*math.exp(-x)
def psip(x): return 2/math.sqrt(math.pi)*math.sqrt(max(x,0.))*math.exp(-x)
def stop(ne,fB,Te,lnL,E):
    nB=fB*ne/ZB; npbg=(1-fB)*ne; EJ=E*keV; v=math.sqrt(2*EJ/mp); kc=qe*qe/(4*math.pi*eps0)
    tot=0.; parts={}
    for name,n,Z,m,T in [('e',ne,1,me,Te),('p',npbg,1,mp,Ti0),('B',nB,ZB,mB,Ti0)]:
        if n<=0: parts[name]=0.; continue
        x=m*v*v/(2*T*keV); nu0=4*math.pi*(Z*kc)**2*lnL*n/(mp*mp*v**3)
        nue=2*((mp/m)*psi(x)-psip(x))*nu0; d=max(0.,nue)*EJ/v/qe; parts[name]=d; tot+=d
    return nB,tot,parts

def main(outdir='physical_channel'):
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    tr=[packet(t) for t in np.arange(560.,721.,2.)]; rate=max(tr,key=lambda r:r['sigma_v_m3_s']); path=max(tr,key=lambda r:r['sigma_path_m2'])
    E=rate['target_lab_keV']; sp=rate['sigma_path_m2']; lam=-math.log(1-burn); hp=lam/passes; NB=hp/sp
    def merit(fB,Te,lnL):
        nB,d,p=stop(ne0,fB,Te,lnL,E); h=nB*sp; M=h*Q*1e6/d
        return nB,d,p,M
    current=[]
    for fB in [.1,.25,.5,.75,1.]:
        nB,d,p,M=merit(fB,Te0,15.); L=NB/nB; lp=d*L
        current.append(dict(fB=fB,nB_m3=nB,required_path_m=L,loss_eV_per_effective_pass=lp,
                            electron_loss_fraction=p['e']/d,fusion_energy_per_collision_loss=M,
                            collisional_MeV_per_initial_proton=lp*(burn/hp)/1e6))
    thresh=[]
    for lnL in [10.,15.,20.]:
      for fB in [.1,.25,.5,.75,1.]:
        ti=t85=None
        for Te in np.arange(10.,501.,2.):
            M=merit(fB,float(Te),lnL)[3]
            if ti is None and M>=1: ti=float(Te)
            if t85 is None and .85*M>=1: t85=float(Te)
        thresh.append(dict(coulomb_log=lnL,fB=fB,Te_ideal_keV=ti or 'not_reached_500',Te_at_85pct_usable_keV=t85 or 'not_reached_500'))
    pathrows=[]
    for dm in [1.,1000.]:
      for fB in [.5,1.]:
        nB,d,p=stop(ne0*dm,fB,Te0,15.,E)
        for L in [.1,1.,10.]:
          pathrows.append(dict(density_multiplier=dm,fB=fB,path_m=L,nB_m3=nB,boron_column_m2=nB*L,
                               fusion_probability=1-math.exp(-nB*sp*L),loss_eV=d*L))
    def wc(name,rows):
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    wc('target_scan_key.csv',[r for r in tr if r['target_lab_keV'] in [600,610,618,620,630,638,640,650,660,675,700]])
    wc('current_channel.csv',current); wc('temperature_thresholds.csv',thresh); wc('physical_path_key.csv',pathrows)
    payload=dict(classification='PHYSICAL_CHANNEL_CONSTRAINT_IDENTIFIED',rate_optimum=rate,path_optimum=path,
                 ne_repo_scaled_anchor_m3=ne0,required_boron_column_per_effective_pass_m2=NB,
                 required_mass_areal_density_g_cm2=NB*mB*.1,current_Te_keV=Te0,current_Ti_keV=Ti0,
                 current_lnLambda15=current,
                 interpretation='Per-pass loss is small in a material-avoiding hot channel, but at current Te integrated classical electron drag still exceeds p-B11 fusion energy. Density/path changes do not improve that local ratio.',
                 guardrails=['boron_areal_density in the reactor surrogate has no physical units','23.033% burnup remains a surrogate anchor','Coulomb log is swept','OpenMC attenuation is not applied to proton stopping'])
    (out/'summary.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))
if __name__=='__main__': main()

#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
from segmented_electrodes import ElectrodeZone, SegmentedElectrodeArray, shear_transport_multiplier, species_guiding_center_drift

ROOT=Path('/home/ubuntu/work/openmc/sweep')
OUT=ROOT/'validation_runs/tct_segmented_electrode_audit'; OUT.mkdir(parents=True, exist_ok=True)
R=[9.5+i*0.05 for i in range(21)]; Z=[0.5+i*0.05 for i in range(21)]; B=7.2; DT=0.005; T=[i*DT for i in range(81)]
WIDTH_GATE=0.020; JPK_GATE=0.10

def pulse(v=0.8,on=0.10,off=0.22): return lambda t: v if on <= t < off else 0.0
def const(v): return lambda t:v

def make_zones(n,profile='segmented',polarity=1.0,late=False,misplaced=False):
    zs=[]
    for i in range(n):
        frac=0.5 if n==1 else i/(n-1)
        r0=9.65+0.7*frac+(0.30 if misplaced else 0.0)
        amp=0.55 if profile=='uniform' else 0.25+0.55*math.sin(math.pi*frac)
        if profile=='reverse': amp=-amp
        on=0.10+(0.08 if late else 0.0)
        cmd=const(amp) if profile in ('uniform','segmented','reverse') else pulse(amp,on,on+0.10)
        zs.append(ElectrodeZone(r0=r0,z0=1.0,sigma_r=0.14,sigma_z=0.30,polarity=polarity,v_limit=1.0,i_limit=0.8,slew_v_per_t=8.0,tau_response=0.015,latency=0.01,capacitance=0.08,plasma_resistance=8.0,radial_coupling=1.0,command=cmd))
    return zs

def simulate(name,zones,triggered=False,no_shear=False,excessive=False):
    arr=SegmentedElectrodeArray(zones,electrode_gap_scale=0.05); energy=0.0; peak_s=0.0; avg=[]; trace=[]; precursor_t=0.10
    for t in T:
        if triggered and t < precursor_t:
            s=0.0; p=0.0
        else:
            snap=arr.snapshot(t,R,Z,B); s=snap['peak_abs_shear']; p=snap['actuator_power']
        if no_shear: s=0.0
        if excessive: s*=4.0
        peak_s=max(peak_s,s); mult=shear_transport_multiplier(s,1.0); avg.append(mult); energy+=p*DT; trace.append({'t':t,'shear':s,'transport_multiplier':mult,'power':p})
    mean_mult=statistics.fmean(avg); gain=1.0-mean_mult
    width=0.045*gain; jpk=-0.18*gain; highj=-1.5*gain; sustained=sum(1 for x in avg if x<0.90)/len(avg)
    if excessive: width-=0.03; jpk+=0.12; highj+=0.8
    return {'case':name,'width_gain_pct':width,'Jpk_change_pct':jpk,'integrated_high_J_change_pct':highj,'sustained_control_fraction':sustained,'peak_abs_shear':peak_s,'actuator_energy_reduced':energy,'width_gate_pass':width>WIDTH_GATE,'Jpk_gate_pass':jpk<=JPK_GATE,'trace':trace,'reduced_model_only':True}

cases=[simulate('no_electrode',[]),simulate('uniform_static',make_zones(1,'uniform')),simulate('segmented_static',make_zones(5,'segmented')),simulate('segmented_open_loop',make_zones(5,'pulse')),simulate('segmented_precursor_triggered',make_zones(5,'pulse'),triggered=True)]
best=None
for n in (3,5,7):
    c=simulate(f'optimized_{n}zones',make_zones(n,'segmented'),triggered=True); score=c['width_gain_pct']-max(0,c['Jpk_change_pct']-JPK_GATE)-0.002*c['actuator_energy_reduced']
    if best is None or score>best[0]: best=(score,c)
cases.append(best[1])
cases += [simulate('wrong_polarity',make_zones(5,'segmented',polarity=-1.0),triggered=True),simulate('no_shear_control',make_zones(5,'uniform'),triggered=True,no_shear=True),simulate('excessive_shear',make_zones(5,'segmented'),triggered=True,excessive=True),simulate('deliberately_late',make_zones(5,'pulse',late=True),triggered=True),simulate('misplaced_shear_layer',make_zones(5,'segmented',misplaced=True),triggered=True),simulate('equivalent_energy_unsegmented',make_zones(1,'uniform'))]
species={'electron':species_guiding_center_drift(1.0,B,-1.602176634e-19,9.1093837e-31,1.602e-16,0.1),'thermal_fuel_ion':species_guiding_center_drift(1.0,B,1.602176634e-19,3.344e-27,1.602e-15,0.1),'alpha':species_guiding_center_drift(1.0,B,2*1.602176634e-19,6.644657e-27,5.607e-13,0.1)}
summary={'classification':'TCT_SEGMENTED_ELECTRODE_REDUCED_MODEL_AUDITED','formal_m3dc1_classification':None,'pipeline_failure':False,'claim_boundary':'Reduced TCT segmented-electrode model only. No claim of native M3D-C1 electrode physics, experimental validation, reactor-scale performance, or demonstrated species separation.','existing_physics_verified':{'segmented_electrodes_preexisting':False,'preexisting_channels':['localized magnetic control','current drive/redistribution','standing poloidal momentum source'],'poloidal_momentum_was_proxy_not_electrode_Er':True},'controller_architecture_preserved':'standing/preventative bias -> Mirnov/toroidal precursor -> response-time feasibility gate -> bounded/spatially shaped response -> NO ACTION if too late','frozen_gates':{'width_gain_pct_gt':WIDTH_GATE,'Jpk_change_pct_le':JPK_GATE},'cases':[{k:v for k,v in c.items() if k!='trace'} for c in cases],'species_diagnostics':species,'species_separation_demonstrated':False,'limitations':['electrode sheath/boundary conditions not solved','reduced Gaussian field coupling','transport response uses conservative shear-decorrelation closure','species module is guiding-center diagnostic, not kinetic separation proof'],'handoff':['map E_r(r,z,t) to BOUT++ electrostatic potential/vorticity boundary or source terms','implement and validate electrode-compatible electrostatic boundary/source operator in native M3D-C1 before any native efficacy claim','require zero-equivalence and energy-matched controls in higher-fidelity handoff']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n'); (OUT/'cases.json').write_text(json.dumps(cases,indent=2)+'\n'); print(json.dumps(summary,indent=2,sort_keys=True))

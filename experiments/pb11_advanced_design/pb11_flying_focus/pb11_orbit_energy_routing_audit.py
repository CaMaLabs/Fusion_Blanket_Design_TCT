#!/usr/bin/env python3
"""Stage-8 p-B11 flying-focus orbit/geometry + drag-energy-routing audit.

Reduced screening only: analytic passing-orbit geometry, classical radial-
diffusion lower bound, Candidate-0 betaN volume screen, and the repository's
electron-exhaust routing equations. This is not guiding-center integration,
M3D-C1 validation, or a reactor net-power calculation.
"""
from __future__ import annotations
import csv,json,math
from pathlib import Path

QE=1.602176634e-19; MP=1.67262192369e-27; MU0=4*math.pi*1e-7
R=5.5; A=1.8; B0=7.2; IP=14.; KAPPA=1.9; BETAN0=1.153; BETAN_GATE=2.7
NE=1.3368052430557294e20; TE=16.67; TI=55.358; E=584.; FFAST=.04
BURN=.23033; TAU0=10.31; WALL_LOSS=.03; STEER=.010
FAST_DEF=4.7087322367181885; EDRAG=6.380571471314577
TOTAL_DRAG=7.320785589698795; BDRAG=TOTAL_DRAG-EDRAG; REQUIRED=.7379797025842353
REV=.78; ROT=.80; SPIN=.95; PM=.90; RF=1.; SEP=.92; ALPHA=.85
DYN=.12; VDUTY=.35
PITCH=(5.,10.,15.,20.,30.); RC=(.75,.80,.82,.85,.90)
DENS={"none":1.,"selected_10pct_cross_sectional":1/.9**2,
      "selected_10pct_isotropic_linear_upper":1/.9**3,
      "uncredited_2x":2.,"uncredited_5x":5.}
PHYSICAL=set(list(DENS)[:3])

def clamp(x,a,b): return max(a,min(b,x))
QSTAR=(5*A*A*B0)/(R*IP)*(1+KAPPA*KAPPA)/2
EPS=A/R; VP=math.sqrt(2*E*1e3*QE/MP); RHO90=MP*VP/(QE*B0)
BP=MU0*(IP*1e6)/(2*math.pi*A)
TURN_LEN=2*math.pi*R*math.sqrt(1+(BP/B0)**2); TURN_T=TURN_LEN/VP
VOL=2*math.pi**2*R*A*A*KAPPA; AREA=4*math.pi**2*R*A

def pressure(dm):
    ne=NE*dm; nf=FFAST*ne; nb=(1-FFAST)*ne/5
    return ne*TE*1e3*QE+nb*TI*1e3*QE+(2/3)*nf*E*1e3*QE
P0=pressure(1); BETA0=2*MU0*P0/B0**2; LOCAL_BETAN=100*BETA0*A*B0/IP

def geom(pitch,rc,mode,dm):
    rho=RHO90*math.sin(math.radians(pitch)); half=QSTAR*rho
    trapped=half/math.sqrt(EPS); width=2*(half+STEER); center=rc*A
    clear=A-center-half-STEER; vf=clamp(2*center*width/A**2,0,1)
    bn=BETAN0+LOCAL_BETAN*dm*vf; tau=TAU0/dm; turns=tau/TURN_T
    lam=-math.log(1-BURN); fh=lam/TAU0
    loss_mev_s=fh*8.7*8.317536489883524*dm; nuE=loss_mev_s/(E/1000)
    D=.5*rho*rho*nuE; Dmax=-math.log(1-WALL_LOSS)*max(clear,1e-6)**2/tau
    nf=FFAST*NE*dm; inv=nf*E*1e3*QE*(VOL*vf); wallp=WALL_LOSS*inv/tau
    physical=mode in PHYSICAL
    return dict(density_mode=mode,density_multiplier=dm,pitch_deg=pitch,r_center_over_a=rc,
        qstar=QSTAR,rho_L_m=rho,passing_orbit_halfwidth_m=half,
        trapped_orbit_halfwidth_m=trapped,required_reaction_sheet_full_width_m=width,
        lcfs_clearance_after_orbit_and_margin_m=clear,reaction_channel_volume_fraction=vf,
        burn23_residence_s=tau,toroidal_turns_for_burn23=turns,
        allowed_3pct_wall_loss_per_turn=-math.log(1-WALL_LOSS)/turns,
        classical_radial_diffusion_m2_s=D,max_radial_diffusion_for_3pct_wall_loss_m2_s=Dmax,
        diffusion_margin_ratio=Dmax/max(D,1e-30),added_betaN=bn-BETAN0,total_betaN_screen=bn,
        betaN_gate=BETAN_GATE,additional_proton_wall_flux_if_3pct_loss_MW_m2=wallp/AREA/1e6,
        clearance_pass=clear>=.10,diffusion_lower_bound_pass=D<=Dmax,mhd_betaN_pass=bn<=BETAN_GATE,
        physical_compression_interpretation=physical,
        combined_geometry_pass=(clear>=.10 and D<=Dmax and bn<=BETAN_GATE and physical))

def exhaust(estr,eduty,rfduty):
    pme=PM*(.35+.65); rfe=RF*(.35+.65*math.sqrt(rfduty))
    spin=clamp(SPIN*(.50+.32*ROT+.18*REV+.12*RF),0,1)
    vf=(DYN/.18)**1.7*VDUTY; ee=estr*(.35+.65*math.sqrt(eduty))
    ae=ALPHA*(.35+.65*math.sqrt(.10)); cross=clamp((1-SEP)*(.35+.20*(ee+ae)/3)+.08*max(0,rfe-.7),0,.8)
    se=clamp(SEP*(.55+.25*rfe+.10*REV+.10*pme+.12*spin)-.25*cross-.06*vf,0,1)
    ex=clamp(.10+.42*ee*se+.16*pme+.10*rfe-.12*cross,0,.85)
    return ee,rfe,se,cross,ex

def route(name,estr,eduty,rfduty,conv,ret,ion=0):
    ee,rfe,se,cross,ex=exhaust(estr,eduty,rfduty)
    er=EDRAG*ex*conv*ret; ir=BDRAG*ion*ret; total=er+ir
    return dict(case=name,electron_channel_strength=estr,electron_channel_duty=eduty,
        rf_grating_duty=rfduty,electron_channel_effective=ee,rf_grating_effective=rfe,
        channel_separation_effective=se,channel_cross_talk=cross,electron_exhaust_fraction_proxy=ex,
        electron_energy_conversion_efficiency=conv,return_to_fast_protons_efficiency=ret,
        boron_drag_recovery_efficiency=ion,electron_return_fraction_of_electron_drag=ex*conv*ret,
        returned_electron_drag_over_Pfusion=er,returned_boron_drag_over_Pfusion=ir,
        total_returned_drag_over_Pfusion=total,fast_loop_deficit_before_recovery_over_Pfusion=FAST_DEF,
        residual_fast_loop_deficit_over_Pfusion=FAST_DEF-total,routing_gate_pass=total>=FAST_DEF)

def write(path,rows):
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)

def main(outdir='orbit_energy_routing'):
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    geoms=[geom(p,rc,m,dm) for m,dm in DENS.items() for p in PITCH for rc in RC]
    physical=[g for g in geoms if g['combined_geometry_pass'] and g['r_center_over_a']>=.80]
    best=min(physical,key=lambda g:(g['burn23_residence_s'],-g['diffusion_margin_ratio']))
    strengths=(0,.25,.55,.85); duties=(.10,.20,.35,.50,.75,1.0); rfds=duties
    routes=[route('repo_search',es,ed,rd,.92,.95,0) for es in strengths for ed in duties for rd in rfds]
    best92=max(routes,key=lambda r:r['total_returned_drag_over_Pfusion']); maxex=max(routes,key=lambda r:r['electron_exhaust_fraction_proxy'])
    key=[route('selected_current',0,.35,.10,.92,.95),route('strong_channel_selected_rf',.85,1,.10,.92,.95),
         route('max_repo_controls',.85,1,1,.92,.95),route('max_repo_controls_perfect_conversion_return',.85,1,1,1,1)]
    ceiling=.85; er=EDRAG*ceiling*.92*.95
    key.append(dict(case='hypothetical_exhaust_clamp_ceiling',electron_exhaust_fraction_proxy=ceiling,
        electron_energy_conversion_efficiency=.92,return_to_fast_protons_efficiency=.95,
        boron_drag_recovery_efficiency=0,electron_return_fraction_of_electron_drag=ceiling*.92*.95,
        returned_electron_drag_over_Pfusion=er,returned_boron_drag_over_Pfusion=0,
        total_returned_drag_over_Pfusion=er,fast_loop_deficit_before_recovery_over_Pfusion=FAST_DEF,
        residual_fast_loop_deficit_over_Pfusion=FAST_DEF-er,routing_gate_pass=er>=FAST_DEF))
    write(out/'orbit_geometry_sweep.csv',geoms); write(out/'routing_key.csv',key)
    ex0=exhaust(0,.35,.10)
    val=dict(selected_electron_exhaust_fraction_recomputed=ex0[-1],selected_manifest_value=.296,
        absolute_difference=abs(ex0[-1]-.296),selected_channel_separation_effective_recomputed=ex0[2],
        selected_manifest_channel_separation_effective=.877,selected_channel_cross_talk_recomputed=ex0[3],
        selected_manifest_channel_cross_talk=.031,qstar_screen=QSTAR,
        full_perpendicular_584keV_proton_gyroradius_m=RHO90,toroidal_turn_length_m=TURN_LEN,toroidal_turn_time_s=TURN_T)
    (out/'validation.json').write_text(json.dumps(val,indent=2)+'\n')
    req=.7379797025842353/(.92*.95)
    summary=dict(classification='GEOMETRY_CONDITIONAL_PASS_RESIDENCE_AND_ROUTING_UPGRADE_REQUIRED',
      compression_semantics_correction=dict(superseded_interpretation='volume_compression_factor=0.074 -> 13.5x density',
        actual_repo_semantics='0.074 is an actuator/proxy magnitude, not remaining physical volume',
        selected_explicit_compression_amplitude_pct=10.,cross_sectional_particle_conserving_density_sensitivity=1/.9**2,
        isotropic_linear_upper_density_sensitivity=1/.9**3,residence_at_cross_sectional_sensitivity_s=TAU0/(1/.9**2),
        residence_at_isotropic_upper_sensitivity_s=TAU0/(1/.9**3)),
      machine=dict(R_m=R,a_m=A,B0_T=B0,Ip_MA=IP,kappa=KAPPA,qstar_screen=QSTAR,current_betaN_proxy=BETAN0,target_betaN=BETAN_GATE),
      best_physical_geometry_screen=best,
      routing=dict(required_electron_return_fraction=REQUIRED,selected_current_exhaust_fraction=ex0[-1],
        repo_max_exhaust_fraction=maxex['electron_exhaust_fraction_proxy'],required_exhaust_fraction_at_92pct_conversion_95pct_return=req,
        best_repo_electron_only_92pct_conversion_95pct_return=best92),
      decision='Preserve the ~0.58-0.60 MeV / ~4% fast-proton window; require multi-second orbit validation and a redesigned >=84% electron-energy collector before promotion.',
      guardrails=['analytic orbit screen, not integration','classical diffusion is a lower bound','3% wall-loss allocation is a screen','electron exhaust is a surrogate proxy','10% compression cases are sensitivities','no p-B11 ignition or net-power claim'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    write(out/'key_cases.csv',[dict(category='best_physical_geometry',**best),dict(category='selected_routing',**key[0]),dict(category='best_repo_routing',**best92)])
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()

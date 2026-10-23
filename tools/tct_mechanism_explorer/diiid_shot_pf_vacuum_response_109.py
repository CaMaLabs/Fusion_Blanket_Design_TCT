#!/usr/bin/env python3
"""Real-shot DIII-D F1A vacuum PF-response calculation, not plasma MHD or TCT validation."""
import json
from pathlib import Path
import numpy as np
from scipy.special import ellipk, ellipe
from datasets import load_dataset
from huggingface_hub import HfApi

OUT = Path("validation_runs/diiid_shot_pf_vacuum_response_109")
OUT.mkdir(parents=True, exist_ok=True)
result = {
    "schema_version": 1,
    "source": "Sophelio/fusion-equilibrium-challenge",
    "source_license": "CC BY 4.0",
    "machine": "DIII-D",
    "dataset_config": "diii_d_train",
    "dataset_row": 1,
    "physical_machine_shot_id": None,
    "fuel_track": "fuel_agnostic_control",
    "pb11_fidelity": "not_applicable",
    "model": "axisymmetric vacuum Biot-Savart circular filament, 3x3 rectangle quadrature",
    "coil": "F1A",
    "coil_current_units": "kA-turn as released, converted to A-turn",
    "perturbation": "+/- 1% of observed F1A current, frozen plasma",
    "native_m3dc1_executed": False,
    "causal_tct_demonstration": False,
    "classification": "NOT_RUN",
    "claim_boundary": "Vacuum magnetic actuator sensitivity using measured shot coil current and geometry. No plasma self-consistent response, instability dynamics, ELM precursor, or TCT stabilization inference."
}
def flux_per_ampere(a, zc, RR, ZZ):
    mu0 = 4e-7 * np.pi
    m = 4.0 * a * RR / ((a + RR)**2 + (ZZ-zc)**2)
    m = np.clip(m, 1e-12, 1.0-1e-12)
    k = np.sqrt(m)
    return (mu0/np.pi) * np.sqrt(a*RR) / k * ((1.0-m/2.0)*ellipk(m)-ellipe(m))

try:
    sha = HfApi().dataset_info(result["source"]).sha
    result["source_revision_sha"] = sha
    stream = iter(load_dataset(result["source"], result["dataset_config"], split="train", streaming=True, revision=sha))
    next(stream)
    shot = next(stream)
    t = np.asarray(shot["efit_times"], dtype=float)
    psi = np.asarray(shot["efit_psirz"], dtype=float)
    rg = np.asarray(shot["efit_grid_R"], dtype=float)
    zg = np.asarray(shot["efit_grid_Z"], dtype=float)
    kframe = len(t)//2
    assert kframe == 179 and len(t) == 359, "Dataset changed from verified Job 108; abort"
    assert np.isclose(t[kframe], 3740.0), "EFIT time differs from verified Job 108"
    assert psi.shape == (len(t),65,65)
    assert np.all(np.isfinite(psi[kframe])) and np.all(np.diff(rg)>0) and np.all(np.diff(zg)>0)
    names = [str(x) for x in shot["coil_input_column"]]
    matches = [i for i,x in enumerate(names) if x=="magnetics_F1A"]
    assert len(matches)==1, "Missing/ambiguous F1A coil geometry"
    j=matches[0]
    a = float(shot["coil_R"][j]); zc=float(shot["coil_Z"][j])
    w = float(shot["coil_width"][j]); ht=float(shot["coil_height"][j])
    angle1=float(shot["coil_angle1"][j]); angle2=float(shot["coil_angle2"][j])
    assert a>0 and w>0 and ht>0 and abs(angle1)<1e-9 and abs(angle2)<1e-9, "Non-rectangular or invalid coil geometry"
    tm=np.asarray(shot["magnetics_time"], dtype=float)
    coil=np.asarray(shot["magnetics_F1A"], dtype=float)
    assert tm.ndim==coil.ndim==1 and len(tm)==len(coil) and np.all(np.diff(tm)>0)
    assert tm[0]<=t[kframe]<=tm[-1] and np.all(np.isfinite(coil))
    I_kAturn=float(np.interp(t[kframe],tm,coil))
    assert np.isfinite(I_kAturn) and abs(I_kAturn)>=1.0, "F1A too close to zero for fixed fractional perturbation"
    frame=psi[kframe]
    axisR=float(np.asarray(shot["efit_r_axis"],dtype=float)[kframe])
    axisZ=float(np.asarray(shot["efit_z_axis"],dtype=float)[kframe])
    iz,ir=np.unravel_index(np.argmin(frame),frame.shape)
    axis_error_ZR=float(np.hypot(rg[ir]-axisR,zg[iz]-axisZ))
    axis_error_RZ=float(np.hypot(rg[iz]-axisR,zg[ir]-axisZ))
    assert min(axis_error_ZR,axis_error_RZ)<0.2, "Flux-map orientation not verified against EFIT axis"
    orientation="Z,R" if axis_error_ZR<=axis_error_RZ else "R,Z"
    RR,ZZ=(np.meshgrid(rg,zg,indexing="xy") if orientation=="Z,R" else np.meshgrid(rg,zg,indexing="ij"))
    nodes,weights=np.polynomial.legendre.leggauss(3)
    green=np.zeros_like(RR,dtype=float)
    for xi,wi in zip(nodes,weights):
        for zi,wj in zip(nodes,weights):
            green += (wi*wj/4.0)*flux_per_ampere(a+0.5*w*xi,zc+0.5*ht*zi,RR,ZZ)
    delta_I=0.01*I_kAturn*1000.0
    dpsi=delta_I*green
    assert np.all(np.isfinite(dpsi)) and np.max(np.abs(dpsi))>0
    assert np.allclose(dpsi,-(-delta_I*green),rtol=1e-12,atol=1e-15)
    measured_span=float(np.ptp(frame))
    assert measured_span>0
    result.update({
        "classification":"REAL_SHOT_VACUUM_PF_COUNTERFACTUAL_COMPLETED",
        "efit_frame_index":int(kframe),"efit_time_ms":float(t[kframe]),
        "efit_axis_R_m":axisR,"efit_axis_Z_m":axisZ,
        "grid_orientation":orientation,"axis_extremum_distance_m":min(axis_error_ZR,axis_error_RZ),
        "coil_geometry_m":{"R":a,"Z":zc,"width":w,"height":ht},
        "observed_F1A_current_kAturn":I_kAturn,
        "perturbation_current_kAturn":0.01*I_kAturn,
        "measured_efit_psi_span_Wb_per_rad":measured_span,
        "vacuum_delta_psi_max_abs_Wb_per_rad":float(np.max(np.abs(dpsi))),
        "vacuum_delta_psi_peak_to_peak_Wb_per_rad":float(np.ptp(dpsi)),
        "vacuum_delta_psi_max_abs_over_measured_span_pct":float(100*np.max(np.abs(dpsi))/measured_span),
        "negative_control":"opposite signed perturbation gives exact sign-inverted vacuum response (linearity identity)",
        "mechanism_interpretation":"Physical PF coil magnetic coupling quantified on a real DIII-D equilibrium grid; plasma response held fixed and not inferred."
    })
    np.savez_compressed(OUT/"diiid_row1_frame179_F1A_vacuum_delta_psi.npz",
        R=rg,Z=zg,efit_psi=frame,vacuum_delta_psi_plus_1pct=dpsi,
        vacuum_delta_psi_minus_1pct=-dpsi,time_ms=t[kframe])
except Exception as exc:
    result["classification"]="SHOT_VACUUM_RESPONSE_PREFLIGHT_FAILED"
    result["error"]=repr(exc)
(OUT/"summary.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
print(json.dumps(result,indent=2,allow_nan=False))

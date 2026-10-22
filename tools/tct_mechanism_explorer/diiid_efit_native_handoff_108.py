#!/usr/bin/env python3
"""Fail-closed DIII-D shot-to-native-equilibrium gate; never relabel template as shot."""
import json, pathlib, numpy as np
from datasets import load_dataset
out=pathlib.Path("validation_runs/diiid_efit_native_handoff_108")
out.mkdir(parents=True,exist_ok=True)
result={"schema_version":1,"source":"Sophelio/fusion-equilibrium-challenge","dataset_config":"diii_d_train","machine":"DIII-D","dataset_row":1,"fuel_track":"fuel_agnostic_control","classification":"NOT_RUN","native_simulation_executed":False,"matched_tct_control_executed":False,"claim_boundary":"EFIT is an experimental reconstruction, not an M3D-C1 initial state. Do not call template simulations shot-informed."}
try:
    row=next(iter(load_dataset("Sophelio/fusion-equilibrium-challenge","diii_d_train",split="train",streaming=True,trust_remote_code=False,revision="main",)))
    # Use row 1, which has 359 EFIT frames according to recorded intake.
    stream=iter(load_dataset("Sophelio/fusion-equilibrium-challenge","diii_d_train",split="train",streaming=True,trust_remote_code=False,revision="main"))
    next(stream); row=next(stream)
    t=np.asarray(row["efit_times"],dtype=float)
    psi=np.asarray(row["efit_psirz"],dtype=float)
    R=np.asarray(row["efit_grid_R"],dtype=float); Z=np.asarray(row["efit_grid_Z"],dtype=float)
    assert psi.shape==(len(t),65,65) and R.shape==(65,) and Z.shape==(65,)
    assert len(t)>=3 and np.all(np.isfinite(t)) and np.all(np.diff(t)>0)
    assert np.all(np.isfinite(psi)) and np.all(np.diff(R)>0) and np.all(np.diff(Z)>0)
    k=len(t)//2
    result.update({"classification":"EFIT_SHOT_FRAME_VERIFIED_NATIVE_HANDOFF_NOT_YET_VALIDATED","efit_frame_index":int(k),"efit_time_ms":float(t[k]),"psi_min":float(psi[k].min()),"psi_max":float(psi[k].max()),"grid_R_m":[float(R[0]),float(R[-1])],"grid_Z_m":[float(Z[0]),float(Z[-1])],"frames":len(t),"native_blocker":"Requires a validated DIII-D geometry, equilibrium and profile mapping into a solver-compatible M3D-C1 deck; existing template must not be passed off as shot-derived."})
    np.savez_compressed(out/"shot_0001_efit_frame.npz",psi=psi[k],R=R,Z=Z,time_ms=t[k])
except Exception as e:
    result.update({"classification":"EFIT_HANDOFF_PREFLIGHT_FAILED","error":repr(e)})
(out/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))

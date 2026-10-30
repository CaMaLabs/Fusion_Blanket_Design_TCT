#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Native jphi spatial balance: does a nominally neutral source redistribute observed current?"""
import datetime
import json
import math
import pathlib
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0, str(repo / "tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta

job = "20261029-129-native-current-drive-current-balance-audit"
parent = "20261029-128-native-current-drive-spatial-response-audit"
out = repo / "validation_runs/m3dc1_tct_native_current_balance_129"
native.OUT = out
native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_current_balance_129_runs")
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1,
    "job_id": job,
    "parent_result_job_id": parent,
    "classification": "M3DC1_NATIVE_CURRENT_DRIVE_CURRENT_BALANCE_UNRESOLVED",
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1",
    "shot_ids": [],
    "dt": 0.01,
    "steps": 3,
    "source_mode": 4,
    "gate_window": [0.0, 0.04],
    "amplitudes": [-0.005, 0.0, 0.005],
    "zero_equivalence_tolerance": 1e-12,
    "expected_parent_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Native M3D-C1 mesh-weighted jphi balance proxy, not a calibrated physical current integral or measured injected source. No shot handoff, segmented-electrode authority, causal TCT stabilization or p-B11 fidelity claim.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
try:
    if abs(native.DT - 0.01) > 1e-12:
        raise RuntimeError("DT_PREREQUISITE_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_parent_executable_sha256"]:
        raise RuntimeError("PARENT_EXECUTABLE_SHA_MISMATCH: source/build prerequisite changed")
    import h5py
    report["field_read_backend"] = "h5py_native_dataset"
    configs = (
        ("baseline", 0, 0.0), ("same_mode_zero", 4, 0.0),
        ("full_negative", 4, -0.005), ("full_positive", 4, 0.005),
    )
    dirs = {}
    for name, mode, amp in configs:
        d = native.write_input(name, mode, amp, 0, 0.0, 0.04, nmax_steps=3)
        print("[current-balance] running " + name, flush=True)
        native.execute(d)
        dirs[name] = d

    times = [float(row["time"]) for row in pta.c1ke(dirs["baseline"])]
    if len(times) != 4:
        raise RuntimeError("EXPECTED_FOUR_FRAMES")
    for name, d in dirs.items():
        ts = [float(row["time"]) for row in pta.c1ke(d)]
        if len(ts) != len(times) or any(abs(a-b)>1e-8 for a,b in zip(times,ts)):
            raise RuntimeError("TIME_GRID_MISMATCH: " + name)
    report["observed_time_samples"] = times

    def read_frame(d, frame):
        with h5py.File(d / ("time_%03d.h5" % frame), "r") as f:
            elems = f["/mesh/elements"][:]
            values = f["/fields/jphi"][:]
            mesh = [(float(e[4]),float(e[5]),max(0.0,float(e[2]))) for e in elems]
            field = [float(v[0]) for v in values]
        if len(mesh) != len(field) or not mesh or not all(math.isfinite(v) for v in field):
            raise RuntimeError("INVALID_MESH_OR_FIELD")
        return mesh,field

    report["frames"] = []
    max_zero = 0.0
    nonzero_response = False
    for frame,t in enumerate(times):
        data = {name:read_frame(d,frame) for name,d in dirs.items()}
        mesh,base = data["baseline"]
        for name,(other,vals) in data.items():
            if len(other)!=len(mesh) or any(abs(a-b)>1e-10 for x,y in zip(mesh,other) for a,b in zip(x,y)):
                raise RuntimeError("MESH_CORRESPONDENCE_FAILED: "+name)
        zero = data["same_mode_zero"][1]
        max_zero = max(max_zero,max(abs(a-b) for a,b in zip(base,zero)))
        idx = [i for i,(_,_,w) in enumerate(mesh) if w>0]
        if not idx:
            raise RuntimeError("NO_POSITIVE_MESH_WEIGHTS")
        weights = [mesh[i][2] for i in idx]
        def response(name):
            return [data[name][1][i]-zero[i] for i in idx]
        def integral(v):
            return sum(w*x for w,x in zip(weights,v))
        def abs_integral(v):
            return sum(w*abs(x) for w,x in zip(weights,v))
        pos = response("full_positive")
        neg = response("full_negative")
        frame_out = {
            "frame":frame,"time":t,"mesh_elements":len(mesh),
            "positive_weight_elements":len(idx),
            "mesh_weight_sum":sum(weights),
            "max_abs_zero_vs_baseline_jphi":max(abs(a-b) for a,b in zip(base,zero)),
            "odd_symmetry_residual_fraction":abs_integral([a+b for a,b in zip(pos,neg)])/max(abs_integral(pos)+abs_integral(neg),1e-300),
            "cases":{}
        }
        for name,v in (("full_negative",neg),("full_positive",pos)):
            signed=integral(v)
            absolute=abs_integral(v)
            positive=integral([max(x,0.0) for x in v])
            negative=integral([max(-x,0.0) for x in v])
            nonzero_response |= absolute>1e-12
            def centroid(sign):
                numerator=denominator=0.0
                for i,x,w in zip(idx,v,weights):
                    contribution=w*max(sign*x,0.0)
                    numerator+=contribution*mesh[i][1]
                    denominator+=contribution
                return numerator/denominator if denominator>1e-15 else None
            frame_out["cases"][name]={
                "max_abs_delta_jphi":max(map(abs,v)),
                "mesh_weighted_signed_delta_jphi":signed,
                "mesh_weighted_abs_delta_jphi":absolute,
                "positive_lobe_integral_proxy":positive,
                "negative_lobe_magnitude_proxy":negative,
                "cancellation_fraction":1.0-abs(signed)/absolute if absolute>1e-15 else None,
                "positive_lobe_z_centroid":centroid(1.0),
                "negative_lobe_z_centroid":centroid(-1.0),
            }
        report["frames"].append(frame_out)
    report["zero_equivalence"]={"max_abs_field_delta":max_zero,"pass":max_zero<=1e-12}
    report["field_response_observed"]=nonzero_response
    if not report["zero_equivalence"]["pass"]:
        report["classification"]="M3DC1_NATIVE_CURRENT_DRIVE_CURRENT_BALANCE_ZERO_EQUIVALENCE_FAILED"
    elif not nonzero_response:
        report["classification"]="M3DC1_NATIVE_CURRENT_DRIVE_CURRENT_BALANCE_NO_RESPONSE"
    else:
        report["classification"]="M3DC1_NATIVE_CURRENT_DRIVE_CURRENT_BALANCE_DIAGNOSTIC_COMPLETE"
    report["interpretation"]=(
        "Full positive-weight native mesh jphi delta balance, signed lobes and vertical centroids "
        "test whether the observed response resembles redistribution rather than merely a peak shift. "
        "Mesh element weight e[2] is a proxy, not a validated physical area/current quadrature; "
        "source-mode 4 subtracts its native int1-weighted mean at injection, but the resulting "
        "jphi field need not have zero mesh-weighted integral. No physical actuator calibration."
    )
except Exception as exc:
    report["pipeline_error"]=type(exc).__name__+": "+str(exc)
    report["classification"]="M3DC1_NATIVE_CURRENT_DRIVE_CURRENT_BALANCE_PIPELINE_BLOCKED"
path=out/"native_current_balance_summary.json"
tmp=path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
tmp.replace(path)
print(json.dumps(report,indent=2,sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

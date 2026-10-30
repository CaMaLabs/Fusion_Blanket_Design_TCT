#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Bounded native jphi balance sensitivity to axisymmetric R weighting.

This does not certify the HDF5 element weight as physical area or infer a
physical current integral. No solver equations or thresholds are changed.
"""
import datetime
import json
import math
import pathlib
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0, str(repo / "tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta

job = "20261029-130-native-current-drive-geometry-weight-sensitivity"
parent = "20261029-129-native-current-drive-current-balance-audit"
out = repo / "validation_runs/m3dc1_tct_native_geometry_weight_130"
native.OUT = out
native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs")
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1,
    "job_id": job,
    "parent_result_job_id": parent,
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1",
    "shot_ids": [],
    "classification": "M3DC1_NATIVE_CURRENT_DRIVE_GEOMETRY_WEIGHT_SENSITIVITY_UNRESOLVED",
    "expected_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "source_mode": 4, "amplitudes": [-0.005, 0.0, 0.005],
    "dt": 0.01, "steps": 3, "gate_window": [0.0, 0.04],
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Both e[2] and R*e[2] are uncalibrated mesh-weighted jphi response proxies. R weighting is an axisymmetric geometry sensitivity, NOT independently validated area/current quadrature. No physical current conservation, injected-current calibration, segmented-electrode authority, shot handoff, causal TCT stabilization, p-B11 fidelity or net-power claim.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    if abs(native.DT - 0.01) > 1e-12:
        raise RuntimeError("DT_PREREQUISITE_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_executable_sha256"]:
        raise RuntimeError("PARENT_EXECUTABLE_SHA_MISMATCH")
    import h5py
    cases = (("baseline",0,0.0), ("same_mode_zero",4,0.0),
             ("full_negative",4,-0.005), ("full_positive",4,0.005))
    dirs = {}
    for name, mode, amp in cases:
        d = native.write_input(name, mode, amp, 0, 0.0, 0.04, nmax_steps=3)
        print("[geometry-weight] running " + name, flush=True)
        native.execute(d)
        dirs[name] = d
    times = [float(row["time"]) for row in pta.c1ke(dirs["baseline"])]
    if len(times) != 4:
        raise RuntimeError("EXPECTED_FOUR_FRAMES")
    for name,d in dirs.items():
        t = [float(row["time"]) for row in pta.c1ke(d)]
        if len(t) != 4 or any(abs(a-b)>1e-8 for a,b in zip(t,times)):
            raise RuntimeError("TIME_GRID_MISMATCH: " + name)
    report["observed_time_samples"] = times

    def read(d,i):
        with h5py.File(d / ("time_%03d.h5" % i),"r") as f:
            e = f["/mesh/elements"][:]
            j = f["/fields/jphi"][:]
            if i == 0 and d == dirs["baseline"]:
                report["mesh_elements_shape"] = list(e.shape)
                report["mesh_element_attrs"] = {str(k):str(v)[:256] for k,v in f["/mesh/elements"].attrs.items()}
                report["mesh_group_keys"] = list(f["/mesh"].keys())
        if len(e) != len(j) or e.shape[1] < 6:
            raise RuntimeError("MESH_SCHEMA_MISMATCH")
        mesh = [(float(row[4]),float(row[5]),float(row[2])) for row in e]
        field = [float(row[0]) for row in j]
        if not all(math.isfinite(v) for row in mesh for v in row) or not all(math.isfinite(v) for v in field):
            raise RuntimeError("NONFINITE_MESH_OR_FIELD")
        return mesh,field

    report["frames"] = []
    max_zero = 0.0
    for i,t in enumerate(times):
        data = {name:read(d,i) for name,d in dirs.items()}
        mesh,baseline = data["baseline"]
        if not mesh or any(r <= 0.0 or w <= 0.0 for r,z,w in mesh):
            raise RuntimeError("NONPOSITIVE_RADIUS_OR_ELEMENT_WEIGHT")
        for name,(m,j) in data.items():
            if len(m) != len(mesh) or any(abs(a-b)>1e-10 for x,y in zip(mesh,m) for a,b in zip(x,y)):
                raise RuntimeError("MESH_CORRESPONDENCE_FAILED: "+name)
        zero = data["same_mode_zero"][1]
        max_zero = max(max_zero,max(abs(a-b) for a,b in zip(baseline,zero)))
        neg = [a-b for a,b in zip(data["full_negative"][1],zero)]
        pos = [a-b for a,b in zip(data["full_positive"][1],zero)]
        frame = {"frame":i,"time":t,"mesh_elements":len(mesh),"weighting":{}}
        for key,weights in (
            ("element_e2_proxy",[w for r,z,w in mesh]),
            ("axisymmetric_r_times_e2_proxy",[r*w for r,z,w in mesh]),
        ):
            entries = {}
            for name,v in (("full_negative",neg),("full_positive",pos)):
                signed = sum(w*x for w,x in zip(weights,v))
                absolute = sum(w*abs(x) for w,x in zip(weights,v))
                plus = sum(w*max(x,0.0) for w,x in zip(weights,v))
                minus = sum(w*max(-x,0.0) for w,x in zip(weights,v))
                entries[name] = {
                    "signed_proxy":signed,"absolute_proxy":absolute,
                    "positive_lobe_proxy":plus,"negative_lobe_proxy":minus,
                    "cancellation_fraction":1.0-abs(signed)/absolute if absolute>1e-15 else None
                }
            frame["weighting"][key] = entries
        frame["odd_symmetry_residual_fraction_e2"] = (
            sum(w*abs(a+b) for (_,_,w),a,b in zip(mesh,neg,pos)) /
            max(sum(w*(abs(a)+abs(b)) for (_,_,w),a,b in zip(mesh,neg,pos)),1e-300)
        )
        report["frames"].append(frame)
    report["zero_equivalence"] = {"max_abs_field_delta":max_zero,"pass":max_zero<=1e-12}
    if not report["zero_equivalence"]["pass"]:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_GEOMETRY_WEIGHT_ZERO_EQUIVALENCE_FAILED"
    else:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_GEOMETRY_WEIGHT_SENSITIVITY_DIAGNOSTIC_COMPLETE"
    report["interpretation"] = (
        "Independent re-run and per-frame comparison of native jphi response using "
        "both e[2] and R*e[2] positive weights tests whether opposing-lobe cancellation "
        "is robust to an axisymmetric geometry factor. These are NOT independently "
        "validated physical area, volume, toroidal-current or source int1 quadratures."
    )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_GEOMETRY_WEIGHT_PIPELINE_BLOCKED"
path = out / "native_geometry_weight_summary.json"
tmp = path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
tmp.replace(path)
print(json.dumps(report,indent=2,sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

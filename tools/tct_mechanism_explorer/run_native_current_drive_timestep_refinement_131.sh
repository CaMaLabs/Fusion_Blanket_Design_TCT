#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Matched dt-halving audit of normalized-native M3D-C1 jphi lobe balance.

Refines time discretization without modifying solver physics or the frozen
TCT gates. Mesh-weighted integrals remain uncalibrated response proxies.
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

job = "20261030-131-native-current-drive-timestep-refinement"
parent_id = "20261029-130-native-current-drive-geometry-weight-sensitivity"
out = repo / "validation_runs/m3dc1_tct_native_timestep_131"
native.OUT = out
native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_timestep_131_runs")
native.DT = 0.005
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job, "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "classification": "M3DC1_NATIVE_CURRENT_DRIVE_TIMESTEP_REFINEMENT_UNRESOLVED",
    "dt": 0.005, "parent_dt": 0.01, "steps": 6,
    "source_mode": 4, "amplitudes": [-0.005, 0.0, 0.005],
    "gate_window": [0.0, 0.04], "zero_equivalence_tolerance": 1e-12,
    "expected_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "expected_parent_summary_sha256": "9ee23732ec6a4976da647980155fc6228d3de6f687cfbf317aa1202e86ef693e",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Numerical time-step sensitivity of normalized-native M3D-C1 jphi response only. e[2] and R*e[2] are uncalibrated mesh-weighted proxies, not physical current quadrature. No calibrated current conservation, segmented-electrode authority, experimental shot handoff, causal TCT stabilization, p-B11 fidelity or net-power claim.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    parent_path = repo / "validation_runs/m3dc1_tct_native_geometry_weight_130/native_geometry_weight_summary.json"
    if not parent_path.is_file():
        raise RuntimeError("PARENT_SUMMARY_MISSING")
    if pta.sha256_file(parent_path) != report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_SHA_MISMATCH")
    parent = json.loads(parent_path.read_text())
    if parent.get("classification") != "M3DC1_NATIVE_CURRENT_DRIVE_GEOMETRY_WEIGHT_SENSITIVITY_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_CHANGED")
    if parent.get("zero_equivalence", {}).get("pass") is not True:
        raise RuntimeError("PARENT_ZERO_EQUIVALENCE_NOT_PASSED")
    if len(parent.get("frames", [])) != 4:
        raise RuntimeError("PARENT_FRAME_COUNT_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_executable_sha256"]:
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")
    import h5py
    cases = (("baseline", 0, 0.0), ("same_mode_zero", 4, 0.0),
             ("full_negative", 4, -0.005), ("full_positive", 4, 0.005))
    dirs = {}
    for name, mode, amp in cases:
        d = native.write_input(name, mode, amp, 0, 0.0, 0.04, nmax_steps=6)
        print("[timestep-refinement] running " + name, flush=True)
        native.execute(d)
        dirs[name] = d
    times = [float(row["time"]) for row in pta.c1ke(dirs["baseline"])]
    if len(times) != 7 or any(abs(t - 0.005*i) > 1e-8 for i, t in enumerate(times)):
        raise RuntimeError("REFINED_TIME_GRID_MISMATCH")
    for name, d in dirs.items():
        t = [float(row["time"]) for row in pta.c1ke(d)]
        if len(t) != 7 or any(abs(a-b) > 1e-8 for a,b in zip(t, times)):
            raise RuntimeError("CASE_TIME_GRID_MISMATCH: " + name)
    report["observed_time_samples"] = times

    def read_frame(d, i):
        with h5py.File(d / ("time_%03d.h5" % i), "r") as f:
            e = f["/mesh/elements"][:]
            j = f["/fields/jphi"][:]
        if e.ndim != 2 or e.shape[1] < 6 or len(e) != len(j):
            raise RuntimeError("MESH_SCHEMA_MISMATCH")
        mesh = [(float(row[4]), float(row[5]), float(row[2])) for row in e]
        field = [float(row[0]) for row in j]
        if not mesh or any(not all(math.isfinite(v) for v in row) or row[0] <= 0 or row[2] <= 0 for row in mesh):
            raise RuntimeError("INVALID_MESH_WEIGHTS")
        if not all(math.isfinite(v) for v in field):
            raise RuntimeError("NONFINITE_JPHI")
        return mesh, field

    report["frames"] = []
    max_zero = 0.0
    for i, t in enumerate(times):
        data = {name: read_frame(d, i) for name, d in dirs.items()}
        mesh, baseline = data["baseline"]
        if len(mesh) != 1004:
            raise RuntimeError("MESH_SIZE_CHANGED")
        for name, (m, j) in data.items():
            if len(m) != len(mesh) or any(abs(a-b) > 1e-10 for x,y in zip(mesh,m) for a,b in zip(x,y)):
                raise RuntimeError("MESH_CORRESPONDENCE_FAILED: " + name)
        zero = data["same_mode_zero"][1]
        max_zero = max(max_zero, max(abs(a-b) for a,b in zip(baseline, zero)))
        neg = [a-b for a,b in zip(data["full_negative"][1], zero)]
        pos = [a-b for a,b in zip(data["full_positive"][1], zero)]
        frame = {"frame": i, "time": t, "mesh_elements": len(mesh), "weighting": {}}
        for key, weights in (
            ("element_e2_proxy", [w for r,z,w in mesh]),
            ("axisymmetric_r_times_e2_proxy", [r*w for r,z,w in mesh])
        ):
            vals = {}
            for name, v in (("full_negative", neg), ("full_positive", pos)):
                signed = math.fsum(w*x for w,x in zip(weights,v))
                absolute = math.fsum(w*abs(x) for w,x in zip(weights,v))
                vals[name] = {
                    "signed_proxy": signed, "absolute_proxy": absolute,
                    "positive_lobe_proxy": math.fsum(w*max(x,0) for w,x in zip(weights,v)),
                    "negative_lobe_proxy": math.fsum(w*max(-x,0) for w,x in zip(weights,v)),
                    "cancellation_fraction": 1-abs(signed)/absolute if absolute > 1e-15 else None
                }
            frame["weighting"][key] = vals
        denom = math.fsum(w*(abs(a)+abs(b)) for (_,_,w),a,b in zip(mesh,neg,pos))
        frame["odd_symmetry_residual_fraction_e2"] = (
            math.fsum(w*abs(a+b) for (_,_,w),a,b in zip(mesh,neg,pos)) / max(denom,1e-300)
        )
        if i % 2 == 0:
            coarse = parent["frames"][i//2]
            if abs(float(coarse["time"])-t) > 1e-8:
                raise RuntimeError("PARENT_TIME_ALIGNMENT_FAILED")
            comp = {"coarse_frame": i//2, "odd_symmetry_residual_delta_e2":
                    frame["odd_symmetry_residual_fraction_e2"] - coarse["odd_symmetry_residual_fraction_e2"],
                    "weighting": {}}
            for key, values in frame["weighting"].items():
                comp["weighting"][key] = {}
                for name, fine in values.items():
                    old = coarse["weighting"][key][name]
                    comp["weighting"][key][name] = {
                        "cancellation_fraction_delta": (
                            fine["cancellation_fraction"] - old["cancellation_fraction"]
                            if fine["cancellation_fraction"] is not None and old["cancellation_fraction"] is not None
                            else None
                        ),
                        "signed_proxy_delta": fine["signed_proxy"]-old["signed_proxy"],
                        "absolute_proxy_delta": fine["absolute_proxy"]-old["absolute_proxy"]
                    }
            frame["comparison_to_parent_dt001"] = comp
        report["frames"].append(frame)
    report["zero_equivalence"] = {"max_abs_field_delta": max_zero, "pass": max_zero <= 1e-12}
    report["classification"] = (
        "M3DC1_NATIVE_CURRENT_DRIVE_TIMESTEP_REFINEMENT_DIAGNOSTIC_COMPLETE"
        if report["zero_equivalence"]["pass"]
        else "M3DC1_NATIVE_CURRENT_DRIVE_TIMESTEP_REFINEMENT_ZERO_EQUIVALENCE_FAILED"
    )
    report["interpretation"] = "Matched dt=0.005 native reruns compared at t=0,0.01,0.02,0.03 with the verified dt=0.01 parent. Report signed-lobe cancellation and odd-symmetry sensitivity without assuming numerical convergence or physical current conservation. No frozen physics thresholds changed."
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_TIMESTEP_REFINEMENT_PIPELINE_BLOCKED"
path = out / "timestep_refinement_summary.json"
tmp = path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(path)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

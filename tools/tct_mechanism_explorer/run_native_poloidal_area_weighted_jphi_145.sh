#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Re-evaluate saved normalized-native M3D-C1 jphi response with validated 2-D triangle areas.
This is a poloidal area-weighted diagnostic, NOT a physical toroidal-current integral.
No solver execution, source modification, threshold change or controller claim.
"""
import datetime
import hashlib
import json
import math
import pathlib
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
src = pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
job = "20261030-145-native-poloidal-area-weighted-jphi-response"
parent_id = "20261030-144-native-mesh-poloidal-area-crosscheck"
parent_path = repo / "validation_runs/m3dc1_tct_native_geometry_144/native_mesh_poloidal_area_summary.json"
parent_sha = "3b7224526ad316e172f0fd3a054355f631117609d02f781bf984177c11317501"
out = repo / "validation_runs/m3dc1_tct_native_area_jphi_145"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job, "parent_result_job_id": parent_id,
    "expected_parent_summary_sha256": parent_sha,
    "classification": "M3DC1_NATIVE_POLOIDAL_AREA_WEIGHTED_JPHI_RESPONSE_UNRESOLVED",
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "physics_solver_runs": 0, "source_mode": 4,
    "saved_run_origin_job_id": "20261029-130-native-current-drive-geometry-weight-sensitivity",
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "physical_current_quadrature_validated": False,
    "calibrated_physical_width_validated": False,
    "causal_segmented_controller_authority_validated": False,
    "temporal_convergence_validated": False,
    "pb11_fidelity_validated": False,
    "claim_boundary": "Saved normalized-native 2-D M3D-C1 open-loop jphi field with independently crosschecked poloidal triangle area. Area*jphi and R*area*jphi are diagnostics only, not native int1, toroidal current, calibrated injected current, 3-D quadrature, causal segmented TCT, shot handoff, p-B11, ignition or net power.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def integrate(w, x):
    signed = math.fsum(a*b for a,b in zip(w,x))
    absolute = math.fsum(a*abs(b) for a,b in zip(w,x))
    plus = math.fsum(a*max(b,0.0) for a,b in zip(w,x))
    minus = math.fsum(a*max(-b,0.0) for a,b in zip(w,x))
    return {"signed": signed, "absolute": absolute, "positive_lobe": plus,
            "negative_lobe_magnitude": minus,
            "cancellation_fraction": 1.0-abs(signed)/absolute if absolute>1e-15 else None}
try:
    if not parent_path.is_file() or digest(parent_path) != parent_sha:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("job_id") != parent_id or parent.get("classification") != "M3DC1_NATIVE_MESH_POLOIDAL_AREA_CROSSCHECK_COMPLETE":
        raise RuntimeError("PARENT_ID_OR_CLASSIFICATION_CHANGED")
    if parent.get("analytic_poloidal_geometry_crosscheck_passed") is not True or parent.get("hdf5_e2_is_area") is not False:
        raise RuntimeError("PARENT_GEOMETRY_GATE_CHANGED")
    for source_name, expected in parent["native_source_sha256"].items():
        p = pathlib.Path("/home/ubuntu/M3DC1-official") / source_name
        if not p.is_file() or digest(p) != expected:
            raise RuntimeError("NATIVE_SOURCE_CHANGED:" + source_name)
    import h5py
    root = pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs")
    cases = ("baseline", "same_mode_zero", "full_negative", "full_positive")
    frames = (0,1,2,3)
    required = [root / c / ("time_%03d.h5" % frame) for c in cases for frame in frames]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        report["classification"] = "M3DC1_NATIVE_POLOIDAL_AREA_WEIGHTED_JPHI_DATA_ACCESS_BLOCKED"
        report["missing_saved_hdf5_count"] = len(missing)
        report["missing_saved_hdf5_paths"] = missing
        report["interpretation"] = "Saved run HDF5 is unavailable; this is a data-access prerequisite, not a negative scientific result."
    else:
        report["frames"] = []
        max_zero = 0.0
        sign_flips = 0
        max_cancellation_shift = 0.0
        for frame in frames:
            data = {}
            for case in cases:
                with h5py.File(root / case / ("time_%03d.h5" % frame), "r") as h:
                    e = h["/mesh/elements"][:]
                    j = h["/fields/jphi"][:]
                    is3d = int(h["/mesh"].attrs.get("3D",0))
                if e.ndim!=2 or e.shape!=(1004,8) or j.ndim!=2 or j.shape[0]!=1004 or is3d:
                    raise ValueError("UNEXPECTED_NATIVE_2D_HDF5_SCHEMA:" + case)
                mesh = [tuple(float(v) for v in row[:6]) for row in e]
                vals = [float(row[0]) for row in j]
                if not all(math.isfinite(v) for row in mesh for v in row) or not all(map(math.isfinite,vals)):
                    raise ValueError("NONFINITE_NATIVE_FIELD")
                data[case] = (mesh, vals)
            mesh, baseline = data["baseline"]
            if any(m!=mesh for m,_ in data.values()):
                raise ValueError("MESH_CORRESPONDENCE_FAILED")
            a,b,c,theta,R,Z = zip(*mesh)
            if any(aa+bb<=0 or cc<=0 or rr<=0 for aa,bb,cc,rr in zip(a,b,c,R)):
                raise ValueError("DEGENERATE_NATIVE_TRIANGLE")
            area = [0.5*(aa+bb)*cc for aa,bb,cc in zip(a,b,c)]
            weights = {
                "old_e2_altitude_proxy": list(c),
                "old_R_e2_proxy": [rr*cc for rr,cc in zip(R,c)],
                "crosschecked_2d_poloidal_area": area,
                "R_times_2d_poloidal_area_diagnostic": [rr*ar for rr,ar in zip(R,area)]
            }
            zero = data["same_mode_zero"][1]
            max_zero = max(max_zero, max(abs(v-z) for v,z in zip(baseline,zero)))
            row = {"frame": frame, "time": frame*0.01, "mesh_elements":len(mesh),
                   "poloidal_area_sum":math.fsum(area), "cases":{}}
            for case in ("full_negative","full_positive"):
                delta = [v-z for v,z in zip(data[case][1],zero)]
                metrics = {name:integrate(w,delta) for name,w in weights.items()}
                old = metrics["old_e2_altitude_proxy"]
                corrected = metrics["crosschecked_2d_poloidal_area"]
                if old["signed"]*corrected["signed"] < 0:
                    sign_flips += 1
                if old["cancellation_fraction"] is not None and corrected["cancellation_fraction"] is not None:
                    max_cancellation_shift = max(max_cancellation_shift,
                        abs(old["cancellation_fraction"]-corrected["cancellation_fraction"]))
                row["cases"][case] = {"max_abs_delta_jphi":max(map(abs,delta)),
                                      "weighting":metrics}
            report["frames"].append(row)
        report["zero_equivalence"] = {"max_abs_field_delta":max_zero,
                                       "pass":max_zero<=1e-12}
        report["e2_vs_poloidal_area_signed_response_sign_flip_count"] = sign_flips
        report["max_e2_vs_area_cancellation_fraction_shift"] = max_cancellation_shift
        report["classification"] = (
            "M3DC1_NATIVE_POLOIDAL_AREA_WEIGHTED_JPHI_RESPONSE_DIAGNOSTIC_COMPLETE"
            if report["zero_equivalence"]["pass"] else
            "M3DC1_NATIVE_POLOIDAL_AREA_WEIGHTED_JPHI_ZERO_EQUIVALENCE_FAILED"
        )
        report["interpretation"] = (
            "Replace e[2] altitude weighting with independently crosschecked 2-D triangle area "
            "on existing signed-command jphi fields. Compare signed lobes and cancellation with "
            "the old proxies; neither area nor R*area alone validates native int1/toroidal current."
        )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_POLOIDAL_AREA_WEIGHTED_JPHI_PIPELINE_BLOCKED"
target = out / "poloidal_area_weighted_jphi_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

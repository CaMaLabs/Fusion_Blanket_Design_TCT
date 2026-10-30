#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Test whether unforced native M3D-C1 jphi itself changes across the three dt levels.

This is a baseline diagnostic, not a new current-drive controller or a convergence claim.
"""
import datetime
import json
import math
import pathlib
import sys

import h5py
import numpy as np

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0, str(repo / "tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta

job_id = "20261030-137-native-current-drive-unforced-baseline-dt-audit"
parent_id = "20261030-136-native-current-drive-fixed-dt-repeatability"
out = repo / "validation_runs/m3dc1_tct_native_unforced_dt_137"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1,
    "job_id": job_id,
    "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1",
    "shot_ids": [],
    "classification": "M3DC1_NATIVE_UNFORCED_BASELINE_DT_SENSITIVITY_UNRESOLVED",
    "dt_sequence": [0.0025, 0.00125, 0.000625],
    "matched_times": [0.01, 0.02, 0.03],
    "source_mode": 4,
    "source_gate": [0.0, 0.04],
    "source_amplitude": 0.0,
    "zero_equivalence_tolerance": 1e-12,
    "expected_parent_summary_sha256": "763de278fcb2a2cab22830c15ebc5c03feffb114894241b17e378270add8c89a",
    "expected_executable_sha256": "8282c940fe1692b3c40ed6d7ba4b56e96f7197ac0ea2b11cef109969dcb5f0ec",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Three-level unforced baseline jphi field sensitivity in normalized-native M3D-C1 only. No claim of numerical convergence, physical current conservation, segmented TCT controller authority, calibrated experimental shot handoff, p-B11 fidelity, ignition or reactor net power. e[2] is an uncalibrated mesh weight.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
try:
    parent_path = repo / "validation_runs/m3dc1_tct_native_repeatability_136/fixed_dt_repeatability_summary.json"
    if not parent_path.is_file() or pta.sha256_file(parent_path) != report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("classification") != "M3DC1_NATIVE_CURRENT_DRIVE_FIXED_DT_REPEATABILITY_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_CHANGED")
    if parent.get("zero_equivalence", {}).get("pass") is not True:
        raise RuntimeError("PARENT_ZERO_EQUIVALENCE_NOT_PASSED")
    if parent.get("fixed_dt_repeatability", {}).get("pass") is not True:
        raise RuntimeError("PARENT_FIXED_DT_REPEATABILITY_NOT_PASSED")
    if parent.get("temporal_convergence_established") is not False:
        raise RuntimeError("PARENT_TEMPORAL_CONVERGENCE_STATUS_CHANGED")

    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    if report["executable_sha256"] != report["expected_executable_sha256"]:
        raise RuntimeError("NATIVE_EXECUTABLE_SHA_MISMATCH")

    levels = {}
    for label, dt, steps in (("coarse", 0.0025, 12), ("medium", 0.00125, 24), ("fine", 0.000625, 48)):
        native.DT = dt
        native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_unforced_dt_137_" + label)
        native.OUT = out
        dirs = {}
        for name, mode in (("baseline", 0), ("same_mode_zero", 4)):
            d = native.write_input(name, mode, 0.0, 0, 0.0, 0.04, nmax_steps=steps)
            print("[unforced-baseline-dt] " + label + " " + name, flush=True)
            native.execute(d)
            dirs[name] = d
        grids = {name: [float(row["time"]) for row in pta.c1ke(d)] for name, d in dirs.items()}
        expected = [i * dt for i in range(steps + 1)]
        if any(len(g) != len(expected) or any(abs(a-b) > 1e-8 for a,b in zip(g,expected))
               for g in grids.values()):
            raise RuntimeError("TIME_GRID_MISMATCH_" + label)
        levels[label] = {"dt": dt, "dirs": dirs, "times": grids["baseline"]}

    def read(d, frame):
        with h5py.File(d / ("time_%03d.h5" % frame), "r") as h:
            e = np.asarray(h["/mesh/elements"][:], dtype=float)
            j = np.asarray(h["/fields/jphi"][:], dtype=float)
        if e.ndim != 2 or e.shape[1] < 6 or j.ndim != 2 or len(e) != len(j) or len(e) != 1004:
            raise RuntimeError("MESH_OR_FIELD_SCHEMA_MISMATCH")
        mesh, field = e[:,[4,5,2]], j[:,0]
        if not np.isfinite(mesh).all() or not np.isfinite(field).all() or np.any(mesh[:,2] <= 0):
            raise RuntimeError("NONFINITE_OR_INVALID_MESH_FIELD")
        return mesh, field

    report["matched_frames"] = []
    zero_max = 0.0
    for time in report["matched_times"]:
        pairs = {}
        for label, level in levels.items():
            hits = [i for i,t in enumerate(level["times"]) if abs(t-time) < 1e-8]
            if len(hits) != 1:
                raise RuntimeError("MATCHED_FRAME_NOT_FOUND_" + label)
            mesh, baseline = read(level["dirs"]["baseline"], hits[0])
            zero_mesh, zero = read(level["dirs"]["same_mode_zero"], hits[0])
            if not np.allclose(mesh, zero_mesh, atol=1e-10, rtol=0):
                raise RuntimeError("ZERO_CASE_MESH_MISMATCH_" + label)
            zero_max = max(zero_max, float(np.max(np.abs(zero-baseline))))
            pairs[label] = {"mesh": mesh, "field": baseline}
        coarse, medium, fine = (pairs[label] for label in ("coarse","medium","fine"))
        if not (np.allclose(coarse["mesh"],medium["mesh"],atol=1e-10,rtol=0)
                and np.allclose(medium["mesh"],fine["mesh"],atol=1e-10,rtol=0)):
            raise RuntimeError("CROSS_DT_MESH_MISMATCH")
        w = fine["mesh"][:,2]
        a,b,c = (pairs[label]["field"] for label in ("coarse","medium","fine"))
        def norm(x):
            return math.sqrt(float(np.sum(w*x*x)))
        def cosine(x,y):
            return float(np.sum(w*x*y)) / max(norm(x)*norm(y),1e-300)
        cm, mf = b-a, c-b
        ncm, nmf, nfine = norm(cm), norm(mf), norm(c)
        report["matched_frames"].append({
            "time": time, "mesh_elements": len(w),
            "coarse_weighted_l2": norm(a),
            "medium_weighted_l2": norm(b),
            "fine_weighted_l2": nfine,
            "coarse_medium_difference_weighted_l2": ncm,
            "medium_fine_difference_weighted_l2": nmf,
            "coarse_medium_relative_to_medium_l2": ncm/max(norm(b),1e-300),
            "medium_fine_relative_to_fine_l2": nmf/max(nfine,1e-300),
            "coarse_medium_difference_linf": float(np.max(np.abs(cm))),
            "medium_fine_difference_linf": float(np.max(np.abs(mf))),
            "coarse_medium_weighted_cosine": cosine(a,b),
            "medium_fine_weighted_cosine": cosine(b,c),
            "difference_ratio_coarse_medium_to_medium_fine": ncm/nmf if nmf > 1e-300 else None,
            "empirical_order_log2_ratio": math.log2(ncm/nmf) if ncm > 1e-300 and nmf > 1e-300 else None
        })
    report["zero_equivalence"] = {"max_abs_field_delta": zero_max, "pass": zero_max <= 1e-12}
    report["temporal_convergence_established"] = False
    report["classification"] = (
        "M3DC1_NATIVE_UNFORCED_BASELINE_DT_SENSITIVITY_DIAGNOSTIC_COMPLETE"
        if report["zero_equivalence"]["pass"]
        else "M3DC1_NATIVE_UNFORCED_BASELINE_DT_SENSITIVITY_ZERO_EQUIVALENCE_FAILED")
    report["interpretation"] = (
        "Unforced baseline jphi three-level field differences isolate background numerical dt sensitivity from commanded-response differences. "
        "The two are not interchangeable; fieldwise agreement or disagreement here alone cannot prove causal TCT stabilization or convergence.")
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_UNFORCED_BASELINE_DT_SENSITIVITY_PIPELINE_BLOCKED"
target = out / "unforced_baseline_dt_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

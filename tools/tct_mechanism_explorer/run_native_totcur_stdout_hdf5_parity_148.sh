#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Bounded saved-run native-current stdout/HDF5 value and time-axis audit.
No M3D-C1 solver calls. Value agreement does not establish native int2
operator parity, physical units, current conservation, or causal TCT.
"""
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
native = pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
job_id = "20261030-148-native-totcur-stdout-hdf5-parity"
parent_id = "20261030-147-native-totcur-saved-observable"
parent_path = repo / "validation_runs/m3dc1_tct_native_totcur_147/native_totcur_saved_observable_summary.json"
parent_sha = "953fc7af5e9682f58ce814a967c4a4c76139bc7420271ee9e29525bfd459df6c"
diagnostics_sha = "0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655"
out = repo / "validation_runs/m3dc1_tct_native_totcur_parity_148"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job_id, "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "classification": "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_PARITY_UNRESOLVED",
    "physics_solver_runs": 0, "shot_ids": [], "source_mode": 4,
    "saved_run_origin_job_id": "20261029-130-native-current-drive-geometry-weight-sensitivity",
    "expected_parent_summary_sha256": parent_sha,
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "native_int2_operator_parity_validated": False,
    "physical_current_calibrated": False,
    "temporal_convergence_validated": False,
    "causal_segmented_controller_authority_validated": False,
    "shot_handoff_validated": False, "pb11_fidelity_validated": False,
    "ignition_or_net_power_validated": False,
    "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "claim_boundary": "Saved normalized-native 2-D M3D-C1 stdout/HDF5 current diagnostic value parity only. A same-length C1ke time series is not a proven HDF5 diagnostic time axis; no native int2 parity, calibrated current conservation, causal controller or p-B11/net-power claim."
}
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def numeric(x):
    try:
        y = float(x)
        return y if math.isfinite(y) else None
    except (ValueError, TypeError, OverflowError):
        return None
try:
    import h5py
    import numpy as np
    if not parent_path.is_file() or sha(parent_path) != parent_sha:
        report["classification"] = "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_PARENT_BLOCKED"
        report["prerequisite_blocker"] = "PARENT_SUMMARY_MISSING_OR_CHANGED"
    elif not (native / "diagnostics.f90").is_file() or sha(native / "diagnostics.f90") != diagnostics_sha:
        report["classification"] = "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_SOURCE_BLOCKED"
        report["prerequisite_blocker"] = "DIAGNOSTICS_SOURCE_MISSING_OR_CHANGED"
    else:
        parent = json.loads(parent_path.read_text())
        if (parent.get("job_id") != parent_id
                or parent.get("classification") != "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_PRESENT_TIMING_UNVERIFIED"
                or parent.get("native_int2_parity_validated") is not False
                or parent.get("candidate_zero_minus_baseline") != 0.0):
            report["classification"] = "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_PARENT_BLOCKED"
            report["prerequisite_blocker"] = "PARENT_SCIENTIFIC_GATE_CHANGED"
        else:
            report["diagnostics_source_sha256"] = diagnostics_sha
            root = pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs")
            cases = ("baseline", "same_mode_zero", "full_negative", "full_positive")
            report["cases"] = {}
            missing = []
            all_parity = True
            all_c1ke = True
            all_time_axes = True
            for case in cases:
                d = root / case
                h5_path, stdout_path, c1ke_path = (d / "C1.h5", d / "C1stdout", d / "C1ke")
                row = {"directory": str(d)}
                for path in (h5_path, stdout_path, c1ke_path):
                    if not path.is_file():
                        missing.append(str(path))
                if any(not p.is_file() for p in (h5_path, stdout_path, c1ke_path)):
                    report["cases"][case] = row
                    continue
                row["hdf5_sha256"] = sha(h5_path)
                row["stdout_sha256"] = sha(stdout_path)
                row["c1ke_sha256"] = sha(c1ke_path)
                lines = [s.split() for s in c1ke_path.read_text(errors="replace").splitlines() if s.strip()]
                c1ke_times = [numeric(s[1]) if len(s) > 1 else None for s in lines]
                row["c1ke_times"] = c1ke_times
                if any(t is None for t in c1ke_times):
                    all_c1ke = False
                pattern = re.compile(r"Toroidal current\s*=\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][+-]?\d+)?)", re.I)
                stdout_values = [numeric(m.group(1).replace("D", "E").replace("d", "e"))
                                 for m in pattern.finditer(stdout_path.read_text(errors="replace"))]
                with h5py.File(h5_path, "r") as h:
                    if "scalars/toroidal_current" not in h:
                        missing.append(str(h5_path) + "::scalars/toroidal_current")
                        report["cases"][case] = row
                        continue
                    ds = h["scalars/toroidal_current"]
                    arr = np.asarray(ds[()]).ravel()
                    h5_values = [numeric(v) for v in arr]
                    candidate_axes = {}
                    def visitor(name, obj):
                        if not isinstance(obj, h5py.Dataset):
                            return
                        leaf = name.rsplit("/", 1)[-1].lower()
                        if leaf not in ("time", "times", "t", "simulation_time", "sim_time", "time_steps", "timesteps"):
                            return
                        if obj.ndim != 1 or obj.size != len(h5_values) or obj.size > 1000:
                            return
                        v = [numeric(x) for x in np.asarray(obj[()]).ravel()]
                        if all(x is not None for x in v):
                            candidate_axes[name] = v
                    h.visititems(visitor)
                n = len(h5_values)
                row["hdf5_dtype"] = str(arr.dtype)
                row["hdf5_values"] = h5_values
                row["stdout_values"] = stdout_values
                row["hdf5_scalar_time_candidates"] = candidate_axes
                row["count_parity"] = n == len(stdout_values) == len(c1ke_times)
                if row["count_parity"] and all(x is not None for x in h5_values + stdout_values):
                    errors = [abs(a - b) for a, b in zip(h5_values, stdout_values)]
                    tolerances = [max(2 * float(abs(np.spacing(np.float32(a)))), 1e-10)
                                  for a in h5_values]
                    row["max_abs_stdout_hdf5_error"] = max(errors, default=0.0)
                    row["max_error_to_tolerance_ratio"] = max((e/t for e, t in zip(errors, tolerances)), default=0.0)
                    row["stdout_hdf5_value_parity"] = all(e <= t for e, t in zip(errors, tolerances))
                else:
                    row["stdout_hdf5_value_parity"] = False
                row["explicit_hdf5_time_axis_matches_c1ke"] = [
                    name for name, v in candidate_axes.items()
                    if all(t is not None and abs(t - x) <= 1e-8 for t, x in zip(c1ke_times, v))
                ]
                all_time_axes &= bool(row["explicit_hdf5_time_axis_matches_c1ke"])
                all_parity &= row["stdout_hdf5_value_parity"]
                report["cases"][case] = row
            report["missing_saved_files"] = missing
            report["all_stdout_hdf5_value_parity"] = all_parity and not missing
            report["all_c1ke_times_parseable"] = all_c1ke
            report["all_explicit_hdf5_time_axes_match_c1ke"] = all_time_axes and not missing
            report["hdf5_terminal_time_alignment_verified"] = all_time_axes and all_c1ke and not missing
            if missing:
                report["classification"] = "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_DATA_ACCESS_BLOCKED"
                report["prerequisite_blocker"] = "MISSING_SAVED_NATIVE_RUN_FILES_OR_DATASETS"
            elif not all_parity:
                report["classification"] = "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_VALUE_PARITY_NOT_ESTABLISHED"
            elif all_time_axes and all_c1ke:
                report["classification"] = "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_VALUE_AND_TIME_AXIS_PARITY_COMPLETE"
            else:
                report["classification"] = "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_VALUE_PARITY_TIMING_UNVERIFIED"
            if all_parity and not missing:
                a = report["cases"]["baseline"]["hdf5_values"]
                z = report["cases"]["same_mode_zero"]["hdf5_values"]
                report["zero_source_max_abs_native_diagnostic_delta"] = max(abs(x-y) for x, y in zip(a, z))
            report["interpretation"] = (
                "This is a value-level cross-check of native saved current against stdout using float32 ULP-aware tolerances. "
                "C1ke count agreement alone cannot prove scalar diagnostic time alignment; only explicit HDF5 time-axis matching is marked as such. "
                "No native int2 operator parity, physical-unit calibration, conservation, controller-in-loop or p-B11 claims."
            )
except Exception as exc:
    report["classification"] = "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_PIPELINE_BLOCKED"
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
target = out / "native_totcur_stdout_hdf5_parity_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

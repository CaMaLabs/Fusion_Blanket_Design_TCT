#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Bounded native totcur availability/parity preflight using saved runs only.

No solver execution or physics changes. A named native diagnostic is not
automatically a calibrated physical-current measurement.
"""
import datetime
import hashlib
import json
import math
import pathlib
import re
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
native = pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
job = "20261030-147-native-totcur-saved-observable"
parent_id = "20261030-146-native-current-diagnostic-lineage"
parent_path = repo / "validation_runs/m3dc1_tct_native_current_lineage_146/native_current_diagnostic_lineage_summary.json"
parent_sha = "437d17c6fce97bb9e32c181b59c62a5cda99db67cd17e9c51dfa358cd94d4124"
diag_sha = "0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655"
out = repo / "validation_runs/m3dc1_tct_native_totcur_147"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job, "parent_result_job_id": parent_id,
    "expected_parent_summary_sha256": parent_sha,
    "classification": "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_UNRESOLVED",
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "physics_solver_runs": 0, "source_mode": 4,
    "saved_run_origin_job_id": "20261029-130-native-current-drive-geometry-weight-sensitivity",
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "native_int2_parity_validated": False, "physical_current_calibrated": False,
    "causal_segmented_controller_authority_validated": False,
    "temporal_convergence_validated": False, "shot_handoff_validated": False,
    "pb11_fidelity_validated": False,
    "claim_boundary": "Saved normalized-native 2-D M3D-C1 native totcur availability and time-alignment preflight only; no native int2 parity unless directly matched, no calibrated physical current, controller-in-loop TCT, p-B11, ignition or net power.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def valid_number(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError, OverflowError):
        return None
def h5_current_inventory(p):
    import h5py
    found = []
    exact = []
    names = {"totcur", "total_toroidal_current", "toroidal_current", "total_current", "plasma_current"}
    with h5py.File(p, "r") as h:
        def visit(name, obj):
            if not isinstance(obj, h5py.Dataset):
                return
            leaf = name.rsplit("/", 1)[-1].lower().replace("-", "_")
            if re.search(r"totcur|toroidal.*current|total.*current|plasma.*current", name, re.I):
                row = {"path": name, "shape": list(obj.shape), "dtype": str(obj.dtype)}
                found.append(row)
                if leaf in names and obj.size <= 10000:
                    import numpy as np
                    arr = np.asarray(obj[()]).ravel()
                    if arr.size and arr.dtype.kind in "fiu":
                        values = [valid_number(v) for v in arr]
                        if all(v is not None for v in values):
                            exact.append({**row, "values": values[-4:], "count": len(values)})
        h.visititems(visit)
    return found[:40], exact[:20]
try:
    if not parent_path.is_file() or sha(parent_path) != parent_sha:
        report["classification"] = "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_PARENT_BLOCKED"
        report["prerequisite_blocker"] = "PARENT_SUMMARY_MISSING_OR_CHANGED"
    else:
        parent = json.loads(parent_path.read_text())
        if (parent.get("job_id") != parent_id
                or parent.get("classification") != "M3DC1_NATIVE_CURRENT_DIAGNOSTIC_LINEAGE_COMPLETE"
                or parent.get("native_int2_physical_current_parity_validated") is not False
                or parent.get("parent_zero_max_abs_field_delta") != 0.0):
            report["classification"] = "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_PARENT_BLOCKED"
            report["prerequisite_blocker"] = "PARENT_SCIENTIFIC_GATE_CHANGED"
        elif not (native / "diagnostics.f90").is_file() or sha(native / "diagnostics.f90") != diag_sha:
            report["classification"] = "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_SOURCE_BLOCKED"
            report["prerequisite_blocker"] = "NATIVE_DIAGNOSTICS_SOURCE_MISSING_OR_CHANGED"
        else:
            report["diagnostics_source_sha256"] = diag_sha
            root = pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs")
            cases = ("baseline", "same_mode_zero", "full_negative", "full_positive")
            report["cases"] = {}
            missing = []
            for case in cases:
                d = root / case
                h5 = d / "C1.h5"
                c1ke = d / "C1ke"
                stdout = d / "C1stdout"
                row = {"directory": str(d), "native_totcur_dataset_candidates": [],
                       "native_totcur_exact_datasets": [], "stdout_current_lines": []}
                if not h5.is_file():
                    missing.append(str(h5))
                else:
                    row["c1_h5_size_bytes"] = h5.stat().st_size
                    row["native_totcur_dataset_candidates"], row["native_totcur_exact_datasets"] = h5_current_inventory(h5)
                if c1ke.is_file():
                    row["c1ke_sha256"] = sha(c1ke)
                    lines = [s.split() for s in c1ke.read_text(errors="replace").splitlines() if s.strip()]
                    row["c1ke_frame_count"] = len(lines)
                    row["c1ke_final_time"] = valid_number(lines[-1][1]) if lines and len(lines[-1]) > 1 else None
                else:
                    missing.append(str(c1ke))
                if stdout.is_file():
                    row["stdout_sha256"] = sha(stdout)
                    row["stdout_current_lines"] = [s.strip()[:240] for s in stdout.read_text(errors="replace").splitlines()
                                                   if re.search(r"\btotcur\b|toroidal current|total plasma current", s, re.I)][:15]
                report["cases"][case] = row
            report["missing_saved_files"] = missing
            if missing:
                report["classification"] = "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_DATA_ACCESS_BLOCKED"
                report["prerequisite_blocker"] = "SAVED_NATIVE_RUN_FILES_MISSING"
            else:
                times = [report["cases"][c].get("c1ke_final_time") for c in cases]
                report["final_c1ke_times"] = times
                report["matched_final_c1ke_time"] = (all(t is not None for t in times)
                    and max(times) - min(times) <= 1e-8)
                matches = {c: report["cases"][c]["native_totcur_exact_datasets"] for c in cases}
                common = set.intersection(*(set(x["path"] for x in matches[c]) for c in cases))
                report["common_exact_native_totcur_datasets"] = sorted(common)
                if not common:
                    report["classification"] = "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_UNAVAILABLE"
                    report["prerequisite_blocker"] = "NO_MATCHED_NATIVE_TOTCUR_HDF5_DATASET"
                else:
                    chosen = sorted(common)[0]
                    vals = {c: next(x for x in matches[c] if x["path"] == chosen)["values"][-1] for c in cases}
                    report["candidate_dataset"] = chosen
                    report["candidate_terminal_values"] = vals
                    report["candidate_zero_minus_baseline"] = vals["same_mode_zero"] - vals["baseline"]
                    report["candidate_negative_minus_zero"] = vals["full_negative"] - vals["same_mode_zero"]
                    report["candidate_positive_minus_zero"] = vals["full_positive"] - vals["same_mode_zero"]
                    report["hdf5_diagnostic_terminal_time_alignment_verified"] = False
                    report["classification"] = "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_PRESENT_TIMING_UNVERIFIED"
                report["interpretation"] = (
                    "Native totcur uses int2(ri2_79,pst79(:,OP_GS))/tpirzero. "
                    "Saved HDF5 diagnostic availability does not prove terminal time alignment, "
                    "operator parity, units or physical current conservation; absence is a prerequisite blocker, not a negative TCT result."
                )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_TOTCUR_SAVED_OBSERVABLE_PIPELINE_BLOCKED"
target = out / "native_totcur_saved_observable_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

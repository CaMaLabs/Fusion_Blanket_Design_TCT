#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Source-hashed native int2 reconstruction preflight; no solver calls or physical-current claims."""
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
native = pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
job_id = "20261030-149-native-int2-quadrature-reconstruction-preflight"
parent_id = "20261030-148-native-totcur-stdout-hdf5-parity"
parent_path = repo / "validation_runs/m3dc1_tct_native_totcur_parity_148/native_totcur_stdout_hdf5_parity_summary.json"
parent_sha = "d7c7369d4eb33f6390bc2abfe3ddec4545ce2f27ac9d9b5c55901f50912c3409"
source_shas = {
    "diagnostics.f90": "0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655",
    "nintegrate_mod.f90": "fd4be567e954d9df18e7ed83d3f622816a48c939832a4b7df700be3746471d00",
}
out = repo / "validation_runs/m3dc1_tct_native_int2_preflight_149"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job_id, "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "classification": "M3DC1_NATIVE_INT2_RECONSTRUCTION_PREFLIGHT_UNRESOLVED",
    "expected_parent_summary_sha256": parent_sha,
    "expected_native_source_sha256": source_shas,
    "saved_run_origin_job_id": "20261029-130-native-current-drive-geometry-weight-sensitivity",
    "physics_solver_runs": 0, "shot_ids": [], "source_mode": 4,
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "native_int2_operator_parity_validated": False, "physical_current_calibrated": False,
    "temporal_convergence_validated": False, "shot_handoff_validated": False,
    "causal_segmented_controller_authority_validated": False,
    "pb11_fidelity_validated": False, "ignition_or_net_power_validated": False,
    "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "claim_boundary": "Source and saved-schema preflight for native int2 inputs only; no reconstructed int2, calibrated physical current, causal segmented TCT, shot handoff, p-B11, ignition or net power."
}
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def snippet(lines, regex, radius=3, limit=12):
    matches = []
    for i, line in enumerate(lines):
        if re.search(regex, line, re.I):
            matches.append({"line": i+1, "context": "\n".join(
                str(j+1)+": "+lines[j][:240] for j in range(max(0,i-radius), min(len(lines),i+radius+1)))})
    return matches[:limit]
try:
    import h5py
    if not parent_path.is_file() or sha(parent_path) != parent_sha:
        report["classification"] = "M3DC1_NATIVE_INT2_PREFLIGHT_PARENT_BLOCKED"
        report["prerequisite_blocker"] = "PARENT_SUMMARY_MISSING_OR_CHANGED"
    else:
        parent = json.loads(parent_path.read_text())
        if (parent.get("job_id") != parent_id
                or parent.get("classification") != "M3DC1_NATIVE_TOTCUR_STDOUT_HDF5_VALUE_AND_TIME_AXIS_PARITY_COMPLETE"
                or parent.get("all_stdout_hdf5_value_parity") is not True
                or parent.get("hdf5_terminal_time_alignment_verified") is not True
                or parent.get("zero_source_max_abs_native_diagnostic_delta") != 0.0):
            report["classification"] = "M3DC1_NATIVE_INT2_PREFLIGHT_PARENT_BLOCKED"
            report["prerequisite_blocker"] = "PARENT_SCIENTIFIC_GATES_CHANGED"
        else:
            report["parent_stdout_hdf5_value_parity"] = True
            report["parent_explicit_hdf5_time_axis_parity"] = True
            report["parent_zero_source_max_abs_native_diagnostic_delta"] = 0.0
            changed = [name for name, expected in source_shas.items()
                       if not (native/name).is_file() or sha(native/name) != expected]
            if changed:
                report["classification"] = "M3DC1_NATIVE_INT2_PREFLIGHT_SOURCE_BLOCKED"
                report["prerequisite_blocker"] = "NATIVE_SOURCE_MISSING_OR_CHANGED"
                report["changed_or_missing_sources"] = changed
            else:
                diag = (native/"diagnostics.f90").read_text(errors="replace").splitlines()
                integrator = (native/"nintegrate_mod.f90").read_text(errors="replace").splitlines()
                report["totcur_int2_callsites"] = snippet(diag, r"totcur\s*=\s*totcur\s*-\s*int2\s*\(", 3)
                report["int2_definition"] = snippet(integrator, r"\bfunction\s+int2\s*\(", 13)
                report["int2_weight_use"] = snippet(integrator, r"int2\s*=\s*int2\s*\+.*weight_79", 5)
                if not report["totcur_int2_callsites"] or not report["int2_definition"] or not report["int2_weight_use"]:
                    report["classification"] = "M3DC1_NATIVE_INT2_PREFLIGHT_SOURCE_MAPPING_BLOCKED"
                    report["prerequisite_blocker"] = "NATIVE_INT2_EXPRESSION_NOT_FOUND"
                else:
                    root = pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs")
                    cases = ("baseline", "same_mode_zero", "full_negative", "full_positive")
                    report["cases"] = {}
                    missing = []
                    for case in cases:
                        case_path = root / case
                        row = {"saved_run_dir": str(case_path), "files": {}}
                        for file_name in ("C1.h5", "time_003.h5"):
                            path = case_path / file_name
                            if not path.is_file():
                                missing.append(str(path))
                                continue
                            entry = {"sha256": sha(path), "datasets": []}
                            with h5py.File(path, "r") as h:
                                def visit(name, obj):
                                    if isinstance(obj, h5py.Dataset):
                                        entry["datasets"].append({"path": name, "shape": list(obj.shape), "dtype": str(obj.dtype)})
                                h.visititems(visit)
                            names = [x["path"].lower() for x in entry["datasets"]]
                            entry["native_quadrature_state_named_candidates"] = {
                                token: [n for n in names if re.search(r"(^|[/_])"+token+r"($|[/_])", n)]
                                for token in ("weight_79", "ri2_79", "pst79")
                            }
                            entry["dataset_count"] = len(names)
                            row["files"][file_name] = entry
                        report["cases"][case] = row
                    report["missing_saved_files"] = missing
                    report["direct_named_quadrature_inputs_present_in_all_cases"] = all(
                        all(any(entry["native_quadrature_state_named_candidates"][token]
                                for entry in row["files"].values())
                            for token in ("weight_79", "ri2_79", "pst79"))
                        for row in report["cases"].values()) if not missing else False
                    if missing:
                        report["classification"] = "M3DC1_NATIVE_INT2_PREFLIGHT_DATA_ACCESS_BLOCKED"
                        report["prerequisite_blocker"] = "SAVED_NATIVE_HDF5_MISSING"
                    else:
                        report["classification"] = "M3DC1_NATIVE_INT2_RECONSTRUCTION_PREFLIGHT_COMPLETE"
                    report["interpretation"] = (
                        "Native totcur uses int2(ri2_79,pst79(:,OP_GS)) and weight_79 quadrature. "
                        "This audit inventories saved datasets and source-hashed callsites; absence of direct named arrays "
                        "is not proof that native state cannot be reconstructed from coefficients. "
                        "No operator-level parity or calibrated current is established."
                    )
except Exception as exc:
    report["classification"] = "M3DC1_NATIVE_INT2_PREFLIGHT_PIPELINE_BLOCKED"
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
target = out / "native_int2_reconstruction_preflight_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+"\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Bounded native int2 input-producer lineage; source/saved-data audit, zero solver calls."""
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
native = pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
job_id = "20261030-150-native-int2-input-producer-lineage"
parent_id = "20261030-149-native-int2-quadrature-reconstruction-preflight"
parent_file = repo / "validation_runs/m3dc1_tct_native_int2_preflight_149/native_int2_reconstruction_preflight_summary.json"
parent_sha = "9f21d3b44a3e28365a7bb6b13cbd43495143a12a65bc3fe84c2cfe425e3fb01d"
source_shas = {
    "diagnostics.f90": "0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655",
    "nintegrate_mod.f90": "fd4be567e954d9df18e7ed83d3f622816a48c939832a4b7df700be3746471d00"
}
out = repo / "validation_runs/m3dc1_tct_native_int2_lineage_150"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job_id, "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "classification": "M3DC1_NATIVE_INT2_INPUT_PRODUCER_LINEAGE_UNRESOLVED",
    "expected_parent_summary_sha256": parent_sha, "expected_native_source_sha256": source_shas,
    "saved_run_origin_job_id": "20261029-130-native-current-drive-geometry-weight-sensitivity",
    "physics_solver_runs": 0, "shot_ids": [], "source_mode": 4,
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "native_int2_operator_parity_validated": False, "physical_current_calibrated": False,
    "temporal_convergence_validated": False, "shot_handoff_validated": False,
    "causal_segmented_controller_authority_validated": False,
    "pb11_fidelity_validated": False, "ignition_or_net_power_validated": False,
    "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "claim_boundary": "Source-level input-producer lineage only. No independent int2 parity, current calibration/conservation, causal segmented TCT, experimental shot handoff, p-B11, ignition or net power."
}
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def context(lines, i):
    return "\n".join(f"{j+1}: {lines[j][:210]}" for j in range(max(0, i-2), min(len(lines), i+3)))
try:
    if not parent_file.is_file() or sha(parent_file) != parent_sha:
        report["classification"] = "M3DC1_NATIVE_INT2_INPUT_LINEAGE_PARENT_BLOCKED"
        report["prerequisite_blocker"] = "PARENT_SUMMARY_MISSING_OR_CHANGED"
    else:
        parent = json.loads(parent_file.read_text())
        if (parent.get("job_id") != parent_id
            or parent.get("classification") != "M3DC1_NATIVE_INT2_RECONSTRUCTION_PREFLIGHT_COMPLETE"
            or parent.get("parent_stdout_hdf5_value_parity") is not True
            or parent.get("parent_explicit_hdf5_time_axis_parity") is not True
            or parent.get("parent_zero_source_max_abs_native_diagnostic_delta") != 0
            or parent.get("native_int2_operator_parity_validated") is not False):
            report["classification"] = "M3DC1_NATIVE_INT2_INPUT_LINEAGE_PARENT_BLOCKED"
            report["prerequisite_blocker"] = "PARENT_EVIDENCE_OR_GATES_CHANGED"
        else:
            report["parent_value_time_parity_supported"] = True
            report["parent_direct_named_quadrature_inputs_present"] = parent.get("direct_named_quadrature_inputs_present_in_all_cases")
            missing = [n for n,h in source_shas.items() if not (native/n).is_file() or sha(native/n) != h]
            if missing:
                report["classification"] = "M3DC1_NATIVE_INT2_INPUT_LINEAGE_SOURCE_BLOCKED"
                report["prerequisite_blocker"] = "HASHED_NATIVE_SOURCE_MISSING_OR_CHANGED"
                report["changed_or_missing_sources"] = missing
            else:
                tokens = ("ri2_79", "pst79", "weight_79", "OP_GS")
                report["producer_references"] = {t: [] for t in tokens}
                report["source_files_scanned"] = 0
                report["source_files_with_hits"] = []
                suffixes = {".f", ".f90", ".f95", ".for", ".F", ".F90"}
                for p in sorted(native.rglob("*")):
                    if not p.is_file() or p.suffix not in suffixes or p.stat().st_size > 2_000_000:
                        continue
                    report["source_files_scanned"] += 1
                    lines = p.read_text(errors="replace").splitlines()
                    found = False
                    for token in tokens:
                        for i,line in enumerate(lines):
                            if re.search(r"(?<![a-zA-Z0-9_])"+re.escape(token)+r"(?![a-zA-Z0-9_])", line, re.I):
                                found = True
                                if len(report["producer_references"][token]) < 45:
                                    report["producer_references"][token].append({
                                        "file": str(p.relative_to(native)), "line": i+1,
                                        "context": context(lines, i),
                                        "assignment_candidate": bool(re.search(re.escape(token)+r"(?:\s*\([^)]*\))?\s*=(?!=)", line, re.I))
                                    })
                    if found:
                        report["source_files_with_hits"].append({
                            "file": str(p.relative_to(native)), "sha256": sha(p)
                        })
                report["token_hit_counts_capped"] = {t: len(report["producer_references"][t]) for t in tokens}
                report["source_files_with_hits_count"] = len(report["source_files_with_hits"])
                report["direct_native_quadrature_arrays_in_saved_hdf5"] = False
                report["saved_coefficients_sufficient_for_exact_int2_reconstruction_verified"] = False
                report["interpretation"] = (
                    "Trace producers and uses of ri2_79, pst79, weight_79 and OP_GS in native source. "
                    "Direct named quadrature arrays are absent from the saved HDF5 inventory. "
                    "Source references do not prove reconstruction from saved coefficients or operator parity. "
                    "A later reconstruction or instrumented native comparison requires separately verified prerequisites."
                )
                if all(report["producer_references"][t] for t in tokens):
                    report["classification"] = "M3DC1_NATIVE_INT2_INPUT_PRODUCER_LINEAGE_AUDIT_COMPLETE"
                else:
                    report["classification"] = "M3DC1_NATIVE_INT2_INPUT_LINEAGE_SOURCE_MAPPING_BLOCKED"
                    report["prerequisite_blocker"] = "REQUIRED_NATIVE_INPUT_REFERENCES_NOT_FOUND"
except Exception as exc:
    report["classification"] = "M3DC1_NATIVE_INT2_INPUT_LINEAGE_PIPELINE_BLOCKED"
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
target = out / "native_int2_input_producer_lineage_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+"\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

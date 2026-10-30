#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Bounded source-level audit of the M3D-C1 HDF5 mesh/elements column-3 writer.
The prior Python e[2] proxy is HDF5 column 3 (zero-based index 2).
This audit does not establish physical area, current, quadrature, or TCT control.
"""
import datetime
import hashlib
import json
import pathlib
import re
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
source_root = pathlib.Path("/home/ubuntu/M3DC1-official")
job_id = "20261030-143-native-mesh-elements-column2-writer-audit"
parent_id = "20261030-142-native-mesh-hdf5-column-lineage"
parent_path = repo / "validation_runs/m3dc1_tct_native_quadrature_142/native_mesh_hdf5_column_lineage_summary.json"
expected_parent_sha = "d415bce33aefbfb985cd6775727cfb051a5de19bee4e95f6c387b1f8d393b6a8"
out = repo / "validation_runs/m3dc1_tct_native_quadrature_143"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1,
    "job_id": job_id,
    "parent_result_job_id": parent_id,
    "expected_parent_summary_sha256": expected_parent_sha,
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1",
    "shot_ids": [],
    "physics_solver_runs": 0,
    "classification": "M3DC1_NATIVE_MESH_ELEMENTS_COLUMN2_WRITER_AUDIT_UNRESOLVED",
    "hdf5_python_e2_column_one_based": 3,
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "source_writer_trace_only": True,
    "hdf5_column_to_physical_geometry_validated": False,
    "independent_analytic_geometry_check_passed": False,
    "calibrated_physical_current_validated": False,
    "calibrated_physical_width_validated": False,
    "causal_segmented_controller_authority_validated": False,
    "claim_boundary": "Targeted native M3D-C1 mesh/elements writer assignments and HDF5 write-layout provenance only. No independent analytic geometry/physical quadrature check, calibrated current or width, timestep convergence, causal segmented TCT stabilization, experimental shot handoff, p-B11 fidelity, ignition or net-power evidence.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    if not parent_path.is_file() or hashlib.sha256(parent_path.read_bytes()).hexdigest() != expected_parent_sha:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("job_id") != parent_id or parent.get("classification") != "M3DC1_NATIVE_MESH_HDF5_COLUMN_LINEAGE_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_OR_ID_CHANGED")
    if parent.get("physical_quadrature_validated") is not False or parent.get("physics_solver_runs") != 0:
        raise RuntimeError("PARENT_FIDELITY_BOUNDARY_CHANGED")
    report["parent_evidence_counts"] = parent.get("evidence_counts")
    writer = source_root / "unstructured/output.f90"
    hdf5 = source_root / "unstructured/hdf5_output.f90"
    if not writer.is_file() or not hdf5.is_file():
        report["classification"] = "M3DC1_NATIVE_MESH_ELEMENTS_COLUMN2_WRITER_SOURCE_BLOCKED"
        report["prerequisite_blocker"] = "NATIVE_OUTPUT_OR_HDF5_WRITER_SOURCE_MISSING"
    else:
        writer_data, hdf5_data = writer.read_bytes(), hdf5.read_bytes()
        wl = writer_data.decode("utf-8", errors="replace").splitlines()
        hl = hdf5_data.decode("utf-8", errors="replace").splitlines()
        report["source_sha256"] = {
            "unstructured/output.f90": hashlib.sha256(writer_data).hexdigest(),
            "unstructured/hdf5_output.f90": hashlib.sha256(hdf5_data).hexdigest()
        }
        calls = [i for i, line in enumerate(wl) if re.search(r'call\s+output_field\s*\(\s*mesh_group_id\s*,\s*["\x27]elements["\x27]', line, re.I)]
        report["elements_writer_call_lines"] = [i + 1 for i in calls]
        if calls:
            call_index = calls[0]
            lo, hi = max(0, call_index - 120), min(len(wl), call_index + 15)
            report["mesh_writer_context"] = [
                {"line": i + 1, "text": wl[i][:300]}
                for i in range(lo, hi)
            ]
            report["elm_data_assignment_candidates"] = [
                {"line": i + 1, "text": wl[i][:300]}
                for i in range(lo, hi)
                if re.search(r'\belm_data\s*\(', wl[i], re.I)
            ]
            report["column_three_direct_assignment_candidates"] = [
                x for x in report["elm_data_assignment_candidates"]
                if re.search(r'\belm_data\s*\(\s*3\s*,', x["text"], re.I)
                or re.search(r'\belm_data\s*\(\s*[^,]+\s*,\s*3\s*\)', x["text"], re.I)
            ]
            report["layout_declaration_candidates"] = [
                {"line": i + 1, "text": wl[i][:300]}
                for i in range(lo, hi)
                if re.search(r'\b(vals_per_elm|dimension\s*\(|allocate\s*\(|elm_data|mesh_coord|tri_area)\b', wl[i], re.I)
            ][:100]
        output_field_defs = [i for i, line in enumerate(hl) if re.search(r'^\s*subroutine\s+output_field\b', line, re.I)]
        report["hdf5_output_field_definition_lines"] = [i + 1 for i in output_field_defs]
        report["hdf5_write_layout_context"] = [
            {"line": i + 1, "text": hl[i][:300]}
            for d in output_field_defs[:2]
            for i in range(max(0, d - 4), min(len(hl), d + 75))
        ]
        report["source_lineage_status"] = (
            "TARGETED_WRITER_CONTEXT_CAPTURED_MAPPING_REQUIRES_REVIEW"
            if calls and report.get("elm_data_assignment_candidates")
            else "WRITER_ASSIGNMENT_OR_LAYOUT_NOT_LOCATED"
        )
        report["classification"] = (
            "M3DC1_NATIVE_MESH_ELEMENTS_COLUMN2_WRITER_AUDIT_COMPLETE"
            if calls and report.get("elm_data_assignment_candidates")
            else "M3DC1_NATIVE_MESH_ELEMENTS_COLUMN2_WRITER_MAPPING_UNRESOLVED"
        )
        report["interpretation"] = (
            "Captured exact hashed native mesh/elements writer context and output_field layout context. "
            "Candidate elm_data assignments are not a validated HDF5-column-to-physical-area mapping. "
            "An independent analytic geometry check remains required before interpreting e[2] or R*e[2] "
            "as a physical quadrature or using it for current conservation or calibrated width."
        )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_MESH_ELEMENTS_COLUMN2_WRITER_PIPELINE_BLOCKED"
target = out / "native_mesh_elements_column2_writer_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps({k: v for k, v in report.items() if k not in ("mesh_writer_context", "hdf5_write_layout_context")}, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

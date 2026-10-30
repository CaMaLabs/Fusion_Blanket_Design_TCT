#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Trace native M3D-C1 mesh/elements column provenance, without physics edits.
This is a source-lineage audit, not a validation of physical area/current.
"""
import datetime
import hashlib
import json
import pathlib
import re
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
src = pathlib.Path("/home/ubuntu/M3DC1-official")
job_id = "20261030-142-native-mesh-hdf5-column-lineage"
parent_id = "20261030-141-native-mesh-quadrature-provenance"
parent_path = repo / "validation_runs/m3dc1_tct_native_quadrature_141/native_mesh_quadrature_provenance_summary.json"
expected_sha = "ad8ed8e97a475090d966f29a1a9de59e1956844e67b99ad6fa84dfb4a63ef7b4"
out = repo / "validation_runs/m3dc1_tct_native_quadrature_142"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job_id, "parent_result_job_id": parent_id,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "physics_solver_runs": 0,
    "expected_parent_summary_sha256": expected_sha,
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "physical_quadrature_validated": False,
    "calibrated_physical_current_validated": False,
    "calibrated_physical_width_validated": False,
    "causal_segmented_controller_authority_validated": False,
    "classification": "M3DC1_NATIVE_MESH_HDF5_COLUMN_LINEAGE_UNRESOLVED",
    "claim_boundary": "Source-level mesh/elements writer and element-weight lineage candidates only. Neither e[2], R*e[2], int1 nor HDF5 jphi is independently calibrated to physical current/area. No new native solver run, shot handoff, temporal convergence, controller-in-loop, causal TCT stabilization, p-B11 fidelity, ignition or net-power evidence.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    if not parent_path.is_file() or hashlib.sha256(parent_path.read_bytes()).hexdigest() != expected_sha:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("job_id") != parent_id or parent.get("classification") != "M3DC1_NATIVE_MESH_QUADRATURE_PROVENANCE_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_ID_OR_CLASSIFICATION_CHANGED")
    if parent.get("physical_quadrature_validated") is not False or parent.get("physics_solver_runs") != 0:
        raise RuntimeError("PARENT_FIDELITY_OR_RUN_COUNT_CHANGED")
    report["parent_source_scan_count"] = parent.get("native_source_files_scanned")
    report["parent_mesh_elements_shape"] = parent.get("prior_mesh_metadata", {}).get("mesh_elements_shape")
    if not src.is_dir():
        report["classification"] = "M3DC1_NATIVE_MESH_HDF5_COLUMN_LINEAGE_PREREQUISITE_BLOCKED"
        report["prerequisite_blocker"] = "NATIVE_SOURCE_ROOT_UNAVAILABLE"
    else:
        patterns = {
            "mesh_dataset_writer": re.compile(r'(?:["\x27](?:/mesh/)?elements["\x27]|["\x27]mesh["\x27]|write.*mesh|mesh.*write)', re.I),
            "element_weight_geometry": re.compile(r'\be\s*\(\s*2\s*\)|\b(?:elem\w*|tri\w*)\b.*\b(?:area|jacob|weight)|\b(?:area|jacob|weight)\b.*\b(?:elem\w*|tri\w*)', re.I),
            "int1_definition_or_use": re.compile(r'\b(?:function\s+int1|int1\s*\()', re.I),
            "jphi_writer": re.compile(r'\bjphi\b|["\x27]fields["\x27]', re.I),
        }
        candidates = {k: [] for k in patterns}
        file_count = 0
        source_files = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in {".f", ".f90", ".f95", ".c", ".cpp", ".h", ".hpp"} and p.stat().st_size <= 2000000)
        # Prefer active unstructured source to skeleton copies, then keep deterministic order.
        source_files.sort(key=lambda p: (0 if "unstructured" in p.parts else 1, str(p)))
        for p in source_files:
            file_count += 1
            data = p.read_bytes()
            lines = data.decode("utf-8", errors="replace").splitlines()
            rel = str(p.relative_to(src))
            sha = hashlib.sha256(data).hexdigest()
            for n, line in enumerate(lines):
                for kind, pattern in patterns.items():
                    if pattern.search(line) and len(candidates[kind]) < 45:
                        candidates[kind].append({
                            "file": rel, "line": n + 1, "source_sha256": sha,
                            "context": "\n".join("%d: %s" % (j + 1, lines[j][:180]) for j in range(max(0, n - 3), min(len(lines), n + 5)))
                        })
        report["native_source_root"] = str(src)
        report["source_files_scanned"] = file_count
        report["source_evidence"] = candidates
        report["evidence_counts"] = {k: len(v) for k, v in candidates.items()}
        # A search match is NOT a proven column-to-physical-geometry mapping.
        report["hdf5_column_to_geometry_mapping_validated"] = False
        report["independent_analytic_geometry_check_passed"] = False
        report["source_lineage_status"] = "CANDIDATES_ONLY_NO_INDEPENDENT_GEOMETRY_CHECK"
        report["classification"] = (
            "M3DC1_NATIVE_MESH_HDF5_COLUMN_LINEAGE_DIAGNOSTIC_COMPLETE"
            if candidates["mesh_dataset_writer"] and candidates["element_weight_geometry"]
            else "M3DC1_NATIVE_MESH_HDF5_COLUMN_LINEAGE_SOURCE_TRACES_INCOMPLETE"
        )
        report["interpretation"] = (
            "Targeted source context for the mesh/elements writer, e(2) geometry/weight candidates, "
            "int1 and jphi is collected with source hashes. Context hits do not prove the HDF5 "
            "column schema or a physical quadrature. A column-level mapping and independent "
            "analytic geometry comparison are required before physical current or width claims."
        )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_MESH_HDF5_COLUMN_LINEAGE_PIPELINE_BLOCKED"
target = out / "native_mesh_hdf5_column_lineage_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps({k: v for k, v in report.items() if k != "source_evidence"}, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

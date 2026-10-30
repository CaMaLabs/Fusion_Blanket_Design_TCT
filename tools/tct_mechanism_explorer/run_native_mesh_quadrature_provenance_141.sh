#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Source-provenance gate for M3D-C1 HDF5 element weights and native int1.
No solver run, source edit, physical quadrature claim, or gate modification.
"""
import datetime
import hashlib
import json
import pathlib
import re
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0, str(repo / "tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta

job = "20261030-141-native-mesh-quadrature-provenance"
parent_id = "20261030-140-native-current-drive-width-roi-sensitivity"
out = repo / "validation_runs/m3dc1_tct_native_quadrature_141"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job, "parent_result_job_id": parent_id,
    "classification": "M3DC1_NATIVE_MESH_QUADRATURE_PROVENANCE_UNRESOLVED",
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1", "shot_ids": [],
    "expected_parent_summary_sha256": "15c1df24ee75906fc306402a5b22fea153bc11534514efc59580c296aa5decac",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "zero_equivalence_tolerance": 1e-12,
    "physics_solver_runs": 0,
    "physical_quadrature_validated": False,
    "calibrated_physical_width_validated": False,
    "causal_controller_authority_validated": False,
    "claim_boundary": "Source-level quadrature and mesh-output provenance only. No independent validation of e[2], R*e[2], int1 or physical current/area; no calibrated sheet width, temporal convergence, shot handoff, segmented controller-in-loop, causal TCT stabilization, p-B11 fidelity, ignition or net power.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
try:
    parent_path = repo / "validation_runs/m3dc1_tct_native_width_roi_140/width_roi_sensitivity_summary.json"
    if not parent_path.is_file() or pta.sha256_file(parent_path) != report["expected_parent_summary_sha256"]:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_path.read_text())
    if parent.get("job_id") != parent_id or parent.get("classification") != "M3DC1_NATIVE_CURRENT_DRIVE_WIDTH_ROI_SENSITIVITY_DIAGNOSTIC_COMPLETE":
        raise RuntimeError("PARENT_CLASSIFICATION_OR_ID_CHANGED")
    if parent.get("zero_equivalence", {}).get("pass") is not True:
        raise RuntimeError("PARENT_ZERO_EQUIVALENCE_FAILED")
    rows = []
    for frame in parent["matched_frames"]:
        for roi in frame["roi_comparisons"]:
            for command, metrics in roi["cases"].items():
                rows.append({"time": frame["time"], "roi": roi["radial_half_width"], "command": command,
                             "width_gain_pct": metrics["width_gain_pct"],
                             "jpk_change_pct": metrics["Jpk_change_pct"]})
    sign_flips = []
    for time in parent["matched_times"]:
        for command in ("neg_nominal", "neg_double", "pos_nominal", "pos_double"):
            vals = [r["width_gain_pct"] for r in rows if r["time"] == time and r["command"] == command]
            if min(vals) < 0 < max(vals):
                sign_flips.append({"time": time, "command": command, "min_pct": min(vals), "max_pct": max(vals)})
    report["parent_roi_quantitative_audit"] = {
        "comparison_count": len(rows), "sign_flip_groups": sign_flips,
        "sign_flip_count": len(sign_flips), "max_width_gain_pct": max(r["width_gain_pct"] for r in rows),
        "min_width_gain_pct": min(r["width_gain_pct"] for r in rows),
        "frozen_width_crossings": sum(r["width_gain_pct"] > 0.02 for r in rows),
        "max_jpk_increase_pct": max(r["jpk_change_pct"] for r in rows),
        "zero_source_max_abs_field_delta": parent["zero_equivalence"]["max_abs_field_delta"]
    }
    old = repo / "validation_runs/m3dc1_tct_native_geometry_weight_130/native_geometry_weight_summary.json"
    if old.is_file():
        prior = json.loads(old.read_text())
        report["prior_mesh_metadata"] = {
            "source_job_id": prior.get("job_id"), "mesh_elements_shape": prior.get("mesh_elements_shape"),
            "mesh_group_keys": prior.get("mesh_group_keys"),
            "mesh_element_attrs": prior.get("mesh_element_attrs"),
            "source_summary_sha256": pta.sha256_file(old)
        }
    src = pathlib.Path(native.SRC)
    report["native_source_root"] = str(src)
    if not src.is_dir():
        report["classification"] = "M3DC1_NATIVE_MESH_QUADRATURE_PROVENANCE_PREREQUISITE_BLOCKED"
        report["prerequisite_blocker"] = "NATIVE_SOURCE_ROOT_UNAVAILABLE"
    else:
        patterns = {
            "int1_quadrature": re.compile(r"\\bint1\\s*\\(", re.I),
            "hdf5_mesh_elements": re.compile(r"(mesh/elements|/elements|h5dwrite|h5dcreate)", re.I),
            "element_weight_or_geometry": re.compile(r"(element.*(weight|area|jacob)|jacob.*element|quadrature)", re.I)
        }
        hits = {k: [] for k in patterns}
        scanned = 0
        allowed = {".f", ".f90", ".f95", ".F", ".F90", ".c", ".cpp", ".h", ".hpp"}
        for f in sorted(src.rglob("*")):
            if not f.is_file() or f.suffix not in allowed or f.stat().st_size > 2_000_000:
                continue
            scanned += 1
            if scanned > 3000:
                break
            try:
                data = f.read_bytes()
                lines = data.decode("utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for n, line in enumerate(lines, 1):
                for key, pattern in patterns.items():
                    if len(hits[key]) < 30 and pattern.search(line):
                        hits[key].append({"file": str(f.relative_to(src)), "line": n,
                                          "excerpt": line.strip()[:240],
                                          "source_sha256": hashlib.sha256(data).hexdigest()})
        report["native_source_files_scanned"] = scanned
        report["source_evidence"] = hits
        report["quadrature_mapping_evidence_status"] = "UNVERIFIED_SOURCE_TRACES_ONLY"
        report["classification"] = "M3DC1_NATIVE_MESH_QUADRATURE_PROVENANCE_DIAGNOSTIC_COMPLETE"
    report["interpretation"] = (
        "Parent ROI-derived width response changes sign with ROI in some command/time groups "
        "and never crosses the frozen width gate. This audit inventories native source definitions "
        "for HDF5 element weights and int1 integration; search hits alone do not establish a "
        "physical quadrature mapping. A reviewed mapping and independently checked geometry "
        "must precede physical current/width claims or additional width optimization."
    )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_MESH_QUADRATURE_PROVENANCE_PIPELINE_BLOCKED"
target = out / "native_mesh_quadrature_provenance_summary.json"
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

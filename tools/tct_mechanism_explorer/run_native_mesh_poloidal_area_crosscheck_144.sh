#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
"${TCT_PYTHON:-python3}" - <<'PY'
"""Crosscheck source-defined 2-D M3D-C1 poloidal triangle area using saved HDF5.
No solver execution, source modification, current calibration, or TCT claim.
"""
import datetime
import hashlib
import json
import math
import pathlib
import re
import statistics
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
src = pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
job = "20261030-144-native-mesh-poloidal-area-crosscheck"
parent_id = "20261030-143-native-mesh-elements-column2-writer-audit"
parent_file = repo / "validation_runs/m3dc1_tct_native_quadrature_143/native_mesh_elements_column2_writer_summary.json"
parent_sha = "7eddb653b10c709b0be7e725b9fa8a3b952f56bc7ecccce774a27713e26f3c96"
out = repo / "validation_runs/m3dc1_tct_native_geometry_144"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1, "job_id": job, "parent_result_job_id": parent_id,
    "expected_parent_summary_sha256": parent_sha,
    "fuel_track": "fuel_agnostic_control", "machine": "normalized-native-M3D-C1",
    "shot_ids": [], "physics_solver_runs": 0,
    "classification": "M3DC1_NATIVE_MESH_POLOIDAL_AREA_CROSSCHECK_UNRESOLVED",
    "source_guided_2d_geometry_only": True,
    "physical_current_quadrature_validated": False,
    "calibrated_physical_width_validated": False,
    "causal_segmented_controller_authority_validated": False,
    "temporal_convergence_validated": False,
    "experimental_shot_handoff_validated": False,
    "pb11_fidelity_validated": False,
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Native 2-D poloidal triangle geometry and existing HDF5 mesh only; no native int1/3-D toroidal quadrature, calibrated jphi integral, physical sheet width, timestep convergence, controller-in-loop causal TCT, experimental shot handoff, p-B11, ignition or reactor-net-power claim.",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_check(path, expressions):
    text = path.read_text(errors="replace")
    missing = [p for p in expressions if re.search(p, text, re.I) is None]
    if missing:
        raise ValueError("NATIVE_SOURCE_FORMULA_CHANGED: " + path.name + ": " + repr(missing))
    return digest(path)

try:
    if not parent_file.is_file() or digest(parent_file) != parent_sha:
        raise RuntimeError("PARENT_SUMMARY_MISSING_OR_CHANGED")
    parent = json.loads(parent_file.read_text())
    if parent.get("job_id") != parent_id or parent.get("classification") != "M3DC1_NATIVE_MESH_ELEMENTS_COLUMN2_WRITER_AUDIT_COMPLETE":
        raise RuntimeError("PARENT_ID_OR_CLASSIFICATION_CHANGED")
    if parent.get("hdf5_column_to_physical_geometry_validated") is not False or parent.get("physics_solver_runs") != 0:
        raise RuntimeError("PARENT_FIDELITY_BOUNDARY_CHANGED")
    writer, hdf = src / "output.f90", src / "hdf5_output.f90"
    basic, element = src / "basic_mesh.f90", src / "element.f90"
    expected = parent["source_sha256"]
    if not all(p.is_file() for p in (writer, hdf, basic, element)):
        raise FileNotFoundError("NATIVE_MESH_SOURCE_MISSING")
    if digest(writer) != expected["unstructured/output.f90"] or digest(hdf) != expected["unstructured/hdf5_output.f90"]:
        raise RuntimeError("PARENT_NATIVE_WRITER_SOURCE_CHANGED")
    report["native_source_sha256"] = {
        "unstructured/output.f90": source_check(writer, [
            r"elm_data\s*\(\s*3\s*,\s*i\s*\)\s*=\s*d%c",
            r"output_field\s*\(\s*mesh_group_id\s*,\s*['\"]elements['\"]"
        ]),
        "unstructured/hdf5_output.f90": digest(hdf),
        "unstructured/basic_mesh.f90": source_check(basic, [
            r"d%a\s*=\s*x2p\s*-\s*x3p", r"d%b\s*=\s*x3p", r"d%c\s*=\s*z3p",
            r"d%co\s*=\s*x2\s*\*\s*hi", r"d%sn\s*=\s*z2\s*\*\s*hi"
        ]),
        "unstructured/element.f90": source_check(element, [
            r"R\s*=\s*d%R\s*\+\s*\(\s*d%b\s*\+\s*xi\s*\)\s*\*\s*d%co\s*-\s*eta\s*\*\s*d%sn",
            r"Z\s*=\s*d%Z\s*\+\s*\(\s*d%b\s*\+\s*xi\s*\)\s*\*\s*d%sn\s*\+\s*eta\s*\*\s*d%co"
        ])
    }
    report["source_derived_geometry"] = {
        "hdf5_python_e2": "d%c, rotated triangle altitude (length), not element area",
        "poloidal_triangle_base": "a+b",
        "poloidal_triangle_area": "0.5*(a+b)*c",
        "vertices": ["(R,Z)", "(R+(a+b)cos(theta),Z+(a+b)sin(theta))",
                     "(R+b*cos(theta)-c*sin(theta),Z+b*sin(theta)+c*cos(theta))"]
    }
    def vertices(a, b, c, theta, R, Z):
        co, sn = math.cos(theta), math.sin(theta)
        return ((R,Z), (R+(a+b)*co,Z+(a+b)*sn),
                (R+b*co-c*sn,Z+b*sn+c*co))
    def shoelace(v):
        return abs(sum(v[i][0]*v[(i+1)%3][1]-v[(i+1)%3][0]*v[i][1]
                       for i in range(3)))*0.5
    synthetic = ((1.0,1.0,1.0,0.0,10.0,1.0),
                 (0.25,0.75,0.5,0.31,9.0,-2.0),
                 (0.3,0.7,0.8,-0.72,12.0,0.0))
    synthetic_error = max(abs(shoelace(vertices(*row)) - 0.5*(row[0]+row[1])*row[2])
                          for row in synthetic)
    report["synthetic_shoelace_max_abs_error"] = synthetic_error
    if synthetic_error > 1e-11:
        raise ValueError("SYNTHETIC_GEOMETRY_CROSSCHECK_FAILED")
    candidates = [
        pathlib.Path("/tmp/m3dc1_tct_native_width_roi_140/baseline/time_000.h5"),
        pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs/baseline/time_000.h5")
    ]
    sample = next((p for p in candidates if p.is_file()), None)
    report["candidate_native_hdf5_paths"] = [str(p) for p in candidates]
    if sample is None:
        report["classification"] = "M3DC1_NATIVE_MESH_POLOIDAL_AREA_DATA_ACCESS_BLOCKED"
        report["prerequisite_blocker"] = "EXISTING_NATIVE_HDF5_BASELINE_MESH_NOT_AVAILABLE"
        report["interpretation"] = "Native source establishes e[2]=d%c (altitude), not area. Analytic geometry identity passed synthetic cases, but no saved native mesh was accessible; no physical or scientific failure inferred."
    else:
        import h5py
        with h5py.File(sample, "r") as h:
            e = h["/mesh/elements"][:]
            mesh_is_3d = int(h["/mesh"].attrs.get("3D", 0))
        if e.ndim != 2 or e.shape[1] != 8 or mesh_is_3d != 0:
            raise ValueError("UNEXPECTED_2D_MESH_SCHEMA")
        errors, areas, altitudes, base_lengths = [], [], [], []
        for row in e:
            a,b,c,theta,R,Z = map(float, row[:6])
            if not all(map(math.isfinite, (a,b,c,theta,R,Z))) or a+b <= 0 or c <= 0:
                raise ValueError("NONFINITE_OR_DEGENERATE_ELEMENT")
            analytic = 0.5*(a+b)*c
            independent = shoelace(vertices(a,b,c,theta,R,Z))
            errors.append(abs(independent-analytic)/max(abs(analytic),1e-30))
            areas.append(analytic)
            altitudes.append(c)
            base_lengths.append(a+b)
        report["native_mesh_source_file"] = str(sample)
        report["native_mesh_element_count"] = len(areas)
        report["native_mesh_elements_shape"] = list(e.shape)
        report["poloidal_area_total"] = sum(areas)
        report["altitude_sum_not_area"] = sum(altitudes)
        report["poloidal_area_min"] = min(areas)
        report["poloidal_area_max"] = max(areas)
        report["triangle_base_min"] = min(base_lengths)
        report["triangle_base_max"] = max(base_lengths)
        report["triangle_base_coefficient_of_variation"] = statistics.pstdev(base_lengths)/statistics.mean(base_lengths)
        report["max_shoelace_relative_error"] = max(errors)
        report["mean_shoelace_relative_error"] = statistics.mean(errors)
        report["area_to_e2_ratio_min"] = min(0.5*x for x in base_lengths)
        report["area_to_e2_ratio_max"] = max(0.5*x for x in base_lengths)
        report["hdf5_e2_is_area"] = False
        report["analytic_poloidal_geometry_crosscheck_passed"] = max(errors) <= 1e-6
        report["classification"] = ("M3DC1_NATIVE_MESH_POLOIDAL_AREA_CROSSCHECK_COMPLETE"
                                     if report["analytic_poloidal_geometry_crosscheck_passed"]
                                     else "M3DC1_NATIVE_MESH_POLOIDAL_AREA_CROSSCHECK_DISAGREEMENT")
        report["interpretation"] = (
            "Source-defined e[2] is the rotated triangle altitude c, not area. "
            "Independent shoelace areas on an existing native 2-D mesh are compared "
            "with 0.5*(a+b)*c. This replaces the e[2]-as-area proxy with a poloidal "
            "area candidate only; native int1/toroidal quadrature and physical "
            "current/width remain unvalidated."
        )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_MESH_POLOIDAL_AREA_PIPELINE_BLOCKED"
target = out / "native_mesh_poloidal_area_summary.json"
temp = target.with_suffix(".json.tmp")
temp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
temp.replace(target)
print(json.dumps(report, indent=2, sort_keys=True))
if "pipeline_error" in report:
    sys.exit(1)
PY

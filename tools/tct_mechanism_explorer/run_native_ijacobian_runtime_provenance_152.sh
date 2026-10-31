#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
python3 - <<'PY'
"""Read-only native ijacobian effective-setting provenance audit; no solver runs."""
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
native = pathlib.Path("/home/ubuntu/M3DC1-official/unstructured")
parent = "20261030-151-native-int2-weight-jacobian-branch"
parent_path = repo / "validation_runs/m3dc1_tct_native_int2_weight_branch_151/native_int2_weight_jacobian_branch_summary.json"
parent_sha = "dcf2dd9a7ac59ffbe921c57298faa3fc039ba1a054aa049b5514ed6dfd8d9864"
source_sha = {
    "diagnostics.f90": "0ff2dd130798bdc0dc6fce3b026851eebe2e933abfc7293e84dd5c10f2426655",
    "nintegrate_mod.f90": "fd4be567e954d9df18e7ed83d3f622816a48c939832a4b7df700be3746471d00",
    "m3dc1_nint.f90": "15556646264a010de8a416cedc07258b539e013ef6f507ca5e9b60d437e47693",
}
out = repo / "validation_runs/m3dc1_tct_native_ijacobian_runtime_152"
out.mkdir(parents=True, exist_ok=True)
report = {
    "schema_version": 1,
    "job_id": "20261030-152-native-ijacobian-runtime-provenance",
    "parent_result_job_id": parent,
    "saved_run_origin_job_id": "20261029-130-native-current-drive-geometry-weight-sensitivity",
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1",
    "shot_ids": [],
    "classification": "M3DC1_NATIVE_IJACOBIAN_RUNTIME_PROVENANCE_PREREQUISITE_BLOCKED",
    "expected_parent_summary_sha256": parent_sha,
    "expected_native_source_sha256": source_sha,
    "physics_solver_runs": 0,
    "runtime_jacobian_branch_confirmed": False,
    "native_int2_operator_parity_validated": False,
    "physical_current_calibrated": False,
    "causal_segmented_controller_authority_validated": False,
    "pb11_fidelity_validated": False,
    "ignition_or_net_power_validated": False,
    "zero_equivalence_tolerance": 1e-12,
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "claim_boundary": "Saved native run-input/output and source provenance only; no independent int2 parity, physical-current conservation, causal segmented TCT, experimental-shot handoff, p-B11 or net power.",
    "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
}
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

try:
    if not parent_path.is_file() or sha(parent_path) != parent_sha:
        report["prerequisite_blocker"] = "PARENT_SUMMARY_MISSING_OR_CHANGED"
    else:
        prior = json.loads(parent_path.read_text())
        if prior.get("classification") != "M3DC1_NATIVE_INT2_WEIGHT_JACOBIAN_SOURCE_PATH_AUDIT_COMPLETE":
            report["prerequisite_blocker"] = "PARENT_CLASSIFICATION_CHANGED"
        else:
            bad = [name for name, digest in source_sha.items()
                   if not (native / name).is_file() or sha(native / name) != digest]
            if bad:
                report["prerequisite_blocker"] = "NATIVE_SOURCE_MISSING_OR_CHANGED"
                report["missing_or_changed_source"] = bad
            else:
                source_hits = []
                source_files_scanned = 0
                for path in sorted(native.iterdir()):
                    if not path.is_file() or path.suffix.lower() not in (".f90", ".f", ".inc", ".f95", ".for"):
                        continue
                    if path.stat().st_size > 2_000_000:
                        continue
                    source_files_scanned += 1
                    lines = path.read_text(errors="replace").splitlines()
                    for n, line in enumerate(lines, 1):
                        code = line.split("!", 1)[0].strip()
                        if not re.search(r"\bijacobian\b", code, re.I):
                            continue
                        category = ("assignment" if re.search(r"\bijacobian\s*=", code, re.I)
                                    else "namelist" if re.search(r"\bnamelist\b", code, re.I)
                                    else "conditional" if re.search(r"\bif\s*\(", code, re.I)
                                    else "reference")
                        source_hits.append({"file": path.name, "line": n, "category": category,
                                            "code": code[:250], "sha256": sha(path)})
                report["source_files_scanned"] = source_files_scanned
                report["source_ijacobian_matches"] = len(source_hits)
                report["source_ijacobian_evidence"] = source_hits[:100]

                runroot = pathlib.Path("/tmp/m3dc1_tct_native_geometry_weight_130_runs")
                cases = ("baseline", "same_mode_zero", "full_negative", "full_positive")
                case_evidence = {}
                for case in cases:
                    directory = runroot / case
                    matches = []
                    inspected = 0
                    if directory.is_dir():
                        # Bound file count, depth and bytes; never execute or modify run inputs.
                        for path in sorted(directory.glob("*"))[:200]:
                            if not path.is_file() or path.stat().st_size > 2_000_000:
                                continue
                            if path.suffix.lower() not in ("", ".in", ".dat", ".nml", ".txt", ".cfg", ".log", ".out"):
                                continue
                            inspected += 1
                            for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                                if re.search(r"\bijacobian\b", line, re.I):
                                    effective = re.search(r"\b(?:effective|runtime)\s+ijacobian\s*[:=]\s*([01])\b", line, re.I)
                                    matches.append({"file": path.name, "line": n, "text": line.strip()[:250],
                                                    "sha256": sha(path), "effective_output": bool(effective),
                                                    "value": int(effective.group(1)) if effective else None})
                    case_evidence[case] = {
                        "directory_present": directory.is_dir(),
                        "files_inspected": inspected,
                        "ijacobian_matches": matches[:30],
                    }
                report["saved_case_runtime_evidence"] = case_evidence
                effective_by_case = {}
                for case, evidence in case_evidence.items():
                    values = {m["value"] for m in evidence["ijacobian_matches"] if m["effective_output"]
                              and pathlib.Path(m["file"]).suffix.lower() in (".log", ".out")}
                    if len(values) == 1:
                        effective_by_case[case] = next(iter(values))
                report["effective_runtime_values_by_case"] = effective_by_case
                report["runtime_jacobian_branch_confirmed"] = len(effective_by_case) == len(cases)
                report["source_ijacobian_path_traceable"] = bool(source_hits)
                if source_hits:
                    report["classification"] = "M3DC1_NATIVE_IJACOBIAN_RUNTIME_PROVENANCE_AUDIT_COMPLETE"
                    report["interpretation"] = (
                        "Native ijacobian declarations, assignments and conditionals were inventoried. "
                        "An absent input override is not evidence of an executed default. "
                        "Effective branch is confirmed only for cases with explicit effective/runtime "
                        "ijacobian output; otherwise native int2 parity remains prerequisite-blocked."
                    )
                else:
                    report["prerequisite_blocker"] = "IJACOBIAN_SOURCE_PATH_UNRESOLVED"
except Exception as exc:
    report["classification"] = "M3DC1_NATIVE_IJACOBIAN_RUNTIME_PROVENANCE_PIPELINE_BLOCKED"
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)

target = out / "native_ijacobian_runtime_provenance_summary.json"
temp = target.with_suffix(".json.tmp")
temp.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
temp.replace(target)
print(json.dumps(report, sort_keys=True, indent=2))
if "pipeline_error" in report:
    sys.exit(1)
PY

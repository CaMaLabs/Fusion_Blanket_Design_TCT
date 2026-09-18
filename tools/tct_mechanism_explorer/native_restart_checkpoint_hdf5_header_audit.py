#!/usr/bin/env python3
"""Inventory the persisted native M3D-C1 restart checkpoint with HDF5 CLI tools.

This audit is intentionally static: it does not execute M3D-C1 or test controller
performance. It repairs the job-025 schema-reader tooling gap without changing
solver physics or validation gates.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/ubuntu/work/openmc/sweep")
CAP = REPO / "validation_runs/m3dc1_tct_native_restart_checkpoint_capture/captured"
PARENT_SUMMARY = REPO / "validation_runs/m3dc1_tct_native_restart_checkpoint_capture/native_restart_checkpoint_capture_summary.json"
OUT = REPO / "validation_runs/m3dc1_tct_native_restart_checkpoint_hdf5_header"
SUMMARY = OUT / "native_restart_checkpoint_hdf5_header_summary.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_header_objects(text: str) -> dict[str, int]:
    return {
        "groups": len(re.findall(r"^\s*GROUP\s+", text, re.MULTILINE)),
        "datasets": len(re.findall(r"^\s*DATASET\s+", text, re.MULTILINE)),
        "attributes": len(re.findall(r"^\s*ATTRIBUTE\s+", text, re.MULTILINE)),
        "external_links": len(re.findall(r"EXTERNAL_LINK|EXTERNAL", text, re.IGNORECASE)),
        "soft_links": len(re.findall(r"SOFTLINK|SOFT_LINK", text, re.IGNORECASE)),
    }


def inspect(path: Path, h5dump: str, expected_sha: str | None) -> dict:
    proc = subprocess.run(
        [h5dump, "-H", str(path)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    header_file = OUT / f"{path.name}.header.txt"
    header_file.write_text(proc.stdout + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else ""))
    actual_sha = sha256(path)
    return {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": actual_sha,
        "expected_sha256_from_job_025": expected_sha,
        "sha256_matches_job_025": expected_sha is None or actual_sha == expected_sha,
        "h5dump_return_code": proc.returncode,
        "header_readable": proc.returncode == 0,
        "header_path": str(header_file.relative_to(REPO)),
        "header_counts": count_header_objects(proc.stdout) if proc.returncode == 0 else {},
        "stderr_tail": proc.stderr[-2000:],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    parent = json.loads(PARENT_SUMMARY.read_text()) if PARENT_SUMMARY.exists() else {}
    expected = {x.get("name"): x.get("sha256") for x in parent.get("artifacts", [])}
    artifacts = sorted(CAP.glob("*.h5")) if CAP.exists() else []
    h5dump = shutil.which("h5dump")

    inspected = []
    if h5dump:
        for path in artifacts:
            inspected.append(inspect(path, h5dump, expected.get(path.name)))

    c1 = next((x for x in inspected if x["name"] == "C1.h5"), None)
    all_sha_match = bool(inspected) and all(x["sha256_matches_job_025"] for x in inspected)
    all_readable = bool(inspected) and all(x["header_readable"] for x in inspected)

    if not artifacts:
        classification = "M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_CAPTURE_MISSING_FOR_SCHEMA_AUDIT"
        pipeline_failure = True
    elif not h5dump:
        classification = "M3DC1_TCT_NATIVE_RESTART_HDF5_SCHEMA_TOOL_UNAVAILABLE"
        pipeline_failure = True
    elif c1 is not None and c1["header_readable"] and all_sha_match and all_readable:
        classification = "M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_HDF5_SCHEMA_READABLE"
        pipeline_failure = False
    elif c1 is not None and c1["header_readable"]:
        classification = "M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_HDF5_SCHEMA_PARTIALLY_READABLE"
        pipeline_failure = False
    else:
        classification = "M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_HDF5_SCHEMA_UNREADABLE"
        pipeline_failure = False

    report = {
        "classification": classification,
        "pipeline_failure": pipeline_failure,
        "parent_job_id": "20260918-025-native-restart-checkpoint-capture",
        "audit_scope": "Read the persisted job-025 native checkpoint artifacts with h5dump -H and verify artifact SHA-256 provenance; no M3D-C1 execution and no controller efficacy run.",
        "h5dump_path": h5dump,
        "artifact_count": len(artifacts),
        "artifacts": inspected,
        "zero_equivalence": "NOT_EVALUATED_SCHEMA_AUDIT_ONLY",
        "handoff_equivalence": "NOT_EVALUATED_SCHEMA_AUDIT_ONLY",
        "frozen_width_gate_pct_gt": 0.02,
        "frozen_Jpk_gate_pct_le": 0.1,
        "claim_boundary": "Normalized native M3D-C1 restart artifact/schema provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.",
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }
    SUMMARY.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

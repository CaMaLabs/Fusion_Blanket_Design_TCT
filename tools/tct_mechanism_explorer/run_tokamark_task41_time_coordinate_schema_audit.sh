#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then echo "Missing pinned interpreter: $PY" >&2; exit 2; fi
exec "$PY" - <<'PYCODE'
"""Canonical Task-4.1 coordinate schema audit; no Zarr data chunk reads."""
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("validation_runs/tokamark_task41_time_coordinate_schema_audit")
OUT.mkdir(parents=True, exist_ok=True)
URL = "https://s3.echo.stfc.ac.uk/mast/tokamark/v1/21719.zarr/.zmetadata"
EXPECTED_SHA256 = "92e064bb7cd87203518f452f8a142c4ab45e1325d5eace72b022ef78c3f3d343"
CAP = 262144
source = {"url": URL, "http_status": None, "bytes_read": 0, "sha256": None, "error": None}
metadata = {}
try:
    req = urllib.request.Request(URL, headers={"User-Agent": "TCT-Task41-time-coordinate-schema-audit/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        source["http_status"] = response.status
        raw = response.read(CAP + 1)
    source["bytes_read"] = len(raw)
    if len(raw) > CAP:
        raise ValueError("consolidated_metadata_exceeds_read_cap")
    source["sha256"] = hashlib.sha256(raw).hexdigest()
    if source["sha256"] != EXPECTED_SHA256:
        raise ValueError("source_metadata_sha256_changed_since_job_100")
    document = json.loads(raw)
    if document.get("zarr_consolidated_format") != 1 or not isinstance(document.get("metadata"), dict):
        raise ValueError("not_canonical_zarr_v2_consolidated_metadata")
    metadata = document["metadata"]
except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
    source["error"] = f"{type(exc).__name__}: {exc}"

task = Path("validation_runs/tokamark_group4_task41_metadata_audit/task_4-1.yaml")
task_text = task.read_text(encoding="utf-8")
signals = []
for group, signal in re.findall(r"^\s*-\s*\[\s*([a-z0-9_]+)\s*,\s*([a-z0-9_]+)\s*\]", task_text, flags=re.M):
    if (group, signal) not in signals:
        signals.append((group, signal))
if len(signals) != 18:
    raise SystemExit("Task-4.1 schema drift: expected exactly 18 unique signals")

audit = []
for group, signal in signals:
    stem = f"{group}/{signal}"
    zarray = metadata.get(f"{stem}/.zarray", {})
    zattrs = metadata.get(f"{stem}/.zattrs", {})
    shape = zarray.get("shape") if isinstance(zarray, dict) else None
    dimensions = zattrs.get("_ARRAY_DIMENSIONS") if isinstance(zattrs, dict) else None
    time_dims = [dim for dim in dimensions if isinstance(dim, str) and (dim == "time" or dim.startswith("time_"))] if isinstance(dimensions, list) else []
    time_dim = time_dims[0] if len(time_dims) == 1 else None
    coordinate_path = f"{group}/{time_dim}" if time_dim else None
    coordinate_array = metadata.get(f"{coordinate_path}/.zarray", {}) if coordinate_path else {}
    coordinate_attrs = metadata.get(f"{coordinate_path}/.zattrs", {}) if coordinate_path else {}
    coordinate_shape = coordinate_array.get("shape") if isinstance(coordinate_array, dict) else None
    coordinate_units = coordinate_attrs.get("units") if isinstance(coordinate_attrs, dict) else None
    index = dimensions.index(time_dim) if time_dim and isinstance(dimensions, list) else None
    signal_length = shape[index] if isinstance(shape, list) and index is not None and index < len(shape) else None
    length_consistent = isinstance(coordinate_shape, list) and len(coordinate_shape) == 1 and signal_length == coordinate_shape[0]
    audit.append({
        "group": group, "signal": signal, "canonical_signal_path": stem,
        "signal_shape": shape, "signal_units": zattrs.get("units") if isinstance(zattrs, dict) else None,
        "dimension_names": dimensions, "time_dimension": time_dim, "coordinate_path": coordinate_path,
        "coordinate_shape": coordinate_shape, "coordinate_units": coordinate_units,
        "signal_time_length": signal_length, "coordinate_length_matches_signal": bool(length_consistent),
        "numeric_time_values_read": False, "time_alignment_verified": False
    })
matched = sum(row["coordinate_length_matches_signal"] for row in audit)
units_known = sum(row["coordinate_units"] is not None for row in audit)
classification = ("TOKAMARK_TASK41_TIME_COORDINATE_METADATA_ACCESS_FAILED" if source["error"]
                  else "TOKAMARK_TASK41_TIME_COORDINATE_SCHEMA_MAPPED" if matched == 18
                  else "TOKAMARK_TASK41_TIME_COORDINATE_SCHEMA_INCOMPLETE")
summary = {
    "schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
    "classification": classification,
    "parent_result_job_id": "20261013-100-tokamark-task41-v2-consolidated-metadata-map",
    "machine": "MAST", "shot_ids": [21719], "fuel_track": "fuel_agnostic_control",
    "source": "UKAEA-IBM-STFC TokaMark v1 canonical Zarr-v2, derived from FAIR-MAST",
    "license": "TokaMark CC BY 4.0; underlying FAIR-MAST CC BY-SA 4.0 except where noted",
    "source_metadata": source, "task41_yaml_sha256": hashlib.sha256(task_text.encode()).hexdigest(),
    "task41_unique_signals": 18, "time_coordinate_shape_matches": matched,
    "time_coordinate_units_known": units_known, "time_coordinate_audit": audit,
    "numeric_time_alignment_verified": False, "time_coordinate_chunks_loaded": 0,
    "waveform_chunks_loaded": 0, "shots_analyzed": 0, "events_analyzed": 0,
    "frozen_detector_retuned": False, "temporal_split_unchanged": True,
    "actuator_budgets_ms": {"prebiased_fast": 2.75, "prebiased_nominal": 5.25},
    "pipeline_failure": bool(source["error"]), "scientific_negative": False,
    "mechanism_effect": "neutral", "pb11_fidelity": "not_applicable",
    "claim_boundary": "Coordinate metadata consistency does not validate sampled time coordinates, signal chunks, synchronization, precursor reachability, causal TCT, or p-B11 physics.",
    "next_gate": "If all coordinate lengths match, bounded read of one time-coordinate chunk and one relevant diagnostic chunk with explicit unit and monotonicity checks; no frozen-detector retuning."
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"classification": classification, "coordinate_shape_matches": matched, "coordinate_units_known": units_known, "waveform_chunks_loaded": 0}, sort_keys=True))
if summary["pipeline_failure"]:
    raise SystemExit(3)
PYCODE

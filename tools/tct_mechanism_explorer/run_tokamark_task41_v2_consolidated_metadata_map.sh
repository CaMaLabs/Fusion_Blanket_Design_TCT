#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then echo "Missing pinned interpreter: $PY" >&2; exit 2; fi
exec "$PY" - <<'PYCODE'
"""Read only canonical Task-4.1 Zarr-v2 consolidated metadata; no waveform access."""
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("validation_runs/tokamark_task41_v2_consolidated_metadata_map")
OUT.mkdir(parents=True, exist_ok=True)
URL = "https://s3.echo.stfc.ac.uk/mast/tokamark/v1/21719.zarr/.zmetadata"
TASK = Path("validation_runs/tokamark_group4_task41_metadata_audit/task_4-1.yaml")
CAP = 262144
source = {"url": URL, "status": None, "bytes_read": 0, "content_length": None, "sha256": None, "error": None}
payload = None
try:
    req = urllib.request.Request(URL, headers={"User-Agent": "TCT-Task41-v2-metadata-map/1.0"})
    with urllib.request.urlopen(req, timeout=25) as res:
        source["status"] = res.status
        source["content_length"] = res.headers.get("Content-Length")
        raw = res.read(CAP + 1)
    source["bytes_read"] = len(raw)
    if len(raw) > CAP:
        raise ValueError("consolidated_metadata_exceeds_strict_read_cap")
    source["sha256"] = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw)
except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError, ValueError, UnicodeError) as exc:
    source["error"] = f"{type(exc).__name__}: {exc}"

task_text = TASK.read_text(encoding="utf-8")
task_sha = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
signals = []
for group, signal in re.findall(r"^\s*-\s*\[\s*([a-z0-9_]+)\s*,\s*([a-z0-9_]+)\s*\]", task_text, flags=re.M):
    if [group, signal] not in signals:
        signals.append([group, signal])
if len(signals) != 18:
    raise SystemExit("Task-4.1 schema changed: expected 18 unique signals")

meta = payload.get("metadata", {}) if isinstance(payload, dict) else {}
format_ok = isinstance(meta, dict) and payload.get("zarr_consolidated_format") == 1
matches = []
for group, signal in signals:
    possible = [f"{group}-{signal}", f"{group}/{signal}"]
    selected = next((stem for stem in possible if f"{stem}/.zarray" in meta), None)
    zarray = meta.get(f"{selected}/.zarray", {}) if selected else {}
    zattrs = meta.get(f"{selected}/.zattrs", {}) if selected else {}
    matches.append({
        "group": group, "signal": signal, "canonical_candidates": possible,
        "exact_zarr_v2_path": selected,
        "array_shape": zarray.get("shape") if isinstance(zarray, dict) else None,
        "array_chunks": zarray.get("chunks") if isinstance(zarray, dict) else None,
        "dtype": zarray.get("dtype") if isinstance(zarray, dict) else None,
        "dimension_names": zattrs.get("_ARRAY_DIMENSIONS") if isinstance(zattrs, dict) else None,
        "units": zattrs.get("units") if isinstance(zattrs, dict) else None,
        "timebase_aligned": False,
    })
time_candidates = sorted(k for k in meta if k.endswith("/.zarray") and re.search(r"(?:^|[-_/])time(?:[-_/]|$)", k, re.I))
match_count = sum(m["exact_zarr_v2_path"] is not None for m in matches)
classification = ("TOKAMARK_TASK41_V2_SIGNAL_METADATA_MAPPED" if match_count
    else "TOKAMARK_TASK41_V2_SIGNAL_PATHS_UNRESOLVED") if format_ok else "TOKAMARK_TASK41_V2_METADATA_ACCESS_FAILED"
summary = {
    "schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
    "classification": classification, "parent_result_job_id": "20261012-099-tokamark-task41-public-archive-access-reconciliation",
    "machine": "MAST", "shot_ids": [21719], "fuel_track": "fuel_agnostic_control",
    "source": "UKAEA-IBM-STFC TokaMark v1 canonical S3 Zarr-v2 store, derived from FAIR-MAST",
    "license": "TokaMark CC BY 4.0; underlying FAIR-MAST redistribution terms require verification",
    "canonical_zarr_v2_metadata": source, "task41_yaml_path": str(TASK), "task41_yaml_sha256": task_sha,
    "metadata_entry_count": len(meta) if isinstance(meta, dict) else 0,
    "task41_unique_signals": len(signals), "exact_signal_metadata_matches": match_count,
    "task41_signal_metadata": matches, "timebase_candidate_count": len(time_candidates),
    "timebase_candidates_sample": time_candidates[:80],
    "timebase_alignment_verified": False, "bulk_download_performed": False,
    "waveform_chunks_loaded": 0, "shots_analyzed": 0, "events_analyzed": 0,
    "frozen_detector_retuned": False, "temporal_split_unchanged": True,
    "actuator_budgets_ms": {"prebiased_fast": 2.75, "prebiased_nominal": 5.25},
    "pipeline_failure": not format_ok, "scientific_negative": False,
    "mechanism_effect": "neutral", "pb11_fidelity": "not_applicable",
    "claim_boundary": "Metadata presence is not validated waveform availability, synchronized timing, precursor reachability, causal TCT, native M3D-C1, cross-machine confirmation, or p-B11 physics.",
    "next_gate": "Verify per-signal time coordinates and units, then a bounded read of one diagnostic waveform only if the frozen Task-4.1 temporal split and provenance are preserved."
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps({"classification": classification, "metadata_entry_count": summary["metadata_entry_count"],
                  "exact_signal_metadata_matches": match_count, "timebase_candidate_count": len(time_candidates),
                  "waveform_chunks_loaded": 0}, sort_keys=True))
if summary["pipeline_failure"]:
    raise SystemExit(3)
PYCODE

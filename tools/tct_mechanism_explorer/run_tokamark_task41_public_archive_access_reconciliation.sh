#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then echo "Missing pinned interpreter: $PY" >&2; exit 2; fi

exec "$PY" - <<'PYCODE'
"""Bounded, read-only TokaMark storage-format and public archive access audit."""
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("validation_runs/tokamark_task41_public_archive_access_reconciliation")
OUT.mkdir(parents=True, exist_ok=True)
HF = "https://huggingface.co"
DATASET = "UKAEA-IBM-STFC/tokamark-v1"
S3 = "https://s3.echo.stfc.ac.uk/mast/tokamark/v1/21719.zarr"

def request(url, *, method="GET", limit=0, range_header=None):
    headers = {"User-Agent": "TCT-Task41-public-metadata-audit/1.0"}
    if range_header:
        headers["Range"] = range_header
    result = {
        "url": url,
        "method": method,
        "range_requested": range_header,
        "status": None,
        "content_length": None,
        "content_range": None,
        "content_type": None,
        "bytes_read": 0,
        "body_sha256": None,
        "error": None,
    }
    body = b""
    try:
        req = urllib.request.Request(url, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=18) as res:
            result["status"] = res.status
            result["content_length"] = res.headers.get("Content-Length")
            result["content_range"] = res.headers.get("Content-Range")
            result["content_type"] = res.headers.get("Content-Type")
            if method != "HEAD" and limit > 0:
                body = res.read(limit + 1)
        result["bytes_read"] = len(body)
        if len(body) > limit:
            result["error"] = "metadata_or_range_exceeds_strict_read_cap"
            body = b""
        elif body:
            result["body_sha256"] = hashlib.sha256(body).hexdigest()
    except urllib.error.HTTPError as exc:
        result["status"] = exc.code
        result["error"] = f"HTTPError: {exc.code}"
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result, body

s3 = {}
for suffix in (".zgroup", ".zmetadata", "zarr.json"):
    rec, body = request(f"{S3}/{suffix}", limit=32768)
    if body and suffix in (".zgroup", "zarr.json"):
        try:
            obj = json.loads(body)
            rec["metadata_format"] = (
                "zarr_v2" if suffix == ".zgroup" and obj.get("zarr_format") == 2
                else "zarr_v3" if suffix == "zarr.json" and obj.get("zarr_format") == 3
                else "unrecognized"
            )
        except (ValueError, UnicodeError):
            rec["metadata_format"] = "invalid_json"
    s3[suffix] = rec

listing_url = f"{HF}/api/datasets/{DATASET}/tree/main?recursive=true"
listing, listing_body = request(listing_url, limit=1048576)
batches = []
if listing_body:
    try:
        payload = json.loads(listing_body)
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                path = item.get("path", "")
                size = item.get("size")
                if re.fullmatch(r"batch_\\d{5}\\.tar", path) and isinstance(size, int):
                    batches.append({"path": path, "size_bytes": size})
        else:
            listing["error"] = "unexpected_dataset_tree_schema"
    except (ValueError, UnicodeError) as exc:
        listing["error"] = f"invalid_dataset_tree_json: {exc}"
batches.sort(key=lambda x: (x["size_bytes"], x["path"]))
smallest = batches[0] if batches else None
archive_head = None
archive_range = None
first_tar_member = None
if smallest:
    archive_url = f"{HF}/datasets/{DATASET}/resolve/main/{smallest['path']}"
    archive_head, _ = request(archive_url, method="HEAD")
    archive_range, first_bytes = request(archive_url, limit=512, range_header="bytes=0-511")
    if len(first_bytes) == 512 and first_bytes[257:262] == b"ustar":
        first_tar_member = first_bytes[:100].split(b"\\0", 1)[0].decode("utf-8", errors="replace")

s3_access = any(s3[k]["status"] == 200 for k in (".zgroup", ".zmetadata", "zarr.json"))
hf_range = bool(archive_range and archive_range["status"] == 206 and archive_range["bytes_read"] == 512)
hf_index = bool(batches)
if s3_access:
    classification = "TOKAMARK_TASK41_S3_STORE_METADATA_FORMAT_RESOLVED"
elif hf_range:
    classification = "TOKAMARK_TASK41_HF_ARCHIVE_BOUNDED_ACCESS_CONFIRMED"
elif hf_index:
    classification = "TOKAMARK_TASK41_HF_ARCHIVE_INDEX_CONFIRMED"
else:
    classification = "TOKAMARK_TASK41_PUBLIC_STORAGE_ACCESS_UNRESOLVED"

summary = {
    "schema_version": 1,
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "classification": classification,
    "parent_result_job_id": "20261011-098-tokamark-task41-canonical-s3-metadata-probe",
    "machine": "MAST",
    "shot_ids": [21719],
    "fuel_track": "fuel_agnostic_control",
    "source": "UKAEA-IBM-STFC TokaMark v1, derived from FAIR-MAST",
    "dataset_url": f"{HF}/datasets/{DATASET}",
    "dataset_license": "CC BY 4.0 (check underlying FAIR-MAST redistribution terms)",
    "evidence_class": "storage_format_and_public_archive_metadata",
    "previous_098_result": {
        "classification": "TOKAMARK_TASK41_CANONICAL_S3_METADATA_ACCESS_NOT_ESTABLISHED",
        "v3_root_http_status": 404,
        "v3_task41_signal_metadata_matches": 0,
        "waveform_chunks_loaded": 0,
    },
    "s3_store_probe": s3,
    "hf_dataset_tree_probe": listing,
    "hf_batch_count_listed": len(batches),
    "hf_total_listed_batch_bytes": sum(b["size_bytes"] for b in batches),
    "hf_smallest_batch": smallest,
    "hf_archive_head_probe": archive_head,
    "hf_archive_512_byte_range_probe": archive_range,
    "hf_first_tar_member_if_identifiable": first_tar_member,
    "hf_512_byte_range_confirmed": hf_range,
    "shot_to_archive_membership_verified": False,
    "temporal_split_unchanged": True,
    "bulk_download_performed": False,
    "waveform_chunks_loaded": 0,
    "shots_analyzed": 0,
    "events_analyzed": 0,
    "actuator_budgets_ms": {"prebiased_fast": 2.75, "prebiased_nominal": 5.25},
    "frozen_detector_retuned": False,
    "pipeline_failure": classification.endswith("UNRESOLVED"),
    "scientific_negative": False,
    "mechanism_effect": "neutral",
    "pb11_fidelity": "not_applicable",
    "claim_boundary": (
        "Metadata and access-path audit only. A public archive index is not shot-level "
        "diagnostic availability, timebase alignment, precursor timing, actuator reachability, "
        "causal TCT suppression, independent cross-machine confirmation, or p-B11 validation."
    ),
    "next_gate": (
        "If S3 metadata is accessible, inspect only canonical Task-4.1 diagnostic/time metadata. "
        "Otherwise, if the HF archive is accessible, identify shot-to-batch membership and "
        "download at most one justified batch only after checking free disk, provenance, and "
        "unchanged frozen train/val/test membership. Do not claim shot 21719 is in the smallest batch."
    ),
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps({
    "classification": classification,
    "s3_metadata_access": s3_access,
    "hf_batches_listed": len(batches),
    "hf_512_byte_range_confirmed": hf_range,
    "waveform_chunks_loaded": 0,
}, sort_keys=True))
if summary["pipeline_failure"]:
    raise SystemExit(3)
PYCODE

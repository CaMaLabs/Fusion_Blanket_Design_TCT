#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec "$TCT_PYTHON" - <<'PY'
"""Bounded TCV shot-73927 Thomson-scattering schema audit. No raw signals published."""
import datetime
import hashlib
import io
import json
import pathlib
import re
import struct
import urllib.request
import zlib

URL = "https://zenodo.org/records/19452938/files/FENIX_data.zip?download=1"
PARENT = "20261026-114-tcv-fenix-shot73927-bounded-mat-header-audit"
EXPECTED_SHA256 = "fd787e1ed477a67ae21fdae0bef151e112a72a31d59d7a0c98fc820eaebc3851"
OUT = pathlib.Path("validation_runs/tcv_fenix_shot73927_ts_schema_115")
OUT.mkdir(parents=True, exist_ok=True)
MAX_RANGE = 8 * 1024 * 1024
MAX_EXPANDED = 24 * 1024 * 1024
summary = {
    "schema_version": 1,
    "source_id": "zenodo-19452938-tcv-fenix-experimental-recon",
    "source": URL,
    "machine": "TCV",
    "shot_ids": [73927],
    "diagnostic": "Thomson scattering (TS_73927.mat)",
    "fuel_track": "fuel_agnostic_control",
    "parent_result_job_id": PARENT,
    "classification": "TCV_FENIX_TS_73927_SOURCE_OR_SCHEMA_BLOCKED",
    "diagnostic_units_verified": False,
    "timing_calibrated": False,
    "experimental_waveforms_ingested": False,
    "native_m3dc1_run": False,
    "causal_tct_demonstration": False,
    "license_terms_verified": False,
    "raw_data_published": False,
    "observational_status": "metadata-only; no prospective or controller-in-loop intervention",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "runner_source_sha256": hashlib.sha256(
        pathlib.Path("tools/tct_mechanism_explorer/run_tcv_fenix_shot73927_ts_schema_115.sh").read_bytes()
    ).hexdigest(),
}

def read_range(spec, expected=None):
    request = urllib.request.Request(
        URL, headers={"Range": "bytes=" + spec, "User-Agent": "CaMaLabs-TCT-bounded-TS-schema/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 206:
            raise RuntimeError("HTTP_RANGE_UNSUPPORTED")
        header = response.headers.get("Content-Range", "").strip()
        match = re.fullmatch(r"bytes[ ]+([0-9]+)-([0-9]+)/([0-9]+)", header)
        if not match:
            raise RuntimeError("CONTENT_RANGE_INVALID")
        lo, hi, total = map(int, match.groups())
        count = hi - lo + 1
        if count <= 0 or count > MAX_RANGE or hi >= total:
            raise RuntimeError("RANGE_BOUNDS_GATE")
        if expected is not None and (lo, hi) != expected:
            raise RuntimeError("RANGE_OFFSET_MISMATCH")
        data = response.read(count + 1)
        if len(data) != count:
            raise RuntimeError("RANGE_LENGTH_MISMATCH")
        return data, lo, total

try:
    import numpy as np
    import scipy.io

    tail, _, archive_size = read_range("-65557")
    eocd = tail.rfind(b"PK\x05\x06")
    if eocd < 0 or eocd + 22 > len(tail):
        raise RuntimeError("ZIP_EOCD_MISSING")
    _, disk, cd_disk, disk_count, count, cd_size, cd_offset, _ = struct.unpack_from(
        "<IHHHHIIH", tail, eocd)
    if disk or cd_disk or disk_count != count or count == 65535 or cd_offset == 0xffffffff:
        raise RuntimeError("ZIP64_OR_MULTIDISK_UNSUPPORTED")
    if cd_size < 46 or cd_size > MAX_RANGE:
        raise RuntimeError("ZIP_CENTRAL_DIRECTORY_BOUNDS")
    directory, _, _ = read_range(
        str(cd_offset) + "-" + str(cd_offset + cd_size - 1),
        (cd_offset, cd_offset + cd_size - 1))
    entries = []
    offset = 0
    while offset < len(directory):
        if offset + 46 > len(directory):
            raise RuntimeError("ZIP_CENTRAL_DIRECTORY_TRUNCATED")
        row = struct.unpack_from("<IHHHHHHIIIHHHHHII", directory, offset)
        if row[0] != 0x02014b50:
            raise RuntimeError("ZIP_CENTRAL_DIRECTORY_SIGNATURE")
        nlen, xlen, clen = row[10:13]
        end = offset + 46 + nlen + xlen + clen
        if end > len(directory):
            raise RuntimeError("ZIP_MEMBER_METADATA_TRUNCATED")
        name = directory[offset + 46:offset + 46 + nlen].decode("utf-8", "replace")
        if name == "TS_73927.mat" or name.endswith("/TS_73927.mat"):
            entries.append((name, row))
        offset = end
    if len(entries) != 1:
        raise RuntimeError("TS_MEMBER_MISSING_OR_AMBIGUOUS")
    name, row = entries[0]
    flags, method, crc, compressed, expanded, local_offset = (
        row[3], row[4], row[7], row[8], row[9], row[16])
    if flags & 1 or method not in (0, 8) or not (0 < compressed <= MAX_RANGE):
        raise RuntimeError("TS_MEMBER_COMPRESSION_GATE")
    if not (128 <= expanded <= MAX_EXPANDED):
        raise RuntimeError("TS_MEMBER_EXPANDED_SIZE_GATE")
    local, _, _ = read_range(
        str(local_offset) + "-" + str(local_offset + 29),
        (local_offset, local_offset + 29))
    if struct.unpack_from("<I", local)[0] != 0x04034b50:
        raise RuntimeError("ZIP_LOCAL_HEADER_INVALID")
    lflags, lmethod = struct.unpack_from("<HH", local, 6)
    nlen, xlen = struct.unpack_from("<HH", local, 26)
    if lflags != flags or lmethod != method:
        raise RuntimeError("ZIP_LOCAL_CENTRAL_MISMATCH")
    start = local_offset + 30 + nlen + xlen
    if start + compressed > archive_size:
        raise RuntimeError("ZIP_MEMBER_ARCHIVE_BOUNDARY")
    payload, _, _ = read_range(str(start) + "-" + str(start + compressed - 1),
                               (start, start + compressed - 1))
    if method == 0:
        data = payload
    else:
        decoder = zlib.decompressobj(-15)
        data = decoder.decompress(payload, MAX_EXPANDED + 1)
        if len(data) > MAX_EXPANDED or not decoder.eof:
            raise RuntimeError("ZIP_DECOMPRESSION_GATE")
        data += decoder.flush()
    if len(data) != expanded or (zlib.crc32(data) & 0xffffffff) != crc:
        raise RuntimeError("ZIP_CRC_OR_SIZE_MISMATCH")
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError("SOURCE_MEMBER_SHA_CHANGED_FROM_JOB_114")
    if not (data.startswith(b"MATLAB 5.0 MAT-file") and data[126:128] in (b"IM", b"MI")):
        raise RuntimeError("MAT_V5_FORMAT_MISMATCH")
    mat = scipy.io.loadmat(io.BytesIO(data), squeeze_me=True,
                           struct_as_record=False, verify_compressed_data_integrity=True)
    summary["archive_size_bytes"] = archive_size
    summary["verified_member"] = {"name": name, "sha256": digest,
                                  "crc32_verified": True, "format": "MATLAB_v5",
                                  "compressed_bytes": compressed,
                                  "uncompressed_bytes": expanded}
    fields = []
    time_candidates = []
    unit_hints = []
    limit = 160

    def visit(value, path, depth):
        if len(fields) >= limit or depth > 5:
            return
        if hasattr(value, "_fieldnames"):
            names = list(value._fieldnames or [])
            fields.append({"path": path, "kind": "struct", "field_count": len(names)})
            for key in names[:80]:
                visit(getattr(value, key), path + "." + key, depth + 1)
            return
        if isinstance(value, np.ndarray):
            fields.append({"path": path, "kind": "array", "shape": list(value.shape),
                           "dtype": str(value.dtype)})
            if re.search(r"(^|[._])(t|time|times|timestamp|clock)([._]|$)", path, re.I) and \
                    value.dtype.kind in "fiu" and 1 < value.size <= 100000:
                x = np.asarray(value, dtype=float).reshape(-1)
                if np.isfinite(x).all():
                    diffs = np.diff(x)
                    time_candidates.append({
                        "path": path, "count": int(x.size), "raw_min": float(x.min()),
                        "raw_max": float(x.max()), "monotonic_nondecreasing": bool((diffs >= 0).all()),
                        "raw_median_step": float(np.median(diffs)),
                        "units_verified": False, "clock_reference_verified": False
                    })
            if value.dtype.kind == "O":
                for index, item in enumerate(value.flat):
                    if index >= 4 or len(fields) >= limit:
                        break
                    visit(item, path + "[" + str(index) + "]", depth + 1)
            return
        if isinstance(value, (str, bytes)):
            if re.search(r"unit|label|description|timebase", path, re.I):
                unit_hints.append({"path": path, "text": str(value)[:100]})
            else:
                fields.append({"path": path, "kind": "text", "length": len(value)})
            return
        if isinstance(value, (np.number, int, float)):
            fields.append({"path": path, "kind": "numeric_scalar",
                           "dtype": type(value).__name__})
            return
        fields.append({"path": path, "kind": type(value).__name__})

    for key in sorted(k for k in mat if not k.startswith("__")):
        visit(mat[key], key, 0)
    summary["field_inventory"] = fields
    summary["inventory_truncated"] = len(fields) >= limit
    summary["raw_time_candidates"] = time_candidates[:30]
    summary["unit_label_hints_unverified"] = unit_hints[:30]
    summary["classification"] = "TCV_FENIX_TS_73927_NESTED_SCHEMA_INVENTORIED"
    summary["next_step"] = (
        "Establish source-documented time units and diagnostic clock reference, "
        "then calibrate candidate axes; do not infer time units from numeric ranges.")
except Exception as exc:
    summary["error"] = (type(exc).__name__ + ": " + str(exc))[:500]
with (OUT / "summary.json").open("w", encoding="utf-8") as output:
    json.dump(summary, output, indent=2, sort_keys=True)
    output.write(chr(10))
print(json.dumps(summary, indent=2, sort_keys=True))
PY

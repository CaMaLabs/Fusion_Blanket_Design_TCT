#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec "$TCT_PYTHON" - <<'PY'
"""Bounded TCV 73927 LIUQE timebase compatibility audit; metadata only."""
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
PARENT = "20261026-116-tcv-fenix-shot73927-plot-script-timebase-provenance"
OUT = pathlib.Path("validation_runs/tcv_fenix_shot73927_liuqe_timebase_117")
OUT.mkdir(parents=True, exist_ok=True)
MAX_RANGE = 40 * 1024 * 1024
MAX_EXPANDED = 48 * 1024 * 1024
EXPECTED_ARCHIVE_SIZE = 2444897347
EXPECTED_COMPRESSED = 32864020
EXPECTED_EXPANDED = 32880432
summary = {
    "schema_version": 1,
    "source_id": "zenodo-19452938-tcv-fenix-experimental-recon",
    "source": URL,
    "machine": "TCV",
    "shot_ids": [73927],
    "diagnostic": "LIUQE equilibrium reconstruction paired with TS_73927.mat",
    "fuel_track": "fuel_agnostic_control",
    "parent_result_job_id": PARENT,
    "classification": "TCV_FENIX_LIUQE_73927_SOURCE_OR_SCHEMA_BLOCKED",
    "diagnostic_units_verified": False,
    "clock_reference_verified": False,
    "timing_calibrated": False,
    "experimental_waveforms_ingested": False,
    "native_m3dc1_run": False,
    "causal_tct_demonstration": False,
    "raw_data_published": False,
    "observational_status": "metadata-only comparison of experimental TS and reconstructed LIUQE candidate axes; not prospective or controller-in-loop",
    "parent_ts_time_min_raw": 0.017340000718832016,
    "parent_ts_time_max_raw": 2.9673399925231934,
    "parent_ts_median_step_raw": 0.01699995994567871,
    "parent_ts_time_points": 178,
    "parent_plot_script_sha256": "f895cfa6ebc2ff15ba6ed43f924369cfbecdf168a974f242dd2392a91fa1fce3",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "runner_source_sha256": hashlib.sha256(pathlib.Path(
        "tools/tct_mechanism_explorer/run_tcv_fenix_shot73927_liuqe_timebase_117.sh"
    ).read_bytes()).hexdigest(),
}

def read_range(spec, expected=None):
    request = urllib.request.Request(URL, headers={
        "Range": "bytes=" + spec,
        "User-Agent": "CaMaLabs-TCT-bounded-LIUQE-timebase/1.0",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 206:
            raise RuntimeError("HTTP_RANGE_UNSUPPORTED")
        match = re.fullmatch(r"bytes[ ]+([0-9]+)-([0-9]+)/([0-9]+)",
                             response.headers.get("Content-Range", "").strip())
        if not match:
            raise RuntimeError("CONTENT_RANGE_INVALID")
        lo, hi, total = map(int, match.groups())
        count = hi - lo + 1
        if total != EXPECTED_ARCHIVE_SIZE or count <= 0 or count > MAX_RANGE or hi >= total:
            raise RuntimeError("ARCHIVE_OR_RANGE_BOUNDS_CHANGED")
        if expected is not None and (lo, hi) != expected:
            raise RuntimeError("RANGE_OFFSET_MISMATCH")
        data = response.read(count + 1)
        if len(data) != count:
            raise RuntimeError("RANGE_LENGTH_MISMATCH")
        return data, lo

try:
    import numpy as np
    import scipy.io

    tail, _ = read_range("-65557")
    eocd = tail.rfind(b"PK\x05\x06")
    if eocd < 0 or eocd + 22 > len(tail):
        raise RuntimeError("ZIP_EOCD_MISSING")
    _, disk, cd_disk, disk_count, count, cd_size, cd_offset, _ = struct.unpack_from(
        "<IHHHHIIH", tail, eocd)
    if disk or cd_disk or disk_count != count or count == 65535 or cd_offset == 0xffffffff:
        raise RuntimeError("ZIP64_OR_MULTIDISK_UNSUPPORTED")
    if cd_size < 46 or cd_size > MAX_RANGE:
        raise RuntimeError("ZIP_CENTRAL_DIRECTORY_BOUNDS")
    directory, _ = read_range(
        str(cd_offset) + "-" + str(cd_offset + cd_size - 1),
        (cd_offset, cd_offset + cd_size - 1))
    matches = []
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
        if name == "KER_73927_LIUQE.mat" or name.endswith("/KER_73927_LIUQE.mat"):
            matches.append((name, row))
        offset = end
    if len(matches) != 1:
        raise RuntimeError("LIUQE_MEMBER_MISSING_OR_AMBIGUOUS")
    name, row = matches[0]
    flags, method, crc, compressed, expanded, local_offset = (
        row[3], row[4], row[7], row[8], row[9], row[16])
    if flags & 1 or method not in (0, 8):
        raise RuntimeError("LIUQE_MEMBER_COMPRESSION_GATE")
    if compressed != EXPECTED_COMPRESSED or expanded != EXPECTED_EXPANDED:
        raise RuntimeError("LIUQE_MEMBER_SIZE_CHANGED_FROM_JOB_114")
    if compressed > MAX_RANGE or expanded > MAX_EXPANDED:
        raise RuntimeError("LIUQE_MEMBER_BOUNDS_GATE")
    local, _ = read_range(str(local_offset) + "-" + str(local_offset + 29),
                          (local_offset, local_offset + 29))
    if struct.unpack_from("<I", local)[0] != 0x04034b50:
        raise RuntimeError("ZIP_LOCAL_HEADER_INVALID")
    lflags, lmethod = struct.unpack_from("<HH", local, 6)
    nlen, xlen = struct.unpack_from("<HH", local, 26)
    if lflags != flags or lmethod != method:
        raise RuntimeError("ZIP_LOCAL_CENTRAL_MISMATCH")
    start = local_offset + 30 + nlen + xlen
    if start + compressed > EXPECTED_ARCHIVE_SIZE:
        raise RuntimeError("ZIP_MEMBER_ARCHIVE_BOUNDARY")
    payload, _ = read_range(str(start) + "-" + str(start + compressed - 1),
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
    if not (data.startswith(b"MATLAB 5.0 MAT-file") and data[126:128] in (b"IM", b"MI")):
        raise RuntimeError("MAT_V5_FORMAT_MISMATCH")
    mat = scipy.io.loadmat(io.BytesIO(data), squeeze_me=True,
                           struct_as_record=False, verify_compressed_data_integrity=True)
    summary["verified_member"] = {
        "name": name, "sha256": hashlib.sha256(data).hexdigest(),
        "crc32_verified": True, "compressed_bytes": compressed,
        "uncompressed_bytes": expanded, "format": "MATLAB_v5"
    }
    summary["top_level_variables"] = sorted(k for k in mat if not k.startswith("__"))
    fields = []
    candidates = []
    max_fields = 240

    def visit(value, path, depth):
        if depth > 6 or len(fields) >= max_fields:
            return
        if hasattr(value, "_fieldnames"):
            names = list(value._fieldnames or [])
            fields.append({"path": path, "kind": "struct", "field_count": len(names)})
            for key in names[:80]:
                visit(getattr(value, key), path + "." + key, depth + 1)
            return
        if isinstance(value, np.ndarray):
            fields.append({"path": path, "kind": "array",
                           "shape": list(value.shape), "dtype": str(value.dtype)})
            if (re.search(r"(^|[._])(t|time|times|timestamp|clock)([._]|$)", path, re.I)
                    and value.dtype.kind in "fiu" and 2 <= value.size <= 200000):
                a = np.asarray(value, dtype=float).reshape(-1)
                if np.isfinite(a).all():
                    diffs = np.diff(a)
                    lo, hi = float(a.min()), float(a.max())
                    candidates.append({
                        "path": path, "count": int(a.size),
                        "raw_min": lo, "raw_max": hi,
                        "monotonic_nondecreasing": bool((diffs >= 0).all()),
                        "raw_median_step": float(np.median(diffs)),
                        "numeric_overlap_with_ts_raw": bool(
                            max(lo, summary["parent_ts_time_min_raw"]) <=
                            min(hi, summary["parent_ts_time_max_raw"])),
                        "units_verified": False, "clock_reference_verified": False
                    })
            if value.dtype.kind == "O":
                for i, item in enumerate(value.flat):
                    if i >= 8 or len(fields) >= max_fields:
                        break
                    visit(item, path + "[" + str(i) + "]", depth + 1)
            return
        if isinstance(value, (np.number, int, float, str, bytes)):
            fields.append({"path": path, "kind": "scalar_or_text",
                           "type": type(value).__name__})
            return
        fields.append({"path": path, "kind": type(value).__name__})

    for key in summary["top_level_variables"]:
        visit(mat[key], key, 0)
    summary["field_inventory"] = fields
    summary["field_inventory_truncated"] = len(fields) >= max_fields
    summary["candidate_time_axes"] = candidates[:40]
    summary["candidate_time_axes_truncated"] = len(candidates) > 40
    summary["classification"] = (
        "TCV_FENIX_LIUQE_73927_TIMEBASE_CANDIDATES_INVENTORIED" if candidates
        else "TCV_FENIX_LIUQE_73927_TIMEBASE_SCHEMA_UNRESOLVED"
    )
    summary["next_step"] = (
        "Compare documented TS/LIUQE time origin and trigger reference from primary "
        "TCV diagnostic records; numerical overlap alone is not synchronization. "
        "Do not infer M3D-C1 handoff or controller authority."
    )
except Exception as exc:
    summary["error"] = (type(exc).__name__ + ": " + str(exc))[:500]
with (OUT / "summary.json").open("w", encoding="utf-8") as output:
    json.dump(summary, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

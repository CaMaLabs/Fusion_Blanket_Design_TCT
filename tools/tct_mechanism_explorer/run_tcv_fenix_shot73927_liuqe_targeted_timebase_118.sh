#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec "$TCT_PYTHON" - <<'PY'
"""Targeted LIUQE LY/LX timebase audit; metadata only."""
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
PARENT = "20261026-117-tcv-fenix-shot73927-liuqe-timebase-compatibility-audit"
OUT = pathlib.Path("validation_runs/tcv_fenix_shot73927_liuqe_targeted_timebase_118")
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
    "classification": "TCV_FENIX_LIUQE_73927_TARGETED_TIMEBASE_SOURCE_BLOCKED",
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
        "tools/tct_mechanism_explorer/run_tcv_fenix_shot73927_liuqe_targeted_timebase_118.sh"
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
    if summary["verified_member"]["sha256"] != "7498fcd8b714c0a4d10292043e49d15e413821e60b6ed66618a82f5b306d37d9":
        raise RuntimeError("LIUQE_SOURCE_SHA256_CHANGED")
    # Job 117's breadth-first field limit was reached inside L.P before
    # top-level LY and LX could be inspected. Target these documented structures.
    summary["parent_117_field_inventory_truncated"] = True
    summary["parent_117_candidate_time_axes"] = 0
    summary["target_structures"] = {}
    candidates = []
    for root in ("L", "LX", "LY"):
        obj = mat.get(root)
        names = list(getattr(obj, "_fieldnames", []) or [])
        summary["target_structures"][root] = {
            "present": obj is not None,
            "field_count": len(names),
            "time_named_fields": [n for n in names if re.search(
                r"(^|_)(t|time|times|timestamp|clock)(_|$)", n, re.I)],
            "selected_field_names": [n for n in names if n in (
                "t", "time", "times", "T", "shot", "tokamak", "psi", "psirz")],
        }
        for key in ("t", "T", "time", "times", "timestamp", "clock"):
            if key not in names:
                continue
            val = np.asarray(getattr(obj, key))
            descriptor = {"path": root + "." + key, "shape": list(val.shape),
                          "dtype": str(val.dtype), "units_verified": False,
                          "clock_reference_verified": False}
            if val.dtype.kind not in "fiu" or val.size < 2 or val.size > 200000:
                descriptor["candidate_status"] = "not_bounded_numeric_vector"
                candidates.append(descriptor)
                continue
            a = np.asarray(val, dtype=float).reshape(-1)
            if not np.isfinite(a).all():
                descriptor["candidate_status"] = "nonfinite_values"
                candidates.append(descriptor)
                continue
            diffs = np.diff(a)
            lo, hi = float(a.min()), float(a.max())
            descriptor.update({
                "candidate_status": "numeric_unverified_timebase",
                "count": int(a.size), "raw_min": lo, "raw_max": hi,
                "raw_median_step": float(np.median(diffs)),
                "monotonic_nondecreasing": bool((diffs >= 0).all()),
                "numeric_overlap_with_ts_raw": bool(
                    max(lo, summary["parent_ts_time_min_raw"]) <=
                    min(hi, summary["parent_ts_time_max_raw"])),
            })
            candidates.append(descriptor)
    summary["candidate_time_axes"] = candidates
    summary["classification"] = (
        "TCV_FENIX_LIUQE_73927_TARGETED_TIMEBASE_CANDIDATES_INVENTORIED"
        if any(c.get("candidate_status") == "numeric_unverified_timebase" for c in candidates)
        else "TCV_FENIX_LIUQE_73927_TARGETED_TIMEBASE_UNRESOLVED"
    )
    summary["next_step"] = (
        "Use original TCV shot-trigger and LIUQE/TS diagnostic documentation to "
        "verify time origin and synchronization. Numeric overlap, monotonicity "
        "and source plotting references do not establish clock calibration; "
        "no native M3D-C1 handoff or TCT intervention is implied."
    )
except Exception as exc:
    summary["error"] = (type(exc).__name__ + ": " + str(exc))[:500]
with (OUT / "summary.json").open("w", encoding="utf-8") as output:
    json.dump(summary, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec "$TCT_PYTHON" - <<'PY'
"""Bounded TCV 73927 source plotting script timebase provenance audit. No raw signals."""
import datetime
import hashlib
import json
import pathlib
import re
import struct
import urllib.request
import zlib

URL = "https://zenodo.org/records/19452938/files/FENIX_data.zip?download=1"
PARENT = "20261026-115-tcv-fenix-shot73927-ts-schema-timing-audit"
OUT = pathlib.Path("validation_runs/tcv_fenix_shot73927_plot_timebase_116")
OUT.mkdir(parents=True, exist_ok=True)
MAX_RANGE = 8 * 1024 * 1024
MAX_EXPANDED = 24 * 1024 * 1024
summary = {
    "schema_version": 1,
    "source_id": "zenodo-19452938-tcv-fenix-experimental-recon",
    "source": URL,
    "machine": "TCV",
    "shot_ids": [73927],
    "diagnostic": "TCV 73927 plotting_73927.m provenance for TS and equilibrium timing",
    "fuel_track": "fuel_agnostic_control",
    "parent_result_job_id": PARENT,
    "classification": "TCV_FENIX_73927_PLOTTING_SCRIPT_SOURCE_BLOCKED",
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
        pathlib.Path("tools/tct_mechanism_explorer/run_tcv_fenix_shot73927_plot_timebase_116.sh").read_bytes()
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
        if name == "plotting_73927.m" or name.endswith("/plotting_73927.m"):
            entries.append((name, row))
        offset = end
    if len(entries) != 1:
        raise RuntimeError("PLOT_SCRIPT_MISSING_OR_AMBIGUOUS")
    name, row = entries[0]
    flags, method, crc, compressed, expanded, local_offset = (
        row[3], row[4], row[7], row[8], row[9], row[16])
    if flags & 1 or method not in (0, 8) or not (0 < compressed <= MAX_RANGE):
        raise RuntimeError("PLOT_SCRIPT_COMPRESSION_GATE")
    if not (128 <= expanded <= MAX_EXPANDED):
        raise RuntimeError("PLOT_SCRIPT_EXPANDED_SIZE_GATE")
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

    # Source code is read only to find documented timing and synchronization
    # references. Do not execute MATLAB code or publish diagnostic arrays.
    source = data.decode("utf-8", "replace")
    lines = source.splitlines()
    patterns = {
        "time_unit": re.compile(r"(?i)(time.?unit|\bseconds?\b|\bmilliseconds?\b|\bms\b|\bsec\b)"),
        "time_axis": re.compile(r"(?i)(\btime\b|\bt_?0\b|\bt_?start\b|\bxlim\b|\btimes?\b)"),
        "clock_origin": re.compile(r"(?i)(trigger|offset|reference.?time|clock|discharge.?start|shot.?start)"),
        "diagnostic": re.compile(r"(?i)(TS_73927|\bTS\b|thomson|ne_fit|te_raw|KER_73927|LIUQE|ASTRA)"),
    }
    hits = []
    for number, line in enumerate(lines, 1):
        kinds = [label for label, regex in patterns.items() if regex.search(line)]
        if kinds:
            # Small source excerpts for human verification; no raw experimental signals.
            hits.append({"line": number, "topics": kinds, "excerpt": line.strip()[:180]})
    summary["source_script"] = {
        "member": name, "sha256": digest, "crc32_verified": True,
        "compressed_bytes": compressed, "uncompressed_bytes": expanded,
        "line_count": len(lines), "keyword_hit_count": len(hits),
        "keyword_hits": hits[:60], "keyword_hits_truncated": len(hits) > 60,
    }
    summary["parent_ts_member_sha256"] = "fd787e1ed477a67ae21fdae0bef151e112a72a31d59d7a0c98fc820eaebc3851"
    summary["parent_ts_time_axis_label"] = "s (unverified source label)"
    summary["parent_ts_time_points"] = 178
    summary["parent_ts_raw_median_step"] = 0.01699995994567871
    summary["clock_reference_verified"] = False
    summary["diagnostic_units_verified"] = False
    summary["timing_calibrated"] = False
    summary["license_terms_verified"] = False
    summary["classification"] = "TCV_FENIX_73927_PLOTTING_SCRIPT_PROVENANCE_AUDITED"
    summary["next_step"] = (
        "Manually adjudicate any explicit unit/clock references in verified plotting "
        "script against TS label 's' and original TCV diagnostic documentation; "
        "do not promote timing calibration from source keyword matches alone."
    )
except Exception as exc:
    summary["error"] = (type(exc).__name__ + ": " + str(exc))[:500]
with (OUT / "summary.json").open("w", encoding="utf-8") as output:
    json.dump(summary, output, indent=2, sort_keys=True)
    output.write(chr(10))
print(json.dumps(summary, indent=2, sort_keys=True))
PY

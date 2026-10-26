#!/usr/bin/env bash
set -euo pipefail
cd "${TCT_PIPELINE_REPO:-$(git rev-parse --show-toplevel)}"
export TCT_RUNNER_SOURCE_PATH="$PWD/tools/tct_mechanism_explorer/run_tcv_fenix_shot73927_mat_header_114.sh"
exec "${TCT_PYTHON:-python3}" - <<'PY'
"""Bounded source gate: inspect one TCV FENIX shot 73927 MAT header, never publish raw data."""
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
OUT = pathlib.Path("validation_runs/tcv_fenix_shot73927_mat_header_114")
OUT.mkdir(parents=True, exist_ok=True)
MAX_RANGE = 8 * 1024 * 1024
MAX_UNCOMPRESSED = 24 * 1024 * 1024
summary = {
    "schema_version": 1,
    "source_id": "zenodo-19452938-tcv-fenix-experimental-recon",
    "source": URL,
    "machine": "TCV",
    "shot_ids": [73927],
    "fuel_track": "fuel_agnostic_control",
    "parent_result_job_id": "20261026-113-tcv-fenix-zenodo-archive-index-parser-repair",
    "classification": "TCV_FENIX_MAT_MEMBER_SOURCE_GATE_BLOCKED",
    "license_terms_verified": False,
    "diagnostic_units_verified": False,
    "timing_calibrated": False,
    "experimental_waveforms_ingested": False,
    "native_m3dc1_run": False,
    "causal_tct_demonstration": False,
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "runner_source_sha256": hashlib.sha256(pathlib.Path("tools/tct_mechanism_explorer/run_tcv_fenix_shot73927_mat_header_114.sh").read_bytes()).hexdigest(),
}
def get_range(spec, expected=None):
    req = urllib.request.Request(URL, headers={
        "Range": "bytes=" + spec, "User-Agent": "CaMaLabs-TCT-bounded-mat-preflight/1.0"
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        if resp.status != 206:
            raise RuntimeError("HTTP_RANGE_UNSUPPORTED: refused non-206 full-archive response")
        header = resp.headers.get("Content-Range", "").strip()
        match = re.fullmatch(r"bytes[ ]+([0-9]+)-([0-9]+)/([0-9]+)", header)
        if not match:
            raise RuntimeError("CONTENT_RANGE_INVALID: " + header[:150])
        lo, hi, total = map(int, match.groups())
        n = hi - lo + 1
        if n <= 0 or n > MAX_RANGE or hi >= total:
            raise RuntimeError("RANGE_SIZE_OR_BOUNDS_GATE")
        if expected is not None and (lo, hi) != expected:
            raise RuntimeError("CONTENT_RANGE_OFFSET_MISMATCH")
        data = resp.read(n + 1)
        if len(data) != n:
            raise RuntimeError("RANGE_LENGTH_MISMATCH")
        return data, lo, total

try:
    # Public record metadata is advisory; presence of a license identifier is not a rights audit.
    try:
        req = urllib.request.Request("https://zenodo.org/api/records/19452938",
                                     headers={"User-Agent": "CaMaLabs-TCT-source-provenance/1.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            metadata_bytes = response.read(1024 * 1024 + 1)
        if len(metadata_bytes) > 1024 * 1024:
            raise RuntimeError("RECORD_METADATA_SIZE_GATE")
        record = json.loads(metadata_bytes)
        metadata = record.get("metadata", {})
        license_value = metadata.get("license")
        summary["zenodo_license_metadata"] = license_value
        summary["zenodo_record_id"] = record.get("id")
    except Exception as exc:
        summary["zenodo_metadata_access_error"] = str(exc)[:250]

    tail, start, total = get_range("-65557")
    pos = tail.rfind(b"PK\x05\x06")
    if pos < 0 or pos + 22 > len(tail):
        raise RuntimeError("ZIP_EOCD_MISSING")
    fields = struct.unpack_from("<IHHHHIIH", tail, pos)
    _, disk, cd_disk, disk_count, count, cd_size, cd_offset, comment_len = fields
    if disk or cd_disk or disk_count != count or count == 65535 or cd_offset == 0xffffffff:
        raise RuntimeError("ZIP64_OR_MULTIDISK_UNSUPPORTED")
    if cd_size < 46 or cd_size > MAX_RANGE:
        raise RuntimeError("CENTRAL_DIRECTORY_SIZE_GATE")
    directory, _, _ = get_range(f"{cd_offset}-{cd_offset+cd_size-1}",
                                (cd_offset, cd_offset+cd_size-1))
    entries = {}
    i = 0
    while i < len(directory):
        if i + 46 > len(directory):
            raise RuntimeError("CENTRAL_DIRECTORY_TRUNCATED")
        row = struct.unpack_from("<IHHHHHHIIIHHHHHII", directory, i)
        if row[0] != 0x02014b50:
            raise RuntimeError("CENTRAL_DIRECTORY_SIGNATURE_MISMATCH")
        name_len, extra_len, comment_len = row[10:13]
        name_end = i + 46 + name_len
        if name_end + extra_len + comment_len > len(directory):
            raise RuntimeError("CENTRAL_DIRECTORY_MEMBER_TRUNCATED")
        name = directory[i+46:name_end].decode("utf-8", "replace")
        entries[name] = {
            "flags": row[3], "method": row[4], "crc32": row[7],
            "compressed_bytes": row[8], "uncompressed_bytes": row[9],
            "local_offset": row[16]
        }
        i = name_end + extra_len + comment_len
    summary["archive_size_bytes"] = total
    summary["central_directory_entries"] = len(entries)
    def match(suffix):
        found = [(name, row) for name, row in entries.items()
                 if name == suffix or name.endswith("/" + suffix)]
        if len(found) != 1:
            raise RuntimeError("MISSING_OR_AMBIGUOUS_MEMBER_" + suffix)
        return found[0]
    ts_name, ts = match("TS_73927.mat")
    liuqe_name, liuqe = match("KER_73927_LIUQE.mat")
    summary["paired_member_metadata"] = {
        "TS": {"name": ts_name, "compressed_bytes": ts["compressed_bytes"],
               "uncompressed_bytes": ts["uncompressed_bytes"]},
        "LIUQE": {"name": liuqe_name, "compressed_bytes": liuqe["compressed_bytes"],
                  "uncompressed_bytes": liuqe["uncompressed_bytes"]}
    }
    eligible = [(name, row) for name, row in [(ts_name, ts), (liuqe_name, liuqe)]
                if 0 < row["compressed_bytes"] <= MAX_RANGE
                and 128 <= row["uncompressed_bytes"] <= MAX_UNCOMPRESSED
                and row["method"] in (0, 8) and not row["flags"] & 1]
    if not eligible:
        summary["classification"] = "TCV_FENIX_MAT_MEMBER_BOUNDED_SIZE_GATE"
        summary["source_gate_reason"] = "Neither paired MAT member meets 8MiB compressed/24MiB expanded bound"
    else:
        name, entry = min(eligible, key=lambda item: (item[1]["compressed_bytes"], item[0]))
        off = entry["local_offset"]
        header, _, _ = get_range(f"{off}-{off+29}", (off, off+29))
        if struct.unpack_from("<I", header)[0] != 0x04034b50:
            raise RuntimeError("ZIP_LOCAL_HEADER_INVALID")
        flags, method = struct.unpack_from("<HH", header, 6)
        fname_len, extra_len = struct.unpack_from("<HH", header, 26)
        if flags != entry["flags"] or method != entry["method"] or fname_len + extra_len > 65535:
            raise RuntimeError("ZIP_LOCAL_CENTRAL_HEADER_MISMATCH")
        data_start = off + 30 + fname_len + extra_len
        if data_start + entry["compressed_bytes"] > total:
            raise RuntimeError("ZIP_MEMBER_ARCHIVE_BOUNDARY_MISMATCH")
        payload, _, _ = get_range(
            f"{data_start}-{data_start+entry['compressed_bytes']-1}",
            (data_start, data_start+entry["compressed_bytes"]-1))
        if method == 0:
            expanded = payload
        else:
            decoder = zlib.decompressobj(-15)
            expanded = decoder.decompress(payload, MAX_UNCOMPRESSED + 1)
            if len(expanded) > MAX_UNCOMPRESSED or not decoder.eof:
                raise RuntimeError("ZIP_DECOMPRESSION_LIMIT_OR_INCOMPLETE")
            expanded += decoder.flush()
        if len(expanded) != entry["uncompressed_bytes"] or len(expanded) > MAX_UNCOMPRESSED:
            raise RuntimeError("ZIP_UNCOMPRESSED_SIZE_MISMATCH")
        if zlib.crc32(expanded) & 0xffffffff != entry["crc32"]:
            raise RuntimeError("ZIP_MEMBER_CRC_MISMATCH")
        hdf5 = expanded.startswith(b"\x89HDF\r\n\x1a\n")
        mat5 = expanded[:116].startswith(b"MATLAB 5.0 MAT-file") and expanded[126:128] in (b"IM", b"MI")
        summary["verified_member"] = {
            "name": name, "compressed_bytes": len(payload),
            "uncompressed_bytes": len(expanded),
            "crc32_verified": True,
            "format": "HDF5" if hdf5 else "MATLAB_v5" if mat5 else "unknown",
            "sha256": hashlib.sha256(expanded).hexdigest()
        }
        if mat5:
            try:
                import scipy.io
                variables = scipy.io.whosmat(io.BytesIO(expanded))
                summary["mat_variable_inventory"] = [
                    {"name": v[0], "shape": list(v[1]), "type": v[2]}
                    for v in variables[:100]
                ]
            except Exception as exc:
                summary["mat_inventory_limitation"] = str(exc)[:250]
        summary["classification"] = ("TCV_FENIX_MAT_MEMBER_HEADER_VERIFIED"
                                     if mat5 or hdf5 else "TCV_FENIX_MAT_MEMBER_FORMAT_UNVERIFIED")
    summary["next_step"] = "Resolve verified variable units/time and source reuse terms before any physical interpretation; no native/causal TCT claim."
except Exception as exc:
    summary["error"] = str(exc)[:500]
    summary["classification"] = "TCV_FENIX_MAT_MEMBER_SOURCE_GATE_BLOCKED"
with (OUT / "summary.json").open("w", encoding="utf-8") as f:
    json.dump(summary, f, sort_keys=True, indent=2)
    f.write(chr(10))
print(json.dumps(summary, sort_keys=True, indent=2))
PY

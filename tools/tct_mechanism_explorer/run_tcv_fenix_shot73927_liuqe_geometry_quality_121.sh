#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec "$TCT_PYTHON" - <<'PY'
"""Bounded LIUQE-only geometric-quality mask audit; not a physics validation."""
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
PARENT = "20261028-120-tcv-fenix-shot73927-liuqe-intradiagnostic-syntax-repair"
OUT = pathlib.Path("validation_runs/tcv_fenix_shot73927_liuqe_geometry_quality_121")
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
    "classification": "TCV_FENIX_LIUQE_73927_GEOMETRY_QUALITY_SOURCE_BLOCKED",
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
        "tools/tct_mechanism_explorer/run_tcv_fenix_shot73927_liuqe_geometry_quality_121.sh"
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

    # Inspect only one reconstruction, with no TS clock alignment.
    ly = mat["LY"]
    geom = mat["L"]
    time = np.asarray(ly.t, dtype=float).reshape(-1)
    rgrid = np.asarray(geom.rx, dtype=float).reshape(-1)
    zgrid = np.asarray(geom.zx, dtype=float).reshape(-1)
    convergence = np.asarray(ly.isconverged).reshape(-1)
    niter = np.asarray(ly.niter).reshape(-1)
    if time.shape != (321,) or convergence.shape != (321,) or niter.shape != (321,):
        raise RuntimeError("LIUQE_FRAME_SCHEMA_CHANGED")
    if rgrid.size != 28 or zgrid.size != 65:
        raise RuntimeError("LIUQE_REFERENCE_GRID_SCHEMA_CHANGED")
    if not (np.isfinite(rgrid).all() and np.isfinite(zgrid).all()):
        raise RuntimeError("LIUQE_REFERENCE_GRID_NONFINITE")

    def matrix(name):
        a = np.asarray(getattr(ly, name), dtype=float)
        if a.shape != (61, 321):
            raise RuntimeError("LIUQE_SURFACE_SCHEMA_CHANGED_" + name)
        return a

    rho = matrix("raQ")
    rgeom = matrix("rgeom")
    zgeom = matrix("zgeom")
    aminor = matrix("aminor")
    kappa = matrix("kappa")
    delta = matrix("delta")
    jtor = matrix("jtorQ")
    ip = np.asarray(ly.Ip, dtype=float).reshape(-1)
    q95 = np.asarray(ly.q95, dtype=float).reshape(-1)
    chi = np.asarray(ly.chi, dtype=float).reshape(-1)
    chih = np.asarray(ly.chih, dtype=float).reshape(-1)
    if any(v.shape != (321,) for v in (ip, q95, chi, chih)):
        raise RuntimeError("LIUQE_SCALAR_TRACE_SCHEMA_CHANGED")

    def finite_quantiles(a):
        a = np.asarray(a, dtype=float).reshape(-1)
        good = a[np.isfinite(a)]
        return {"count": int(a.size), "finite_count": int(good.size),
                "q05": float(np.quantile(good, 0.05)) if good.size else None,
                "median": float(np.median(good)) if good.size else None,
                "q95": float(np.quantile(good, 0.95)) if good.size else None}

    finite_geom = np.isfinite(rgeom) & np.isfinite(zgeom)
    box = finite_geom & (rgeom >= rgrid.min()) & (rgeom <= rgrid.max()) & (
        zgeom >= zgrid.min()) & (zgeom <= zgrid.max())
    nonnegative_aminor = np.isfinite(aminor) & (aminor >= 0)
    positive_kappa = np.isfinite(kappa) & (kappa > 0)
    finite_delta = np.isfinite(delta)
    regions = {
        "all_surfaces": np.ones_like(rho, dtype=bool),
        "axis_near_rho_le_0p05": np.isfinite(rho) & (rho <= 0.05),
        "interior_rho_0p05_to_0p95": np.isfinite(rho) & (rho > 0.05) & (rho < 0.95),
        "edge_rho_ge_0p95": np.isfinite(rho) & (rho >= 0.95)
    }
    region_summary = {}
    for name, mask in regions.items():
        n = int(mask.sum())
        region_summary[name] = {
            "surface_frame_cells": n,
            "finite_geometry_cells": int((finite_geom & mask).sum()),
            "centroid_inside_L_grid_box_cells": int((box & mask).sum()),
            "nonnegative_minor_radius_cells": int((nonnegative_aminor & mask).sum()),
            "positive_kappa_cells": int((positive_kappa & mask).sum()),
            "finite_delta_cells": int((finite_delta & mask).sum()),
            "rgeom": finite_quantiles(rgeom[mask]),
            "zgeom": finite_quantiles(zgeom[mask]),
            "aminor": finite_quantiles(aminor[mask]),
            "kappa": finite_quantiles(kappa[mask]),
            "delta": finite_quantiles(delta[mask]),
            "jtorQ": finite_quantiles(jtor[mask])
        }
    interior = regions["interior_rho_0p05_to_0p95"]
    per_frame_n = interior.sum(axis=0)
    per_frame_inside = (interior & box).sum(axis=0)
    interior_fraction = np.divide(per_frame_inside, per_frame_n,
                                  out=np.zeros(321, dtype=float), where=per_frame_n > 0)
    summary["quality_audit"] = {
        "frames": 321, "surfaces_per_frame": 61,
        "LIUQE_converged_true_frames": int(np.count_nonzero(convergence == 1)),
        "LIUQE_converged_false_frames": int(np.count_nonzero(convergence == 0)),
        "niter": finite_quantiles(niter),
        "Ip": finite_quantiles(ip), "q95": finite_quantiles(q95),
        "chi": finite_quantiles(chi), "chih": finite_quantiles(chih),
        "L_grid_r_range_raw": [float(rgrid.min()), float(rgrid.max())],
        "L_grid_z_range_raw": [float(zgrid.min()), float(zgrid.max())],
        "regions": region_summary,
        "interior_centroid_in_grid_fraction_by_frame": finite_quantiles(interior_fraction),
        "frames_with_no_interior_surfaces": int(np.count_nonzero(per_frame_n == 0)),
        "time_numeric_range_raw": [float(time.min()), float(time.max())],
        "diagnostic_units_calibrated": False,
        "shared_diagnostic_clock_verified": False,
        "mask_semantics": "Numerical reconstruction-grid compatibility only, not physical equilibrium validity; rho region bounds are descriptive and not frozen M3D-C1 gates.",
        "raw_signal_values_published": False
    }
    summary["classification"] = "TCV_FENIX_LIUQE_73927_GEOMETRY_QUALITY_MASK_AUDITED"
    summary["observational_status"] = (
        "single-diagnostic LIUQE equilibrium reconstruction numerical-quality audit; "
        "not experimental precursor timing, prospective or controller-in-loop"
    )
    summary["next_step"] = (
        "Review geometric outliers and convergence-vs-quality discrepancy; "
        "require verified units and native handoff before any M3D-C1 or causal TCT claim."
    )
except Exception as exc:
    summary["error"] = (type(exc).__name__ + ": " + str(exc))[:500]
with (OUT / "summary.json").open("w", encoding="utf-8") as output:
    json.dump(summary, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Required interpreter missing: $PY" >&2
  exit 2
fi
exec "$PY" - <<'PYCODE'
"""Bounded FAIR-MAST metadata-path audit for TokaMark Task-4.1; no waveform reads."""
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

shot = 21719
cap = 2 * 1024 * 1024
url = f"https://s3.echo.stfc.ac.uk/mast/level1/shots/{shot}.zarr/.zmetadata"
out = Path("validation_runs/tokamark_task41_remote_signal_metadata_map")
out.mkdir(parents=True, exist_ok=True)
requested = [
    ("magnetics", "flux_loop_flux"),
    ("magnetics", "b_field_pol_probe_ccbv_field"),
    ("magnetics", "b_field_pol_probe_obr_field"),
    ("magnetics", "b_field_pol_probe_obv_field"),
    ("magnetics", "b_field_tor_probe_saddle_voltage"),
    ("pf_active", "coil_current"),
    ("pf_active", "solenoid_current"),
    ("summary", "ip"),
    ("interferometer", "n_e_line"),
    ("spectrometer_visible", "filter_spectrometer_dalpha_voltage"),
    ("soft_x_rays", "horizontal_cam_lower"),
    ("soft_x_rays", "horizontal_cam_upper"),
    ("magnetics", "b_field_tor_probe_cc_field"),
    ("magnetics", "b_field_pol_probe_omv_voltage"),
    ("pulse_schedule", "i_plasma"),
    ("pulse_schedule", "n_e_line"),
    ("summary", "power_nbi"),
    ("gas_injection", "total_injected"),
]
status = None
error = None
content_range = None
reported_length = None
body = b""
try:
    req = urllib.request.Request(
        url, headers={"User-Agent": "tct-task41-metadata-map/1.0", "Range": f"bytes=0-{cap-1}"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        status = getattr(response, "status", None)
        content_range = response.headers.get("Content-Range")
        reported_length = response.headers.get("Content-Length")
        body = response.read(cap + 1)
except (urllib.error.URLError, TimeoutError, OSError) as exc:
    error = f"{type(exc).__name__}: {exc}"
sample = body[:cap]
full = False
keys = []
if status in (200, 206) and sample:
    try:
        parsed = json.loads(sample)
        if isinstance(parsed, dict) and isinstance(parsed.get("metadata"), dict):
            keys = sorted(parsed["metadata"])
            full = True
    except (ValueError, UnicodeDecodeError):
        pass
    if not full:
        keys = sorted(set(re.findall(
            r'"([^"\\]+/(?:\.zarray|\.zattrs|\.zgroup))"\s*:',
            sample.decode("utf-8", errors="replace"),
        )))
matched = []
for group, name in requested:
    stem = f"{group}/{name}"
    matching = [k for k in keys if k == stem or k.startswith(stem + "/")]
    matched.append({"task41_group": group, "task41_signal": name,
                    "present_in_metadata_sample": bool(matching),
                    "matched_paths": matching[:5]})
time_keys = [k for k in keys if re.search(r"(^|/)(time|timestamp|t_axis)(/|_|\.)", k, re.I)]
classification = (
    "TOKAMARK_TASK41_REMOTE_SIGNAL_METADATA_MAPPED" if full
    else "TOKAMARK_TASK41_REMOTE_SIGNAL_METADATA_PARTIAL" if status in (200, 206)
    else "TOKAMARK_TASK41_REMOTE_SIGNAL_METADATA_ACCESS_FAILURE"
)
summary = {
    "schema_version": 1,
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "classification": classification,
    "fuel_track": "fuel_agnostic_control",
    "machine": "MAST",
    "shot_ids": [shot],
    "parent_result_job_id": "20261007-095-tokamark-task41-remote-shot-access-probe",
    "source": "FAIR-MAST Level-1 public Zarr, used as a TokaMark Task-4.1 diagnostic provenance candidate",
    "tokaMark_license": "CC BY 4.0 for TokaMark release; FAIR-MAST Level-1 reuse terms require independent verification",
    "source_url": url,
    "source_metadata_status": status,
    "source_content_range": content_range,
    "source_content_length": reported_length,
    "sample_bytes": len(sample),
    "sample_sha256": hashlib.sha256(sample).hexdigest(),
    "metadata_fully_parsed": full,
    "metadata_key_count_in_sample": len(keys),
    "metadata_paths_sample": keys[:80],
    "task41_requested_signals": matched,
    "task41_signal_count_found_in_sample": sum(x["present_in_metadata_sample"] for x in matched),
    "candidate_timebase_metadata_paths": time_keys[:40],
    "timebase_alignment_verified": False,
    "waveform_chunks_loaded": False,
    "bulk_download_performed": False,
    "frozen_detector_retuned": False,
    "actuator_budgets_ms": {"prebiased_fast": 2.75, "prebiased_nominal": 5.25},
    "ready_for_precursor_reachability": False,
    "pipeline_failure": status not in (200, 206),
    "error": error,
    "claim_boundary": "Metadata path inspection only; no confirmed Mirnov/D-alpha waveforms, timebase alignment, causal TCT, segmented-electrode efficacy, p-B11 fidelity, or native M3D-C1 validation.",
    "next_gate": "If task signal paths and time coordinates can be verified, retrieve bounded waveform chunks and independently align event/trigger timestamps before running frozen 2.75/5.25 ms observational reachability. Otherwise inspect further metadata ranges or canonical FAIR-MAST path schema without fabricating channels."
}
(out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"classification": classification, "status": status,
                  "keys": len(keys), "task41_sample_hits": summary["task41_signal_count_found_in_sample"],
                  "timebase_verified": False, "waveform_chunks_loaded": False}))
if status not in (200, 206):
    raise SystemExit(3)
PYCODE

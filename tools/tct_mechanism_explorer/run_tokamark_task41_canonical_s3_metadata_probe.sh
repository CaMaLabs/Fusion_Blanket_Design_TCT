#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then echo "Missing pinned interpreter: $PY" >&2; exit 2; fi

exec "$PY" - <<'PYCODE'
"""Metadata-only probe of the canonical public TokaMark S3 shot store."""
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SHOT = 21719
BASE = f"https://s3.echo.stfc.ac.uk/mast/tokamark/v1/{SHOT}.zarr"
OUT = Path("validation_runs/tokamark_task41_canonical_s3_metadata_probe")
OUT.mkdir(parents=True, exist_ok=True)

TASK_SIGNALS = [
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
TIME_PATHS = [
    "magnetics/time", "magnetics/time_mirnov", "magnetics/time_omaha",
    "magnetics/time_saddle", "pf_active/time", "summary/time",
    "interferometer/time", "spectrometer_visible/time", "soft_x_rays/time",
    "pulse_schedule/time", "gas_injection/time",
]

def fetch_json(path, cap=262144):
    url = f"{BASE}/{path}/zarr.json" if path else f"{BASE}/zarr.json"
    rec = {
        "path": path or "/",
        "url": url,
        "status": None,
        "content_length": None,
        "bytes_read": 0,
        "sha256": None,
        "json": None,
        "error": None,
    }
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "tct-tokamark-canonical-s3-metadata-probe/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as res:
            rec["status"] = getattr(res, "status", None)
            rec["content_length"] = res.headers.get("Content-Length")
            data = res.read(cap + 1)
        rec["bytes_read"] = len(data)
        rec["sha256"] = hashlib.sha256(data).hexdigest()
        if len(data) > cap:
            rec["error"] = "metadata exceeds bounded cap"
        else:
            obj = json.loads(data)
            rec["json"] = {
                k: obj.get(k)
                for k in ("zarr_format", "node_type", "shape", "data_type",
                          "dimension_names", "chunk_grid", "attributes")
                if k in obj
            }
    except (urllib.error.URLError, OSError, TimeoutError, ValueError, UnicodeError) as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec

root = fetch_json("")
signal_records = {}
for group, signal in TASK_SIGNALS:
    key = f"{group}/{signal}"
    signal_records[key] = fetch_json(key)

time_records = {path: fetch_json(path) for path in TIME_PATHS}

signal_ok = [k for k, v in signal_records.items() if v["status"] == 200 and v["json"]]
time_ok = [k for k, v in time_records.items() if v["status"] == 200 and v["json"]]
fast_required = {
    "spectrometer_visible/filter_spectrometer_dalpha_voltage",
    "magnetics/b_field_tor_probe_saddle_voltage",
}
fast_signal_metadata_present = fast_required.issubset(set(signal_ok))
fast_time_metadata_present = (
    "spectrometer_visible/time" in time_ok
    and ("magnetics/time_saddle" in time_ok or "magnetics/time" in time_ok)
)

if len(signal_ok) == len(TASK_SIGNALS) and fast_time_metadata_present:
    classification = "TOKAMARK_TASK41_CANONICAL_S3_SIGNAL_METADATA_CONFIRMED"
elif signal_ok or root["status"] == 200:
    classification = "TOKAMARK_TASK41_CANONICAL_S3_METADATA_PARTIAL"
else:
    classification = "TOKAMARK_TASK41_CANONICAL_S3_METADATA_ACCESS_NOT_ESTABLISHED"

ready = bool(fast_signal_metadata_present and fast_time_metadata_present)
summary = {
    "schema_version": 1,
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "classification": classification,
    "parent_result_job_id": "20261010-097-tokamark-task41-l1-alias-provenance-audit",
    "machine": "MAST",
    "shot_ids": [SHOT],
    "fuel_track": "fuel_agnostic_control",
    "evidence_class": "canonical_remote_metadata_access",
    "source": "TokaMark canonical public S3 store",
    "canonical_store_root": "s3://mast/tokamark/v1",
    "https_store_root": "https://s3.echo.stfc.ac.uk/mast/tokamark/v1",
    "upstream_store_constructor": "UKAEA-IBM-STFC-Fusion-FMs/tokamark src/MAST_tools/utils/store_utils.py",
    "upstream_task": "src/tokamark/tasks_configs/group_4_mhd_activity/task_4-1.yaml",
    "temporal_split": "TokaMark_data_splits.csv; shot 21719 training; no resplitting",
    "root_metadata": root,
    "signal_metadata": signal_records,
    "time_metadata": time_records,
    "requested_signal_count": len(TASK_SIGNALS),
    "signal_metadata_confirmed_count": len(signal_ok),
    "signal_metadata_confirmed": signal_ok,
    "time_metadata_confirmed_count": len(time_ok),
    "time_metadata_confirmed": time_ok,
    "fast_required_signal_metadata_present": fast_signal_metadata_present,
    "fast_required_time_metadata_present": fast_time_metadata_present,
    "waveform_chunks_loaded": 0,
    "bulk_download_performed": False,
    "shots_analyzed": 0,
    "events_analyzed": 0,
    "frozen_detector_retuned": False,
    "actuator_budgets_ms": {"prebiased_fast": 2.75, "prebiased_nominal": 5.25},
    "ready_for_bounded_waveform_retrieval": ready,
    "pipeline_failure": classification.endswith("NOT_ESTABLISHED"),
    "mechanism_effect": "neutral",
    "claim_boundary": (
        "Canonical TokaMark metadata-access audit only. No waveform/event analysis, "
        "precursor performance, causal TCT suppression, segmented-electrode efficacy, "
        "native M3D-C1 validation, independent cross-machine validation, or p-B11 inference."
    ),
    "next_gate": (
        "If canonical fast diagnostic and time metadata are confirmed, retrieve only bounded "
        "waveform slices for the frozen prospective Task-4.1 observational reachability design; "
        "otherwise repair canonical data access without changing scientific thresholds."
    ),
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps({
    "classification": classification,
    "signal_metadata_confirmed_count": len(signal_ok),
    "time_metadata_confirmed_count": len(time_ok),
    "ready_for_bounded_waveform_retrieval": ready,
    "waveform_chunks_loaded": 0,
}, sort_keys=True))
if summary["pipeline_failure"]:
    raise SystemExit(3)
PYCODE

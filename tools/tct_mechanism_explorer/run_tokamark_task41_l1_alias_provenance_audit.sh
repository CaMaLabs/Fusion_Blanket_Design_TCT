#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then echo "Missing pinned interpreter: $PY" >&2; exit 2; fi
exec "$PY" - <<'PYCODE'
"""Bounded, read-only Task-4.1/FAIR-MAST Level-1 vs Level-2 alias provenance audit."""
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SHOT = 21719
OUT = Path("validation_runs/tokamark_task41_l1_alias_provenance_audit")
OUT.mkdir(parents=True, exist_ok=True)
TASK = [
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
# Exact canonical Level-2 signal names must not be equated to Level-1 aliases by spelling alone.
# These are search hints, not accepted diagnostic mappings.
HINTS = {
 "magnetics": ("mirnov", "flux", "saddle", "pol", "tor", "mag"),
 "pf_active": ("coil", "current", "solenoid", "pf"),
 "summary": ("ip", "plasma", "power", "nbi"),
 "interferometer": ("interfer", "density", "n_e", "line"),
 "spectrometer_visible": ("dalpha", "ha", "spectr"),
 "soft_x_rays": ("sxr", "xray", "x_ray", "soft"),
 "pulse_schedule": ("plasma", "pulse", "n_e", "density"),
 "gas_injection": ("gas", "inject", "puff"),
}
def fetch(level, cap):
    url = f"https://s3.echo.stfc.ac.uk/mast/{level}/shots/{SHOT}.zarr/.zmetadata"
    record = {"url":url, "status":None, "content_range":None,
              "bytes_read":0, "sha256":None, "complete_json":False,
              "metadata_entries":0, "error":None}
    metadata = {}
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent":"tct-task41-l1-alias-provenance/1.0",
            "Range":f"bytes=0-{cap-1}"})
        with urllib.request.urlopen(req, timeout=35) as res:
            record["status"] = getattr(res, "status", None)
            record["content_range"] = res.headers.get("Content-Range")
            data = res.read(cap+1)
        record["bytes_read"] = len(data)
        record["sha256"] = hashlib.sha256(data).hexdigest()
        if len(data) > cap:
            record["error"] = "metadata exceeds bounded cap"
        else:
            obj = json.loads(data)
            metadata = obj.get("metadata", {}) if isinstance(obj, dict) else {}
            if not isinstance(metadata, dict):
                metadata = {}
            record["complete_json"] = bool(metadata)
            record["metadata_entries"] = len(metadata)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError, UnicodeError) as e:
        record["error"] = f"{type(e).__name__}: {e}"
    return record, metadata

sources = {}
indexes = {}
for level, cap in (("level1", 2*1024*1024), ("level2", 4*1024*1024)):
    rec, md = fetch(level, cap)
    sources[level] = rec
    indexes[level] = md

matches = []
for group, signal in TASK:
    path = f"{group}/{signal}"
    row = {"task41_group":group, "task41_signal":signal, "canonical_path":path}
    for level in ("level1", "level2"):
        md = indexes[level]
        found = (path+"/.zarray") in md
        attrs = md.get(path+"/.zattrs", {}) if found else {}
        row[level] = {
            "exact_path_present":found,
            "zarray":md.get(path+"/.zarray") if found else None,
            "attrs_excerpt":{k:str(v)[:250] for k,v in attrs.items()
                             if k in ("units","long_name","description","_ARRAY_DIMENSIONS")}
        }
    matches.append(row)

l1_arrays = sorted(k[:-8] for k in indexes["level1"] if k.endswith("/.zarray"))
alias_hints = {}
for group, tokens in HINTS.items():
    candidates = [x for x in l1_arrays if any(token in x.lower() for token in tokens)]
    alias_hints[group] = candidates[:25]
timebases = {}
for level in ("level1", "level2"):
    md = indexes[level]
    timebases[level] = sorted(k[:-8] for k in md if k.endswith("/.zarray")
       and k[:-8].split("/")[-1].lower() in ("time","time_","t_axis","timestamp"))[:40]
n1 = sum(int(x["level1"]["exact_path_present"]) for x in matches)
n2 = sum(int(x["level2"]["exact_path_present"]) for x in matches)
classification = (
 "TOKAMARK_TASK41_L1_L2_ALIAS_PROVENANCE_AUDITED"
 if sources["level1"]["complete_json"] or sources["level2"]["complete_json"]
 else "TOKAMARK_TASK41_L1_L2_ALIAS_PROVENANCE_ACCESS_BLOCKED"
)
summary = {
 "schema_version":1, "created_utc":datetime.now(timezone.utc).isoformat(),
 "classification":classification, "parent_result_job_id":"20261008-096-tokamark-task41-remote-signal-metadata-map",
 "machine":"MAST", "shot_ids":[SHOT], "fuel_track":"fuel_agnostic_control",
 "source":"FAIR-MAST public Level-1/Level-2 Zarr metadata and TokaMark Task-4.1 schema",
 "source_provenance":sources, "requested_task41_signals":len(TASK),
 "exact_path_matches":{"level1":n1,"level2":n2},
 "task41_path_checks":matches, "level1_alias_search_hints_unverified":alias_hints,
 "candidate_timebase_arrays_unverified":timebases,
 "canonical_task_source":"UKAEA-IBM-STFC-Fusion-FMs/tokamark src/tokamark/tasks_configs/group_4_mhd_activity/task_4-1.yaml",
 "temporal_split":"TokaMark_data_splits.csv; shot 21719 training; no resplitting",
 "license":"TokaMark CC BY 4.0; FAIR-MAST Level-1/Level-2 reuse terms independently unverified",
 "waveform_chunks_loaded":0, "shots_analyzed":0, "events_analyzed":0,
 "timebase_alignment_verified":False, "frozen_detector_retuned":False,
 "bulk_download_performed":False, "actuator_budgets_ms":{"prebiased_fast":2.75,"prebiased_nominal":5.25},
 "ready_for_frozen_reachability":False,
 "pipeline_failure":classification.endswith("ACCESS_BLOCKED"),
 "mechanism_effect":"neutral",
 "claim_boundary":"Metadata-only provenance candidates, not confirmed signal equivalence. No measured precursors, causal TCT suppression, segmented-electrode efficacy, independent cross-machine validation, native M3D-C1 validation or p-B11 fidelity.",
 "next_gate":"Verify matched Level-2 channel semantics and time coordinates (or document defensible Level-1 aliases) before any bounded waveform retrieval; then frozen observational reachability with circular-shift and shuffled-event nulls."
}
(OUT/"summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
print(json.dumps({"classification":classification, "level1_exact":n1, "level2_exact":n2,
                  "level1_keys":sources["level1"]["metadata_entries"],
                  "level2_keys":sources["level2"]["metadata_entries"],
                  "waveform_chunks_loaded":0}))
if summary["pipeline_failure"]: raise SystemExit(3)
PYCODE

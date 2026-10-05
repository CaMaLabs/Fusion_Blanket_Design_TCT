#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
OUT="validation_runs/tokamark_mast_intake"
mkdir -p "$OUT"
python3 - <<'PY'
import json, urllib.request, datetime
from pathlib import Path
url="https://huggingface.co/api/datasets/UKAEA-IBM-STFC/tokamark-v1"
with urllib.request.urlopen(url, timeout=30) as r:
    meta=json.load(r)
tags=meta.get("tags",[])
summary={
 "schema_version":1,
 "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "classification":"TOKAMARK_MAST_OPEN_SHOT_FAMILY_ACCESS_CONFIRMED",
 "machine":"MAST",
 "fuel_track":"fuel_agnostic_control",
 "source":"UKAEA-IBM-STFC/tokamark-v1",
 "access_status":"public",
 "license":"CC BY 4.0" if "license:cc-by-4.0" in tags else next((x.split("license:",1)[1] for x in tags if x.startswith("license:")),None),
 "shot_family":{"shots":11573,"signals":39,"tasks":14,"archive_size_gb_approx":565},
 "diagnostics":["Mirnov coils (500 kHz)","D-alpha and soft X-ray (50 kHz)","flux/pickup/saddle magnetics","Thomson scattering","interferometer","PF/solenoid/plasma currents","PF coil voltages","reference plasma current/density","NBI power","gas puffing","EFIT shape/J_tor/flux map"],
 "tct_relevance":["frozen multi-shot precursor benchmark","actuator-to-equilibrium response","preventative-vs-reactive timing","MHD/disruption forecasting","controller generalization across campaigns"],
 "claim_boundary":"TokaMark is a task-ready repackaging of FAIR-MAST MAST shots, not an independent machine. Intake/access evidence only; no causal TCT, segmented-electrode efficacy, p-B11, or reactor-scale claim.",
 "pb11_fidelity":{"applicable":False},
 "next_experiment":"Use TokaMark task metadata/smallest available batch to define a frozen temporal-split precursor/reachability audit before any bulk 565-GB download; reuse the established 2.75 ms and 5.25 ms TCT budgets without retuning."
}
Path("validation_runs/tokamark_mast_intake/summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print(json.dumps(summary,indent=2))
PY

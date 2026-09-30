#!/usr/bin/env python3
"""TCABR open-discharge intake probe for the TCT experimental shot bank."""
from __future__ import annotations
import json, urllib.request, hashlib
from pathlib import Path
from datetime import datetime, timezone

RUN=Path("validation_runs/tcabr_open_disruption_intake")
RUN.mkdir(parents=True, exist_ok=True)
BASE="https://zenodo.org/records/21843354/files/"
files={"data":"tcabr_data.nc","tools":"tcabr_tools.py"}
out={"schema_version":1,"machine":"TCABR","fuel_track":"fuel_agnostic_control",
"source_record":"Zenodo 21843354","doi":"10.5281/zenodo.21843354",
"release":"v1.0.0 (2026-08-09)","shot_family":{"total":2189,"non_disruptive":1754,"disruptive":435},
"sampling_resolution_us":1.0,
"diagnostics":["IPlasma","VLoop","BbMirnovN01-N20","BobFlux","CpToroidal","EletrCurrent","EletrVoltage","GasPuffing02","HardXRay","HAlfaRef","IVert01","IVert02","VSin"],
"tct_relevance":["disruption precursor timing","Mirnov multi-channel precursor generalization","actuator-latency feasibility","electrode voltage/current analog timing","preventative-vs-reactive controller evaluation"],
"claim_boundary":"Open TCABR Ohmic L-mode disruption/precursor dataset. Electrode channels are experimental analogs only; no causal TCT, segmented-electrode efficacy, p-B11 reactivity, alpha transport, or reactor-scale claim.",
"pb11_fidelity":{"applicable":False,"reason":"TCABR dataset is not a p-B11 validation corpus."},
"access":{},"created_utc":datetime.now(timezone.utc).isoformat()}
for role,name in files.items():
    url=BASE+name+"?download=1"
    req=urllib.request.Request(url, method="HEAD", headers={"User-Agent":"TCT-shot-intake/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            out["access"][role]={"url":url,"status":r.status,"content_length":r.headers.get("Content-Length"),"content_type":r.headers.get("Content-Type")}
    except Exception as e:
        out["access"][role]={"url":url,"error":f"{type(e).__name__}: {e}"}
# Download only the small official helper now; do not pull 4.8 GB until the worker confirms access/disk.
try:
    data=urllib.request.urlopen(BASE+"tcabr_tools.py?download=1", timeout=90).read()
    (RUN/"tcabr_tools.py").write_bytes(data)
    out["tools_sha256"]=hashlib.sha256(data).hexdigest()
    out["tools_bytes"]=len(data)
except Exception as e:
    out["tools_download_error"]=f"{type(e).__name__}: {e}"
data_ok=out["access"].get("data",{}).get("status") in (200,206)
tools_ok=(RUN/"tcabr_tools.py").exists()
out["classification"]="TCABR_OPEN_SHOT_FAMILY_ACCESS_CONFIRMED" if data_ok and tools_ok else "TCABR_OPEN_SHOT_FAMILY_ACCESS_NOT_CONFIRMED"
out["next_experiment"]="Download/cache tcabr_data.nc once, stratify disruptive/non-disruptive shots, freeze a train/test split, and measure Mirnov/H-alpha/electrode precursor lead distributions with shuffled/circular-shift controls against 2.75 ms and 5.25 ms TCT budgets." if data_ok else "Repair public-data access before scientific testing."
(RUN/"summary.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))

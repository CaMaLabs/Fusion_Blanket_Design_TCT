#!/usr/bin/env python3
"""Bounded, fail-closed GOLEM shot-data probe. No raw waveform redistribution."""
from __future__ import annotations
import hashlib, json, math, urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT=Path("validation_runs/golem_51929_51926_signal_probe_110")
OUT.mkdir(parents=True,exist_ok=True)
BASE="https://golem.fjfi.cvut.cz"
SHOTS={51929:{"plasma_reported":True,"date":"2026-03-27","plasma_window_ms":[3.71,32.99]},
       51926:{"plasma_reported":False,"date":"2026-03-27","plasma_window_ms":None}}
SIGNALS=("plasma_current","loop_voltage")
MAX_BYTES=2_000_000
result={"schema_version":1,"classification":"GOLEM_SHOT_FAMILY_ACCESS_UNVERIFIED",
"source":"GOLEM tokamak official discharge database","machine":"GOLEM",
"shot_ids":[51929,51926],"fuel_track":"fuel_agnostic_control",
"pb11_fidelity":"not_applicable","recorded_utc":datetime.now(timezone.utc).isoformat(),
"source_shot_pages":{str(s):f"{BASE}/shots/{s}/" for s in SHOTS},
"source_access_documentation":"https://golem.fjfi.cvut.cz/wiki/Handling/DataAccess/DataProcessing",
"access_conditions":"Public per-shot download interface; explicit waveform redistribution license not independently verified. Record hashes and derived metadata only.",
"shot_metadata":SHOTS,"diagnostics_requested":list(SIGNALS),
"claim_boundary":"GOLEM observational H-fuel pulse/disruption-control analog; no Mirnov/ELM/precursor assertion, no actuator causal comparison, no native M3D-C1, no p-B11 inference.",
"signals":{},"errors":{}}

def fetch(shot,name):
    url=f"{BASE}/utils/data/{shot}/{name}"
    req=urllib.request.Request(url,headers={"User-Agent":"CaMaLabs-TCT-research-intake/1.0"})
    with urllib.request.urlopen(req,timeout=18) as response:
        raw=response.read(MAX_BYTES+1)
        typ=response.headers.get("Content-Type","")
        if len(raw)>MAX_BYTES: raise ValueError("bounded_fetch_limit_exceeded")
        if "html" in typ.lower() or b"<html" in raw[:500].lower(): raise ValueError("html_instead_of_waveform")
    points=[]
    for line in raw.decode("utf-8",errors="replace").splitlines():
        line=line.strip()
        if not line or line.startswith(("#",";","%")): continue
        tokens=line.replace(","," ").split()
        if len(tokens)<2: continue
        try: t,v=float(tokens[0]),float(tokens[1])
        except ValueError: continue
        if math.isfinite(t) and math.isfinite(v): points.append((t,v))
    if len(points)<20: raise ValueError(f"insufficient_numeric_time_value_rows:{len(points)}")
    if any(points[i+1][0]<=points[i][0] for i in range(len(points)-1)):
        raise ValueError("time_axis_not_strictly_increasing")
    vals=[v for _,v in points]
    return {"url":url,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
        "samples":len(points),"first_time_native_units":points[0][0],
        "last_time_native_units":points[-1][0],"time_units":"unverified",
        "signal_units":"unverified","minimum_native":min(vals),"maximum_native":max(vals),
        "interpretation":"Measured signal access only; no time-unit or diagnostic calibration assumed."}

for shot in SHOTS:
    for name in SIGNALS:
        key=f"{shot}/{name}"
        try: result["signals"][key]=fetch(shot,name)
        except Exception as e: result["errors"][key]=f"{type(e).__name__}: {e}"
if all(f"51929/{name}" in result["signals"] for name in SIGNALS):
    result["classification"]="GOLEM_SHOT_51929_BASIC_WAVEFORMS_VERIFIED"
    result["next_justified_test"]="Verify units, clock alignment and available Mirnov/H-alpha before precursor or latency feasibility analysis. Keep 51926 as instrument/no-plasma negative control only if signals exist."
else:
    result["classification"]="GOLEM_SHOT_51929_ACCESS_OR_SCHEMA_BLOCKED"
    result["next_justified_test"]="Repair only the documented endpoint/schema after examining error; do not claim data ingestion."
(OUT/"summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps({"classification":result["classification"],"verified_signals":list(result["signals"]),"errors":result["errors"]},indent=2))

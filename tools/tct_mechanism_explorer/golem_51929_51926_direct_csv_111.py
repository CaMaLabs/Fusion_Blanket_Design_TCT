#!/usr/bin/env python3
"""GOLEM 2026 shot data retry: official direct BasicDiagnostics Results CSV."""
import hashlib, json, math, urllib.request
from datetime import datetime, timezone
from pathlib import Path
OUT=Path("validation_runs/golem_51929_51926_direct_csv_111")
OUT.mkdir(parents=True,exist_ok=True)
ROOT="https://golem.fjfi.cvut.cz"
FILES={"plasma_current":"Ip.csv","loop_voltage":"U_loop.csv"}
SHOTS={51929:{"plasma":True,"plasma_start_ms":3.71,"plasma_end_ms":32.99},51926:{"plasma":False}}
MAX=2_000_000
summary={"schema_version":1,"classification":"GOLEM_DIRECT_CSV_ACCESS_UNVERIFIED",
"machine":"GOLEM","shot_ids":[51929,51926],"shot_date":"2026-03-27",
"fuel_track":"fuel_agnostic_control","pb11_fidelity":"not_applicable",
"source":"https://golem.fjfi.cvut.cz/shots/51929/",
"access_documentation":"https://golem.fjfi.cvut.cz/wiki/Handling/DataMining/Collaborators/index",
"endpoint_repair":"20261025-110 legacy utils/data endpoints returned 404 for four requests; use official BasicDiagnostics/Results/Ip.csv and U_loop.csv direct paths",
"license_access":"Public shot files; explicit redistribution license unverified. Preserve only derived summaries and SHA256, no waveform republishing.",
"shots":SHOTS,"signals":{},"errors":{},"recorded_utc":datetime.now(timezone.utc).isoformat(),
"claim_boundary":"Observed GOLEM H-fuel discharge and no-plasma control only; no M3D-C1, ELM precursor, actuator causality, or p-B11 inference."}
def get(shot,filename):
    attempts=[]
    for path in (f"/shots/{shot}/Diagnostics/BasicDiagnostics/Results/{filename}",
                 f"/shotdir/{shot}/Diagnostics/BasicDiagnostics/Results/{filename}"):
        url=ROOT+path
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"CaMaLabs-TCT/1.0"})
            with urllib.request.urlopen(req,timeout=15) as response:
                raw=response.read(MAX+1); mime=response.headers.get("Content-Type","")
            if len(raw)>MAX: raise ValueError("bounded_limit_exceeded")
            if "html" in mime.lower() or b"<html" in raw[:512].lower(): raise ValueError("html_not_csv")
            rows=[]
            for line in raw.decode("utf-8",errors="replace").splitlines():
                parts=line.replace(","," ").replace(";"," ").split()
                if len(parts)<2: continue
                try: t,v=float(parts[0]),float(parts[1])
                except ValueError: continue
                if math.isfinite(t) and math.isfinite(v): rows.append((t,v))
            if len(rows)<20: raise ValueError(f"numeric_rows_below_20:{len(rows)}")
            if any(rows[i][0]>=rows[i+1][0] for i in range(len(rows)-1)):
                raise ValueError("nonmonotonic_time_axis")
            values=[v for _,v in rows]
            return {"url":url,"sha256":hashlib.sha256(raw).hexdigest(),
              "bytes":len(raw),"samples":len(rows),"time_start_raw":rows[0][0],
              "time_end_raw":rows[-1][0],"time_units":"unverified",
              "value_min_raw":min(values),"value_max_raw":max(values),
              "signal_units":"unverified","raw_waveform_committed":False}
        except Exception as e: attempts.append(f"{path}: {type(e).__name__}: {e}")
    raise RuntimeError("; ".join(attempts))
for shot in SHOTS:
    for signal,filename in FILES.items():
        key=f"{shot}/{signal}"
        try: summary["signals"][key]=get(shot,filename)
        except Exception as e: summary["errors"][key]=str(e)
if all(f"51929/{s}" in summary["signals"] for s in FILES):
    summary["classification"]="GOLEM_51929_EXPERIMENTAL_WAVEFORM_ACCESS_VERIFIED"
    summary["next_step"]="Validate source units and clock reference; compare 51926 no-plasma signal only if available; then perform bounded onset/lag null test. No ELM/Mirnov precursor claim."
else:
    summary["classification"]="GOLEM_51929_DIRECT_CSV_ACCESS_OR_SCHEMA_BLOCKED"
    summary["next_step"]="Inspect authoritative shot-specific Results directory or obtain exact endpoint from GOLEM operators. Do not count as ingested."
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print(json.dumps({"classification":summary["classification"],"signals":list(summary["signals"]),"errors":summary["errors"]},indent=2))

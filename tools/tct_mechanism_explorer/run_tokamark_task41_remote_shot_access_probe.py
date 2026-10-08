#!/usr/bin/env python3
"""Bounded metadata-only anonymous remote access probe for one MAST shot.

Does not read any waveform chunks or materialize bulk shot datasets.
"""
from __future__ import annotations
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

OUT=Path("validation_runs/tokamark_task41_remote_shot_access_probe")
OUT.mkdir(parents=True,exist_ok=True)
SHOT=21719
ENDPOINTS=[
 ("fair_mast_s3_shot_zgroup","https://s3.echo.stfc.ac.uk/mast/level1/shots/21719.zarr/.zgroup"),
 ("fair_mast_s3_shot_zmetadata","https://s3.echo.stfc.ac.uk/mast/level1/shots/21719.zarr/.zmetadata"),
]
results=[]
for label,url in ENDPOINTS:
  item={"name":label,"url":url,"status":None,"error":None,"response_bytes":0,"content_type":None}
  req=urllib.request.Request(url,headers={"User-Agent":"tct-shot-metadata-probe/1.0","Range":"bytes=0-4095"})
  try:
    with urllib.request.urlopen(req,timeout=12) as response:
      data=response.read(4096)
      item.update(status=getattr(response,"status",None),response_bytes=len(data),content_type=response.headers.get("Content-Type"))
  except urllib.error.HTTPError as exc:
    item["status"]=exc.code
    item["error"]=f"HTTP {exc.code}"
  except Exception as exc:
    item["error"]=f"{type(exc).__name__}: {exc}"
  results.append(item)

reachable=any(x["status"] in (200,206) for x in results)
summary={
 "schema_version":1,
 "created_utc":datetime.now(timezone.utc).isoformat(),
 "classification":"TOKAMARK_MAST_TASK41_REMOTE_SHOT_ACCESS_PROBED",
 "fuel_track":"fuel_agnostic_control",
 "machine":"MAST",
 "shot_ids":[SHOT],
 "evidence_class":"pipeline_remote_data_access",
 "parent_result_job_id":"20261007-094-tokamark-task41-shot-data-availability-audit",
 "anonymous_metadata_probe":results,
 "metadata_endpoint_reachable":reachable,
 "shot_level_signals_loaded":False,
 "bulk_download_performed":False,
 "actuator_budgets_ms":{"prebiased_fast":2.75,"prebiased_nominal":5.25},
 "pipeline_failure":not reachable,
 "claim_boundary":"Remote dataset metadata accessibility only; no precursor/causal TCT result, no inferred diagnostic time calibration or segment-electrode efficacy; M3D-C1 thresholds remain unmapped.",
 "next_gate":"If a canonical single-shot endpoint is verified, map diagnostic paths, exact shot ID, timebases and small bounded signal slices before applying the unchanged frozen observational reachability design. A 404 indicates candidate-path failure, not unavailable public data or a TCT negative."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2))

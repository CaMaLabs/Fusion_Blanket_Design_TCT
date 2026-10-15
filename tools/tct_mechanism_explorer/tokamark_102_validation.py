#!/usr/bin/env python3
"""Bounded, reproducible TokaMark shot 21719 observed-precursor validation.
No detector retuning; no causal intervention claims."""
import json, hashlib, urllib.request, urllib.error, zlib, math
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
ROOT="https://s3.echo.stfc.ac.uk/mast/tokamark/v1/21719.zarr/"
OUT=Path("validation_runs/tokamark_task41_bounded_validation")
OUT.mkdir(parents=True,exist_ok=True)
MAX_META=262144
MAX_CHUNK=8*1024*1024
SEED=10221719
rng=np.random.default_rng(SEED)
summary={"schema_version":1,"created_utc":datetime.now(timezone.utc).isoformat(),"machine":"MAST","shot_ids":[21719],"fuel_track":"fuel_agnostic_control","pb11_fidelity":"not_applicable","source":ROOT,"source_license":"TokaMark CC BY 4.0; FAIR-MAST CC BY-SA 4.0 except where noted","parent_result_job_id":"20261014-101-tokamark-task41-time-coordinate-schema-audit","frozen_detector_retuned":False,"actuator_budgets_ms":{"prebiased_fast":2.75,"prebiased_nominal":5.25},"numeric_time_alignment_verified":False,"mechanism_effect":"neutral","events_analyzed":0,"observed_lead_times_ms":[],"chunk_reads":[],"errors":[]}
def download(key,cap):
    u=ROOT+key
    with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"TCT-bounded-validation-102/1.0"}),timeout=35) as r:
        b=r.read(cap+1)
    if len(b)>cap: raise ValueError("bounded_chunk_cap_exceeded: "+key)
    summary["chunk_reads"].append({"key":key,"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()})
    return b
def chunk(path,md):
    za=md[path+"/.zarray"]
    if za.get("zarr_format")!=2: raise ValueError("not_zarr_v2:"+path)
    if za.get("filters"): raise ValueError("unsupported_filters:"+path)
    dims=za["shape"]; chunks=za["chunks"]
    index=".".join("0" for _ in dims)
    b=download(path+"/"+index,MAX_CHUNK)
    compressor=za.get("compressor")
    if compressor:
        cid=compressor.get("id")
        if cid=="zlib": b=zlib.decompress(b)
        elif cid=="gzip":
            import gzip
            b=gzip.decompress(b)
        elif cid=="blosc":
            import numcodecs
            b=numcodecs.get_codec(compressor).decode(b)
        else: raise ValueError("unsupported_compression:"+str(cid))
    dtype=np.dtype(za["dtype"])
    target=tuple(min(a,c) for a,c in zip(dims,chunks))
    if len(b)!=int(np.prod(target))*dtype.itemsize: raise ValueError("chunk_bytes_mismatch:"+path)
    x=np.frombuffer(b,dtype=dtype)
    return x.reshape(target,order=za.get("order","C"))
try:
    raw=download(".zmetadata",MAX_META)
    if hashlib.sha256(raw).hexdigest()!="92e064bb7cd87203518f452f8a142c4ab45e1325d5eace72b022ef78c3f3d343":
        raise ValueError("metadata_fingerprint_changed")
    md=json.loads(raw)["metadata"]
    paths=["magnetics/time_saddle","magnetics/b_field_tor_probe_saddle_voltage",
           "spectrometer_visible/time","spectrometer_visible/filter_spectrometer_dalpha_voltage",
           "pf_active/time","pf_active/coil_current"]
    arrays={}
    for path in paths:
        try: arrays[path]=chunk(path,md)
        except Exception as e: summary["errors"].append({"path":path,"error":str(e)})
    pairs=[("magnetics/time_saddle","magnetics/b_field_tor_probe_saddle_voltage"),
           ("spectrometer_visible/time","spectrometer_visible/filter_spectrometer_dalpha_voltage"),
           ("pf_active/time","pf_active/coil_current")]
    valid={}
    for tp,sp in pairs:
        if tp not in arrays or sp not in arrays: continue
        t=np.asarray(arrays[tp]).ravel().astype(float)
        x=np.asarray(arrays[sp])
        axis=int(md[sp+"/.zattrs"]["_ARRAY_DIMENSIONS"].index(tp.split("/")[-1]))
        x=np.moveaxis(x,axis,-1)
        if x.shape[-1]!=len(t): summary["errors"].append({"path":sp,"error":"first_chunk_time_length_mismatch"});continue
        if len(t)<8 or not np.isfinite(t).all() or not np.all(np.diff(t)>0): summary["errors"].append({"path":tp,"error":"time_not_finite_strictly_monotonic"});continue
        if not np.isfinite(x).all(): summary["errors"].append({"path":sp,"error":"nonfinite_chunk_values"});continue
        valid[sp]={"time":t,"value":x.reshape(-1,len(t)), "dt_median_s":float(np.median(np.diff(t))),"t_start":float(t[0]),"t_end":float(t[-1])}
    summary["valid_time_signal_pairs"]=list(valid)
    if len(valid)==3:
        summary["numeric_time_alignment_verified"]=True
        mag=valid["magnetics/b_field_tor_probe_saddle_voltage"];dal=valid["spectrometer_visible/filter_spectrometer_dalpha_voltage"];act=valid["pf_active/coil_current"]
        lo=max(z["t_start"] for z in (mag,dal,act));hi=min(z["t_end"] for z in (mag,dal,act))
        summary["overlap_seconds"]=max(0.0,hi-lo)
        if hi>lo:
            # Proxy anomaly locations are DESCRIPTIVE ONLY. The frozen Task-4.1 detector
            # is not reimplemented here; no precursor-reachability claim is allowed.
            summary["classification"]="TOKAMARK_BOUNDED_WAVEFORMS_ALIGNED_FROZEN_DETECTOR_NOT_EXECUTED"
            summary["next_gate"]="Run repository frozen Task-4.1 detector and event/null controls using complete calibrated spans; do not infer event lead from proxy anomaly peaks."
        else:
            summary["classification"]="TOKAMARK_BOUNDED_CHUNKS_NO_COMMON_TIME_OVERLAP"
    else: summary["classification"]="TOKAMARK_BOUNDED_CHUNK_INCOMPLETE"
except Exception as e:
    summary["classification"]="TOKAMARK_BOUNDED_DATA_ACCESS_OR_DECODER_FAILURE"
    summary["errors"].append({"stage":"source","error":str(e)})
summary["observational_only"]=True
summary["causal_tct_demonstration"]=False
summary["null_controls_executed"]=False
summary["claim_boundary"]="Chunk-level sample access and numeric synchronization checks are not precursor detection, intervention efficacy, or p-B11 physics. No fitted or substituted detector."
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print(json.dumps({"classification":summary["classification"],"valid_pairs":summary.get("valid_time_signal_pairs",[]),"errors":summary["errors"]},sort_keys=True))

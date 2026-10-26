#!/usr/bin/env python3
"""Bounded ZIP-central-directory metadata probe: never download the 2.4 GB archive."""
import json, os, pathlib, re, struct, urllib.request, datetime, hashlib
URL="https://zenodo.org/records/19452938/files/FENIX_data.zip?download=1"
OUT=pathlib.Path("validation_runs/tcv_fenix_zenodo_archive_index_113")
OUT.mkdir(parents=True,exist_ok=True)
summary={"schema_version":1,"source_id":"zenodo-19452938-tcv-fenix-experimental-recon","source":URL,"machine":"TCV","shot_ids":[73927,83448,87688,87697],"fuel_track":"fuel_agnostic_control","classification":"TCV_FENIX_ARCHIVE_PREFLIGHT_NOT_RUN","experimental_waveforms_ingested":False,"native_m3dc1_run":False,"causal_tct_demonstration":False,"license":"explicit redistribution terms not yet verified","timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
summary["runner_source_sha256"]=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
MAX_BYTES=8*1024*1024
def get_range(spec):
    req=urllib.request.Request(URL,headers={"Range":"bytes="+spec,"User-Agent":"CaMaLabs-TCT-metadata-preflight/1.0"})
    with urllib.request.urlopen(req,timeout=45) as resp:
        if resp.status!=206:
            raise RuntimeError("Range request returned HTTP %s; refusing full archive transfer"%resp.status)
        cr=resp.headers.get("Content-Range","")
        m=re.fullmatch(r"bytes[ ]+([0-9]+)-([0-9]+)/([0-9]+)",cr.strip())
        if not m: raise RuntimeError("Missing/invalid Content-Range: "+cr)
        length=int(m.group(2))-int(m.group(1))+1
        if length>MAX_BYTES: raise RuntimeError("Range exceeds bounded transfer")
        data=resp.read(length+1)
        if len(data)!=length: raise RuntimeError("Unexpected response length")
        return data,(int(m.group(1)),int(m.group(3)))
try:
    tail,(start,total)=get_range("-65557")
    ix=tail.rfind(b"PK\x05\x06")
    if ix<0 or len(tail)-ix<22: raise RuntimeError("ZIP end-of-central-directory absent")
    sig,disk,cd_disk,disk_n,n,cd_size,cd_offset,comment=struct.unpack_from("<IHHHHIIH",tail,ix)
    if disk or cd_disk or n!=disk_n or n==65535 or cd_offset==0xffffffff:
        raise RuntimeError("Multi-disk or ZIP64 archive requires separate audited handler")
    if cd_size<1 or cd_size>MAX_BYTES: raise RuntimeError("Central directory too large for bounded probe")
    cd,_=get_range("%d-%d"%(cd_offset,cd_offset+cd_size-1))
    names=[]; pos=0
    while pos<len(cd):
        if pos+46>len(cd): raise RuntimeError("Truncated central directory")
        h=struct.unpack_from("<IHHHHHHIIIHHHHHII",cd,pos)
        if h[0]!=0x02014b50: raise RuntimeError("Invalid central directory entry")
        fl,el,cl=h[10],h[11],h[12]
        name=cd[pos+46:pos+46+fl].decode("utf-8","replace")
        names.append(name)
        pos+=46+fl+el+cl
    expected={str(s):[f"TS_{s}.mat",f"KER_{s}_LIUQE.mat",f"KER_{s}_ASTRA.mat"] for s in (73927,83448)}
    matches={s:{f:any(n.endswith("/"+f) or n==f for n in names) for f in fs} for s,fs in expected.items()}
    summary.update({"classification":"TCV_FENIX_ARCHIVE_MEMBER_INDEX_VERIFIED" if any(all(x.values()) for x in matches.values()) else "TCV_FENIX_MEMBER_PREREQUISITES_INCOMPLETE","archive_size_bytes":total,"central_directory_entries":len(names),"matched_experimental_and_reconstruction_members":matches,"matching_members":[n for n in names if re.search(r"(TS_|KER_).*(73927|83448|87688|87697)|(?:73927|83448|87688|87697).*(?:TS_|KER_)",n)][:50],"next_step":"Inspect one paired TS/LIUQE MAT member with bounded verified extraction and check units, time and license; no physics job until source gate passes."})
except Exception as e:
    summary.update({"classification":"TCV_FENIX_ARCHIVE_RANGE_PREFLIGHT_BLOCKED","error":repr(e),"next_step":"Obtain archive index through an approved bounded-access path; do not download 2.4GB or assert shot ingestion."})
with (OUT/"summary.json").open("w",encoding="utf-8") as f:
    json.dump(summary,f,indent=2,sort_keys=True)
    f.write(chr(10))
print(json.dumps(summary,indent=2))

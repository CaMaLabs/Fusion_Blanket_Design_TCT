#!/usr/bin/env python3
"""Audit persisted native M3D-C1 C1.h5 external-link/checkpoint consistency without solver execution."""
from __future__ import annotations
import hashlib, json, re, subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/home/ubuntu/work/openmc/sweep')
CAP=REPO/'validation_runs/m3dc1_tct_native_restart_checkpoint_capture/captured'
OUT=REPO/'validation_runs/m3dc1_tct_native_restart_checkpoint_link_consistency'
EXPECTED={
'C1.h5':'842285cfec17235d76dc4f91c2230f74f31b5f9a25c224458f598dcdd5f1c5c4',
'equilibrium.h5':'bbafea066f96bea14ed31ef4064bab5354de4df5a6ceea782867b1359a7c63a4',
'time_000.h5':'f0a91cc1d9c8e71751caefa15eab996544ee5f8bf507a7bb5060f1c968bc0bad',
'time_001.h5':'32d4b5bd85648f93593533c79e6053b0678fb3831d0583221bffd7fa69a1dd80',
'time_002.h5':'620c8dd7a8f28d0901d6f7f8551bdf1803a1f04fd0bc7c7d2e76c5cbecfc5c47',
'time_003.h5':'cd0c5ce22e098d384455787d68c3550c143a32072e4778c21c2146c4952b3ae7',
'time_004.h5':'4024dfe22bc1e61bc164878dbdf56480cb36a945a659bd3d87b4463fad12e4a4',
'time_005.h5':'776b49b874dde55b5f0d901d8ef667d3a522e8dcc82ddd7a05b6749153f743bb'}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p):
    x=subprocess.run(['h5dump','-H',str(p)],text=True,capture_output=True)
    return x.returncode,x.stdout,x.stderr[-2000:]
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    missing=[n for n in EXPECTED if not (CAP/n).is_file()]
    hashes={n:sha(CAP/n) for n in EXPECTED if (CAP/n).is_file()}
    hash_ok=not missing and all(hashes.get(n)==v for n,v in EXPECTED.items())
    rc,h,err=dump(CAP/'C1.h5') if not missing else (2,'','missing artifacts')
    links=[]
    if rc==0:
        pat=re.compile(r'EXTERNAL_LINK\s+"([^"]+)"\s*\{\s*TARGETFILE\s+"([^"]+)"\s*TARGETPATH\s+"([^"]+)"',re.S)
        links=[{'name':a,'target_file':b,'target_path':c,'target_exists':(CAP/b).is_file()} for a,b,c in pat.findall(h)]
    time_links=sorted([x for x in links if x['name'].startswith('time_')],key=lambda x:x['name'])
    expected_times=[f'time_{i:03d}' for i in range(6)]
    names=[x['name'] for x in time_links]
    link_set_ok=names==expected_times and all(x['target_file']==x['name']+'.h5' and x['target_exists'] for x in time_links)
    latest_ok=bool(time_links) and time_links[-1]['name']=='time_005'
    pipeline_failure=bool(missing or rc!=0 or not hash_ok)
    classification=('M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_LINK_GRAPH_CONSISTENT' if not pipeline_failure and link_set_ok and latest_ok
                    else 'M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_LINK_GRAPH_INCONSISTENT' if not pipeline_failure
                    else 'M3DC1_TCT_NATIVE_RESTART_CHECKPOINT_LINK_AUDIT_FAILED')
    report={'classification':classification,'pipeline_failure':pipeline_failure,'parent_job_id':'20260918-026-native-restart-checkpoint-hdf5-header-audit',
      'audit_scope':'Verify persisted C1.h5 external-link graph, target presence, checkpoint sequence, and SHA-256 provenance; no M3D-C1 execution.',
      'missing_artifacts':missing,'hashes_match_job_025':hash_ok,'h5dump_return_code':rc,'h5dump_stderr_tail':err,
      'external_links':links,'time_link_names':names,'expected_time_link_names':expected_times,'link_set_ok':link_set_ok,'latest_time_link_ok':latest_ok,
      'zero_equivalence':'NOT_EVALUATED_LINK_AUDIT_ONLY','handoff_equivalence':'NOT_EVALUATED_LINK_AUDIT_ONLY',
      'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
      'claim_boundary':'Normalized native M3D-C1 restart artifact/link provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
      'finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_checkpoint_link_consistency_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 1 if pipeline_failure else 0
if __name__=='__main__': raise SystemExit(main())

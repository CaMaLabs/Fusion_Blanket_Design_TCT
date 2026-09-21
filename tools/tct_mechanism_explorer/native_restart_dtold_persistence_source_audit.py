#!/usr/bin/env python3
"""Static audit of native M3D-C1 restart persistence for dt/dtold.

Source-context collection only: no M3D-C1 execution or physics modification.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
OUT = REPO / 'validation_runs/m3dc1_tct_native_restart_dtold_persistence_source'
SOURCE_CANDIDATES = [Path('/home/ubuntu/M3DC1-official'), Path('/home/ubuntu/m3dc1')]
TARGETS = {'dt', 'dtold'}
IO_RX = re.compile(r'(h5|hdf5|restart|read|write|scalar|attribute|dataset)', re.I)
TOKEN_RX = re.compile(r'\b(dtold|dt)\b', re.I)

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    root = next((p for p in SOURCE_CANDIDATES if p.exists()), None)
    if root is None:
        report = {'classification':'M3DC1_TCT_NATIVE_RESTART_DTOLD_PERSISTENCE_SOURCE_AUDIT_SOURCE_NOT_FOUND','pipeline_failure':True,'source_candidates':[str(p) for p in SOURCE_CANDIDATES]}
    else:
        hits=[]
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in {'.f90','.f','.f95','.f03'}: continue
            try: lines=p.read_text(errors='replace').splitlines()
            except OSError: continue
            for i,line in enumerate(lines):
                if TOKEN_RX.search(line) and IO_RX.search(line):
                    lo=max(0,i-10); hi=min(len(lines),i+11)
                    hits.append({'path':str(p.relative_to(root)),'line':i+1,'match':line.strip(),'context':'\n'.join(lines[lo:hi])})
                elif TOKEN_RX.search(line) and ('restart_hdf5' in str(p).lower() or 'hdf5_output' in str(p).lower()):
                    lo=max(0,i-8); hi=min(len(lines),i+9)
                    hits.append({'path':str(p.relative_to(root)),'line':i+1,'match':line.strip(),'context':'\n'.join(lines[lo:hi])})
        uniq=[]; seen=set()
        for h in hits:
            k=(h['path'],h['line'])
            if k not in seen: seen.add(k); uniq.append(h)
        dtold_io=[h for h in uniq if re.search(r'\bdtold\b',h['match'],re.I)]
        report={
          'classification':'M3DC1_TCT_NATIVE_RESTART_DTOLD_PERSISTENCE_CONTEXT_CAPTURED' if uniq else 'M3DC1_TCT_NATIVE_RESTART_DTOLD_PERSISTENCE_CONTEXT_NOT_FOUND',
          'pipeline_failure':False,
          'parent_job_id':'20260921-035-native-restart-dtold-state-source-audit',
          'audit_scope':'Static source audit for explicit dt/dtold restart/HDF5 persistence paths; no M3D-C1 execution or physics modification.',
          'source_root':str(root),'hits':uniq[:100],'explicit_dtold_io_match_count':len(dtold_io),
          'interpretation_guard':'Absence of a textual dtold I/O match is not proof that dtold is not persisted indirectly; source context only.',
          'causation_status':'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION',
          'handoff_equivalence':'INHERITED_FAILED_AT_1E-12_FROM_JOB_028','zero_equivalence':'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
          'frozen_width_gate_pct_gt':0.02,'frozen_Jpk_gate_pct_le':0.1,
          'claim_boundary':'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
          'finished_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'native_restart_dtold_persistence_source_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2)); return 1 if report.get('pipeline_failure') else 0
if __name__=='__main__': raise SystemExit(main())

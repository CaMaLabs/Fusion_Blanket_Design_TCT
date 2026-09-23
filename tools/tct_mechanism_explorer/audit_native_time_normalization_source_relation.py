#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path

SRC=Path('/home/ubuntu/M3DC1-official')
OUT=Path('/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_time_normalization_source_relation_audit')
EXTS={'.f','.f90','.F','.F90','.c','.cc','.cpp','.h','.hpp'}
PAT=re.compile(r'(time.?scale|time.?norm|normaliz.{0,30}time|alfv[eé]n|tau[_a-z0-9]*|v[_]?a\b|r0\b|b0\b|rho0\b|den0\b)',re.I)

def main():
    if not SRC.is_dir():
        report={'classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_SOURCE_RELATION_AUDIT_PIPELINE_FAILURE','pipeline_failure':True,'pipeline_error':f'native source tree missing: {SRC}','physical_time_calibrated':False,'frozen_width_gate_pct_gt':0.020,'frozen_Jpk_gate_pct_le':0.10,'claim_boundary':'Normalized native M3D-C1 provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'}
        OUT.mkdir(parents=True,exist_ok=True); (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); return 96
    hits=[]
    for p in SRC.rglob('*'):
        if not p.is_file() or p.suffix not in EXTS: continue
        try: lines=p.read_text(errors='replace').splitlines()
        except Exception: continue
        for i,line in enumerate(lines):
            if PAT.search(line):
                lo=max(0,i-3); hi=min(len(lines),i+4)
                hits.append({'path':str(p.relative_to(SRC)),'line_number':i+1,'matched_line':line.strip(),'context':'\n'.join(lines[lo:hi])})
    report={
      'classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_SOURCE_RELATION_AUDITED',
      'pipeline_failure':False,
      'diagnostic_only':True,
      'parent_classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_PARAMETER_PROVENANCE_AUDITED',
      'source_context_hits':hits[:300],
      'physical_time_calibrated':False,
      'interpretation':'Native M3D-C1 source context relevant to time normalization was captured for explicit-relation review. Keyword/source context alone is not an SI time calibration; physical time remains fail-closed unless an explicit documented relation with sufficient parameters is present and subsequently verified.',
      'frozen_width_gate_pct_gt':0.020,
      'frozen_Jpk_gate_pct_le':0.10,
      'claim_boundary':'Normalized native M3D-C1 provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
    }
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

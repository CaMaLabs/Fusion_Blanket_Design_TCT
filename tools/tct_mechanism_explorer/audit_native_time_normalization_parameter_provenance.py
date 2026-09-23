#!/usr/bin/env python3
import json, re
from pathlib import Path

RUN = Path('validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run')
OUT = Path('validation_runs/m3dc1_tct_native_time_normalization_parameter_provenance_audit')
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = [RUN/'C1input', RUN/'C1ke', RUN/'C1stdout']
# Target normalization/characteristic-scale provenance rather than generic timing output.
pat = re.compile(r'(tau|alfven|va\b|v_a\b|b0\b|n0\b|rho0\b|r0\b|a0\b|length.?scale|time.?scale|normaliz|dimensionless)', re.I)
hits=[]
for p in SOURCES:
    if not p.exists():
        continue
    lines=p.read_text(errors='replace').splitlines()
    for i,line in enumerate(lines):
        if pat.search(line):
            lo=max(0,i-2); hi=min(len(lines),i+3)
            hits.append({'source':p.name,'line_number':i+1,'matched_line':line,'context':[{'line_number':j+1,'text':lines[j]} for j in range(lo,hi)]})
summary={
 'classification':'M3DC1_TCT_NATIVE_TIME_NORMALIZATION_PARAMETER_PROVENANCE_AUDITED',
 'pipeline_failure':False,
 'diagnostic_only':True,
 'parent_classification':'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_SECONDS_CONTEXT_AUDITED',
 'provenance_matches':hits,
 'physical_time_calibrated':False,
 'interpretation':'Native normalization/characteristic-scale parameter provenance was inventoried. No SI time conversion is established by this inventory alone; any conversion requires an explicit documented normalization relation and sufficient native parameters.',
 'frozen_width_gate_pct_gt':0.020,
 'frozen_Jpk_gate_pct_le':0.10,
 'claim_boundary':'Normalized native M3D-C1 provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

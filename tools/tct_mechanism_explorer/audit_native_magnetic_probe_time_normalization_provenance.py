#!/usr/bin/env python3
import json
import re
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
RUN = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run'
OUT = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_time_normalization_provenance_audit'
OUT.mkdir(parents=True, exist_ok=True)

c1input = (RUN / 'C1input').read_text(errors='replace')
c1ke = (RUN / 'C1ke').read_text(errors='replace') if (RUN / 'C1ke').exists() else ''
stdout = (RUN / 'C1stdout').read_text(errors='replace') if (RUN / 'C1stdout').exists() else ''

def scalar(name):
    m = re.search(rf'^\s*{re.escape(name)}\s*=\s*([^!\n/]+)', c1input, re.M | re.I)
    return m.group(1).strip() if m else None

inputs = {k: scalar(k) for k in ('dt','rzero','bzero','ion_mass','z_ion','xzero','xmag','p0','pi0')}
# Record only explicit textual provenance. Do not derive SI time from dimensional-looking
# parameters unless the native run itself declares the required unit/normalization relation.
patterns = [
    r'(?i)normaliz[^\n]*time[^\n]*', r'(?i)time[^\n]*normaliz[^\n]*',
    r'(?i)alfv[eé]n[^\n]*', r'(?i)tau[_ ]?a[^\n]*', r'(?i)seconds?[^\n]*',
    r'(?i)milliseconds?[^\n]*', r'(?i)microseconds?[^\n]*', r'(?i)time unit[^\n]*'
]
provenance = []
for source, text in [('C1input', c1input), ('C1ke', c1ke), ('C1stdout', stdout)]:
    for pat in patterns:
        for m in re.finditer(pat, text):
            line = m.group(0).strip()
            if line and {'source': source, 'text': line} not in provenance:
                provenance.append({'source': source, 'text': line})

summary = {
    'classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_TIME_NORMALIZATION_PROVENANCE_AUDITED',
    'pipeline_failure': False,
    'diagnostic_only': True,
    'parent_classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_TIME_METADATA_AUDITED',
    'native_input_scalars': inputs,
    'normalization_provenance_matches': provenance,
    'physical_time_calibrated': False,
    'interpretation': 'Native time values and dt are internally cross-consistent, but physical-time conversion remains fail-closed unless native output/input provenance explicitly establishes the time unit or normalization relation. No SI time is inferred from dimensional-looking input scalars alone.',
    'frozen_width_gate_pct_gt': 0.020,
    'frozen_Jpk_gate_pct_le': 0.10,
    'claim_boundary': 'Normalized native M3D-C1 magnetic diagnostic provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))

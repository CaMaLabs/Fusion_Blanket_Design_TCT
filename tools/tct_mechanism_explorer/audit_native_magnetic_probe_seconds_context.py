#!/usr/bin/env python3
import json
import re
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
RUN = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run'
OUT = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_seconds_context_audit'
OUT.mkdir(parents=True, exist_ok=True)

sources = {}
for name in ('C1input', 'C1ke', 'C1stdout'):
    p = RUN / name
    sources[name] = p.read_text(errors='replace') if p.exists() else ''

matches = []
for source, text in sources.items():
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(r'(?i)seconds?', line):
            lo = max(0, i - 3)
            hi = min(len(lines), i + 4)
            matches.append({
                'source': source,
                'line_number': i + 1,
                'matched_line': line.strip(),
                'context': [{'line_number': j + 1, 'text': lines[j]} for j in range(lo, hi)]
            })

# A bare occurrence of "seconds" is not enough to calibrate native time. This audit
# only records context so a later step can require an explicit relation tying the
# native time coordinate/dt to seconds.
summary = {
    'classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_SECONDS_CONTEXT_AUDITED',
    'pipeline_failure': False,
    'diagnostic_only': True,
    'parent_classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_TIME_NORMALIZATION_PROVENANCE_AUDITED',
    'seconds_context_matches': matches,
    'explicit_native_time_to_seconds_relation_established': False,
    'physical_time_calibrated': False,
    'interpretation': 'Context around every native provenance occurrence of seconds was captured. Physical-time conversion remains fail-closed unless the context explicitly relates the native time coordinate or dt to seconds.',
    'frozen_width_gate_pct_gt': 0.020,
    'frozen_Jpk_gate_pct_le': 0.10,
    'claim_boundary': 'Normalized native M3D-C1 magnetic diagnostic provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))

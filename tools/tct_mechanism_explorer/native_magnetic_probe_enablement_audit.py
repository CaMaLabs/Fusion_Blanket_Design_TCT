#!/usr/bin/env python3
import json, re
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
BASE = Path('/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE/C1input')
OUT = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_enablement_audit'
OUT.mkdir(parents=True, exist_ok=True)

patterns = ('imag_probes', 'mag_probe_x', 'mag_probe_z', 'mag_probe_phi', 'mag_probe_nx', 'mag_probe_nz', 'mag_probe_nphi')
examples = []
for root in (REPO / 'validation_inputs', REPO / 'validation_runs'):
    if not root.exists():
        continue
    for p in root.rglob('C1input*'):
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(errors='replace')
        except OSError:
            continue
        if 'imag_probes' not in text:
            continue
        lines = [ln.strip() for ln in text.splitlines() if any(k in ln.lower() for k in patterns)]
        examples.append({'path': str(p.relative_to(REPO)), 'probe_lines': lines[:40]})

base_text = BASE.read_text(errors='replace') if BASE.exists() else ''
base_probe_lines = [ln.strip() for ln in base_text.splitlines() if any(k in ln.lower() for k in patterns)]
active_examples = [e for e in examples if any(re.search(r'(?i)^\s*imag_probes\s*=\s*[1-9]', ln) for ln in e['probe_lines'])]

summary = {
    'audit_scope': 'Read-only provenance/enablement audit for native M3D-C1 magnetic probes; no solver physics modification.',
    'baseline_c1input': str(BASE),
    'baseline_probe_lines': base_probe_lines,
    'repository_probe_example_count': len(examples),
    'active_probe_example_count': len(active_examples),
    'active_probe_examples': active_examples[:20],
    'classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_ENABLEMENT_EVIDENCE_FOUND' if active_examples else 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_ENABLEMENT_NOT_ESTABLISHED',
    'pipeline_failure': False,
    'claim_boundary': 'Normalized native M3D-C1 diagnostic provenance/enablement only; no precursor lead-time, controller efficacy, experimental, or reactor-scale claim.',
    'next_step_contract': 'Only if native magnetic-probe enablement is evidenced, configure a diagnostic-only baseline rerun that preserves all plasma/actuator physics and records the native probe time series before constructing any precursor.'
}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))

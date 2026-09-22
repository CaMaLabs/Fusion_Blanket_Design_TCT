#!/usr/bin/env python3
import json
from pathlib import Path
import h5py

REPO = Path('/home/ubuntu/work/openmc/sweep')
RUN = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run'
OUT = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_time_metadata_audit'
OUT.mkdir(parents=True, exist_ok=True)

def clean(v):
    if hasattr(v, 'tolist'):
        v = v.tolist()
    if isinstance(v, bytes):
        return v.decode(errors='replace')
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    return v

def attrs(obj):
    return {str(k): clean(v) for k, v in obj.attrs.items()}

files = [RUN / 'C1.h5'] + sorted(RUN.glob('time_*.h5'))
records = []
for p in files:
    if not p.exists():
        continue
    with h5py.File(p, 'r') as h:
        rec = {'file': p.name, 'root_attributes': attrs(h), 'time_like_objects': []}
        def visit(name, obj):
            low = name.lower()
            if any(k in low for k in ('time', 'dt', 'step')):
                item = {'path': name, 'attributes': attrs(obj)}
                if isinstance(obj, h5py.Dataset):
                    item['shape'] = list(obj.shape)
                    item['dtype'] = str(obj.dtype)
                    if obj.size <= 64:
                        item['value'] = clean(obj[()])
                rec['time_like_objects'].append(item)
        h.visititems(visit)
        records.append(rec)

# This audit is intentionally conservative: metadata is evidence, but no physical
# milliseconds are inferred unless an explicit native value and unit are present.
explicit = []
for rec in records:
    for k, v in rec['root_attributes'].items():
        lk = k.lower()
        if any(x in lk for x in ('time', 'dt', 'timestep')):
            explicit.append({'file': rec['file'], 'source': 'root_attribute', 'key': k, 'value': v})
    for obj in rec['time_like_objects']:
        explicit.append({'file': rec['file'], 'source': 'object', **obj})

summary = {
    'classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_TIME_METADATA_AUDITED',
    'pipeline_failure': False,
    'diagnostic_only': True,
    'parent_classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_VALUE_SEMANTICS_AUDITED',
    'files_inspected': len(records),
    'time_metadata_candidates': explicit,
    'physical_time_calibrated': False,
    'interpretation': 'Native time-related metadata inventoried. Physical-time calibration remains fail-closed until an explicit native time value plus unit/normalization is positively identified and cross-checked; output index is not milliseconds.',
    'frozen_width_gate_pct_gt': 0.020,
    'frozen_Jpk_gate_pct_le': 0.10,
    'claim_boundary': 'Normalized native M3D-C1 magnetic diagnostic provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
}
(OUT / 'metadata_inventory.json').write_text(json.dumps(records, indent=2, default=str) + '\n')
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2, default=str) + '\n')
print(json.dumps(summary, indent=2, default=str))

#!/usr/bin/env python3
from pathlib import Path
import json

repo = Path('/home/ubuntu/work/openmc/sweep')
parent = repo / 'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries'
out = repo / 'validation_runs/m3dc1_tct_native_magnetic_probe_observable_audit'
out.mkdir(parents=True, exist_ok=True)

files = sorted(parent.glob('*.h5'))
findings = []
try:
    import h5py
    for path in files:
        with h5py.File(path, 'r') as h5:
            names = []
            def visitor(name, obj):
                low = name.lower()
                if any(k in low for k in ('probe','mag','br','b_r','fluxloop','flux_loop')):
                    shape = list(obj.shape) if hasattr(obj, 'shape') else None
                    names.append({'name': name, 'shape': shape})
            h5.visititems(visitor)
            findings.append({'file': path.name, 'matches': names})
    err = None
except Exception as exc:
    err = f'{type(exc).__name__}: {exc}'

usable = any(any(m.get('shape') and len(m['shape']) >= 1 and all(int(x) > 0 for x in m['shape']) for m in f['matches']) for f in findings)
classification = ('M3DC1_TCT_NATIVE_MAGNETIC_PROBE_OBSERVABLE_IDENTIFIED' if usable else
                  'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_OBSERVABLE_NOT_IDENTIFIED')
summary = {
    'classification': classification,
    'pipeline_failure': err is not None,
    'diagnostic_only': True,
    'parent_classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_SELECTED_TIMESERIES_CAPTURED',
    'hdf5_inspection_error': err,
    'observable_matches': findings,
    'usable_native_observable_identified': usable,
    'solver_physics_modified': False,
    'frozen_width_gate_pct_gt': 0.020,
    'frozen_Jpk_gate_pct_le': 0.10,
    'claim_boundary': 'Normalized native M3D-C1 magnetic diagnostic provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.',
    'next_step_contract': 'Construct no precursor unless a native magnetic-probe observable is positively identified and its time ordering/value semantics are verified.'
}
(out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
raise SystemExit(2 if err else 0)

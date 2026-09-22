#!/usr/bin/env python3
from pathlib import Path
import json

repo = Path('/home/ubuntu/work/openmc/sweep')
parent = repo / 'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run'
out = repo / 'validation_runs/m3dc1_tct_native_magnetic_probe_run_hdf5_schema_audit'
out.mkdir(parents=True, exist_ok=True)

inventory = []
err = None
try:
    import h5py
    paths = sorted(parent.glob('*.h5'))
    if not paths:
        raise FileNotFoundError(f'no HDF5 files found in selected-timeseries run directory: {parent}')
    for path in paths:
        entry = {'file': path.name, 'root_attributes': {}, 'objects': []}
        with h5py.File(path, 'r') as h5:
            for k, v in h5.attrs.items():
                try:
                    entry['root_attributes'][k] = v.tolist() if hasattr(v, 'tolist') else str(v)
                except Exception:
                    entry['root_attributes'][k] = repr(v)
            def visitor(name, obj):
                rec = {'name': name, 'kind': type(obj).__name__, 'attributes': {}}
                if hasattr(obj, 'shape'):
                    rec['shape'] = list(obj.shape)
                    rec['dtype'] = str(obj.dtype)
                for k, v in obj.attrs.items():
                    try:
                        rec['attributes'][k] = v.tolist() if hasattr(v, 'tolist') else str(v)
                    except Exception:
                        rec['attributes'][k] = repr(v)
                entry['objects'].append(rec)
            h5.visititems(visitor)
        inventory.append(entry)
except Exception as exc:
    err = f'{type(exc).__name__}: {exc}'

summary = {
    'classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_RUN_HDF5_SCHEMA_AUDITED' if err is None else 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_RUN_HDF5_SCHEMA_AUDIT_FAILED',
    'pipeline_failure': err is not None,
    'diagnostic_only': True,
    'parent_classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_HDF5_SCHEMA_AUDITED',
    'source_directory': str(parent),
    'hdf5_inspection_error': err,
    'file_count': len(inventory),
    'inventory': inventory,
    'solver_physics_modified': False,
    'frozen_width_gate_pct_gt': 0.020,
    'frozen_Jpk_gate_pct_le': 0.10,
    'claim_boundary': 'Normalized native M3D-C1 magnetic diagnostic provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.',
    'next_step_contract': 'Use this corrected run-directory schema inventory only to locate documented native probe output semantics; do not construct a precursor until a magnetic observable and its time/value semantics are positively established.'
}
(out/'summary.json').write_text(json.dumps(summary, indent=2, default=str)+'\n')
print(json.dumps(summary, indent=2, default=str))
raise SystemExit(2 if err else 0)

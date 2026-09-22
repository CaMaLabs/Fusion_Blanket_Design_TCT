#!/usr/bin/env python3
import json
from pathlib import Path
import h5py

repo = Path('/home/ubuntu/work/openmc/sweep')
run = repo / 'validation_runs/m3dc1_tct_native_magnetic_probe_selected_timeseries/run'
out = repo / 'validation_runs/m3dc1_tct_native_magnetic_probe_value_semantics_audit'
out.mkdir(parents=True, exist_ok=True)
summary_path = out / 'summary.json'

result = {
    'classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_VALUE_SEMANTICS_AUDITED',
    'pipeline_failure': False,
    'diagnostic_only': True,
    'parent_classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_RUN_HDF5_SCHEMA_AUDITED',
    'source_file': str(run / 'C1.h5'),
    'observable_path': 'mag_probes/value',
    'observable_identified': False,
    'time_ordering_identified': False,
    'value_semantics_identified': False,
    'frozen_width_gate_pct_gt': 0.020,
    'frozen_Jpk_gate_pct_le': 0.10,
    'claim_boundary': 'Normalized native M3D-C1 magnetic diagnostic provenance only; no Mirnov equivalence, precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
}
try:
    with h5py.File(run / 'C1.h5', 'r') as h5:
        if 'mag_probes/value' not in h5:
            raise RuntimeError('mag_probes/value missing from C1.h5')
        ds = h5['mag_probes/value']
        values = ds[...]
        result['observable_identified'] = True
        result['shape'] = list(values.shape)
        result['dtype'] = str(values.dtype)
        result['values'] = values.tolist()
        result['dataset_attributes'] = {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in ds.attrs.items()}
        result['root_ntime'] = int(h5.attrs['ntime']) if 'ntime' in h5.attrs else None
        result['scalar_ntimestep'] = int(h5['scalars'].attrs['ntimestep']) if 'scalars' in h5 and 'ntimestep' in h5['scalars'].attrs else None
        # A 6x1 probe vector with ntime=6 and ntimestep=5 establishes native sample ordering
        # by solver output index. It does not establish physical milliseconds.
        result['time_ordering_identified'] = bool(values.ndim == 2 and values.shape[0] == result['root_ntime'] and result['scalar_ntimestep'] == values.shape[0] - 1)
        result['time_semantics'] = 'native solver output-index ordering only; no physical-time calibration inferred'
        # Positive identification is limited to the native mag_probes dataset. Component/unit
        # semantics require explicit native metadata/input provenance and are not guessed here.
        result['value_semantics_identified'] = bool(result['observable_identified'])
        result['value_semantics'] = 'native M3D-C1 mag_probes/value output for the configured single probe; component/unit interpretation remains limited to configured native probe provenance'
except Exception as exc:
    result['pipeline_failure'] = True
    result['error'] = f'{type(exc).__name__}: {exc}'

summary_path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(2 if result['pipeline_failure'] else 0)

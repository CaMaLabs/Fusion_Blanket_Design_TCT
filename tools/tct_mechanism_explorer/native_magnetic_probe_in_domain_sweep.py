#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
BASE = Path('/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE')
OUT = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_in_domain_sweep'
PARENT = REPO / 'validation_runs/m3dc1_tct_native_magnetic_probe_placement_audit/summary.json'
BIN = Path(os.environ.get('M3DC1_BIN', '/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d'))
MPI = shutil.which('mpiexec.mpich') or shutil.which('mpirun')

if not PARENT.exists():
    raise SystemExit('missing parent summary')
parent = json.loads(PARENT.read_text())
if parent.get('classification') != 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_PLACEMENT_INVALID_CONFIRMED':
    raise SystemExit('unexpected parent classification')
if not BIN.exists() or not os.access(BIN, os.X_OK):
    raise SystemExit(f'missing executable: {BIN}')
if not MPI:
    raise SystemExit('missing MPI launcher')

axes = parent.get('magnetic_axis_matches') or []
if not axes:
    raise SystemExit('parent did not capture a native magnetic axis')
axis_r = float(axes[0][0])
axis_z = float(axes[0][1])

# Geometry-only bounded sweep. These points deliberately span the magnetic axis
# and a modest radial/vertical neighborhood. A valid point is only an in-domain
# placement candidate; it is NOT automatically a Mirnov-equivalent location.
candidates = [
    ('axis', axis_r, axis_z),
    ('out_r_0p50', axis_r + 0.50, axis_z),
    ('out_r_0p80', axis_r + 0.80, axis_z),
    ('out_r_0p95', axis_r + 0.95, axis_z),
    ('out_r_1p10', axis_r + 1.10, axis_z),
    ('in_r_0p50', axis_r - 0.50, axis_z),
    ('in_r_0p80', axis_r - 0.80, axis_z),
    ('up_z_0p50', axis_r, axis_z + 0.50),
    ('down_z_0p50', axis_r, axis_z - 0.50),
]

OUT.mkdir(parents=True, exist_ok=True)
runs = OUT / 'runs'
if runs.exists():
    shutil.rmtree(runs)
runs.mkdir()

float_pat = r'([+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)'
point_re = re.compile(r'Point not found in domain:\s+' + float_pat + r'\s+' + float_pat + r'\s+' + float_pat)

def set_key(text: str, key: str, value: str) -> str:
    pat = re.compile(rf'^(\s*{re.escape(key)}\s*=\s*)(.*?)(\s*(?:!.*)?$)', re.M)
    if pat.search(text):
        return pat.sub(rf'\g<1>{value}\g<3>', text, count=1)
    return text.replace('\n /', f'\n  {key} = {value}\n /', 1)

results = []
for name, r, z in candidates:
    run_dir = runs / name
    shutil.copytree(BASE, run_dir)
    for p in run_dir.glob('*.h5'):
        p.unlink()
    inp = run_dir / 'C1input'
    text = inp.read_text()
    text = set_key(text, 'imag_probes', '1')
    text = set_key(text, 'mag_probe_x(1)', f'{r:.8f}')
    text = set_key(text, 'mag_probe_phi(1)', '0.0')
    text = set_key(text, 'mag_probe_z(1)', f'{z:.8f}')
    text = set_key(text, 'mag_probe_nx(1)', '1.0')
    text = set_key(text, 'mag_probe_nz(1)', '0.0')
    inp.write_text(text)

    log = run_dir / 'probe.log'
    with log.open('w') as fh:
        proc = subprocess.run([MPI, '-np', '1', str(BIN)], cwd=run_dir, stdin=inp.open(), stdout=fh, stderr=subprocess.STDOUT, text=True)
    log_text = log.read_text(errors='replace')
    rejects = []
    for m in point_re.finditer(log_text):
        x, phi, zz = map(float, m.groups())
        rejects.append([x, phi, zz])
    rejected_requested = any(abs(x-r) <= 5e-4 and abs(zz-z) <= 5e-4 for x, _phi, zz in rejects)
    results.append({
        'name': name,
        'r': r,
        'z': z,
        'return_code': proc.returncode,
        'requested_point_rejected': rejected_requested,
        'in_domain_candidate': proc.returncode == 0 and not rejected_requested,
        'point_not_found_matches': rejects,
        'log_tail': log_text[-4000:],
    })

valid = [x for x in results if x['in_domain_candidate']]
radial_valid = [x for x in valid if x['name'].startswith(('out_r_', 'in_r_'))]
selected = max(radial_valid, key=lambda x: math.hypot(x['r']-axis_r, x['z']-axis_z), default=(valid[0] if valid else None))
classification = (
    'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_IN_DOMAIN_CANDIDATE_FOUND'
    if valid else
    'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_IN_DOMAIN_CANDIDATE_NOT_FOUND'
)
summary = {
    'classification': classification,
    'pipeline_failure': False,
    'diagnostic_only': True,
    'parent_classification': parent['classification'],
    'native_magnetic_axis': {'r': axis_r, 'z': axis_z},
    'candidate_results': results,
    'selected_in_domain_candidate': None if selected is None else {
        'name': selected['name'], 'r': selected['r'], 'z': selected['z'], 'orientation': 'BR/nx=1.0'
    },
    'selected_candidate_status': 'GEOMETRY_ONLY_NOT_YET_MIRNOV_EQUIVALENT',
    'solver_physics_modified': False,
    'frozen_width_gate_pct_gt': 0.020,
    'frozen_Jpk_gate_pct_le': 0.10,
    'claim_boundary': 'Normalized native M3D-C1 magnetic diagnostic geometry/provenance only; no precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.',
    'next_step_contract': 'Only if an in-domain candidate is found, use a separate diagnostic-only native run to capture its magnetic-probe time series before any precursor or controller analysis.'
}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))

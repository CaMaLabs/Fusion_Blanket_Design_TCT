#!/usr/bin/env python3
from pathlib import Path
import json, re

repo = Path('/home/ubuntu/work/openmc/sweep')
log = repo / 'agent_pipeline/logs/20260921-050-native-magnetic-probe-timeseries-baseline-env-repair.log'
out = repo / 'validation_runs/m3dc1_tct_native_magnetic_probe_placement_audit'
out.mkdir(parents=True, exist_ok=True)
text = log.read_text(errors='replace')
requested = re.findall(r'Point not found in domain:\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)', text)
axes = re.findall(r'magnetic axis:\s+([+-]?\d+(?:\.\d+)?(?:E[+-]?\d+)?)\s+([+-]?\d+(?:\.\d+)?(?:E[+-]?\d+)?)', text, re.I)
summary = {
  'classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_PLACEMENT_INVALID_CONFIRMED',
  'pipeline_failure': False,
  'scientific_negative_result': True,
  'parent_classification': 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_TIMESERIES_BASELINE_CAPTURED',
  'requested_probe_point': {'x': 2.3, 'z': 0.0, 'nx': 1.0},
  'point_not_found_matches': requested,
  'magnetic_axis_matches': axes,
  'probe_valid': not any(abs(float(x)-2.3) < 1e-12 and abs(float(z)) < 1e-12 for x, z, _ in requested),
  'interpretation': 'The native solver completed, but the requested magnetic probe point was explicitly reported outside the computational domain. Do not treat the run as a valid magnetic-probe timeseries measurement. Establish an in-domain probe location from native geometry before any precursor analysis.',
  'solver_physics_modified': False,
  'frozen_width_gate_pct_gt': 0.020,
  'frozen_Jpk_gate_pct_le': 0.10,
  'claim_boundary': 'Normalized native M3D-C1 magnetic diagnostic geometry/provenance only; no precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.'
}
(out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))

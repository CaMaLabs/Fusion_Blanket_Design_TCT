#!/usr/bin/env python3
"""Trace native M3D-C1 unsplit timestep work vectors across restart.

Focuses on vectors freshly created by initialize_timestep_unsplit (phi_vec,
phip_vec, q4_vec, b1_phi, b2_phi) and finds where they are initialized,
updated, copied, or serialized. Static source context only.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
OUT = REPO / 'validation_runs/m3dc1_tct_native_restart_unsplit_work_vectors'
SOURCE_CANDIDATES = [Path('/home/ubuntu/M3DC1-official'), Path('/home/ubuntu/m3dc1')]
TOKENS = ('phi_vec', 'phip_vec', 'q4_vec', 'b1_phi', 'b2_phi')
ACTION_RX = re.compile(r'(=|copy|vec|assign|create|destroy|read|write|restart|initialize|advance|solve)', re.I)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    root = next((p for p in SOURCE_CANDIDATES if p.exists()), None)
    if root is None:
        report = {
            'classification': 'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_WORK_VECTOR_SOURCE_NOT_FOUND',
            'pipeline_failure': True,
            'source_candidates': [str(p) for p in SOURCE_CANDIDATES],
        }
    else:
        hits = {token: [] for token in TOKENS}
        files_scanned = 0
        for p in sorted(root.rglob('*.f90')):
            try:
                lines = p.read_text(errors='replace').splitlines()
            except OSError:
                continue
            files_scanned += 1
            for i, line in enumerate(lines):
                lower = line.lower()
                for token in TOKENS:
                    if token in lower and ACTION_RX.search(line):
                        lo = max(0, i - 8)
                        hi = min(len(lines), i + 9)
                        hits[token].append({
                            'path': str(p.relative_to(root)),
                            'line': i + 1,
                            'match': line.strip(),
                            'context': '\n'.join(lines[lo:hi]),
                        })
        restart_text = ''
        restart_path = root / 'unstructured/restart_hdf5.f90'
        if restart_path.exists():
            restart_text = restart_path.read_text(errors='replace')
        explicit_restart_mentions = {
            token: bool(re.search(rf'\b{re.escape(token)}\b', restart_text, re.I))
            for token in TOKENS
        }
        report = {
            'classification': 'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_WORK_VECTOR_CONTEXT_CAPTURED',
            'pipeline_failure': False,
            'parent_job_id': '20260921-042-native-restart-unsplit-history-reconstruction-audit',
            'audit_scope': 'Static trace of unsplit timestep work-vector lifecycle after job 042 showed these vectors are freshly created on restart; no solver execution or modification.',
            'source_root': str(root),
            'files_scanned': files_scanned,
            'tokens': list(TOKENS),
            'hits': {k: v[:100] for k, v in hits.items()},
            'explicit_restart_hdf5_mentions': explicit_restart_mentions,
            'interpretation_guard': 'Fresh allocation or lack of a direct restart_hdf5 mention does not by itself prove a causative missing state. Use the source trace to define one minimal dynamic initialization test.',
            'causation_status': 'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION',
            'handoff_equivalence': 'FAILED_AT_1E-12_IN_JOB_041_WITH_DOUBLE_CHECKPOINT_FIELDS',
            'zero_equivalence': 'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
            'frozen_width_gate_pct_gt': 0.02,
            'frozen_Jpk_gate_pct_le': 0.1,
            'claim_boundary': 'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
            'finished_utc': datetime.now(timezone.utc).isoformat(),
        }
    (OUT / 'native_restart_unsplit_work_vector_summary.json').write_text(
        json.dumps(report, indent=2, sort_keys=True) + '\n'
    )
    print(json.dumps(report, indent=2))
    return 1 if report.get('pipeline_failure') else 0


if __name__ == '__main__':
    raise SystemExit(main())

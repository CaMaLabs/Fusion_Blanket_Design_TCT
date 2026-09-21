#!/usr/bin/env python3
"""Static audit of unsplit timestep/history reconstruction across native restart.

No M3D-C1 execution or source modification. The goal is to identify state used
by the first postrestart step that is reconstructed rather than serialized.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
OUT = REPO / 'validation_runs/m3dc1_tct_native_restart_unsplit_history_reconstruction'
SOURCE_CANDIDATES = [Path('/home/ubuntu/M3DC1-official'), Path('/home/ubuntu/m3dc1')]
TARGET_ROUTINES = {
    'initialize_timestep',
    'initialize_timestep_unsplit',
    'assign_variables_unsplit',
    'advance_timestep_unsplit',
    'finalize_timestep_unsplit',
}
HISTORY_RX = re.compile(r'\b(?:\w*(?:old|prev|previous|last|hist|save|guess|0|n1|nm1)\w*)\b', re.I)
RESTART_RX = re.compile(r'\b(?:irestart|ntime0|restart)\b', re.I)


def extract_routines(path: Path) -> list[dict]:
    try:
        lines = path.read_text(errors='replace').splitlines()
    except OSError:
        return []
    out = []
    i = 0
    start_rx = re.compile(r'^\s*subroutine\s+([a-z0-9_]+)\b', re.I)
    end_rx = re.compile(r'^\s*end\s+subroutine\b', re.I)
    while i < len(lines):
        m = start_rx.search(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1).lower()
        start = i
        j = i + 1
        while j < len(lines) and not end_rx.search(lines[j]):
            j += 1
        body = '\n'.join(lines[start:min(j + 1, len(lines))])
        if name in TARGET_ROUTINES or (RESTART_RX.search(body) and ('time_step' in path.name.lower() or 'newpar' in path.name.lower())):
            out.append({
                'path': str(path),
                'name': name,
                'start_line': start + 1,
                'end_line': min(j + 1, len(lines)),
                'body': body,
                'restart_condition_present': bool(RESTART_RX.search(body)),
                'history_tokens': sorted(set(HISTORY_RX.findall(body)))[:120],
            })
        i = max(j + 1, i + 1)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    root = next((p for p in SOURCE_CANDIDATES if p.exists()), None)
    if root is None:
        report = {
            'classification': 'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_HISTORY_RECONSTRUCTION_SOURCE_NOT_FOUND',
            'pipeline_failure': True,
            'source_candidates': [str(p) for p in SOURCE_CANDIDATES],
        }
    else:
        routines = []
        for p in sorted(root.rglob('*.f90')):
            if any(k in p.name.lower() for k in ('time_step', 'newpar', 'restart')):
                routines.extend(extract_routines(p))

        named = {r['name']: r for r in routines if r['name'] in TARGET_ROUTINES}
        # Collect symbols assigned or referenced in the two initialization routines,
        # then look for direct serialization references in restart_hdf5.f90.
        focus_text = '\n'.join(
            named[n]['body'] for n in ('initialize_timestep_unsplit', 'assign_variables_unsplit') if n in named
        )
        candidates = sorted(set(re.findall(r'\b[a-z][a-z0-9_]*(?:old|prev|last|guess|0|n1|nm1)[a-z0-9_]*\b', focus_text, re.I)))
        restart_path = root / 'unstructured/restart_hdf5.f90'
        restart_text = restart_path.read_text(errors='replace') if restart_path.exists() else ''
        candidate_serialization = {
            symbol: bool(re.search(rf'\b{re.escape(symbol)}\b', restart_text, re.I))
            for symbol in candidates
        }
        unmentioned = [k for k, v in candidate_serialization.items() if not v]
        restart_conditioned_routines = [
            {'path': r['path'], 'name': r['name'], 'start_line': r['start_line'], 'end_line': r['end_line']}
            for r in routines if r['restart_condition_present']
        ]

        classification = (
            'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_HISTORY_RECONSTRUCTION_CONTEXT_CAPTURED'
            if named else
            'M3DC1_TCT_NATIVE_RESTART_UNSPLIT_HISTORY_RECONSTRUCTION_CONTEXT_NOT_FOUND'
        )
        report = {
            'classification': classification,
            'pipeline_failure': False,
            'parent_job_id': '20260921-041-native-restart-full-precision-handoff-repair-rerun',
            'audit_scope': 'Static native M3D-C1 audit of unsplit timestep initialization/history reconstruction after full-precision restart failed to restore 1e-12 handoff equivalence; no solver execution or modification.',
            'source_root': str(root),
            'target_routines_found': sorted(named),
            'target_routines': [named[n] for n in sorted(named)],
            'restart_conditioned_routines': restart_conditioned_routines,
            'history_candidate_symbols': candidates,
            'history_candidate_explicit_restart_mentions': candidate_serialization,
            'history_candidates_without_explicit_restart_mention': unmentioned,
            'interpretation_guard': 'Static absence from restart_hdf5.f90 is not proof of missing persistence; use only to select one dynamic reconstruction test.',
            'causation_status': 'STATIC_SOURCE_CONTEXT_ONLY_NOT_DYNAMIC_CAUSATION',
            'handoff_equivalence': 'FAILED_AT_1E-12_IN_JOB_041_WITH_DOUBLE_CHECKPOINT_FIELDS',
            'zero_equivalence': 'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
            'frozen_width_gate_pct_gt': 0.02,
            'frozen_Jpk_gate_pct_le': 0.1,
            'claim_boundary': 'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
            'finished_utc': datetime.now(timezone.utc).isoformat(),
        }
    (OUT / 'native_restart_unsplit_history_reconstruction_summary.json').write_text(
        json.dumps(report, indent=2, sort_keys=True) + '\n'
    )
    print(json.dumps(report, indent=2))
    return 1 if report.get('pipeline_failure') else 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Static audit of native M3D-C1 restart-field HDF5 precision paths.

This audit is source/provenance only. It does not execute or modify M3D-C1.
It is intended to determine whether the restart time-slice state used by
rdrestart_hdf5 is serialized at lower precision than the live solver state.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/home/ubuntu/work/openmc/sweep')
OUT = REPO / 'validation_runs/m3dc1_tct_native_restart_field_precision_source'
SOURCE_CANDIDATES = [Path('/home/ubuntu/M3DC1-official'), Path('/home/ubuntu/m3dc1')]
HEADER = REPO / 'validation_runs/m3dc1_tct_native_restart_checkpoint_hdf5_header/C1.h5.header.txt'

SOURCE_NAMES = {
    'unstructured/hdf5_output.f90',
    'unstructured/restart_hdf5.f90',
    'unstructured/output.f90',
    'unstructured/field.f90',
    'unstructured/M3Dmodules.f90',
}
PATTERNS = [
    re.compile(r'\boutput_fields\b', re.I),
    re.compile(r'\bread_fields\b', re.I),
    re.compile(r'\bh5d(create|write|read)_f\b', re.I),
    re.compile(r'\bH5T_(NATIVE|IEEE|STD)[A-Z0-9_]*\b', re.I),
    re.compile(r'\breal\s*\*\s*[48]\b', re.I),
    re.compile(r'\breal\s*\(\s*kind\s*=\s*[48]\s*\)', re.I),
    re.compile(r'\b(float|double|single|precision|real_type|hdf5_type)\b', re.I),
]


def context(lines: list[str], idx: int, radius: int = 10) -> str:
    lo = max(0, idx - radius)
    hi = min(len(lines), idx + radius + 1)
    return '\n'.join(lines[lo:hi])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    root = next((p for p in SOURCE_CANDIDATES if p.exists()), None)
    if root is None:
        report = {
            'classification': 'M3DC1_TCT_NATIVE_RESTART_FIELD_PRECISION_SOURCE_AUDIT_SOURCE_NOT_FOUND',
            'pipeline_failure': True,
            'source_candidates': [str(p) for p in SOURCE_CANDIDATES],
        }
    else:
        hits = []
        for rel in sorted(SOURCE_NAMES):
            p = root / rel
            if not p.exists():
                continue
            try:
                lines = p.read_text(errors='replace').splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                if any(rx.search(line) for rx in PATTERNS):
                    hits.append({
                        'path': rel,
                        'line': i + 1,
                        'match': line.strip(),
                        'context': context(lines, i),
                    })

        header_f32_count = 0
        header_f64_count = 0
        header_field_examples = []
        header_present = HEADER.exists()
        if header_present:
            text = HEADER.read_text(errors='replace')
            header_f32_count = len(re.findall(r'H5T_IEEE_F32(?:LE|BE)?', text, re.I))
            header_f64_count = len(re.findall(r'H5T_IEEE_F64(?:LE|BE)?', text, re.I))
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if 'DATASET ' in line:
                    block = '\n'.join(lines[i:i+5])
                    if re.search(r'H5T_IEEE_F32(?:LE|BE)?', block, re.I):
                        header_field_examples.append(block)
                        if len(header_field_examples) >= 12:
                            break

        source_has_read_fields = any(re.search(r'\bread_fields\b', h['match'], re.I) for h in hits)
        source_has_output_fields = any(re.search(r'\boutput_fields\b', h['match'], re.I) for h in hits)
        source_has_hdf5_io = any(re.search(r'\bh5d(create|write|read)_f\b', h['match'], re.I) for h in hits)
        precision_context = any(re.search(r'H5T_|precision|float|double|real\s*\*\s*[48]|kind\s*=\s*[48]', h['match'], re.I) for h in hits)

        confirmed = bool(
            header_present
            and header_f32_count > 0
            and source_has_read_fields
            and source_has_output_fields
            and source_has_hdf5_io
            and precision_context
        )
        classification = (
            'M3DC1_TCT_NATIVE_RESTART_FIELD_PRECISION_PATH_CONFIRMED'
            if confirmed else
            'M3DC1_TCT_NATIVE_RESTART_FIELD_PRECISION_CONTEXT_CAPTURED'
        )
        report = {
            'classification': classification,
            'pipeline_failure': False,
            'parent_job_id': '20260921-036-native-restart-dtold-persistence-source-audit',
            'audit_scope': 'Static source/provenance audit of native M3D-C1 restart time-slice field precision; no solver execution or physics modification.',
            'source_root': str(root),
            'source_hits': hits[:160],
            'checkpoint_header_path': str(HEADER),
            'checkpoint_header_present': header_present,
            'checkpoint_header_f32_type_occurrences': header_f32_count,
            'checkpoint_header_f64_type_occurrences': header_f64_count,
            'checkpoint_f32_dataset_examples': header_field_examples,
            'source_path_checks': {
                'read_fields_found': source_has_read_fields,
                'output_fields_found': source_has_output_fields,
                'hdf5_dataset_io_found': source_has_hdf5_io,
                'precision_context_found': precision_context,
            },
            'causation_status': 'PRECISION_PATH_PROVENANCE_ONLY_NOT_DYNAMIC_CAUSATION',
            'handoff_equivalence': 'INHERITED_FAILED_AT_1E-12_FROM_JOB_028',
            'zero_equivalence': 'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
            'frozen_width_gate_pct_gt': 0.02,
            'frozen_Jpk_gate_pct_le': 0.1,
            'claim_boundary': 'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
            'finished_utc': datetime.now(timezone.utc).isoformat(),
        }
    (OUT / 'native_restart_field_precision_source_summary.json').write_text(
        json.dumps(report, indent=2, sort_keys=True) + '\n'
    )
    print(json.dumps(report, indent=2))
    return 1 if report.get('pipeline_failure') else 0


if __name__ == '__main__':
    raise SystemExit(main())

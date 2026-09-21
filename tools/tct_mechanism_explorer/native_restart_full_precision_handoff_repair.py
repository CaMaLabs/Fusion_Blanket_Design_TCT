#!/usr/bin/env python3
"""Dynamic native M3D-C1 restart handoff test using its built-in double HDF5 output.

This does not change solver equations or actuator physics. It enables the native
idouble_out path for both continuous and split source=0 arms, then requires
continuous-vs-restart equivalence at the checkpoint, first postrestart step,
and final matched time to 1e-12.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pulse_train_audit as pta

REPO = Path('/home/ubuntu/work/openmc/sweep')
BASE = Path('/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE')
SRC = Path('/home/ubuntu/M3DC1-official')
EXE = SRC / 'build-ubuntu-2d/unstructured/m3dc1_2d'
OUT = REPO / 'validation_runs/m3dc1_tct_native_restart_full_precision_handoff'
ROOT = Path('/tmp/m3dc1_tct_native_restart_full_precision_handoff_runs')
DT = 0.01
SPLIT = 5
TOTAL = 10
TOL = 1e-12
METRICS = (
    'W_sheet', 'Jpk', 'Jint_high', 'center_abs_current',
    'shoulder_abs_current', 'Reconnected_Flux', 'magnetic_energy',
)


def rm(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path) if path.is_dir() else path.unlink()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def idouble_out_registered() -> bool:
    candidates = [
        SRC / 'unstructured/input.f90',
        SRC / 'unstructured/M3Dmodules.f90',
        SRC / 'unstructured/hdf5_output.f90',
    ]
    text = '\n'.join(p.read_text(errors='replace') for p in candidates if p.exists())
    return bool(re.search(r'\bidouble_out\b', text, re.I))


def prep(name: str, steps: int, restart: int = 0, restart_slice: int = -1,
         write_restart: int = 0, ntimers: int = 1) -> Path:
    d = ROOT / name
    rm(d)
    d.mkdir(parents=True)
    for item in pta.COPY_NAMES:
        src = BASE / item
        if src.is_symlink():
            (d / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, d / item)
    text = (BASE / 'C1input').read_text()
    updates = {
        'dt': f'{DT:.10g}',
        'ntimemax': str(steps),
        'ntimepr': '1',
        'irestart': str(restart),
        'irestart_slice': str(restart_slice),
        'iwrite_restart': str(write_restart),
        'ntimers': str(ntimers),
        'idouble_out': '1',
        'imag_control': '0',
        'mag_ctrl_amp': '0.0',
        'icd_source': '0',
        'J_0cd': '0.0',
    }
    for key, value in updates.items():
        text = pta.replace_or_add(text, key, value)
    (d / 'C1input').write_text(text)
    return d


def run(d: Path) -> dict:
    shell = f'''
set -euo pipefail
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
export TMPDIR="/tmp/tct-${{USER:-ubuntu}}"
export OMPI_MCA_orte_tmpdir_base="$TMPDIR"
mkdir -p "$TMPDIR"
cd "{d}"
set +e
timeout 1200s mpirun --oversubscribe -n 1 "{EXE}" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
rc=$?
set -e
exit "$rc"
'''
    t0 = time.time()
    p = subprocess.run(['bash', '-lc', shell], text=True, capture_output=True)
    return {
        'return_code': p.returncode,
        'elapsed_seconds': time.time() - t0,
        'wrapper_stdout_tail': p.stdout[-2000:],
        'wrapper_stderr_tail': p.stderr[-2000:],
        'C1stdout_tail': (d / 'C1stdout').read_text(errors='replace')[-3000:]
        if (d / 'C1stdout').exists() else '',
        'launcher_stderr_tail': (d / 'launcher.stderr').read_text(errors='replace')[-2000:]
        if (d / 'launcher.stderr').exists() else '',
    }


def compare(a: dict, b: dict) -> dict:
    by_metric = {}
    ok = True
    for metric in METRICS:
        av = float(a[metric])
        bv = float(b[metric])
        delta = bv - av
        passed = abs(delta) <= TOL
        ok = ok and passed
        by_metric[metric] = {'continuous': av, 'split': bv, 'delta': delta, 'pass': passed}
    td = float(b['time']) - float(a['time'])
    tp = abs(td) <= TOL
    return {
        'pass': ok and tp,
        'continuous_time': float(a['time']),
        'split_time': float(b['time']),
        'time_delta': td,
        'time_pass': tp,
        'by_metric': by_metric,
    }


def nearest(rows: list[dict], target: float) -> dict:
    return min(rows, key=lambda row: abs(float(row['time']) - target))


def inspect_checkpoint_precision(d: Path) -> dict:
    target = d / f'time_{SPLIT:03d}.h5'
    if not target.exists():
        return {'path': str(target), 'exists': False, 'psi_double': False, 'I_double': False}
    shell = f'''
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
h5dump -H "{target}"
'''
    p = subprocess.run(['bash', '-lc', shell], text=True, capture_output=True)
    text = p.stdout
    def dataset_is_double(name: str) -> bool:
        m = re.search(rf'DATASET\s+"{re.escape(name)}"\s*\{{(.{{0,400}}?)\n\s*\}}', text, re.I | re.S)
        return bool(m and re.search(r'H5T_IEEE_F64|H5T_NATIVE_DOUBLE', m.group(1), re.I))
    return {
        'path': str(target),
        'exists': True,
        'h5dump_return_code': p.returncode,
        'psi_double': dataset_is_double('psi'),
        'I_double': dataset_is_double('I'),
        'f32_occurrences': len(re.findall(r'H5T_IEEE_F32', text, re.I)),
        'f64_occurrences': len(re.findall(r'H5T_IEEE_F64', text, re.I)),
        'stderr_tail': p.stderr[-1000:],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not BASE.exists() or not EXE.exists():
        report = {
            'classification': 'M3DC1_TCT_NATIVE_RESTART_FULL_PRECISION_HANDOFF_EXECUTION_FAILED',
            'pipeline_failure': True,
            'error': f'missing baseline or executable: BASE={BASE.exists()} EXE={EXE.exists()}',
        }
        write_json(OUT / 'native_restart_full_precision_handoff_summary.json', report)
        print(json.dumps(report, indent=2))
        return 1
    if not idouble_out_registered():
        report = {
            'classification': 'M3DC1_TCT_NATIVE_RESTART_FULL_PRECISION_HANDOFF_EXECUTION_FAILED',
            'pipeline_failure': True,
            'error': 'idouble_out was not found in the native source checkout; refusing to invent an input control.',
        }
        write_json(OUT / 'native_restart_full_precision_handoff_summary.json', report)
        print(json.dumps(report, indent=2))
        return 1

    rm(ROOT)
    ROOT.mkdir(parents=True)

    continuous = prep('continuous', TOTAL, write_restart=1, ntimers=SPLIT)
    continuous_status = run(continuous)
    first = prep('split_first', SPLIT, write_restart=1, ntimers=SPLIT)
    first_status = run(first)
    precision = inspect_checkpoint_precision(first)

    second = ROOT / 'split_second'
    shutil.copytree(first, second, symlinks=True)
    text = (second / 'C1input').read_text()
    for key, value in {
        'ntimemax': str(TOTAL),
        'irestart': '1',
        'irestart_slice': '-1',
        'iwrite_restart': '0',
        'idouble_out': '1',
    }.items():
        text = pta.replace_or_add(text, key, value)
    (second / 'C1input').write_text(text)
    second_status = run(second)

    execution_ok = all(s['return_code'] == 0 for s in (continuous_status, first_status, second_status))
    pre = post = final = None
    extraction_error = None
    try:
        cr = pta.extract(continuous)
        fr = pta.extract(first)
        sr = pta.extract(second)
        c5 = nearest(cr, SPLIT * DT)
        f5 = nearest(fr, SPLIT * DT)
        c6 = nearest(cr, (SPLIT + 1) * DT)
        s6 = nearest(sr, (SPLIT + 1) * DT)
        c10 = nearest(cr, TOTAL * DT)
        s10 = nearest(sr, TOTAL * DT)
        pre = compare(c5, f5)
        post = compare(c6, s6)
        final = compare(c10, s10)
    except Exception as exc:
        extraction_error = repr(exc)

    precision_ok = bool(precision.get('psi_double') and precision.get('I_double'))
    handoff_pass = bool(execution_ok and precision_ok and pre and pre['pass'] and post and post['pass'] and final and final['pass'])

    if not execution_ok or extraction_error or not precision_ok:
        classification = 'M3DC1_TCT_NATIVE_RESTART_FULL_PRECISION_HANDOFF_EXECUTION_FAILED'
        pipeline_failure = True
    elif handoff_pass:
        classification = 'M3DC1_TCT_NATIVE_RESTART_FULL_PRECISION_HANDOFF_EQUIVALENCE_PASSED'
        pipeline_failure = False
    else:
        classification = 'M3DC1_TCT_NATIVE_RESTART_FULL_PRECISION_HANDOFF_EQUIVALENCE_FAILED'
        pipeline_failure = False

    report = {
        'classification': classification,
        'pipeline_failure': pipeline_failure,
        'parent_job_id': '20260921-039-native-restart-field-precision-source-audit',
        'parent_classification': 'M3DC1_TCT_NATIVE_RESTART_FIELD_PRECISION_PATH_CONFIRMED',
        'audit_scope': 'Source=0 native continuous-vs-split restart validation using M3D-C1 built-in idouble_out=1 serialization only; no controller efficacy run and no solver-equation change.',
        'native_output_control': {'idouble_out': 1},
        'checkpoint_precision': precision,
        'execution': {
            'continuous': continuous_status,
            'split_first': first_status,
            'split_second': second_status,
        },
        'precheckpoint_equivalence': pre,
        'first_postrestart_step_equivalence': post,
        'final_handoff_equivalence': final,
        'handoff_equivalence': {'tolerance': TOL, 'pass': handoff_pass},
        'extraction_error': extraction_error,
        'zero_equivalence': 'NOT_APPLICABLE_SOURCE0_RESTART_CAPABILITY_TEST',
        'frozen_width_gate_pct_gt': 0.02,
        'frozen_Jpk_gate_pct_le': 0.1,
        'claim_boundary': 'Normalized native M3D-C1 restart capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.',
    }
    write_json(OUT / 'native_restart_full_precision_handoff_summary.json', report)
    print(json.dumps(report, indent=2))
    return 1 if pipeline_failure else 0


if __name__ == '__main__':
    raise SystemExit(main())

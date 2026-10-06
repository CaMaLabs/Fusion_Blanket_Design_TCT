#!/usr/bin/env python3
"""Compiled BOUT++ zero- and handoff-equivalence audit for segmented electrodes.

This audit does not test efficacy. It uses the repo's established BOUT++ invocation
contract (tct_current_sheet -d <case_dir>) and the compiled executable discovered by
job 081. It requires:
  1) zero-equivalence: changing the signed electrode profile while electrode_strength=0
     must not change plasma/current observables; and
  2) handoff-equivalence: in an active nonzero-electrode arm, electrode_phi must equal
     electrode_strength*electrode_profile and total phi-phi_plasma must equal
     electrode_phi.

No solver physics are modified.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import netCDF4
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation_runs" / "tct_segmented_electrode_bout_runtime_equivalence_real"
OUT.mkdir(parents=True, exist_ok=True)

TOL = 1.0e-12
FROZEN_WIDTH_GATE_PCT = 0.020
FROZEN_JPK_GATE_PCT = 0.10

exe_candidates = [
    ROOT / "validation_models" / "tct_current_sheet" / "build-openmpi" / "tct_current_sheet",
    ROOT / "validation_models" / "tct_current_sheet" / "build" / "tct_current_sheet",
]
exe = next((p for p in exe_candidates if p.is_file() and os.access(p, os.X_OK)), None)

summary: dict = {
    "schema_version": 1,
    "classification": "TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EQUIVALENCE_NOT_ESTABLISHED",
    "pipeline_failure": False,
    "runtime_executable": str(exe.resolve()) if exe else None,
    "zero_equivalence_required": True,
    "zero_equivalence_tolerance": TOL,
    "zero_equivalence_pass": False,
    "handoff_equivalence_required": True,
    "handoff_equivalence_tolerance": TOL,
    "handoff_equivalence_pass": False,
    "frozen_gates": {
        "width_gain_pct_min": FROZEN_WIDTH_GATE_PCT,
        "jpk_improvement_pct_min": FROZEN_JPK_GATE_PCT,
    },
    "claim_boundary": (
        "BOUT++ compiled-runtime zero/handoff equivalence only; no segmented-electrode "
        "efficacy, fuel-specific efficacy, native M3D-C1 electrode efficacy, experimental, "
        "or reactor-scale claim."
    ),
}

if exe is None:
    summary["pipeline_failure"] = True
    summary["error"] = "compiled tct_current_sheet executable not found"
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    raise SystemExit(2)

base = """
MYG = 0
periodicX = true

[mesh]
nx = 64
ny = 1
nz = 64
dx = 0.18
dy = 1.0
dz = 0.18

[tct]
eta = 0.00075
nu = 0.001
strength = 0
omega_strength = 0
electrode_strength = {electrode_strength}
start_time = 0
end_time = 1e30
feedback_enabled = false
bracket = 2

[psi]
scale = 1.0
function = 0.08 * exp(-((x-0.5)/0.070)^2) + 0.006 * cos(z)
bndry_all = dirichlet_o2

[omega]
scale = 1.0
function = 0.01 * sin(z) * exp(-((x-0.5)/(2*0.070))^2)
bndry_all = dirichlet_o2

[tct_mask]
scale = 1.0
function = exp(-((x-0.5)/0.119)^2)
bndry_all = dirichlet_o2

[electrode_profile]
scale = 1.0
function = {profile}
bndry_all = dirichlet_o2

[solver]
output_step = 0.25
nout = 4
mxstep = 10000
atol = 1e-10
rtol = 1e-6
"""

cases = {
    "zero_profile_a": {
        "electrode_strength": 0.0,
        "profile": "sin(6.283185307179586*x) * exp(-((x-0.5)/0.16)^2)",
    },
    "zero_profile_b": {
        "electrode_strength": 0.0,
        "profile": "-cos(6.283185307179586*x) * exp(-((x-0.5)/0.11)^2)",
    },
    "handoff_active": {
        "electrode_strength": 0.01,
        "profile": "sin(6.283185307179586*x) * exp(-((x-0.5)/0.16)^2)",
    },
}

def run_case(name: str, spec: dict) -> Path:
    case = OUT / name
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    (case / "BOUT.inp").write_text(
        base.format(
            electrode_strength=spec["electrode_strength"],
            profile=spec["profile"],
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["UCX_TLS"] = env.get("BOUT_UCX_TLS", "self")
    proc = subprocess.run(
        [str(exe), "-d", str(case)],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=600,
    )
    (case / "bout_stdout.log").write_text(proc.stdout or "", encoding="utf-8")
    (case / "bout_stderr.log").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"{name} BOUT++ return code {proc.returncode}: {(proc.stderr or '')[-2000:]}")
    out = case / "BOUT.dmp.0.nc"
    if not out.exists():
        raise RuntimeError(f"{name}: missing BOUT.dmp.0.nc")
    return out

def load(path: Path, names: list[str]) -> dict[str, np.ndarray]:
    with netCDF4.Dataset(path) as ds:
        missing = [n for n in names if n not in ds.variables]
        if missing:
            raise RuntimeError(f"{path}: missing variables {missing}")
        return {n: np.asarray(ds.variables[n][:], dtype=float) for n in names}

try:
    outputs = {name: run_case(name, spec) for name, spec in cases.items()}
    compare_vars = ["psi", "omega", "J", "phi", "phi_plasma", "electrode_phi"]
    a = load(outputs["zero_profile_a"], compare_vars)
    b = load(outputs["zero_profile_b"], compare_vars)

    zero_deltas = {}
    for name in compare_vars:
        if a[name].shape != b[name].shape:
            raise RuntimeError(f"zero-equivalence shape mismatch for {name}: {a[name].shape} vs {b[name].shape}")
        zero_deltas[name] = float(np.max(np.abs(a[name] - b[name])))
    zero_max = max(zero_deltas.values()) if zero_deltas else float("inf")
    zero_pass = bool(zero_max <= TOL)

    h = load(
        outputs["handoff_active"],
        ["electrode_profile", "electrode_phi", "phi", "phi_plasma"],
    )
    profile = h["electrode_profile"]
    ephi = h["electrode_phi"]
    phi = h["phi"]
    phi_plasma = h["phi_plasma"]

    expected_ephi = cases["handoff_active"]["electrode_strength"] * profile
    handoff_profile_delta = float(np.max(np.abs(ephi - expected_ephi)))
    handoff_phi_delta = float(np.max(np.abs((phi - phi_plasma) - ephi)))
    handoff_max = max(handoff_profile_delta, handoff_phi_delta)
    handoff_pass = bool(handoff_max <= TOL)

    summary.update({
        "zero_equivalence_pass": zero_pass,
        "zero_equivalence_max_abs_delta": zero_max,
        "zero_equivalence_deltas": zero_deltas,
        "handoff_equivalence_pass": handoff_pass,
        "handoff_equivalence_max_abs_delta": handoff_max,
        "handoff_electrode_phi_vs_strength_profile_max_abs_delta": handoff_profile_delta,
        "handoff_total_phi_identity_max_abs_delta": handoff_phi_delta,
        "classification": (
            "TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EQUIVALENCE_ESTABLISHED"
            if zero_pass and handoff_pass
            else "TCT_SEGMENTED_ELECTRODE_BOUT_RUNTIME_EQUIVALENCE_NOT_ESTABLISHED"
        ),
    })
except Exception as exc:
    summary["pipeline_failure"] = True
    summary["error"] = f"{type(exc).__name__}: {exc}"

(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
raise SystemExit(2 if summary["pipeline_failure"] else 0)

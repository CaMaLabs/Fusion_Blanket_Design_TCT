from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "repo_root": "/home/ubuntu/work/openmc/sweep",
        "m3dc1_root": "/home/ubuntu/M3DC1-official",
        "baseline_dir": "/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE",
        "executable": "/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d",
        "run_root": "/home/ubuntu/m3dc1_runs/TCT_EXPLORER",
        "output_dir": "/home/ubuntu/work/openmc/sweep/validation_runs/tct_mechanism_explorer",
        "h5dump": "",
    },
    "runtime": {
        "mpi_ranks": 1,
        "timeout_seconds": 420,
        "tmpdir": "/var/tmp",
        "spack_setup": "$HOME/spack/share/spack/setup-env.sh",
        "spack_env": "m3dc1-deps",
        "mpirun_extra": ["--oversubscribe"],
        "petsc_args": ["-pc_factor_mat_solver_type", "mumps"],
    },
    "extractor": {
        "r_center": 10.0,
        "r_band": 0.25,
        "z_center": 1.0,
        "z_shoulder": 0.561,
        "center_halfwidth": 0.2805,
        "shoulder_halfwidth": 0.2805,
        "high_j_fraction": 0.75,
    },
    "stages": {
        "probe_ntimemax": 5,
        "probe_duration": 0.05,
        "sustained_ntimemax": 5,
        "full_ntimemax": 6,
        "ntimepr": 1,
        "impulse_response_horizon": 0.05,
        "time_match_tolerance": 1e-9,
        "authority_width_gain_pct": 0.02,
        "authority_peak_j_change_pct": -0.01,
        "sustained_width_gain_pct": 0.02,
        "topology_worsening_tolerance_pct": 0.1,
        "zero_abs_tolerance": 1e-12,
        "noise_abs_tolerance": 1e-10,
    },
    "search": {
        "enabled_mechanisms": [
            "magnetic_pulse",
            "current_drive",
            "current_redistribution",
            "hybrid_mag_redistribution",
        ],
        "elite_fraction": 0.25,
        "mutation_probability": 0.75,
        "crossover_probability": 0.35,
        "mutation_scale": 0.18,
        "verify_zero_before_search": True,
        "evaluate_full_topology": True,
        "seed_candidates": [
            {"mechanism":"magnetic_pulse","params":{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.0,"duration":0.05,"ramp":0.0}},
            {"mechanism":"magnetic_pulse","params":{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.05,"duration":0.05,"ramp":0.0}},
            {"mechanism":"magnetic_pulse","params":{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.10,"duration":0.05,"ramp":0.0}},
            {"mechanism":"magnetic_pulse","params":{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.15,"duration":0.05,"ramp":0.0}},
            {"mechanism":"magnetic_pulse","params":{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.20,"duration":0.05,"ramp":0.0}}
        ],
    },
    "physical_mapping": {
        "enabled": False,
        "mag_ctrl_amp_to_deltaB_T": None,
        "background_B_T": 7.2,
        "lithium_layer_thickness_m": 0.0014,
        "lithium_velocity_km_s": 0.0022,
        "trench_width_mm": 10.0,
        "jb_angle_deg": 90.0,
        "wetted": True,
    },
    "agent": {
        "command": "",
        "timeout_seconds": 60,
    },
}


def deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_update(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return copy.deepcopy(DEFAULT_CONFIG)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return deep_update(DEFAULT_CONFIG, data)


def write_default(path: str | Path) -> None:
    Path(path).write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "repo_root": "${REPO_ROOT}",
        "m3dc1_root": "/home/ubuntu/M3DC1-official",
        "baseline_dir": "/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE",
        "executable": "/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d",
        "run_root": "/home/ubuntu/m3dc1_runs/TCT_EXPLORER_V2",
        "output_dir": "${REPO_ROOT}/validation_runs/tct_mechanism_explorer_v2",
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
        "sustained_ntimemax": 20,
        "full_ntimemax": 40,
        "ntimepr": 1,
        "impulse_response_horizon": 0.05,
        "time_match_tolerance": 1e-9,
        "authority_width_gain_pct": 0.02,
        "authority_peak_j_change_pct": -0.01,
        "sustained_width_gain_pct": 0.02,
        "sustained_integrated_width_gain_pct_time": 0.0,
        "sustained_positive_width_fraction": 0.60,
        "sustained_max_peak_j_increase_pct": 0.50,
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
            "poloidal_momentum_bias",
            "hybrid_mag_momentum",
            "hybrid_mag_momentum_redistribution",
        ],
        "elite_fraction": 0.25,
        "mutation_probability": 0.75,
        "crossover_probability": 0.35,
        "mutation_scale": 0.18,
        "verify_zero_before_search": True,
        "evaluate_full_topology": True,
        "seed_candidates": [
            {
                "mechanism": "magnetic_pulse",
                "params": {
                    "amp": -0.01, "r0": 10.0, "z0": 1.0, "wr": 0.5, "wz": 0.5,
                    "t_on": 0.05, "duration": 0.05, "ramp": 0.0,
                },
            },
            {
                "mechanism": "poloidal_momentum_bias",
                "params": {
                    "amp": -0.005, "force_width": 0.12, "force_x": 0.5, "force_n": 0,
                },
            },
            {
                "mechanism": "poloidal_momentum_bias",
                "params": {
                    "amp": 0.005, "force_width": 0.12, "force_x": 0.5, "force_n": 0,
                },
            },
            {
                "mechanism": "hybrid_mag_momentum",
                "params": {
                    "mag_amp": -0.01,
                    "momentum_amp": -0.005,
                    "force_width": 0.12,
                    "force_x": 0.5,
                    "force_n": 0,
                    "r0": 10.0,
                    "z0": 1.0,
                    "mag_wr": 0.5,
                    "mag_wz": 0.5,
                    "t_on": 0.05,
                    "duration": 0.05,
                    "ramp": 0.0,
                },
            },
            {
                "mechanism": "hybrid_mag_momentum",
                "params": {
                    "mag_amp": -0.01,
                    "momentum_amp": 0.005,
                    "force_width": 0.12,
                    "force_x": 0.5,
                    "force_n": 0,
                    "r0": 10.0,
                    "z0": 1.0,
                    "mag_wr": 0.5,
                    "mag_wz": 0.5,
                    "t_on": 0.05,
                    "duration": 0.05,
                    "ramp": 0.0,
                },
            },
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


def _resolve_paths(cfg: dict[str, Any]) -> dict[str, Any]:
    """Resolve repo-relative tokens after defaults and overrides are merged."""
    out = copy.deepcopy(cfg)
    for key, value in list(out.get("paths", {}).items()):
        if not isinstance(value, str) or not value:
            continue
        value = value.replace("${REPO_ROOT}", str(REPO_ROOT))
        value = os.path.expandvars(os.path.expanduser(value))
        out["paths"][key] = value
    return out


def load_config(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return _resolve_paths(DEFAULT_CONFIG)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return _resolve_paths(deep_update(DEFAULT_CONFIG, data))


def write_default(path: str | Path) -> None:
    # Keep ${REPO_ROOT} in the written config so the same file works in a fresh clone.
    Path(path).write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")

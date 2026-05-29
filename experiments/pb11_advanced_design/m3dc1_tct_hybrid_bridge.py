#!/usr/bin/env python3
"""Bridge M3DC1-style MHD controls with the Fusion_Blanket_Design_TCT reactor model.

This is a control-oriented surrogate. It does not claim physical fidelity or
promise p-B11 ignition; it just couples the design knobs from the two codebases
into a single comparative sandbox.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def gaussian(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z)


ROOT = Path(__file__).resolve().parent
TCT_REPO_ROOT = Path(os.environ.get("TCT_REPO_ROOT", "/root/Fusion_Blanket_Design_TCT"))
M3DC1_ROOT = Path("/root/M3DC1")
M3DC1_TEMPLATE_DIR = M3DC1_ROOT / "unstructured" / "runs" / "first_linear"
M3DC1_BIN = M3DC1_ROOT / "unstructured" / "_localgnu-petsc-opt-25" / "m3dc1_2d"

TCT_ENGINE_AVAILABLE = False
TCT_EVALUATE_CASE = None
TCT_RUN_CONTROLLER = None
TCT_LITHIUM_WALL_TEMPERATURE = None
TCT_MHD_DRAG_POWER = None
TCT_PUMPING_POWER_FROM_HEAT = None
if TCT_REPO_ROOT.exists():
    sys.path.insert(0, str(TCT_REPO_ROOT))
    try:
        from fusion_engine_v5.engine.plasma_model import evaluate_case as TCT_EVALUATE_CASE
    except Exception:
        TCT_EVALUATE_CASE = None
    try:
        from fusion_engine_v5.engine.tct_control import run_tct_controller as TCT_RUN_CONTROLLER
    except Exception:
        TCT_RUN_CONTROLLER = None
    try:
        from fusion_engine_v5.engine.lithium_wall import lithium_wall_temperature as TCT_LITHIUM_WALL_TEMPERATURE
        from fusion_engine_v5.engine.lithium_wall import mhd_drag_power as TCT_MHD_DRAG_POWER
        from fusion_engine_v5.engine.lithium_wall import pumping_power_from_heat as TCT_PUMPING_POWER_FROM_HEAT
    except Exception:
        TCT_LITHIUM_WALL_TEMPERATURE = None
        TCT_MHD_DRAG_POWER = None
        TCT_PUMPING_POWER_FROM_HEAT = None
    TCT_ENGINE_AVAILABLE = any(
        item is not None
        for item in (
            TCT_EVALUATE_CASE,
            TCT_RUN_CONTROLLER,
            TCT_LITHIUM_WALL_TEMPERATURE,
            TCT_MHD_DRAG_POWER,
            TCT_PUMPING_POWER_FROM_HEAT,
        )
    )


# M3DC1 sweep knobs taken from /root/M3DC1/run_mc3d1_fusion_sweep.py
TCT_MODES = {"disabled": 0.0, "mild": 0.55, "aggressive": 1.0}
STRENGTHS = {"none": 0.0, "weak": 0.25, "medium": 0.55, "strong": 0.85, "aggressive": 1.0}
REVERSAL = {"none": 0.0, "shallow reversed-shear": 0.22, "medium reversed-shear": 0.48, "strong local reversal": 0.78}
ROTATION = {"none": 0.0, "weak": 0.2, "medium": 0.5, "strong": 0.8}
PLASMA_SPIN_ORGANIZATION = {"off": 0.0, "edge-biased": 0.30, "core-edge-shear": 0.55, "nested-vortex": 0.78, "phase-locked": 0.95}
RAMP_TIMING = {"before compression": 0.15, "during compression": 0.45, "after compression": -0.05}
RF_TIMING = {"off": 0.0, "before compression": 0.18, "at peak compression": 0.5, "after compression": -0.1}
PM_DRIVE = {"off": 0.0, "weak": 0.25, "medium": 0.55, "strong": 0.9}
BORON_DENSITY = {"low": 0.25, "medium": 0.5, "high": 0.78, "extreme": 1.0}
RECIRC = {
    "single-pass": 1.0,
    "10-pass": 10.0,
    "100-pass": 100.0,
    "1k-pass": 1000.0,
    "10k-pass": 10000.0,
    "100k-pass": 100000.0,
    "1M-pass": 1000000.0,
    "10M-pass": 10000000.0,
}
LI_CURRENT = {"0": 0.0, "low": 0.2, "medium": 0.55, "high": 0.9}
DT_ALPHA_ASSIST = {"off": 0.0, "weak": 0.25, "medium": 0.55, "strong": 0.85}
CHANNEL_STRENGTH = {"off": 0.0, "weak": 0.25, "medium": 0.55, "strong": 0.85}
RF_GRATING = {"off": 0.0, "coarse": 0.35, "phase-locked": 0.70, "adaptive": 1.0}
ENERGY_RECOVERY = {"none": 0.0, "basic": 0.35, "advanced": 0.60, "aggressive": 0.78}
CAVITY_Q = {"open": 0.0, "guided": 0.35, "resonant": 0.70, "high-Q": 1.0}
BORON_VAPOR_CONTROL = {"passive": 0.0, "pulsed": 0.35, "profiled": 0.70, "magnetized": 1.0}
PROTON_DRIVER = {
    "external": {"cost_scale": 1.0, "recovery_bonus": 0.0, "window_bonus": 0.0},
    "recuperated-linac": {"cost_scale": 0.62, "recovery_bonus": 0.12, "window_bonus": 0.03},
    "dt-alpha-knockon": {"cost_scale": 0.48, "recovery_bonus": 0.05, "window_bonus": 0.06},
    "autoresonant": {"cost_scale": 0.40, "recovery_bonus": 0.16, "window_bonus": 0.08},
}
LI_BORON_MIX = {"none": 0.0, "trace": 0.15, "low": 0.35, "medium": 0.60, "rich": 0.85}
BORON_WALL_LOADING = {"none": 0.0, "thin": 0.25, "moderate": 0.55, "heavy": 0.85}
PB11_WALL_THICKNESS = {"standard": 0.0, "thick": 0.35, "very-thick": 0.65, "graded-bulk": 0.90}
PB11_WALL_CURRENT = {"off": 0.0, "low": 0.25, "medium": 0.55, "high": 0.85}
BORON_WICK = {"off": 0.0, "shallow": 0.30, "structured": 0.60, "capillary": 0.90}
ALPHA_CHANNELING = {"off": 0.0, "weak": 0.25, "medium": 0.55, "strong": 0.85}
GRAZING_PATH = {"none": 1.0, "weak": 3.0, "medium": 10.0, "strong": 30.0, "extreme": 100.0}
DIRECT_CONVERTER_GEOMETRY = {"none": 0.0, "remote": 0.25, "edge-staged": 0.55, "divertor-integrated": 0.85}
ALPHA_TO_PROTON_COUPLING = {"off": 0.0, "weak": 0.20, "medium": 0.45, "strong": 0.75}
ADAPTIVE_SKIMMER = {"off": 0.0, "brems-triggered": 0.35, "phase-locked": 0.65, "predictive": 0.90}
DT_SEED_FRACTION = {"full": 1.0, "half": 0.50, "pilot": 0.25, "spark": 0.10, "trace": 0.03}
BORON_PROFILE_SHAPE = {"diffuse": 0.0, "edge-peaked": 0.35, "resonant-sheet": 0.70, "pulsed-sheet": 1.0}
PROTON_PHASE_COOLING = {"none": 0.0, "magnetic-collimation": 0.35, "rf-bunching": 0.65, "mirror-phase-cooling": 1.0}
RESONANT_ORBIT_CLOSURE = {"off": 0.0, "weak": 0.30, "medium": 0.60, "strong": 0.90}
BORON_SHEET_QUALITY = {"broad": 0.0, "focused": 0.35, "phase-locked": 0.70, "self-replenishing": 1.0}
PROTON_PHASE_RECOVERY = {"off": 0.0, "weak": 0.30, "medium": 0.60, "strong": 0.90}
CONVERTER_STAGING = {"simple": 0.0, "multi-stage": 0.35, "traveling-wave": 0.70, "adaptive": 1.0}
ALPHA_BOOTSTRAP_FEEDBACK = {"off": 0.0, "weak": 0.30, "medium": 0.60, "strong": 0.90}
GRAPHENE_HEAT_CHANNELS = {"off": 0.0, "passive": 0.30, "aligned": 0.55, "microchannel": 0.78, "actively-pumped": 0.95}
GRAPHENE_CHANNEL_POWER_SCALE = {"off": 0.0, "passive": 0.0, "aligned": 0.02, "microchannel": 0.35, "actively-pumped": 1.0}
DYNAMIC_VOLUME_COMPRESSION = {"off": 0.0, "minor": 0.03, "moderate": 0.07, "deep": 0.12, "extreme": 0.18}
VOLUME_COMPRESSION_TIMING = {"off": 0.0, "pre-heat": 0.20, "ramp-synced": 0.55, "peak-burn": 0.80, "post-burn": -0.15}
EDGE_RACETRACK = {"off": 0.0, "weak": 0.25, "guided": 0.55, "phase-locked": 0.78, "resonant": 0.95}
RACETRACK_PITCH = {"shallow": 0.35, "medium": 0.70, "steep": 0.50}
RACETRACK_WALL_CLEARANCE = {"wide": 0.25, "nominal": 0.65, "tight": 0.88, "grazing": 1.0}
RACETRACK_ENERGY_REPHASE = {"off": 0.0, "weak": 0.30, "medium": 0.62, "strong": 0.88}
AUX_FUEL_PROFILES = {
    "p-B11": {
        "energy_mu_keV": 260.0,
        "energy_sigma_keV": 95.0,
        "burnup_scale": 1.0,
        "yield_scale": 1.0,
        "radiation_scale": 1.0,
        "support_scale": 1.0,
        "replenishment_scale": 1.0,
        "direct_conversion_scale": 1.0,
        "wall_heat_scale": 1.0,
        "tbr_bonus": 0.0,
    },
    "D-D": {
        "energy_mu_keV": 125.0,
        "energy_sigma_keV": 70.0,
        "burnup_scale": 2.35,
        "yield_scale": 0.62,
        "radiation_scale": 0.34,
        "support_scale": 0.68,
        "replenishment_scale": 0.18,
        "direct_conversion_scale": 0.42,
        "wall_heat_scale": 1.22,
        "tbr_bonus": 0.06,
    },
    "D-He3": {
        "energy_mu_keV": 185.0,
        "energy_sigma_keV": 85.0,
        "burnup_scale": 1.75,
        "yield_scale": 1.42,
        "radiation_scale": 0.58,
        "support_scale": 0.82,
        "replenishment_scale": 0.45,
        "direct_conversion_scale": 1.18,
        "wall_heat_scale": 0.86,
        "tbr_bonus": -0.03,
    },
    "D-Li6": {
        "energy_mu_keV": 320.0,
        "energy_sigma_keV": 115.0,
        "burnup_scale": 1.28,
        "yield_scale": 1.68,
        "radiation_scale": 0.72,
        "support_scale": 0.92,
        "replenishment_scale": 0.62,
        "direct_conversion_scale": 1.05,
        "wall_heat_scale": 0.95,
        "tbr_bonus": 0.10,
    },
    "D-He3+D-Li6": {
        "energy_mu_keV": 225.0,
        "energy_sigma_keV": 135.0,
        "burnup_scale": 1.58,
        "yield_scale": 1.55,
        "radiation_scale": 0.66,
        "support_scale": 0.90,
        "replenishment_scale": 0.56,
        "direct_conversion_scale": 1.12,
        "wall_heat_scale": 0.90,
        "tbr_bonus": 0.06,
    },
    "D-He3+D-Li6+pB11-wall": {
        "energy_mu_keV": 235.0,
        "energy_sigma_keV": 145.0,
        "burnup_scale": 1.66,
        "yield_scale": 1.62,
        "radiation_scale": 0.86,
        "support_scale": 0.94,
        "replenishment_scale": 0.76,
        "direct_conversion_scale": 1.10,
        "wall_heat_scale": 0.94,
        "tbr_bonus": 0.08,
    },
}


@dataclass(frozen=True)
class Scenario:
    name: str
    # M3DC1-facing controls
    li_current: float = 0.10
    tct_mode: str = "aggressive"
    tct_alpha: float = 10.0
    severity_scale: float = 0.6
    lithium_thickness_m: float = 0.003
    # Hybrid geometry / control controls
    tct_strength: str = "none"
    field_reversal_depth: str = "none"
    counter_rotation: str = "none"
    plasma_spin_organization: str = "off"
    compression_amplitude_pct: float = 0.0
    dynamic_volume_compression: str = "off"
    volume_compression_timing: str = "off"
    volume_compression_duty: float = 0.20
    edge_racetrack: str = "off"
    racetrack_pitch: str = "medium"
    racetrack_wall_clearance: str = "nominal"
    racetrack_energy_rephase: str = "off"
    magnetic_ramp_timing: str = "before compression"
    rf_timing: str = "off"
    plasma_mirror_drive: str = "off"
    boron_vapor_density: str = "low"
    proton_recirculation_quality: str = "single-pass"
    boron_areal_density: float = 1.0
    proton_energy_center_keV: float = 250.0
    proton_energy_spread_pct: float = 35.0
    proton_energy_recovery: str = "none"
    proton_driver_mode: str = "external"
    pb11_cavity_q: str = "open"
    boron_vapor_control: str = "passive"
    li_boron_mix_fraction: str = "none"
    boron_wall_loading: str = "none"
    pb11_wall_thickness: str = "standard"
    pb11_wall_current: str = "off"
    boron_wick_efficiency: str = "off"
    alpha_channeling_to_protons: str = "off"
    alpha_to_li_capture_fraction: float = 0.20
    grazing_path_multiplier: str = "none"
    direct_converter_geometry: str = "none"
    alpha_to_proton_coupling: str = "off"
    adaptive_electron_skimmer: str = "off"
    dt_alpha_assist: str = "off"
    rf_grating: str = "off"
    plasma_mirror_duty: float = 1.0
    rf_grating_duty: float = 1.0
    electron_channel: str = "off"
    electron_channel_duty: float = 1.0
    alpha_channel: str = "off"
    alpha_channel_duty: float = 1.0
    ash_channel: str = "off"
    ash_channel_duty: float = 1.0
    channel_separation_quality: float = 0.5
    liquid_lithium_current: str = "0"
    alpha_conversion_efficiency: float = 0.0
    dt_seed_fraction: str = "full"
    boron_profile_shape: str = "diffuse"
    proton_phase_cooling: str = "none"
    resonant_orbit_closure: str = "off"
    boron_sheet_quality: str = "broad"
    proton_phase_recovery: str = "off"
    converter_staging: str = "simple"
    alpha_bootstrap_feedback: str = "off"
    graphene_heat_channels: str = "off"
    aux_fuel: str = "p-B11"
    pB11_enabled: bool = False


@dataclass
class Metrics:
    core_ion_temperature_keV: float
    core_electron_temperature_keV: float
    ti_te_ratio: float
    density_norm: float
    beta_proxy: float
    betaN_proxy: float
    confinement_time_proxy: float
    reconnection_tearing_elm_event_rate: float
    current_sheet_thickness_metric: float
    shear_profile: float
    spin_organization_factor: float
    vortex_channel_stability: float
    electron_exhaust_power: float
    bremsstrahlung_proxy: float
    alpha_extraction_fraction: float
    direct_conversion_power: float
    pB11_alpha_yield: float
    pB11_ignitability_proxy: float
    pB11_net_delta: float
    pB11_gross_power: float
    pB11_power_fraction: float
    proton_recovered_power: float
    boron_vapor_radiation_penalty: float
    cavity_q_effective: float
    surface_pB11_boost: float
    li_boron_mhd_penalty: float
    boron_replenishment_power: float
    alpha_channeling_power: float
    alpha_to_li_heat: float
    grazing_path_effective: float
    alpha_to_proton_power: float
    direct_converter_gain: float
    adaptive_skimmer_gain: float
    pb11_support_recirc_power: float
    pb11_support_areal_power: float
    pb11_support_driver_power: float
    pb11_support_control_power: float
    proton_burnup_fraction: float
    effective_proton_path_length_passes: float
    hardware_recirc_passes: float
    proton_energy_retention_norm: float
    proton_window_fraction: float
    boron_optical_depth_proxy: float
    proton_loss_fraction: float
    dt_alpha_assist_fraction: float
    dt_alpha_coupling_efficiency: float
    rf_grating_power: float
    plasma_mirror_duty_effective: float
    rf_grating_duty_effective: float
    channel_duty_effective: float
    channel_separation_effective: float
    channel_cross_talk: float
    electron_exhaust_fraction: float
    alpha_capture_fraction: float
    alpha_thermalization_fraction: float
    helium_ash_fraction: float
    ash_removal_power: float
    core_dilution_penalty: float
    graphene_heat_spread_factor: float
    graphene_channel_power: float
    volume_compression_factor: float
    volume_actuator_power: float
    racetrack_guidance_factor: float
    racetrack_drive_power: float
    tbr_proxy: float
    liquid_lithium_wall_heat_load: float
    be_b4c_wall_heat_deposition: float
    net_power_proxy: float
    ignition_margin_proxy: float
    fusion_dt_power_proxy: float
    auxiliary_beam_power: float
    rf_power_proxy: float
    coil_power_proxy: float
    pump_power_proxy: float
    m3dc1_li_scale: float
    m3dc1_feedback_scale: float
    m3dc1_eps: float
    m3dc1_pedge: float


@dataclass
class OptimizationResult:
    rank: int
    score: float
    generation: int
    scenario: Scenario
    metrics: Metrics


def m3dc1_mapping(s: Scenario) -> Dict[str, float]:
    mode_scale = TCT_MODES.get(s.tct_mode, 1.0)
    li_scale = 1.0 + (s.li_current - 0.10)
    feedback_scale = mode_scale * (s.tct_alpha / 10.0)
    eps_value = 1e-8 * (s.severity_scale / 0.6)
    pedge_value = 2e-4 * (s.lithium_thickness_m / 0.003)
    return {
        "li_scale": li_scale,
        "feedback_scale": feedback_scale,
        "eps": eps_value,
        "pedge": pedge_value,
    }


def _scale_feedback_line(line: str, scale: float) -> str:
    if "=" not in line:
        return line
    lhs, rhs = line.split("=", 1)
    key = lhs.strip()
    if not key.startswith(
        (
            "gs_vertical_feedback",
            "gs_vertical_feedback_i",
            "gs_radial_feedback",
            "gs_radial_feedback_i",
        )
    ):
        return line
    try:
        value = float(rhs.split("!", 1)[0].strip())
    except ValueError:
        return line
    comment = ""
    if "!" in rhs:
        comment = "!" + rhs.split("!", 1)[1]
    return f"{lhs} = {value * scale:.12g} {comment}".rstrip()


def apply_m3dc1_mapping(s: Scenario, case_dir: Path, quick_init: bool = False) -> Dict[str, float]:
    """Rewrite the copied first_linear deck to reflect the scenario knobs."""
    input_path = case_dir / "C1input.smoke"
    lines = input_path.read_text(encoding="utf-8").splitlines()

    li_scale = 1.0 + (s.li_current - 0.10)
    mode_scale = {"disabled": 0.0, "mild": 0.5, "aggressive": 1.0}.get(s.tct_mode, 1.0)
    feedback_scale = mode_scale * (s.tct_alpha / 10.0)
    eps_value = 0.0 if quick_init else 1e-8 * (s.severity_scale / 0.6)
    pedge_value = 2e-4 * (s.lithium_thickness_m / 0.003)

    updated: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("linear ="):
            updated.append("\tlinear = 0\t! run the nonlinear path for meaningful native diagnostics")
            continue
        if stripped.startswith("eqsubtract ="):
            updated.append("\teqsubtract = 0\t! keep equilibrium terms in the nonlinear run")
            continue
        if stripped.startswith("eps ="):
            updated.append(f"\teps = {eps_value:.12g}\t! amplitude of initial random perturbations")
            continue
        if stripped.startswith("icalc_scalars ="):
            updated.append("\ticalc_scalars = 1\t! keep scalar diagnostics enabled for sweep runs")
            continue
        if stripped.startswith("pedge ="):
            updated.append(f"\tpedge = {pedge_value:.12g}\t! mapped from lithium_thickness_m")
            continue
        if stripped.startswith("gs_vertical_feedback(") or stripped.startswith("gs_vertical_feedback_i(") or stripped.startswith("gs_radial_feedback(") or stripped.startswith("gs_radial_feedback_i("):
            updated.append(_scale_feedback_line(line, feedback_scale))
            continue
        updated.append(line)
    input_path.write_text("\n".join(updated) + "\n", encoding="utf-8")

    current_path = case_dir / "current.dat"
    current_lines: List[str] = []
    for raw in current_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            current_lines.append(raw)
            continue
        try:
            value = float(stripped.split()[0])
        except ValueError:
            current_lines.append(raw)
            continue
        current_lines.append(f"{value * li_scale:12.6f}")
    current_path.write_text("\n".join(current_lines) + "\n", encoding="utf-8")

    return {
        "li_scale": li_scale,
        "feedback_scale": feedback_scale,
        "eps": eps_value,
        "pedge": pedge_value,
    }


def parse_m3dc1_log(log_text: str) -> Dict[str, float | None]:
    metrics: Dict[str, float | None] = {
        "total_energy": None,
        "total_energy_lost": None,
        "toroidal_current": None,
        "toroidal_flux": None,
        "total_particles": None,
        "total_radiation": None,
        "bremsstrahlung_radiation": None,
        "ionization_loss": None,
        "psi0": None,
        "te_max": None,
    }
    for line in log_text.splitlines():
        nums = [float(x) for x in re.findall(r"[-+]?\d+\.\d+(?:[Ee][-+]?\d+)?", line)]
        if not nums:
            continue
        lower = line.lower()
        if "total energy =" in lower:
            metrics["total_energy"] = nums[0]
        elif "total energy lost =" in lower:
            metrics["total_energy_lost"] = nums[0]
        elif "toroidal current =" in lower:
            metrics["toroidal_current"] = nums[0]
        elif "toroidal flux =" in lower:
            metrics["toroidal_flux"] = nums[0]
        elif "total particles =" in lower:
            metrics["total_particles"] = nums[0]
        elif "total radiation =" in lower:
            metrics["total_radiation"] = nums[0]
        elif "bremsstrahlung radiation =" in lower:
            metrics["bremsstrahlung_radiation"] = nums[0]
        elif "ionization loss =" in lower:
            metrics["ionization_loss"] = nums[0]
        elif "max te" in lower:
            metrics["te_max"] = nums[0]
        elif "psi0" in lower:
            metrics["psi0"] = nums[0]
    return metrics


def export_m3dc1_case(s: Scenario, output_dir: Path, *, quick_init: bool = True) -> Dict[str, object]:
    if not M3DC1_TEMPLATE_DIR.exists():
        raise FileNotFoundError(f"M3DC1 template directory not found: {M3DC1_TEMPLATE_DIR}")
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(M3DC1_TEMPLATE_DIR, output_dir, dirs_exist_ok=True)
    applied = apply_m3dc1_mapping(s, output_dir, quick_init=quick_init)
    metrics = simulate(s)
    manifest = {
        "scenario": asdict(s),
        "metrics": asdict(metrics),
        "m3dc1_mapping": applied,
        "template_dir": str(M3DC1_TEMPLATE_DIR),
        "quick_init": quick_init,
        "notes": [
            "This is an M3DC1/TCT handoff deck for the DT-TCT baseline behavior of the surrogate-selected auxiliary hybrid.",
            "Auxiliary p-B11, D-He3, D-Li6, direct conversion, racetrack, and wall-channel effects remain surrogate annotations, not native M3DC1 physics.",
            "Run native MHD stability first; use surrogate metrics only to prioritize cases.",
        ],
    }
    (output_dir / "pb11_surrogate_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "README_pb11_handoff.md").write_text(
        "\n".join([
            "# PB11 Advanced Hybrid M3DC1 Handoff",
            "",
            f"Scenario: `{s.name}`",
            "",
            "Native M3DC1 mappings applied:",
            f"- feedback scale: `{applied['feedback_scale']}`",
            f"- lithium/current scale: `{applied['li_scale']}`",
            f"- perturbation eps: `{applied['eps']}`",
            f"- edge pressure proxy: `{applied['pedge']}`",
            "",
            "Surrogate headline metrics:",
            f"- net power proxy: `{metrics.net_power_proxy}`",
            f"- ignition margin proxy: `{metrics.ignition_margin_proxy}`",
            f"- auxiliary gross power proxy: `{metrics.pB11_gross_power}`",
            f"- auxiliary power fraction: `{metrics.pB11_power_fraction}`",
            f"- TBR proxy: `{metrics.tbr_proxy}`",
            f"- liquid lithium wall heat: `{metrics.liquid_lithium_wall_heat_load}`",
            f"- Be/B4C wall heat: `{metrics.be_b4c_wall_heat_deposition}`",
            "",
            "Caution: the auxiliary edge-fuel and direct-conversion systems are not solved by M3DC1 here. This deck is for DT-TCT MHD/control screening around the selected operating point.",
            "",
        ]) + "\n",
        encoding="utf-8",
    )
    return {
        "output_dir": str(output_dir),
        "applied": applied,
        "metrics": asdict(metrics),
    }


def run_m3dc1_case(s: Scenario, *, keep_logs: bool = False, quick_init: bool = False) -> Dict[str, object]:
    if not M3DC1_TEMPLATE_DIR.exists():
        raise FileNotFoundError(f"M3DC1 template directory not found: {M3DC1_TEMPLATE_DIR}")
    if not M3DC1_BIN.exists():
        raise FileNotFoundError(f"M3DC1 binary not found: {M3DC1_BIN}")

    work_root = ROOT / "m3dc1_case_runs"
    work_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=f"{s.name[:24].replace(' ', '_')}_", dir=str(work_root)))
    shutil.copytree(M3DC1_TEMPLATE_DIR, run_dir, dirs_exist_ok=True)
    applied = apply_m3dc1_mapping(s, run_dir, quick_init=quick_init)

    env = {
        **os.environ,
        "M3DC1_BIN": str(M3DC1_BIN),
        "INPUT": "C1input.smoke",
        "LOG": "run.log",
        "NPROC": "1",
    }
    proc = subprocess.run(
        ["/bin/bash", "./run.sh"],
        cwd=str(run_dir),
        env=env,
        capture_output=True,
        text=True,
    )

    log_path = run_dir / "run.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    log_metrics = parse_m3dc1_log(log_text)

    result: Dict[str, object] = {
        "scenario": s.name,
        "run_dir": str(run_dir),
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "applied": applied,
        "log_metrics": log_metrics,
        "used_real_m3dc1": proc.returncode == 0,
    }

    if not keep_logs:
        shutil.rmtree(run_dir, ignore_errors=True)
        result["run_dir"] = ""
        result["logs_removed"] = True
    else:
        result["logs_removed"] = False

    return result


def plasma_model_proxy(s: Scenario) -> Dict[str, float]:
    # Mirror the TCT repo's plasma surrogate but allow the extra hybrid controls
    # to modulate the same state variables.
    dynamic_volume = DYNAMIC_VOLUME_COMPRESSION.get(s.dynamic_volume_compression, 0.0)
    volume_timing = max(0.0, VOLUME_COMPRESSION_TIMING.get(s.volume_compression_timing, 0.0))
    volume_duty = clamp(s.volume_compression_duty, 0.05, 1.0)
    dynamic_radius_shift = dynamic_volume * (0.45 + 0.55 * volume_timing) * math.sqrt(volume_duty)
    R = 8.0 - 0.45 * (s.compression_amplitude_pct / 10.0) - 1.10 * dynamic_radius_shift
    a = 2.5 - 0.12 * (s.compression_amplitude_pct / 10.0) - 0.42 * dynamic_radius_shift
    rotation = ROTATION.get(s.counter_rotation, 0.0)
    spin = PLASMA_SPIN_ORGANIZATION.get(s.plasma_spin_organization, 0.0)
    spin_shear = clamp(0.65 * rotation + 0.55 * spin + 0.22 * rotation * spin, 0.0, 1.35)
    kappa = 2.0 + 0.08 * rotation + 0.035 * spin
    B0 = 6.0 + 1.2 * STRENGTHS.get(s.tct_strength, 0.0) + 0.5 * PM_DRIVE.get(s.plasma_mirror_drive, 0.0)
    Ip = 22.0 + 1.5 * STRENGTHS.get(s.tct_strength, 0.0) + 0.4 * rotation + 0.28 * spin
    Ti = 25.0 + 8.0 * STRENGTHS.get(s.tct_strength, 0.0) + 4.0 * rotation + 2.2 * spin_shear + 3.5 * REVERSAL.get(s.field_reversal_depth, 0.0)
    Te = 15.0 + 1.2 * (1.0 - STRENGTHS.get(s.tct_strength, 0.0)) + 0.9 * PM_DRIVE.get(s.plasma_mirror_drive, 0.0)
    H98 = 1.2 + 0.08 * STRENGTHS.get(s.tct_strength, 0.0) + 0.04 * PM_DRIVE.get(s.plasma_mirror_drive, 0.0) + 0.035 * spin_shear
    fG = clamp(0.8 + 0.05 * s.compression_amplitude_pct / 10.0 + 0.12 * dynamic_radius_shift, 0.6, 0.98)
    frac_cap = clamp(0.7 + 0.03 * STRENGTHS.get(s.tct_strength, 0.0), 0.5, 0.85)
    return {"R": R, "a": a, "kappa": kappa, "B0": B0, "Ip": Ip, "Ti": Ti, "Te": Te, "H98": H98, "fG": fG, "frac_cap": frac_cap}


def tct_controller_proxy(plasma: Dict[str, float], s: Scenario) -> Dict[str, float]:
    if TCT_RUN_CONTROLLER is not None:
        design = {"reconn_trigger": 0.65, "conf_trigger": 0.65}
        raw = TCT_RUN_CONTROLLER(
            {
                "B0_T": plasma["B0"],
                "n_e": max(plasma["ne"], 1e18),
                "Te_keV": plasma["Te"],
            },
            design,
        )
        stability_obj = raw.get("stability", {})
        stability = stability_obj.get("stability", 1.0) if isinstance(stability_obj, dict) else stability_obj
        delta_m = stability_obj.get("delta_m", 0.0) if isinstance(stability_obj, dict) else 0.0
        return {
            "risk_R": float(raw.get("risk_R", 0.0)),
            "risk_H": float(raw.get("risk_H", 0.0)),
            "precursor": float(raw.get("precursor", 0.0)),
            "upstream_factor": float(raw.get("upstream_factor", 1.0)),
            "control_strength": float(raw.get("control_strength", 0.0)),
            "stability": float(stability),
            "delta_m": float(delta_m),
        }

    B = plasma["B0"]
    n = max(plasma["ne"], 1e18)
    Te = plasma["Te"]

    # Close to the M3DC1 tct_control module semantics.
    risk_R = clamp(B / (B + 4.0), 0.0, 1.0)
    risk_H = clamp((B * n ** 0.5) / (B * n ** 0.5 + 1e10), 0.0, 1.0)
    base_risk = clamp(risk_R + risk_H, 0.0, 1.0)
    precursor = clamp(0.6 * risk_H + 0.4 * risk_R, 0.0, 1.0)
    reconn_trigger = 0.65
    conf_trigger = 0.65
    upstream_factor = 0.65 if precursor > conf_trigger else 0.80 if precursor > reconn_trigger else 1.0
    risk = clamp(base_risk * upstream_factor, 0.0, 1.0)
    control_strength = clamp((risk - reconn_trigger) / max(conf_trigger - reconn_trigger, 1e-9), 0.0, 1.0)
    delta_m = 3e8 / max(n, 1e-9) ** 0.5 * (1.0 + Te / 25.0)
    gamma0 = (B / max(delta_m, 1e-9)) / 1e8
    stability = clamp(1.0 / (1.0 + gamma0 * (1.0 - 0.85 * control_strength)), 0.0, 1.0)
    return {
        "risk_R": risk_R,
        "risk_H": risk_H,
        "precursor": precursor,
        "upstream_factor": upstream_factor,
        "control_strength": control_strength,
        "stability": stability,
        "delta_m": delta_m,
    }


def evaluate_case(plasma: Dict[str, float]) -> Dict[str, float]:
    # TCT repo plasma surrogate formulas, translated to a hybrid proxy.
    R = plasma["R"]
    a = plasma["a"]
    kappa = plasma["kappa"]
    B0 = plasma["B0"]
    Ip = plasma["Ip"]
    Ti = plasma["Ti"]
    Te = plasma["Te"]
    H98 = plasma["H98"]
    fG = plasma["fG"]
    frac_cap = plasma["frac_cap"]

    if TCT_EVALUATE_CASE is not None:
        raw = TCT_EVALUATE_CASE(R, a, kappa, B0, Ip, Ti, Te, H98, fG, frac_cap)
        return {
            "pfus_mw": raw["pfus_mw"],
            "pbrem_mw": raw["pbrem_mw"],
            "ptr_mw": raw["ptr_mw"],
            "wn_mw_m2": raw["wn_mw_m2"],
            "betaN": raw["betaN"],
            "qstar": raw["qstar"],
            "ne": raw.get("ne", raw.get("ne_m3", 0.0)),
            "bootstrap_frac": raw["bootstrap_frac"],
            "current_drive_mw": raw["current_drive_mw"],
            "aspect_ratio": raw["aspect_ratio"],
            "stored_energy_J": raw["stored_energy_J"],
            "volume_m3": raw.get("volume_m3", raw.get("V_m3", 0.0)),
        }

    volume = 2.0 * (math.pi**2) * R * (a**2) * kappa
    area_fw = 4.0 * (math.pi**2) * R * a
    nG = (Ip / (math.pi * a * a)) * 1.0e20
    ne = frac_cap * fG * nG
    sv = 5.0e-22 * (Ti**2) * math.exp(-19.94 / (max(Ti, 1e-9) ** (1.0 / 3.0)))
    pfus_mw = (0.25 * ne**2 * sv * 17.6 * 1.602176634e-13) * volume / 1e6
    pbrem_mw = (5.35e-37 * ne**2 * math.sqrt(Te * 1e3)) * volume / 1e6
    Wth_density = 1.5 * (2.0 * ne * Ti * 1e3) * 1.602176634e-19
    tauE = H98 * 1.39
    ptr_mw = (Wth_density / tauE) * volume / 1e6
    wn_mw_m2 = (0.8 * pfus_mw) / max(area_fw, 1e-12)
    p_pa = (2.0 * ne * Ti * 1e3) * 1.602176634e-19
    beta = (2.0 * 4.0e-7 * math.pi * p_pa) / max(B0**2, 1e-12)
    betaN = 100.0 * beta * a * B0 / max(Ip, 1e-12)
    qstar = (5.0 * a**2 * B0) / max(R * Ip, 1e-12) * (1.0 + kappa**2) / 2.0
    aspect_ratio = R / max(a, 1e-12)
    bootstrap_frac = max(0.05, min(0.18 * betaN * max(0.4, min(aspect_ratio, 4.0)) / max(qstar, 1.2), 0.85))
    current_drive_mw = max(Ip * (1.0 - bootstrap_frac), 0.0) / 0.18
    return {
        "pfus_mw": pfus_mw,
        "pbrem_mw": pbrem_mw,
        "ptr_mw": ptr_mw,
        "wn_mw_m2": wn_mw_m2,
        "betaN": betaN,
        "qstar": qstar,
        "ne": ne,
        "bootstrap_frac": bootstrap_frac,
        "current_drive_mw": current_drive_mw,
        "aspect_ratio": aspect_ratio,
        "stored_energy_J": Wth_density * volume,
        "volume_m3": volume,
    }


def lithium_wall_temperature(heat_flux_mw_m2: float, thickness_m: float, conductivity_W_mK: float = 84.0) -> float:
    if TCT_LITHIUM_WALL_TEMPERATURE is not None:
        return TCT_LITHIUM_WALL_TEMPERATURE(heat_flux_mw_m2, thickness_m, conductivity_W_mK)
    return heat_flux_mw_m2 * 1.0e6 * thickness_m / max(conductivity_W_mK, 1e-9)


def mhd_drag_power(B_T: float, velocity_m_s: float, conductivity_S_m: float, rho_kg_m3: float, half_width_m: float, wetted_area_m2: float = 200.0) -> float:
    if TCT_MHD_DRAG_POWER is not None:
        return TCT_MHD_DRAG_POWER(B_T, velocity_m_s, conductivity_S_m, rho_kg_m3, half_width_m, wetted_area_m2)
    magnetic_pressure = B_T**2 / (2.0 * 4.0e-7 * math.pi)
    pressure_drop = 0.5 * rho_kg_m3 * velocity_m_s**2 * (1.0 + 0.02 * magnetic_pressure / 1e6)
    volumetric_flow = velocity_m_s * 2.0 * half_width_m * wetted_area_m2
    return pressure_drop * volumetric_flow / 1e6


def pumping_power_from_heat(thermal_power_mw: float, recirc_fraction: float = 0.02) -> float:
    if TCT_PUMPING_POWER_FROM_HEAT is not None:
        return TCT_PUMPING_POWER_FROM_HEAT(thermal_power_mw, recirc_fraction)
    return thermal_power_mw * recirc_fraction


def blanket_proxy(s: Scenario, plasma: Dict[str, float]) -> Dict[str, float]:
    mats = {"Be": 0.15, "B4C": 0.22, "Li2TiO3": 0.28, "Li4SiO4": 0.25, "W_Ti_B4C_60_30_10_wt": 0.10}
    # Borrow the material-learning view from the TCT repo: Li-bearing, porous, and boron-rich
    # layers help TBR; heavy outer layers help attenuation.
    boron = BORON_DENSITY.get(s.boron_vapor_density, 0.25)
    li_layer = 0.9 if s.liquid_lithium_current in ("medium", "high") else 0.7
    attenuation = clamp(0.35 + 0.25 * boron + 0.08 * li_layer, 0.0, 1.0)
    front_heating = clamp(0.50 - 0.12 * boron - 0.08 * li_layer, 0.0, 1.0)
    fuel = AUX_FUEL_PROFILES.get(s.aux_fuel, AUX_FUEL_PROFILES["p-B11"])
    tbr = clamp(0.95 + 0.18 * boron + 0.08 * li_layer + 0.03 * plasma["bootstrap_frac"] + fuel["tbr_bonus"], 0.85, 1.35)
    return {"TBR": tbr, "attenuation": attenuation, "front_heating_frac": front_heating, "model": "blanket_proxy"}


def pB11_proxy(
    s: Scenario,
    plasma: Dict[str, float],
    ctrl: Dict[str, float],
    blanket: Dict[str, float],
    pm_effective_override: float | None = None,
    dt_alpha_coupling_override: float | None = None,
    spin_organization_override: float = 0.0,
) -> Dict[str, float]:
    if not s.pB11_enabled:
        return {
            "pB11_alpha_yield": 0.0,
            "proton_burnup_fraction": 0.0,
            "effective_proton_path_length_passes": 0.0,
            "hardware_recirc_passes": 0.0,
            "proton_energy_retention_norm": 0.0,
            "proton_window_fraction": 0.0,
            "boron_optical_depth_proxy": 0.0,
            "proton_loss_fraction": 0.0,
            "dt_alpha_assist_fraction": 0.0,
            "dt_alpha_coupling_efficiency": 0.0,
            "cavity_q_effective": 0.0,
            "boron_vapor_radiation_penalty": 0.0,
            "surface_pB11_boost": 0.0,
            "grazing_path_effective": 1.0,
            "racetrack_guidance_factor": 0.0,
            "direct_conversion_power": 0.0,
            "alpha_extraction_fraction": 0.0,
        }

    fuel = AUX_FUEL_PROFILES.get(s.aux_fuel, AUX_FUEL_PROFILES["p-B11"])
    boron = BORON_DENSITY.get(s.boron_vapor_density, 0.25)
    recirc = RECIRC.get(s.proton_recirculation_quality, 1.0)
    pm = PM_DRIVE.get(s.plasma_mirror_drive, 0.0)
    if pm_effective_override is not None:
        pm = clamp(pm_effective_override, 0.0, 1.0)
    reversal = REVERSAL.get(s.field_reversal_depth, 0.0)
    compression = s.compression_amplitude_pct / 100.0
    rf = RF_TIMING.get(s.rf_timing, 0.0)
    requested_alpha_assist = DT_ALPHA_ASSIST.get(s.dt_alpha_assist, 0.0)
    alpha_assist = requested_alpha_assist
    if dt_alpha_coupling_override is not None:
        alpha_assist = clamp(dt_alpha_coupling_override, 0.0, requested_alpha_assist)
    areal_density = clamp(s.boron_areal_density, 0.1, 20.0)
    vapor_control = BORON_VAPOR_CONTROL.get(s.boron_vapor_control, 0.0)
    cavity_q = CAVITY_Q.get(s.pb11_cavity_q, 0.0)
    li_boron_mix = LI_BORON_MIX.get(s.li_boron_mix_fraction, 0.0)
    wall_boron = BORON_WALL_LOADING.get(s.boron_wall_loading, 0.0)
    wall_thickness = PB11_WALL_THICKNESS.get(s.pb11_wall_thickness, 0.0)
    wall_current = PB11_WALL_CURRENT.get(s.pb11_wall_current, 0.0)
    boron_wick = BORON_WICK.get(s.boron_wick_efficiency, 0.0)
    driver = PROTON_DRIVER.get(s.proton_driver_mode, PROTON_DRIVER["external"])
    grazing = GRAZING_PATH.get(s.grazing_path_multiplier, 1.0)
    profile_shape = BORON_PROFILE_SHAPE.get(s.boron_profile_shape, 0.0)
    phase_cooling = PROTON_PHASE_COOLING.get(s.proton_phase_cooling, 0.0)
    orbit_closure = RESONANT_ORBIT_CLOSURE.get(s.resonant_orbit_closure, 0.0)
    sheet_quality = BORON_SHEET_QUALITY.get(s.boron_sheet_quality, 0.0)
    phase_recovery = PROTON_PHASE_RECOVERY.get(s.proton_phase_recovery, 0.0)
    alpha_bootstrap = ALPHA_BOOTSTRAP_FEEDBACK.get(s.alpha_bootstrap_feedback, 0.0)
    fuel_profile = AUX_FUEL_PROFILES.get(s.aux_fuel, AUX_FUEL_PROFILES["p-B11"])
    racetrack = EDGE_RACETRACK.get(s.edge_racetrack, 0.0)
    racetrack_pitch = RACETRACK_PITCH.get(s.racetrack_pitch, 0.70)
    racetrack_clearance = RACETRACK_WALL_CLEARANCE.get(s.racetrack_wall_clearance, 0.65)
    racetrack_rephase = RACETRACK_ENERGY_REPHASE.get(s.racetrack_energy_rephase, 0.0)
    recirc_factor = clamp(math.log10(max(1.0, recirc)) / 6.0, 0.0, 1.0)
    recirc_log = math.log10(max(1.0, recirc))
    recirc_fatigue = clamp((recirc_log - 4.0) / 3.0, 0.0, 1.0) * (1.0 - 0.35 * orbit_closure - 0.20 * phase_recovery)
    vapor_crowding = clamp((boron * areal_density * (1.0 - 0.35 * profile_shape - 0.22 * sheet_quality) - 5.5) / 9.5, 0.0, 1.0)
    cavity_q_effective = clamp(
        cavity_q
        * (0.45 + 0.25 * reversal + 0.20 * vapor_control + 0.10 * pm)
        * (0.70 + 0.30 * recirc_factor),
        0.0,
        1.0,
    )
    spin_transport_feasibility = clamp(
        0.18
        + 0.24 * reversal
        + 0.18 * cavity_q_effective
        + 0.16 * pm
        + 0.14 * RF_GRATING.get(s.rf_grating, 0.0)
        + 0.10 * clamp(s.channel_separation_quality, 0.0, 1.0),
        0.0,
        0.86,
    )
    spin_transport = clamp(spin_organization_override, 0.0, 1.0) * spin_transport_feasibility
    racetrack_feasibility = clamp(
        0.18
        + 0.20 * reversal
        + 0.18 * cavity_q_effective
        + 0.16 * pm
        + 0.14 * wall_current
        + 0.12 * spin_transport
        + 0.10 * RF_GRATING.get(s.rf_grating, 0.0),
        0.0,
        0.92,
    )
    clearance_quality = clamp(1.0 - abs(racetrack_clearance - 0.72) / 0.72, 0.0, 1.0)
    racetrack_guidance = racetrack * racetrack_feasibility * (0.70 + 0.30 * racetrack_pitch) * (0.65 + 0.35 * clearance_quality)
    racetrack_virtual_multiplier = 1.0 + 26.0 * racetrack_guidance * (0.55 + 0.45 * racetrack_rephase) * (0.72 + 0.28 * clearance_quality)
    hardware_recirc_passes = max(1.0, recirc / (1.0 + 7.0 * racetrack_guidance))
    hardware_recirc_log = math.log10(hardware_recirc_passes)
    recirc_fatigue = clamp((hardware_recirc_log - 4.2) / 2.2, 0.0, 1.0)
    recirc_fatigue *= (1.0 - 0.35 * orbit_closure - 0.20 * phase_recovery) * (1.0 - 0.45 * racetrack_guidance)

    driver_energy_keV = 140.0 + 4.0 * plasma["Ti"] + 55.0 * compression + 18.0 * rf + 14.0 * pm + 10.0 * reversal
    proton_energy_keV = 0.65 * clamp(s.proton_energy_center_keV, 80.0, 700.0) + 0.35 * driver_energy_keV
    proton_energy_keV += 32.0 * alpha_assist

    raw_spread = clamp(s.proton_energy_spread_pct, 5.0, 120.0)
    collimation = 1.0 + 0.45 * pm + 0.25 * reversal + 0.15 * rf + 0.35 * cavity_q_effective + 0.20 * vapor_control + 0.45 * phase_cooling + 0.25 * phase_recovery + 0.32 * spin_transport + 0.34 * racetrack_guidance + 0.18 * racetrack_rephase
    energy_spread_pct = raw_spread / collimation
    resonance_overlap = gaussian(proton_energy_keV, fuel["energy_mu_keV"], fuel["energy_sigma_keV"])
    useful_window = sigmoid((proton_energy_keV - 100.0) / 35.0) * sigmoid((600.0 - proton_energy_keV) / 55.0)
    spread_penalty = 1.0 / (1.0 + (energy_spread_pct / 42.0) ** 1.35)
    window = clamp(
        (0.70 * resonance_overlap + 0.30 * useful_window)
        * spread_penalty
        * (1.0 - 0.10 * vapor_crowding)
        + driver["window_bonus"],
        0.0,
        1.0,
    )

    mirror_boundary_credit = clamp(pm * (0.35 + 0.35 * cavity_q_effective + 0.20 * reversal + 0.10 * vapor_control), 0.0, 1.0)
    dwell_boost = 0.7 + 0.22 * ctrl["stability"] + 0.16 * pm + 0.08 * reversal + 0.05 * alpha_assist + 0.25 * cavity_q_effective + 0.22 * orbit_closure + 0.18 * spin_transport + 0.42 * racetrack_guidance
    grazing_effective = 1.0 + (grazing - 1.0) * clamp(0.20 + 0.26 * reversal + 0.22 * cavity_q_effective + 0.18 * boron_wick + 0.14 * mirror_boundary_credit + 0.12 * orbit_closure + 0.10 * spin_transport + 0.22 * racetrack_guidance, 0.0, 1.0)
    mirror_path_credit = 1.0 + 1.25 * mirror_boundary_credit + 0.55 * orbit_closure + 0.28 * spin_transport + 0.72 * racetrack_guidance
    path_passes = hardware_recirc_passes * racetrack_virtual_multiplier * dwell_boost * grazing_effective * mirror_path_credit
    path_factor = clamp(math.log10(max(2.0, path_passes)) / 7.7, 0.0, 1.25)
    surface_pB11_boost = clamp(
        (0.35 * li_boron_mix + 0.65 * wall_boron)
        * (1.0 + 0.38 * wall_thickness)
        * boron_wick
        * (0.45 + 0.25 * reversal + 0.20 * vapor_control + 0.10 * clamp(s.channel_separation_quality, 0.0, 1.0) + 0.12 * wall_current)
        * (0.70 + 0.30 * min(1.0, recirc_factor)),
        0.0,
        1.25,
    )
    optical_depth = clamp(
        0.18
        * boron
        * areal_density
        * path_factor
        * (1.0 + 0.18 * pm + 0.45 * cavity_q_effective + 0.18 * vapor_control + 0.85 * surface_pB11_boost + 0.42 * profile_shape + 0.32 * sheet_quality),
        0.0,
        4.5,
    )
    optical_absorption = 1.0 - math.exp(-optical_depth)
    vapor_stability = clamp(
        1.0
        - 0.10 * vapor_crowding
        - 0.05 * recirc_fatigue
        - 0.04 * max(0.0, pm - 0.65)
        + 0.06 * vapor_control
        + 0.04 * boron_wick
        + 0.06 * profile_shape
        + 0.05 * sheet_quality,
        0.72,
        1.0,
    )

    electron_drag_loss = clamp(0.16 * (1.0 - pm) + 0.012 * max(0.0, plasma["Te"] - 12.0) - 0.05 * vapor_control, 0.0, 0.45)
    charge_exchange_loss = clamp(0.08 + 0.060 * boron * areal_density / 10.0 + 0.03 * max(0.0, compression - 0.05) + 0.035 * vapor_crowding - 0.04 * vapor_control - 0.03 * surface_pB11_boost, 0.0, 0.40)
    scattering_loss = clamp(
        0.04
        + 0.05 * math.log10(max(1.0, path_passes)) / 7.0
        + 0.055 * recirc_fatigue * (1.0 - 0.55 * mirror_boundary_credit)
        + 0.03 * areal_density / 10.0
        - 0.05 * cavity_q_effective
        - 0.03 * boron_wick
        - 0.025 * phase_recovery
        - 0.018 * orbit_closure
        - 0.030 * spin_transport
        - 0.050 * racetrack_guidance
        - 0.026 * racetrack_rephase
        + 0.012 * math.log10(max(1.0, grazing_effective)),
        0.0,
        0.38,
    )
    wall_clearance_penalty = max(0.0, racetrack_clearance - 0.82) * (0.18 + 0.20 * racetrack)
    wall_strike_loss = clamp(0.22 - 0.12 * reversal - 0.12 * pm - 0.05 * ctrl["stability"] - 0.08 * cavity_q_effective - 0.06 * boron_wick - 0.04 * orbit_closure - 0.06 * spin_transport - 0.08 * racetrack_guidance + wall_clearance_penalty + 0.035 * recirc_fatigue * (1.0 - mirror_boundary_credit), 0.02, 0.38)
    thermalization_loss = clamp(0.12 + 0.18 * max(0.0, energy_spread_pct - 35.0) / 85.0 - 0.08 * alpha_assist - 0.045 * phase_cooling - 0.025 * spin_transport - 0.035 * racetrack_rephase, 0.02, 0.40)
    combined_loss = 1.0
    for loss in (electron_drag_loss, charge_exchange_loss, scattering_loss, wall_strike_loss, thermalization_loss):
        combined_loss *= 1.0 - loss
    survival = clamp(combined_loss, 0.05, 0.95)

    retention = clamp(
        0.50
        + 0.14 * reversal
        + 0.13 * pm
        + 0.08 * compression
        + 0.10 * alpha_assist
        + 0.08 * window
        + 0.08 * cavity_q_effective
        + 0.04 * vapor_control
        + 0.06 * surface_pB11_boost
        + 0.04 * mirror_boundary_credit
        + 0.045 * phase_cooling
        + 0.035 * phase_recovery
        + 0.025 * orbit_closure
        + 0.055 * spin_transport
        + 0.060 * racetrack_guidance
        + 0.040 * racetrack_rephase
        - 0.08 * ctrl["control_strength"]
        - 0.06 * ctrl["risk_H"]
        - 0.05 * recirc_fatigue * (1.0 - 0.45 * mirror_boundary_credit)
        - 0.035 * vapor_crowding
        - 0.06 * energy_spread_pct / 100.0,
        0.0,
        1.0,
    )
    burnup = clamp(
        0.085
        * fuel["burnup_scale"]
        * optical_absorption
        * window
        * (0.35 + 0.65 * retention)
        * survival
        * vapor_stability
        * (1.0 + 0.25 * alpha_assist + 0.55 * surface_pB11_boost + 0.12 * alpha_bootstrap),
        0.0,
        0.45,
    )
    alpha_yield = burnup * (1.0 + 0.25 * boron) * (1.0 + 0.14 * pm) * 4.5 * fuel["yield_scale"]
    alpha_extract = clamp(0.05 + 0.22 * ctrl["stability"] + 0.18 * reversal + 0.15 * pm + 0.12 * compression + 0.16 * spin_transport + 0.12 * racetrack_guidance + 0.20 * clamp(s.alpha_conversion_efficiency, 0.0, 1.0), 0.0, 0.98)
    direct = alpha_yield * clamp(s.alpha_conversion_efficiency, 0.0, 1.0) * alpha_extract
    boron_vapor_radiation_penalty = clamp(
        fuel["radiation_scale"] * 0.015 * boron * areal_density * (1.0 - 0.30 * vapor_control)
        + 0.020 * li_boron_mix * boron_wick
        + 0.006 * wall_boron * boron_wick * (1.0 + 0.75 * wall_thickness)
        + 0.018 * wall_thickness * wall_boron * (1.0 - 0.25 * wall_current)
        + 0.008 * wall_current * wall_boron
        + fuel["radiation_scale"] * 0.030 * vapor_crowding
        + fuel["radiation_scale"] * 0.03 * max(0.0, optical_depth - 2.5),
        0.0,
        0.45,
    )
    return {
        "pB11_alpha_yield": alpha_yield,
        "proton_burnup_fraction": burnup,
        "effective_proton_path_length_passes": path_passes,
        "hardware_recirc_passes": hardware_recirc_passes,
        "proton_energy_retention_norm": retention,
        "proton_window_fraction": window,
        "boron_optical_depth_proxy": optical_depth,
        "proton_loss_fraction": 1.0 - survival,
        "dt_alpha_assist_fraction": alpha_assist,
        "dt_alpha_coupling_efficiency": alpha_assist / max(requested_alpha_assist, 1e-9) if requested_alpha_assist > 0.0 else 0.0,
        "cavity_q_effective": cavity_q_effective,
        "boron_vapor_radiation_penalty": boron_vapor_radiation_penalty,
        "surface_pB11_boost": surface_pB11_boost,
        "grazing_path_effective": grazing_effective,
        "racetrack_guidance_factor": racetrack_guidance,
        "alpha_extraction_fraction": alpha_extract,
        "direct_conversion_power": direct,
    }


def simulate(s: Scenario) -> Metrics:
    m3 = m3dc1_mapping(s)
    plasma_inputs = plasma_model_proxy(s)
    plasma = evaluate_case(plasma_inputs)
    plasma.update(plasma_inputs)
    ctrl = tct_controller_proxy(plasma, s)
    blanket = blanket_proxy(s, plasma)

    tct_strength = STRENGTHS.get(s.tct_strength, 0.0)
    reversal = REVERSAL.get(s.field_reversal_depth, 0.0)
    rotation = ROTATION.get(s.counter_rotation, 0.0)
    spin = PLASMA_SPIN_ORGANIZATION.get(s.plasma_spin_organization, 0.0)
    compression = s.compression_amplitude_pct / 100.0
    dynamic_volume = DYNAMIC_VOLUME_COMPRESSION.get(s.dynamic_volume_compression, 0.0)
    volume_timing = VOLUME_COMPRESSION_TIMING.get(s.volume_compression_timing, 0.0)
    volume_duty = clamp(s.volume_compression_duty, 0.05, 1.0)
    volume_compression = clamp(dynamic_volume * max(0.0, volume_timing) * (0.45 + 0.55 * math.sqrt(volume_duty)), 0.0, 0.22)
    volume_actuator_power = dynamic_volume * volume_duty * (0.18 + 1.35 * dynamic_volume + 0.18 * max(0.0, volume_timing))
    volume_fatigue = clamp((dynamic_volume / 0.18) ** 1.7 * volume_duty, 0.0, 1.5)
    ramp = RAMP_TIMING.get(s.magnetic_ramp_timing, 0.15)
    rf = RF_TIMING.get(s.rf_timing, 0.0)
    pm = PM_DRIVE.get(s.plasma_mirror_drive, 0.0)
    dt_seed = DT_SEED_FRACTION.get(s.dt_seed_fraction, 1.0)
    profile_shape = BORON_PROFILE_SHAPE.get(s.boron_profile_shape, 0.0)
    phase_cooling = PROTON_PHASE_COOLING.get(s.proton_phase_cooling, 0.0)
    orbit_closure = RESONANT_ORBIT_CLOSURE.get(s.resonant_orbit_closure, 0.0)
    sheet_quality = BORON_SHEET_QUALITY.get(s.boron_sheet_quality, 0.0)
    phase_recovery = PROTON_PHASE_RECOVERY.get(s.proton_phase_recovery, 0.0)
    converter_staging = CONVERTER_STAGING.get(s.converter_staging, 0.0)
    alpha_bootstrap = ALPHA_BOOTSTRAP_FEEDBACK.get(s.alpha_bootstrap_feedback, 0.0)
    graphene_channels = GRAPHENE_HEAT_CHANNELS.get(s.graphene_heat_channels, 0.0)
    graphene_power_scale = GRAPHENE_CHANNEL_POWER_SCALE.get(s.graphene_heat_channels, 0.0)
    fuel_profile = AUX_FUEL_PROFILES.get(s.aux_fuel, AUX_FUEL_PROFILES["p-B11"])
    li = LI_CURRENT.get(s.liquid_lithium_current, 0.0)
    rf_grating = RF_GRATING.get(s.rf_grating, 0.0)
    spin_organization = clamp(spin * (0.50 + 0.32 * rotation + 0.18 * reversal + 0.12 * rf_grating), 0.0, 1.0)
    electron_channel = CHANNEL_STRENGTH.get(s.electron_channel, 0.0)
    alpha_channel = CHANNEL_STRENGTH.get(s.alpha_channel, 0.0)
    ash_channel = CHANNEL_STRENGTH.get(s.ash_channel, 0.0)
    pm_duty = clamp(s.plasma_mirror_duty, 0.05, 1.0)
    rf_grating_duty = clamp(s.rf_grating_duty, 0.05, 1.0)
    electron_duty = clamp(s.electron_channel_duty, 0.05, 1.0)
    alpha_duty = clamp(s.alpha_channel_duty, 0.05, 1.0)
    ash_duty = clamp(s.ash_channel_duty, 0.05, 1.0)
    pm_effective = pm * (0.35 + 0.65 * math.sqrt(pm_duty))
    rf_grating_effective = rf_grating * (0.35 + 0.65 * math.sqrt(rf_grating_duty))
    electron_channel_effective = electron_channel * (0.35 + 0.65 * math.sqrt(electron_duty))
    alpha_channel_effective = alpha_channel * (0.35 + 0.65 * math.sqrt(alpha_duty))
    ash_channel_effective = ash_channel * (0.35 + 0.65 * math.sqrt(ash_duty))
    channel_separation = clamp(s.channel_separation_quality, 0.0, 1.0)
    channel_cross_talk = clamp(
        (1.0 - channel_separation) * (0.35 + 0.20 * (electron_channel_effective + alpha_channel_effective + ash_channel_effective) / 3.0)
        + 0.08 * max(0.0, rf_grating_effective - 0.7),
        0.0,
        0.8,
    )
    channel_separation_effective = clamp(
        channel_separation * (0.55 + 0.25 * rf_grating_effective + 0.10 * reversal + 0.10 * pm_effective + 0.12 * spin_organization)
        - 0.25 * channel_cross_talk
        - 0.06 * volume_fatigue,
        0.0,
        1.0,
    )
    requested_alpha_assist = DT_ALPHA_ASSIST.get(s.dt_alpha_assist, 0.0)
    dt_alpha_leakage = clamp(
        0.08
        + 0.030 * plasma["pfus_mw"]
        + 0.10 * reversal
        + 0.08 * compression
        + 0.10 * alpha_channel_effective * channel_separation_effective
        + 0.04 * rf_grating_effective
        - 0.10 * channel_cross_talk,
        0.0,
        1.0,
    )
    dt_alpha_coupling = requested_alpha_assist * dt_alpha_leakage
    pB11 = pB11_proxy(
        s,
        plasma,
        ctrl,
        blanket,
        pm_effective_override=pm_effective,
        dt_alpha_coupling_override=dt_alpha_coupling,
        spin_organization_override=spin_organization,
    )
    rf_grating_power = 0.20 * rf_grating * rf_grating_duty * (1.0 + 0.25 * compression + 0.15 * pm)
    channel_power = (
        0.11 * electron_channel * electron_duty
        + 0.13 * alpha_channel * alpha_duty
        + 0.10 * ash_channel * ash_duty
    ) * (0.75 + 0.25 * channel_separation)
    electron_exhaust_fraction = clamp(
        0.10 + 0.42 * electron_channel_effective * channel_separation_effective + 0.16 * pm_effective + 0.10 * rf_grating_effective - 0.12 * channel_cross_talk,
        0.0,
        0.85,
    )
    ash_removal_fraction = clamp(
        0.10 + 0.55 * ash_channel_effective * channel_separation_effective + 0.12 * rf_grating_effective - 0.10 * channel_cross_talk,
        0.0,
        0.92,
    )

    confinement = clamp(1.0 + 0.30 * tct_strength + 0.16 * rotation + 0.18 * spin_organization + 0.14 * reversal + 0.09 * compression + 0.32 * volume_compression + 0.06 * ramp + 0.05 * rf + 0.08 * ctrl["stability"] - 0.10 * max(0.0, pm - 0.7) - 0.08 * volume_fatigue, 0.2, 2.5)
    event_rate = clamp(1.05 - 0.30 * tct_strength - 0.12 * rotation - 0.18 * spin_organization - 0.16 * reversal - 0.10 * compression - 0.18 * volume_compression - 0.06 * ramp - 0.08 * rf - 0.12 * ctrl["stability"] + 0.18 * max(0.0, pm - 0.7) + 0.16 * volume_fatigue, 0.02, 1.8)
    shear_profile = clamp(0.15 + 0.55 * rotation + 0.52 * spin_organization + 0.35 * reversal + 0.12 * compression + 0.30 * volume_compression, 0.0, 1.8)
    current_sheet = clamp(1.0 - 0.22 * tct_strength - 0.08 * rotation - 0.11 * spin_organization - 0.10 * reversal - 0.05 * compression - 0.08 * volume_compression + 0.10 * event_rate + 0.05 * volume_fatigue, 0.25, 1.5)

    ion_T = max(2.0, plasma["Ti"] + 6.0 * tct_strength + 2.5 * rotation + 2.8 * spin_organization + 2.0 * reversal + 2.0 * compression + 8.0 * volume_compression + 1.4 * rf + 1.4 * ctrl["stability"])
    elec_T = max(1.5, plasma["Te"] + 1.6 * rf + 0.8 * compression + 2.2 * volume_compression + 0.7 * pm - 0.8 * ctrl["stability"] - 0.9 * pm)
    ti_te = ion_T / max(elec_T, 1e-9)

    rf_heating_phase = max(0.0, rf)
    rf_power_level = 0.0 if s.rf_timing == "off" else max(0.18, abs(rf))
    ion_rf_frac = clamp((0.12 + 0.35 * compression + 0.20 * pm) * rf_heating_phase, 0.0, 0.85)
    rf_power = 0.9 * rf_power_level * (1.0 + 1.2 * compression + 0.4 * pm)
    beam_power = 0.6 * pm * pm_duty * (1.0 + 0.2 * compression)
    pB11_support_power = 0.0
    proton_recovered_power = 0.0
    boron_replenishment_power = 0.0
    li_boron_mhd_penalty = 0.0
    alpha_channeling_power = 0.0
    alpha_to_proton_power = 0.0
    alpha_to_li_heat = 0.0
    direct_converter_gain = 0.0
    adaptive_skimmer_gain = 0.0
    pb11_support_recirc_power = 0.0
    pb11_support_areal_power = 0.0
    pb11_support_driver_power = 0.0
    pb11_support_control_power = 0.0
    racetrack_drive_power = 0.0
    racetrack = EDGE_RACETRACK.get(s.edge_racetrack, 0.0)
    racetrack_rephase = RACETRACK_ENERGY_REPHASE.get(s.racetrack_energy_rephase, 0.0)
    racetrack_clearance = RACETRACK_WALL_CLEARANCE.get(s.racetrack_wall_clearance, 0.65)
    energy_recovery = ENERGY_RECOVERY.get(s.proton_energy_recovery, 0.0)
    vapor_control = BORON_VAPOR_CONTROL.get(s.boron_vapor_control, 0.0)
    cavity_q = CAVITY_Q.get(s.pb11_cavity_q, 0.0)
    proton_driver = PROTON_DRIVER.get(s.proton_driver_mode, PROTON_DRIVER["external"])
    li_boron_mix = LI_BORON_MIX.get(s.li_boron_mix_fraction, 0.0)
    wall_boron = BORON_WALL_LOADING.get(s.boron_wall_loading, 0.0)
    wall_thickness = PB11_WALL_THICKNESS.get(s.pb11_wall_thickness, 0.0)
    wall_current = PB11_WALL_CURRENT.get(s.pb11_wall_current, 0.0)
    boron_wick = BORON_WICK.get(s.boron_wick_efficiency, 0.0)
    alpha_channeling = ALPHA_CHANNELING.get(s.alpha_channeling_to_protons, 0.0)
    alpha_to_proton_coupling = ALPHA_TO_PROTON_COUPLING.get(s.alpha_to_proton_coupling, 0.0)
    direct_converter_geometry = DIRECT_CONVERTER_GEOMETRY.get(s.direct_converter_geometry, 0.0)
    adaptive_skimmer = ADAPTIVE_SKIMMER.get(s.adaptive_electron_skimmer, 0.0)
    alpha_to_li_capture = clamp(s.alpha_to_li_capture_fraction, 0.0, 0.95)
    if s.pB11_enabled:
        recirc_requested = RECIRC.get(s.proton_recirculation_quality, 1.0)
        hardware_passes = max(1.0, pB11.get("hardware_recirc_passes", recirc_requested))
        hardware_log = math.log10(hardware_passes)
        virtual_path_log = math.log10(max(1.0, pB11["effective_proton_path_length_passes"]))
        recirc_excess = max(0.0, hardware_log - 4.0) * (1.0 - 0.28 * orbit_closure - 0.20 * phase_recovery)
        recirc_excess *= 1.0 - 0.32 * pB11["racetrack_guidance_factor"]
        grazing_credit = clamp(math.log10(max(1.0, pB11["grazing_path_effective"])) / 2.0, 0.0, 1.0)
        mirror_substitution = clamp(
            pm_effective
            * (0.35 + 0.30 * pB11["cavity_q_effective"] + 0.20 * channel_separation_effective + 0.15 * REVERSAL.get(s.field_reversal_depth, 0.0)),
            0.0,
            0.85,
        )
        recirc_nonlinear_burden = 0.070 * recirc_excess ** 1.70 + 0.060 * max(0.0, hardware_log - 5.0) ** 2
        pb11_support_recirc_power = (
            0.060 * hardware_log
            + 0.006 * virtual_path_log
            + recirc_nonlinear_burden
        ) * (1.0 - 0.42 * grazing_credit) * (1.0 - 0.55 * mirror_substitution)
        pb11_support_areal_power = 0.025 * clamp(s.boron_areal_density, 0.1, 20.0) * fuel_profile["support_scale"]
        pb11_support_driver_power = (
            0.20 * DT_ALPHA_ASSIST.get(s.dt_alpha_assist, 0.0)
            + 0.08 * (1.0 - pB11["proton_energy_retention_norm"])
        ) * (1.0 - 0.25 * phase_recovery - 0.18 * alpha_bootstrap) * fuel_profile["support_scale"]
        pb11_support_control_power = (
            0.06 * energy_recovery
            + 0.08 * cavity_q
            + 0.05 * vapor_control
            + 0.035 * pm_effective * pm_duty
            + 0.035 * orbit_closure
            + 0.030 * sheet_quality
            + 0.035 * phase_recovery
            + 0.040 * converter_staging
            + 0.050 * alpha_bootstrap
        )
        racetrack_drive_power = racetrack * (
            0.020
            + 0.040 * racetrack_rephase
            + 0.022 * wall_current
            + 0.035 * max(0.0, racetrack_clearance - 0.82)
        )
        pB11_support_power = pb11_support_recirc_power + pb11_support_areal_power + pb11_support_driver_power + pb11_support_control_power
        pB11_support_power *= 1.0 - 0.18 * channel_separation_effective - 0.10 * mirror_substitution - 0.06 * spin_organization - 0.08 * pB11["racetrack_guidance_factor"]
        pB11_support_power *= proton_driver["cost_scale"] * fuel_profile["support_scale"]
        energy_recovery = clamp(energy_recovery + proton_driver["recovery_bonus"], 0.0, 0.92)
        boron_replenishment_power = fuel_profile["replenishment_scale"] * (
            0.035 * li_boron_mix * (0.35 + boron_wick)
            + 0.012 * wall_boron * boron_wick * (1.0 + 0.65 * wall_thickness)
            + 0.014 * wall_thickness * wall_boron
            + 0.010 * pB11["boron_optical_depth_proxy"]
            + 0.025 * sheet_quality
        )
        li_boron_mhd_penalty = (
            0.055 * li_boron_mix * (0.50 + li) * (1.0 + 0.35 * boron_wick)
            + 0.052 * wall_current * wall_boron * (0.65 + 0.35 * wall_thickness)
        )
        alpha_channeling_power = (
            pB11["pB11_alpha_yield"]
            * alpha_channeling
            * (0.34 + 0.25 * pB11["cavity_q_effective"] + 0.16 * alpha_channel_effective * channel_separation_effective)
        )
        alpha_to_proton_power = (
            pB11["pB11_alpha_yield"]
            * alpha_to_proton_coupling
            * pB11["dt_alpha_coupling_efficiency"]
            * (0.25 + 0.25 * pB11["cavity_q_effective"] + 0.20 * channel_separation_effective + 0.12 * pB11["surface_pB11_boost"] + 0.10 * alpha_bootstrap)
        )
        proton_recovered_power = (
            pB11_support_power
            * energy_recovery
            * pB11["proton_loss_fraction"]
            * pB11["proton_energy_retention_norm"]
            * (0.55 + 0.35 * channel_separation_effective + 0.10 * pB11["cavity_q_effective"])
        )
    electron_exhaust = (
        0.25 * pm * (1.0 + 0.7 * ctrl["stability"] + 0.4 * compression)
        + 0.15 * max(0.0, elec_T - 8.5)
    ) * (1.0 + 0.35 * electron_exhaust_fraction)
    if adaptive_skimmer > 0.0:
        adaptive_skimmer_gain = adaptive_skimmer * clamp((elec_T - 10.0) / 8.0 + brems if "brems" in locals() else (elec_T - 10.0) / 8.0, 0.0, 1.0)
        electron_exhaust *= 1.0 + 0.18 * adaptive_skimmer_gain
    brems = max(
        0.08,
        (elec_T / max(ion_T, 1e-9))
        * (1.0 + 0.3 * event_rate)
        * (1.0 - 0.15 * clamp(pm, 0.0, 1.0))
        * (1.0 - 0.28 * electron_exhaust_fraction)
        * (1.0 - 0.20 * adaptive_skimmer_gain),
    )

    density = max(0.25, 1.0 + 0.10 * compression + 0.75 * volume_compression + 0.04 * rotation + 0.03 * reversal + 0.05 * tct_strength)
    beta = clamp(0.38 + 0.06 * ion_T / 10.0 + 0.05 * density - 0.05 * event_rate, 0.0, 2.5)
    betaN = beta * (1.0 + 0.3 * confinement)

    burn = sigmoid((ion_T - 8.5) / 2.5)
    helium_ash_fraction = clamp(0.18 * (1.0 - ash_removal_fraction) + 0.05 * event_rate + 0.03 * pB11["pB11_alpha_yield"], 0.0, 0.50)
    core_dilution_penalty = helium_ash_fraction * (0.5 + 0.5 * (1.0 - channel_separation_effective))
    fusion_dt = max(
        0.0,
        6.0
        * dt_seed
        * density
        * burn
        * (1.0 + 0.55 * confinement)
        * (1.0 + 0.12 * compression)
        * (1.0 + 0.38 * volume_compression)
        * (1.0 + 0.05 * ion_rf_frac)
        * (1.0 - 0.14 * event_rate)
        * (1.0 - 0.08 * core_dilution_penalty),
    )
    neutron_heat = 0.45 * fusion_dt
    xray_heat = 0.18 * elec_T * (1.0 + 0.25 * event_rate) + pB11["boron_vapor_radiation_penalty"]
    alpha_capture_fraction = clamp(
        pB11["alpha_extraction_fraction"]
        + 0.35 * alpha_channel_effective * channel_separation_effective
        + 0.10 * rf_grating_effective
        + 0.10 * spin_organization * channel_separation_effective * (0.40 + 0.30 * reversal + 0.30 * rf_grating_effective)
        + 0.08 * wall_current * pB11["surface_pB11_boost"] * channel_separation_effective
        + 0.12 * pB11["racetrack_guidance_factor"] * channel_separation_effective
        + 0.20 * direct_converter_geometry * channel_separation_effective
        + 0.16 * converter_staging * channel_separation_effective
        - 0.15 * channel_cross_talk,
        0.0,
        0.98,
    )
    alpha_thermalization_fraction = clamp(1.0 - alpha_capture_fraction, 0.0, 1.0)
    direct_converter_gain = direct_converter_geometry * alpha_capture_fraction * (1.0 + 0.35 * converter_staging)
    staged_conversion_efficiency = clamp(s.alpha_conversion_efficiency + 0.10 * converter_staging, 0.0, 0.92)
    direct_conversion_power = pB11["pB11_alpha_yield"] * staged_conversion_efficiency * alpha_capture_fraction * (1.0 + 0.12 * direct_converter_gain) * fuel_profile["direct_conversion_scale"]
    alpha_channeling_power = min(alpha_channeling_power, pB11["pB11_alpha_yield"] * alpha_thermalization_fraction * 0.62)
    alpha_to_proton_power = min(alpha_to_proton_power, pB11["pB11_alpha_yield"] * alpha_thermalization_fraction * 0.42)
    missed_alpha_power = max(0.0, pB11["pB11_alpha_yield"] * alpha_thermalization_fraction - alpha_channeling_power - alpha_to_proton_power)
    alpha_to_li_heat = missed_alpha_power * alpha_to_li_capture * (0.45 + 0.35 * boron_wick + 0.20 * li_boron_mix)
    alpha_thermal = missed_alpha_power * (1.0 - 0.35 * alpha_to_li_capture) * 0.55
    proton_loss_heat = max(0.0, pB11_support_power * pB11["proton_loss_fraction"] * 0.8 - 0.45 * proton_recovered_power)
    ash_removal_power = 0.08 * ash_channel * ash_duty * (0.5 + helium_ash_fraction)
    failed_beam_heat = beam_power * (1.0 - 0.45 * ctrl["stability"])
    wall_heat_spread_credit = 1.0 - 0.08 * wall_thickness - 0.04 * wall_current
    racetrack_wall_heat = max(0.0, racetrack_clearance - 0.82) * racetrack * (0.12 + 0.18 * pB11["pB11_alpha_yield"])
    compression_heat_spike = 0.20 * volume_compression * (fusion_dt + pB11["pB11_alpha_yield"]) + 0.10 * volume_fatigue
    raw_li_wall_heat = fuel_profile["wall_heat_scale"] * (0.42 * neutron_heat + 0.50 * failed_beam_heat + 0.25 * xray_heat + 0.20 * alpha_thermal + 0.45 * alpha_to_li_heat + 0.35 * proton_loss_heat + 0.45 * compression_heat_spike + 0.55 * racetrack_wall_heat) * wall_heat_spread_credit - 0.12 * li
    raw_be_b4c_heat = fuel_profile["wall_heat_scale"] * (0.28 * neutron_heat + 0.45 * xray_heat + 0.40 * alpha_thermal + 0.18 * alpha_to_li_heat + 0.45 * proton_loss_heat + 0.35 * racetrack_wall_heat) * (1.0 - 0.06 * wall_thickness) + 0.12 * event_rate - 0.08 * li
    graphene_heat_spread = clamp(
        graphene_channels
        * (0.45 + 0.22 * li + 0.12 * boron_wick + 0.10 * channel_separation_effective + 0.08 * alpha_to_li_capture)
        * (1.0 - 0.08 * event_rate),
        0.0,
        0.82,
    )
    graphene_channel_power = graphene_power_scale * (0.045 + 0.025 * (raw_li_wall_heat + raw_be_b4c_heat) + 0.020 * max(0.0, compression - 0.03))
    li_wall_heat = raw_li_wall_heat * (1.0 - 0.36 * graphene_heat_spread)
    be_b4c_heat = raw_be_b4c_heat * (1.0 - 0.44 * graphene_heat_spread)

    coil_power = 0.35 * tct_strength + 0.25 * reversal + 0.22 * rotation + 0.16 * spin_organization + 0.18 * compression + 0.62 * volume_compression + 0.28 * pm_effective
    pump_power = 0.10 + 0.10 * li + 0.05 * compression + 0.04 * pm + graphene_channel_power
    mhd_power = m3["li_scale"] * 0.12 + m3["feedback_scale"] * 0.18 + m3["eps"] * 1e8 * 0.02 + m3["pedge"] * 120.0

    # Base electric balance from the TCT repo plus the p-B11 auxiliary terms.
    thermal_balance = fusion_dt - brems - mhd_power - pump_power - (plasma["current_drive_mw"] * 0.02)
    net_electric = thermal_balance * 0.42
    pB11_dedicated_power = 0.0
    pB11_wall_penalty = 0.0
    if s.pB11_enabled:
        pB11_dedicated_power = (
            pB11_support_power
            + 0.65 * rf_grating_power
            + 0.60 * beam_power
            + 0.70 * channel_power
            + ash_removal_power
            + boron_replenishment_power
            + li_boron_mhd_penalty
            + 0.04 * direct_converter_geometry
            + 0.03 * alpha_to_proton_coupling
            + 0.025 * adaptive_skimmer
            + 0.030 * profile_shape
            + 0.045 * phase_cooling
            + 0.030 * orbit_closure
            + 0.025 * sheet_quality
            + 0.030 * phase_recovery
            + 0.035 * converter_staging
            + 0.045 * alpha_bootstrap
            + 0.040 * graphene_channels
            + 0.055 * dynamic_volume
            + 0.065 * racetrack
            + 0.040 * racetrack_rephase
            + 0.035 * wall_thickness
            + 0.050 * wall_current
            + 0.18 * alpha_channeling_power
            + 0.22 * alpha_to_proton_power
            + 0.05 * max(0.0, pB11["boron_optical_depth_proxy"] - 3.0)
        )
        pB11_wall_penalty = (
            0.13 * (alpha_thermal + proton_loss_heat)
            + 0.08 * pB11["boron_vapor_radiation_penalty"]
            + 0.10 * max(0.0, li_wall_heat + be_b4c_heat - 6.0)
        )
    bootstrap_power_credit = (
        pB11["pB11_alpha_yield"]
        * alpha_bootstrap
        * alpha_capture_fraction
        * (0.10 + 0.10 * phase_recovery + 0.08 * orbit_closure)
    )
    pB11_gross_power = direct_conversion_power + proton_recovered_power + alpha_channeling_power + alpha_to_proton_power + bootstrap_power_credit
    pB11_power_fraction = pB11_gross_power / max(fusion_dt + pB11_gross_power, 1e-9)
    pB11_net_delta = pB11_gross_power - pB11_dedicated_power - pB11_wall_penalty
    net_power_proxy = fusion_dt + direct_conversion_power + proton_recovered_power + alpha_channeling_power + alpha_to_proton_power + bootstrap_power_credit - rf_power - rf_grating_power - channel_power - beam_power - pB11_support_power - racetrack_drive_power - ash_removal_power - boron_replenishment_power - li_boron_mhd_penalty - coil_power - pump_power - volume_actuator_power - electron_exhaust
    ignition_margin = fusion_dt + 0.75 * direct_conversion_power + 0.50 * proton_recovered_power + 0.65 * alpha_channeling_power + 0.55 * alpha_to_proton_power + 0.50 * bootstrap_power_credit - (rf_power + rf_grating_power + channel_power + beam_power + pB11_support_power + racetrack_drive_power + ash_removal_power + boron_replenishment_power + li_boron_mhd_penalty + coil_power + pump_power + volume_actuator_power + 0.55 * electron_exhaust + 0.18 * brems + 0.12 * event_rate + 0.20 * volume_fatigue)
    pB11_ignitability = 0.0
    if s.pB11_enabled:
        alpha_feedback = 1.0 + 0.35 * pB11["dt_alpha_assist_fraction"] + 0.20 * alpha_capture_fraction
        forcing_cost = (
            1.0
            + 0.7 * pB11["proton_loss_fraction"]
            + 0.12 * max(0.0, elec_T - 12.0)
            + 0.10 * (li_wall_heat + be_b4c_heat)
            + 0.18 * pB11_support_power
            + 0.16 * pB11["boron_vapor_radiation_penalty"]
            + 0.12 * alpha_thermalization_fraction
            + 0.04 * math.log10(max(1.0, pB11["effective_proton_path_length_passes"]))
        )
        pB11_ignitability = (
            pB11["proton_window_fraction"]
            * (1.0 - math.exp(-pB11["boron_optical_depth_proxy"]))
            * pB11["proton_energy_retention_norm"]
            * alpha_feedback
            / max(forcing_cost, 1e-9)
        )

    return Metrics(
        core_ion_temperature_keV=round(ion_T, 3),
        core_electron_temperature_keV=round(elec_T, 3),
        ti_te_ratio=round(ti_te, 3),
        density_norm=round(density, 3),
        beta_proxy=round(beta, 3),
        betaN_proxy=round(betaN, 3),
        confinement_time_proxy=round(confinement, 3),
        reconnection_tearing_elm_event_rate=round(event_rate, 3),
        current_sheet_thickness_metric=round(current_sheet, 3),
        shear_profile=round(shear_profile, 3),
        spin_organization_factor=round(spin_organization, 3),
        vortex_channel_stability=round(ctrl["stability"], 3),
        electron_exhaust_power=round(electron_exhaust, 3),
        bremsstrahlung_proxy=round(brems, 3),
        alpha_extraction_fraction=round(alpha_capture_fraction, 3),
        direct_conversion_power=round(direct_conversion_power, 3),
        pB11_alpha_yield=round(pB11["pB11_alpha_yield"], 3),
        pB11_ignitability_proxy=round(pB11_ignitability, 5),
        pB11_net_delta=round(pB11_net_delta, 3),
        pB11_gross_power=round(pB11_gross_power, 3),
        pB11_power_fraction=round(pB11_power_fraction, 4),
        proton_recovered_power=round(proton_recovered_power, 3),
        boron_vapor_radiation_penalty=round(pB11["boron_vapor_radiation_penalty"], 3),
        cavity_q_effective=round(pB11["cavity_q_effective"], 3),
        surface_pB11_boost=round(pB11["surface_pB11_boost"], 3),
        li_boron_mhd_penalty=round(li_boron_mhd_penalty, 3),
        boron_replenishment_power=round(boron_replenishment_power, 3),
        alpha_channeling_power=round(alpha_channeling_power, 3),
        alpha_to_li_heat=round(alpha_to_li_heat, 3),
        grazing_path_effective=round(pB11["grazing_path_effective"], 3),
        alpha_to_proton_power=round(alpha_to_proton_power, 3),
        direct_converter_gain=round(direct_converter_gain, 3),
        adaptive_skimmer_gain=round(adaptive_skimmer_gain, 3),
        pb11_support_recirc_power=round(pb11_support_recirc_power, 3),
        pb11_support_areal_power=round(pb11_support_areal_power, 3),
        pb11_support_driver_power=round(pb11_support_driver_power, 3),
        pb11_support_control_power=round(pb11_support_control_power, 3),
        proton_burnup_fraction=round(pB11["proton_burnup_fraction"], 5),
        effective_proton_path_length_passes=round(pB11["effective_proton_path_length_passes"], 3),
        hardware_recirc_passes=round(pB11["hardware_recirc_passes"], 3),
        proton_energy_retention_norm=round(pB11["proton_energy_retention_norm"], 3),
        proton_window_fraction=round(pB11["proton_window_fraction"], 3),
        boron_optical_depth_proxy=round(pB11["boron_optical_depth_proxy"], 3),
        proton_loss_fraction=round(pB11["proton_loss_fraction"], 3),
        dt_alpha_assist_fraction=round(pB11["dt_alpha_assist_fraction"], 3),
        dt_alpha_coupling_efficiency=round(pB11["dt_alpha_coupling_efficiency"], 3),
        rf_grating_power=round(rf_grating_power, 3),
        plasma_mirror_duty_effective=round(pm_duty, 3),
        rf_grating_duty_effective=round(rf_grating_duty, 3),
        channel_duty_effective=round((electron_duty + alpha_duty + ash_duty) / 3.0, 3),
        channel_separation_effective=round(channel_separation_effective, 3),
        channel_cross_talk=round(channel_cross_talk, 3),
        electron_exhaust_fraction=round(electron_exhaust_fraction, 3),
        alpha_capture_fraction=round(alpha_capture_fraction, 3),
        alpha_thermalization_fraction=round(alpha_thermalization_fraction, 3),
        helium_ash_fraction=round(helium_ash_fraction, 3),
        ash_removal_power=round(ash_removal_power, 3),
        core_dilution_penalty=round(core_dilution_penalty, 3),
        graphene_heat_spread_factor=round(graphene_heat_spread, 3),
        graphene_channel_power=round(graphene_channel_power, 3),
        volume_compression_factor=round(volume_compression, 3),
        volume_actuator_power=round(volume_actuator_power, 3),
        racetrack_guidance_factor=round(pB11["racetrack_guidance_factor"], 3),
        racetrack_drive_power=round(racetrack_drive_power, 3),
        tbr_proxy=round(blanket["TBR"], 3),
        liquid_lithium_wall_heat_load=round(li_wall_heat, 3),
        be_b4c_wall_heat_deposition=round(be_b4c_heat, 3),
        net_power_proxy=round(net_power_proxy, 3),
        ignition_margin_proxy=round(ignition_margin, 3),
        fusion_dt_power_proxy=round(fusion_dt, 3),
        auxiliary_beam_power=round(beam_power + pB11_support_power + rf_grating_power + channel_power + ash_removal_power + boron_replenishment_power + li_boron_mhd_penalty, 3),
        rf_power_proxy=round(rf_power, 3),
        coil_power_proxy=round(coil_power, 3),
        pump_power_proxy=round(pump_power, 3),
        m3dc1_li_scale=round(m3["li_scale"], 3),
        m3dc1_feedback_scale=round(m3["feedback_scale"], 3),
        m3dc1_eps=round(m3["eps"], 12),
        m3dc1_pedge=round(m3["pedge"], 8),
    )


def case_definitions() -> Dict[str, Scenario]:
    return {
        "A": Scenario(name="A. Conventional tokamak baseline", tct_mode="disabled"),
        "B": Scenario(name="B. Tokamak + TCT only", tct_mode="aggressive", tct_strength="medium"),
        "C": Scenario(name="C. TCT + counter-rotation", tct_mode="aggressive", tct_strength="medium", counter_rotation="medium"),
        "D": Scenario(name="D. TCT + field reversal / reversed shear", tct_mode="aggressive", tct_strength="medium", field_reversal_depth="medium reversed-shear"),
        "E": Scenario(name="E. TCT + vortex electron skimmer", tct_mode="aggressive", tct_strength="medium", plasma_mirror_drive="weak"),
        "F": Scenario(name="F. Full hybrid without plasma mirror", tct_mode="aggressive", tct_strength="strong", field_reversal_depth="medium reversed-shear", counter_rotation="strong", compression_amplitude_pct=5.0, magnetic_ramp_timing="during compression", rf_timing="at peak compression", plasma_mirror_drive="off", liquid_lithium_current="medium"),
        "G": Scenario(name="G. Full hybrid with plasma mirror", tct_mode="aggressive", tct_strength="strong", field_reversal_depth="medium reversed-shear", counter_rotation="strong", compression_amplitude_pct=5.0, magnetic_ramp_timing="during compression", rf_timing="at peak compression", plasma_mirror_drive="medium", liquid_lithium_current="medium"),
        "H": Scenario(name="H. Full hybrid + p-B11 cavity + direct conversion", tct_mode="aggressive", tct_strength="strong", field_reversal_depth="medium reversed-shear", counter_rotation="strong", compression_amplitude_pct=5.0, magnetic_ramp_timing="during compression", rf_timing="at peak compression", plasma_mirror_drive="medium", boron_vapor_density="high", proton_recirculation_quality="100k-pass", liquid_lithium_current="high", alpha_conversion_efficiency=0.7, pB11_enabled=True),
    }


def h_conversion_sweep() -> List[Scenario]:
    base = case_definitions()["H"]
    return [dataclasses.replace(base, alpha_conversion_efficiency=eff, name=f"H @ {int(eff * 100)}% conversion") for eff in (0.30, 0.50, 0.70, 0.85)]


SEARCH_SPACE = {
    "li_current": [0.00, 0.05, 0.10, 0.15, 0.20],
    "tct_mode": ["disabled", "mild", "aggressive"],
    "tct_alpha": [8.0, 9.0, 10.0, 11.0, 12.0],
    "severity_scale": [0.4, 0.5, 0.6, 0.7, 0.8],
    "lithium_thickness_m": [0.001, 0.002, 0.003, 0.005, 0.010],
    "tct_strength": list(STRENGTHS),
    "field_reversal_depth": list(REVERSAL),
    "counter_rotation": list(ROTATION),
    "plasma_spin_organization": list(PLASMA_SPIN_ORGANIZATION),
    "compression_amplitude_pct": [0.0, 1.0, 3.0, 5.0, 10.0],
    "dynamic_volume_compression": list(DYNAMIC_VOLUME_COMPRESSION),
    "volume_compression_timing": list(VOLUME_COMPRESSION_TIMING),
    "volume_compression_duty": [0.10, 0.20, 0.35, 0.50, 0.75],
    "edge_racetrack": list(EDGE_RACETRACK),
    "racetrack_pitch": list(RACETRACK_PITCH),
    "racetrack_wall_clearance": list(RACETRACK_WALL_CLEARANCE),
    "racetrack_energy_rephase": list(RACETRACK_ENERGY_REPHASE),
    "magnetic_ramp_timing": list(RAMP_TIMING),
    "rf_timing": list(RF_TIMING),
    "plasma_mirror_drive": list(PM_DRIVE),
    "boron_vapor_density": list(BORON_DENSITY),
    "proton_recirculation_quality": list(RECIRC),
    "boron_areal_density": [0.5, 1.0, 2.0, 4.0, 7.0, 10.0, 15.0],
    "proton_energy_center_keV": [120.0, 180.0, 250.0, 320.0, 450.0, 600.0],
    "proton_energy_spread_pct": [8.0, 15.0, 25.0, 35.0, 55.0, 80.0],
    "proton_energy_recovery": list(ENERGY_RECOVERY),
    "proton_driver_mode": list(PROTON_DRIVER),
    "pb11_cavity_q": list(CAVITY_Q),
    "boron_vapor_control": list(BORON_VAPOR_CONTROL),
    "li_boron_mix_fraction": list(LI_BORON_MIX),
    "boron_wall_loading": list(BORON_WALL_LOADING),
    "pb11_wall_thickness": list(PB11_WALL_THICKNESS),
    "pb11_wall_current": list(PB11_WALL_CURRENT),
    "boron_wick_efficiency": list(BORON_WICK),
    "alpha_channeling_to_protons": list(ALPHA_CHANNELING),
    "alpha_to_li_capture_fraction": [0.0, 0.20, 0.45, 0.70, 0.90],
    "grazing_path_multiplier": list(GRAZING_PATH),
    "direct_converter_geometry": list(DIRECT_CONVERTER_GEOMETRY),
    "alpha_to_proton_coupling": list(ALPHA_TO_PROTON_COUPLING),
    "adaptive_electron_skimmer": list(ADAPTIVE_SKIMMER),
    "dt_alpha_assist": list(DT_ALPHA_ASSIST),
    "rf_grating": list(RF_GRATING),
    "plasma_mirror_duty": [0.10, 0.20, 0.35, 0.50, 0.75, 1.0],
    "rf_grating_duty": [0.10, 0.20, 0.35, 0.50, 0.75, 1.0],
    "electron_channel": list(CHANNEL_STRENGTH),
    "electron_channel_duty": [0.10, 0.20, 0.35, 0.50, 0.75, 1.0],
    "alpha_channel": list(CHANNEL_STRENGTH),
    "alpha_channel_duty": [0.10, 0.20, 0.35, 0.50, 0.75, 1.0],
    "ash_channel": list(CHANNEL_STRENGTH),
    "ash_channel_duty": [0.10, 0.20, 0.35, 0.50, 0.75, 1.0],
    "channel_separation_quality": [0.35, 0.50, 0.65, 0.80, 0.92],
    "liquid_lithium_current": list(LI_CURRENT),
    "alpha_conversion_efficiency": [0.0, 0.30, 0.50, 0.70, 0.85],
    "dt_seed_fraction": list(DT_SEED_FRACTION),
    "boron_profile_shape": list(BORON_PROFILE_SHAPE),
    "proton_phase_cooling": list(PROTON_PHASE_COOLING),
    "resonant_orbit_closure": list(RESONANT_ORBIT_CLOSURE),
    "boron_sheet_quality": list(BORON_SHEET_QUALITY),
    "proton_phase_recovery": list(PROTON_PHASE_RECOVERY),
    "converter_staging": list(CONVERTER_STAGING),
    "alpha_bootstrap_feedback": list(ALPHA_BOOTSTRAP_FEEDBACK),
    "graphene_heat_channels": list(GRAPHENE_HEAT_CHANNELS),
    "aux_fuel": list(AUX_FUEL_PROFILES),
    "pB11_enabled": [False, True],
}


def scenario_signature(s: Scenario) -> Tuple[object, ...]:
    payload = asdict(s)
    payload.pop("name", None)
    return tuple(payload[k] for k in sorted(payload))


def score_metrics(m: Metrics, objective: str = "balanced") -> float:
    if objective == "outperform":
        score = 0.0
        score += 5.0 * m.net_power_proxy
        score += 2.5 * m.ignition_margin_proxy
        score += 10.0 * m.pB11_net_delta
        score += 8.0 * m.direct_conversion_power
        score += 3.0 * m.pB11_alpha_yield
        score += 25.0 * m.pB11_ignitability_proxy
        score += 80.0 * m.proton_burnup_fraction
        score -= 1.8 * m.reconnection_tearing_elm_event_rate
        score -= 1.2 * m.bremsstrahlung_proxy
        score -= 0.7 * m.electron_exhaust_power
        score -= 0.20 * max(0.0, m.liquid_lithium_wall_heat_load - 3.6) ** 2
        score -= 0.20 * max(0.0, m.be_b4c_wall_heat_deposition - 3.6) ** 2
        score -= 0.0000007 * m.effective_proton_path_length_passes
        score -= 0.9 * max(0.0, math.log10(max(1.0, m.hardware_recirc_passes)) - 5.0) ** 2
        if m.pB11_alpha_yield < 0.05:
            score -= 8.0 * (0.05 - m.pB11_alpha_yield)
        return score

    if objective == "pb11_delta":
        score = 0.0
        score += 120.0 * m.pB11_net_delta
        score += 35.0 * m.direct_conversion_power
        score += 18.0 * m.pB11_alpha_yield
        score += 250.0 * m.proton_burnup_fraction
        score += 25.0 * m.pB11_ignitability_proxy
        score += 1.2 * m.net_power_proxy
        score -= 2.0 * m.proton_loss_fraction
        score -= 1.0 * m.bremsstrahlung_proxy
        score -= 0.25 * max(0.0, m.liquid_lithium_wall_heat_load - 3.3) ** 2
        score -= 0.25 * max(0.0, m.be_b4c_wall_heat_deposition - 3.3) ** 2
        score -= 15.0 * max(0.0, 1.1 - m.tbr_proxy) ** 2
        return score

    if objective == "breakthrough":
        score = 0.0
        score += 80.0 * m.pB11_net_delta
        score += 5.0 * m.net_power_proxy
        score += 3.0 * m.ignition_margin_proxy
        score += 20.0 * m.direct_conversion_power
        score += 15.0 * m.proton_recovered_power
        score += 25.0 * m.alpha_channeling_power
        score += 18.0 * m.alpha_to_proton_power
        score += 120.0 * m.proton_burnup_fraction
        score += 20.0 * m.pB11_ignitability_proxy
        score += 4.0 * m.cavity_q_effective
        score += 3.0 * m.surface_pB11_boost
        score += 2.0 * m.direct_converter_gain
        score += 1.5 * m.adaptive_skimmer_gain
        score -= 1.2 * m.proton_loss_fraction
        score -= 1.0 * m.boron_vapor_radiation_penalty
        score -= 1.5 * m.li_boron_mhd_penalty
        score -= 1.0 * m.boron_replenishment_power
        score -= 0.6 * m.bremsstrahlung_proxy
        score -= 1.3 * max(0.0, math.log10(max(1.0, m.effective_proton_path_length_passes)) - 6.0) ** 2
        score -= 1.0 * max(0.0, math.log10(max(1.0, m.hardware_recirc_passes)) - 5.0) ** 2
        score -= 0.30 * max(0.0, m.liquid_lithium_wall_heat_load - 3.3) ** 2
        score -= 0.30 * max(0.0, m.be_b4c_wall_heat_deposition - 3.3) ** 2
        score -= 18.0 * max(0.0, 1.1 - m.tbr_proxy) ** 2
        return score

    if objective == "ignite_breakthrough":
        score = 0.0
        score += 115.0 * m.pB11_ignitability_proxy
        score += 55.0 * m.pB11_net_delta
        score += 7.0 * m.ignition_margin_proxy
        score += 3.5 * m.net_power_proxy
        score += 90.0 * m.proton_burnup_fraction
        score += 12.0 * m.pB11_alpha_yield
        score += 10.0 * m.direct_conversion_power
        score += 12.0 * m.alpha_channeling_power
        score += 10.0 * m.alpha_to_proton_power
        score += 4.0 * m.proton_energy_retention_norm
        score += 4.0 * m.proton_window_fraction
        score += 2.5 * m.cavity_q_effective
        score -= 45.0 * max(0.0, -m.pB11_net_delta) ** 2
        score -= 2.0 * m.proton_loss_fraction
        score -= 1.4 * m.bremsstrahlung_proxy
        score -= 1.2 * m.boron_vapor_radiation_penalty
        score -= 1.5 * m.li_boron_mhd_penalty
        score -= 1.2 * m.boron_replenishment_power
        score -= 1.0 * max(0.0, math.log10(max(1.0, m.effective_proton_path_length_passes)) - 6.0) ** 2
        score -= 1.0 * max(0.0, math.log10(max(1.0, m.hardware_recirc_passes)) - 5.0) ** 2
        score -= 0.35 * max(0.0, m.liquid_lithium_wall_heat_load - 3.25) ** 2
        score -= 0.35 * max(0.0, m.be_b4c_wall_heat_deposition - 3.25) ** 2
        score -= 20.0 * max(0.0, 1.1 - m.tbr_proxy) ** 2
        return score

    if objective == "pb11_primary":
        score = 0.0
        score += 250.0 * m.pB11_power_fraction
        score += 95.0 * m.pB11_net_delta
        score += 140.0 * m.proton_burnup_fraction
        score += 55.0 * m.pB11_ignitability_proxy
        score += 35.0 * m.pB11_gross_power
        score += 14.0 * m.direct_conversion_power
        score += 10.0 * m.alpha_channeling_power
        score += 8.0 * m.alpha_to_proton_power
        score += 1.6 * m.net_power_proxy
        score += 1.0 * m.ignition_margin_proxy
        score -= 2.5 * m.proton_loss_fraction
        score -= 2.0 * m.boron_vapor_radiation_penalty
        score -= 2.0 * m.li_boron_mhd_penalty
        score -= 1.5 * m.boron_replenishment_power
        score -= 1.3 * m.bremsstrahlung_proxy
        score -= 1.0 * max(0.0, math.log10(max(1.0, m.effective_proton_path_length_passes)) - 6.0) ** 2
        score -= 1.0 * max(0.0, math.log10(max(1.0, m.hardware_recirc_passes)) - 5.0) ** 2
        score -= 0.65 * max(0.0, m.fusion_dt_power_proxy - 8.0) ** 2
        score -= 80.0 * max(0.0, 0.20 - m.pB11_power_fraction) ** 2
        score -= 65.0 * max(0.0, -m.pB11_net_delta) ** 2
        score -= 0.35 * max(0.0, m.liquid_lithium_wall_heat_load - 3.35) ** 2
        score -= 0.35 * max(0.0, m.be_b4c_wall_heat_deposition - 3.35) ** 2
        return score

    if objective in ("pb11_20", "pb11_25", "pb11_25_net", "pb11_30", "pb11_40", "pb11_50"):
        target = {"pb11_20": 0.20, "pb11_25": 0.25, "pb11_25_net": 0.25, "pb11_30": 0.30, "pb11_40": 0.40, "pb11_50": 0.50}[objective]
        net_weight = 5.0 if objective == "pb11_25_net" else 2.0
        margin_weight = 1.8 if objective == "pb11_25_net" else 1.2
        score = 0.0
        score += 220.0 * (1.0 - min(1.0, abs(m.pB11_power_fraction - target) / target))
        score += 90.0 * m.pB11_net_delta
        score += 80.0 * m.proton_burnup_fraction
        score += 50.0 * m.pB11_ignitability_proxy
        score += 30.0 * m.pB11_gross_power
        score += net_weight * m.net_power_proxy
        score += margin_weight * m.ignition_margin_proxy
        score -= 55.0 * max(0.0, -m.pB11_net_delta) ** 2
        score -= 45.0 * max(0.0, -m.net_power_proxy) ** 2
        score -= 2.0 * m.proton_loss_fraction
        score -= 1.7 * m.boron_vapor_radiation_penalty
        score -= 1.5 * m.bremsstrahlung_proxy
        score -= 0.8 * max(0.0, math.log10(max(1.0, m.effective_proton_path_length_passes)) - 6.0) ** 2
        score -= 0.8 * max(0.0, math.log10(max(1.0, m.hardware_recirc_passes)) - 5.0) ** 2
        score -= 0.35 * max(0.0, m.liquid_lithium_wall_heat_load - 3.35) ** 2
        score -= 0.35 * max(0.0, m.be_b4c_wall_heat_deposition - 3.35) ** 2
        return score

    if objective == "ignitability":
        score = 0.0
        score += 80.0 * m.pB11_ignitability_proxy
        score += 180.0 * m.proton_burnup_fraction
        score += 12.0 * m.pB11_alpha_yield
        score += 3.0 * m.direct_conversion_power
        score += 0.35 * m.net_power_proxy
        score += 0.35 * m.ignition_margin_proxy
        score -= 1.2 * m.proton_loss_fraction
        score -= 0.9 * m.reconnection_tearing_elm_event_rate
        score -= 0.9 * m.bremsstrahlung_proxy
        score -= 0.18 * max(0.0, m.core_electron_temperature_keV - 14.0) ** 2
        score -= 0.22 * max(0.0, m.liquid_lithium_wall_heat_load - 3.5) ** 2
        score -= 0.22 * max(0.0, m.be_b4c_wall_heat_deposition - 3.5) ** 2
        score -= 0.0000015 * m.effective_proton_path_length_passes
        return score

    if objective == "burnup":
        score = 0.0
        score += 900.0 * m.proton_burnup_fraction
        score += 30.0 * m.pB11_alpha_yield
        score += 8.0 * m.direct_conversion_power
        score += 1.5 * m.proton_energy_retention_norm
        score += 2.0 * m.proton_window_fraction
        score += 0.7 * m.boron_optical_depth_proxy
        score += 0.9 * math.log10(max(1.0, m.effective_proton_path_length_passes))
        score -= 1.0 * max(0.0, math.log10(max(1.0, m.effective_proton_path_length_passes)) - 6.0) ** 2
        score += 0.4 * m.net_power_proxy
        score -= 1.0 * m.reconnection_tearing_elm_event_rate
        score -= 0.8 * m.bremsstrahlung_proxy
        score -= 1.5 * m.proton_loss_fraction
        score -= 0.15 * m.electron_exhaust_power
        score -= 0.06 * max(0.0, m.core_electron_temperature_keV - 18.0) ** 2
        score -= 0.20 * max(0.0, m.liquid_lithium_wall_heat_load - 4.0) ** 2
        score -= 0.20 * max(0.0, m.be_b4c_wall_heat_deposition - 4.0) ** 2
        return score

    if objective == "yield":
        score = 0.0
        score += 40.0 * m.pB11_alpha_yield
        score += 12.0 * m.direct_conversion_power
        score += 450.0 * m.proton_burnup_fraction
        score += 0.8 * m.proton_energy_retention_norm
        score += 1.0 * m.proton_window_fraction
        score -= 0.8 * m.proton_loss_fraction
        score += 0.6 * m.net_power_proxy
        score -= 0.8 * m.reconnection_tearing_elm_event_rate
        score -= 0.6 * m.bremsstrahlung_proxy
        score -= 0.2 * m.electron_exhaust_power
        return score

    score = 0.0
    score += 2.0 * m.net_power_proxy
    score += 1.5 * m.ignition_margin_proxy
    score += 1.2 * m.ti_te_ratio
    score += 1.0 * m.confinement_time_proxy
    score += 2.0 * m.direct_conversion_power
    score += 1.0 * m.pB11_alpha_yield
    score -= 3.0 * m.reconnection_tearing_elm_event_rate
    score -= 1.4 * m.bremsstrahlung_proxy
    score -= 0.35 * m.electron_exhaust_power
    score -= 0.10 * max(0.0, m.core_electron_temperature_keV - 18.0) ** 2
    score -= 2.5 * max(0.0, m.betaN_proxy - 2.5) ** 2
    score -= 0.35 * max(0.0, m.liquid_lithium_wall_heat_load - 4.0) ** 2
    score -= 0.35 * max(0.0, m.be_b4c_wall_heat_deposition - 4.0) ** 2
    if m.proton_burnup_fraction > 0.05:
        score -= 10.0 * (m.proton_burnup_fraction - 0.05)
    if m.vortex_channel_stability < 0.25:
        score -= 4.0 * (0.25 - m.vortex_channel_stability)
    return score


def normalize_scenario(s: Scenario, name: str | None = None) -> Scenario:
    updates = {}
    if s.pB11_enabled:
        if s.proton_recirculation_quality == "single-pass":
            updates["proton_recirculation_quality"] = "100-pass"
        if s.alpha_conversion_efficiency == 0.0:
            updates["alpha_conversion_efficiency"] = 0.50
    else:
        updates["alpha_conversion_efficiency"] = 0.0
    if s.tct_strength == "none":
        updates["tct_mode"] = "disabled"
        updates["tct_alpha"] = 8.0
    elif s.tct_mode == "disabled":
        updates["tct_mode"] = "mild"
    if name is not None:
        updates["name"] = name
    return dataclasses.replace(s, **updates) if updates else s


def random_scenario(rng: random.Random, name: str) -> Scenario:
    payload = {field: rng.choice(values) for field, values in SEARCH_SPACE.items()}
    return normalize_scenario(Scenario(name=name, **payload))


def crossover(a: Scenario, b: Scenario, rng: random.Random, name: str) -> Scenario:
    payload = {}
    for field in SEARCH_SPACE:
        payload[field] = getattr(a, field) if rng.random() < 0.5 else getattr(b, field)
    return normalize_scenario(Scenario(name=name, **payload))


def mutate(s: Scenario, rng: random.Random, name: str, mutation_rate: float = 0.22) -> Scenario:
    payload = asdict(s)
    payload["name"] = name
    changed = False
    for field, values in SEARCH_SPACE.items():
        if rng.random() < mutation_rate:
            payload[field] = rng.choice(values)
            changed = True
    if not changed:
        field = rng.choice(list(SEARCH_SPACE))
        payload[field] = rng.choice(SEARCH_SPACE[field])
    return normalize_scenario(Scenario(**payload))


def passes_constraints(
    m: Metrics,
    *,
    min_net: float | None = None,
    min_tbr: float | None = None,
    max_li_wall: float | None = None,
    max_be_b4c_wall: float | None = None,
    min_pb11_net_delta: float | None = None,
    min_pb11_burnup: float | None = None,
    min_aux_fraction: float | None = None,
) -> bool:
    if min_net is not None and m.net_power_proxy < min_net:
        return False
    if min_tbr is not None and m.tbr_proxy < min_tbr:
        return False
    if max_li_wall is not None and m.liquid_lithium_wall_heat_load > max_li_wall:
        return False
    if max_be_b4c_wall is not None and m.be_b4c_wall_heat_deposition > max_be_b4c_wall:
        return False
    if min_pb11_net_delta is not None and m.pB11_net_delta < min_pb11_net_delta:
        return False
    if min_pb11_burnup is not None and m.proton_burnup_fraction < min_pb11_burnup:
        return False
    if min_aux_fraction is not None and m.pB11_power_fraction < min_aux_fraction:
        return False
    return True


def optimize_scenarios(
    population_size: int,
    generations: int,
    elite_keep: int,
    seed: int,
    require_pb11: bool = False,
    objective: str = "balanced",
    constraints: Dict[str, float | None] | None = None,
    aux_fuel_filter: str | None = None,
    graphene_filter: str | None = None,
    spin_filter: str | None = None,
    dt_seed_filter: str | None = None,
    edge_racetrack_filter: str | None = None,
) -> List[OptimizationResult]:
    rng = random.Random(seed)
    seeds = [normalize_scenario(s, name=f"seed_{key}_{s.name}") for key, s in case_definitions().items()]
    if aux_fuel_filter is not None:
        seeds = [dataclasses.replace(s, aux_fuel=aux_fuel_filter) for s in seeds]
    if graphene_filter is not None:
        seeds = [dataclasses.replace(s, graphene_heat_channels=graphene_filter) for s in seeds]
    if spin_filter is not None:
        seeds = [dataclasses.replace(s, plasma_spin_organization=spin_filter) for s in seeds]
    if dt_seed_filter is not None:
        seeds = [dataclasses.replace(s, dt_seed_fraction=dt_seed_filter) for s in seeds]
    if edge_racetrack_filter is not None:
        seeds = [dataclasses.replace(s, edge_racetrack=edge_racetrack_filter) for s in seeds]
    population = seeds[:]
    seen = {scenario_signature(s) for s in population}
    while len(population) < population_size:
        candidate = random_scenario(rng, f"random_0_{len(population)}")
        sig = scenario_signature(candidate)
        if sig not in seen:
            seen.add(sig)
            population.append(candidate)

    archive: Dict[Tuple[object, ...], OptimizationResult] = {}
    elite_keep = max(1, min(elite_keep, population_size))

    for gen in range(generations):
        evaluated = []
        for scenario in population:
            metrics = simulate(scenario)
            score = score_metrics(metrics, objective=objective)
            result = OptimizationResult(0, round(score, 6), gen, scenario, metrics)
            evaluated.append(result)
            sig = scenario_signature(scenario)
            if sig not in archive or result.score > archive[sig].score:
                archive[sig] = result

        evaluated.sort(key=lambda item: item.score, reverse=True)
        elites = evaluated[:elite_keep]
        next_population = [item.scenario for item in elites]
        next_seen = {scenario_signature(s) for s in next_population}

        attempts = 0
        while len(next_population) < population_size and attempts < population_size * 30:
            attempts += 1
            if len(elites) >= 2 and rng.random() < 0.65:
                parent_a, parent_b = rng.sample(elites, 2)
                child = crossover(parent_a.scenario, parent_b.scenario, rng, f"gen_{gen + 1}_{len(next_population)}")
            else:
                parent = rng.choice(elites).scenario
                child = mutate(parent, rng, f"gen_{gen + 1}_{len(next_population)}")
            if rng.random() < 0.75:
                child = mutate(child, rng, child.name, mutation_rate=0.12)
            sig = scenario_signature(child)
            if sig not in next_seen:
                next_seen.add(sig)
                next_population.append(child)

        while len(next_population) < population_size:
            child = random_scenario(rng, f"random_{gen + 1}_{len(next_population)}")
            sig = scenario_signature(child)
            if sig not in next_seen:
                next_seen.add(sig)
                next_population.append(child)

        population = next_population

    ranked = sorted(archive.values(), key=lambda item: item.score, reverse=True)
    if require_pb11:
        ranked = [
            item for item in ranked
            if item.scenario.pB11_enabled and item.metrics.pB11_alpha_yield > 0.0
        ]
    if constraints:
        ranked = [
            item for item in ranked
            if passes_constraints(item.metrics, **constraints)
        ]
    if aux_fuel_filter is not None:
        ranked = [
            item for item in ranked
            if item.scenario.aux_fuel == aux_fuel_filter
        ]
    if graphene_filter is not None:
        ranked = [
            item for item in ranked
            if item.scenario.graphene_heat_channels == graphene_filter
        ]
    if spin_filter is not None:
        ranked = [
            item for item in ranked
            if item.scenario.plasma_spin_organization == spin_filter
        ]
    if dt_seed_filter is not None:
        ranked = [
            item for item in ranked
            if item.scenario.dt_seed_fraction == dt_seed_filter
        ]
    if edge_racetrack_filter is not None:
        ranked = [
            item for item in ranked
            if item.scenario.edge_racetrack == edge_racetrack_filter
        ]
    return [
        dataclasses.replace(item, rank=i + 1)
        for i, item in enumerate(ranked)
    ]


def optimization_table(results: List[OptimizationResult], limit: int) -> str:
    rows = []
    for result in results[:limit]:
        row = {
            "rank": result.rank,
            "score": round(result.score, 3),
            "gen": result.generation,
            "name": result.scenario.name,
            "fuel": result.scenario.aux_fuel,
            "net": result.metrics.net_power_proxy,
            "ign": result.metrics.ignition_margin_proxy,
            "Ti/Te": result.metrics.ti_te_ratio,
            "event": result.metrics.reconnection_tearing_elm_event_rate,
            "brems": result.metrics.bremsstrahlung_proxy,
            "pB11": result.metrics.pB11_alpha_yield,
            "pBign": result.metrics.pB11_ignitability_proxy,
            "pBnet": result.metrics.pB11_net_delta,
            "pBgross": result.metrics.pB11_gross_power,
            "pBfrac": result.metrics.pB11_power_fraction,
            "DT": result.metrics.fusion_dt_power_proxy,
            "precov": result.metrics.proton_recovered_power,
            "achpow": result.metrics.alpha_channeling_power,
            "a2p": result.metrics.alpha_to_proton_power,
            "surf": result.metrics.surface_pB11_boost,
            "graze": result.metrics.grazing_path_effective,
            "dcgain": result.metrics.direct_converter_gain,
            "skim": result.metrics.adaptive_skimmer_gain,
            "supR": result.metrics.pb11_support_recirc_power,
            "supA": result.metrics.pb11_support_areal_power,
            "supD": result.metrics.pb11_support_driver_power,
            "supC": result.metrics.pb11_support_control_power,
            "LiBpen": result.metrics.li_boron_mhd_penalty,
            "Bfeed": result.metrics.boron_replenishment_power,
            "cavQ": result.metrics.cavity_q_effective,
            "Brad": result.metrics.boron_vapor_radiation_penalty,
            "burn": result.metrics.proton_burnup_fraction,
            "hwrecirc": result.metrics.hardware_recirc_passes,
            "ret": result.metrics.proton_energy_retention_norm,
            "win": result.metrics.proton_window_fraction,
            "loss": result.metrics.proton_loss_fraction,
            "od": result.metrics.boron_optical_depth_proxy,
            "conv": result.metrics.direct_conversion_power,
            "sep": result.metrics.channel_separation_effective,
            "xtalk": result.metrics.channel_cross_talk,
            "ash": result.metrics.helium_ash_fraction,
            "gspread": result.metrics.graphene_heat_spread_factor,
            "gpower": result.metrics.graphene_channel_power,
            "vcomp": result.metrics.volume_compression_factor,
            "vpower": result.metrics.volume_actuator_power,
            "rtrack": result.metrics.racetrack_guidance_factor,
            "rpower": result.metrics.racetrack_drive_power,
            "spinorg": result.metrics.spin_organization_factor,
            "tct": result.scenario.tct_strength,
            "rot": result.scenario.counter_rotation,
            "spin": result.scenario.plasma_spin_organization,
            "rev": result.scenario.field_reversal_depth,
            "pm": result.scenario.plasma_mirror_drive,
            "pmduty": result.scenario.plasma_mirror_duty,
            "vol": result.scenario.dynamic_volume_compression,
            "voltime": result.scenario.volume_compression_timing,
            "volduty": result.scenario.volume_compression_duty,
            "etrack": result.scenario.edge_racetrack,
            "rpitch": result.scenario.racetrack_pitch,
            "rclear": result.scenario.racetrack_wall_clearance,
            "rephase": result.scenario.racetrack_energy_rephase,
            "recirc": result.scenario.proton_recirculation_quality,
            "areal": result.scenario.boron_areal_density,
            "E": result.scenario.proton_energy_center_keV,
            "spread": result.scenario.proton_energy_spread_pct,
            "recover": result.scenario.proton_energy_recovery,
            "driver": result.scenario.proton_driver_mode,
            "cavity": result.scenario.pb11_cavity_q,
            "vapor": result.scenario.boron_vapor_control,
            "LiB": result.scenario.li_boron_mix_fraction,
            "Bwall": result.scenario.boron_wall_loading,
            "Bthick": result.scenario.pb11_wall_thickness,
            "Bcurr": result.scenario.pb11_wall_current,
            "wick": result.scenario.boron_wick_efficiency,
            "achannel": result.scenario.alpha_channeling_to_protons,
            "LiAlpha": result.scenario.alpha_to_li_capture_fraction,
            "graze_set": result.scenario.grazing_path_multiplier,
            "dcgeo": result.scenario.direct_converter_geometry,
            "a2p_set": result.scenario.alpha_to_proton_coupling,
            "eskim": result.scenario.adaptive_electron_skimmer,
            "assist": result.scenario.dt_alpha_assist,
            "couple": result.metrics.dt_alpha_coupling_efficiency,
            "TBR": result.metrics.tbr_proxy,
            "LiHeat": result.metrics.liquid_lithium_wall_heat_load,
            "BeHeat": result.metrics.be_b4c_wall_heat_deposition,
            "rfgrid": result.scenario.rf_grating,
            "rgduty": result.scenario.rf_grating_duty,
            "ech": result.scenario.electron_channel,
            "eduty": result.scenario.electron_channel_duty,
            "ach": result.scenario.alpha_channel,
            "aduty": result.scenario.alpha_channel_duty,
            "ashch": result.scenario.ash_channel,
            "ashduty": result.scenario.ash_channel_duty,
            "dtseed": result.scenario.dt_seed_fraction,
            "bshape": result.scenario.boron_profile_shape,
            "pcool": result.scenario.proton_phase_cooling,
            "orbit": result.scenario.resonant_orbit_closure,
            "sheetq": result.scenario.boron_sheet_quality,
            "precover": result.scenario.proton_phase_recovery,
            "stage": result.scenario.converter_staging,
            "aboot": result.scenario.alpha_bootstrap_feedback,
            "graphene": result.scenario.graphene_heat_channels,
        }
        rows.append(row)

    headers = ["rank", "score", "gen", "name", "fuel", "net", "ign", "Ti/Te", "event", "brems", "pB11", "pBign", "pBnet", "pBgross", "pBfrac", "DT", "precov", "achpow", "a2p", "surf", "graze", "dcgain", "skim", "supR", "supA", "supD", "supC", "LiBpen", "Bfeed", "cavQ", "Brad", "burn", "hwrecirc", "ret", "win", "loss", "od", "conv", "sep", "xtalk", "ash", "gspread", "gpower", "vcomp", "vpower", "rtrack", "rpower", "spinorg", "tct", "rot", "spin", "rev", "pm", "pmduty", "vol", "voltime", "volduty", "etrack", "rpitch", "rclear", "rephase", "recirc", "areal", "E", "spread", "recover", "driver", "cavity", "vapor", "LiB", "Bwall", "Bthick", "Bcurr", "wick", "achannel", "LiAlpha", "graze_set", "dcgeo", "a2p_set", "eskim", "assist", "couple", "TBR", "LiHeat", "BeHeat", "rfgrid", "rgduty", "ech", "eduty", "ach", "aduty", "ashch", "ashduty", "dtseed", "bshape", "pcool", "orbit", "sheetq", "precover", "stage", "aboot", "graphene"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row[h])))
    lines = [" | ".join(h.ljust(widths[h]) for h in headers)]
    lines.append("-+-".join("-" * widths[h] for h in headers))
    for row in rows:
        lines.append(" | ".join(str(row[h]).ljust(widths[h]) for h in headers))
    return "\n".join(lines)


def optimization_json(results: List[OptimizationResult], limit: int) -> str:
    payload = []
    for result in results[:limit]:
        payload.append({
            "rank": result.rank,
            "score": result.score,
            "generation": result.generation,
            "scenario": asdict(result.scenario),
            "metrics": asdict(result.metrics),
        })
    return json.dumps(payload, indent=2, sort_keys=True)


def format_table(rows: List[Tuple[str, Metrics]], fields: List[str]) -> str:
    def cell_text(value: object) -> str:
        if value is None:
            return ""
        return str(value)

    headers = ["case"] + fields
    data = []
    for name, m in rows:
        row = [name] + [getattr(m, f) for f in fields]
        data.append(row)
    widths = [len(str(h)) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell_text(cell)))
    out = [" | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))]
    out.append("-+-".join("-" * w for w in widths))
    for row in data:
        out.append(" | ".join(cell_text(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(out)


def summarize(case_metrics: Dict[str, Metrics], log_metrics_by_case: Dict[str, Dict[str, float | None]] | None = None) -> str:
    fields = [
        "core_ion_temperature_keV",
        "core_electron_temperature_keV",
        "ti_te_ratio",
        "confinement_time_proxy",
        "reconnection_tearing_elm_event_rate",
        "bremsstrahlung_proxy",
        "pB11_alpha_yield",
        "direct_conversion_power",
        "pB11_net_delta",
        "tbr_proxy",
        "liquid_lithium_wall_heat_load",
        "be_b4c_wall_heat_deposition",
        "net_power_proxy",
        "ignition_margin_proxy",
    ]
    base = format_table([(k, case_metrics[k]) for k in case_metrics], fields)

    if not log_metrics_by_case:
        return base

    extra_fields = [
        "total_energy",
        "total_energy_lost",
        "toroidal_current",
        "toroidal_flux",
        "total_radiation",
        "bremsstrahlung_radiation",
        "ionization_loss",
        "te_max",
    ]

    class RowProxy:
        def __init__(self, name: str, base_metrics: Metrics, log_metrics: Dict[str, float | None] | None):
            self.name = name
            self.base_metrics = base_metrics
            self.log_metrics = log_metrics or {}

        def __getattr__(self, item: str) -> object:
            if hasattr(self.base_metrics, item):
                return getattr(self.base_metrics, item)
            return self.log_metrics.get(item)

    rows = [(k, RowProxy(k, case_metrics[k], log_metrics_by_case.get(k))) for k in case_metrics]
    extra_table = format_table(rows, fields + extra_fields)
    return extra_table


def print_bridge_notes(case_metrics: Dict[str, Metrics], log_metrics_by_case: Dict[str, Dict[str, float | None]] | None = None) -> None:
    print("Bridge notes")
    print("M3DC1 controls mapped to:", "li_current/current.dat scale, tct_alpha/tct_mode feedback scale, severity_scale/eps, lithium_thickness_m/pedge")
    print("TCT model mapped from:", "plasma_model.py, tct_control.py, lithium_wall.py, power_balance.py, engineering_limits.py, materials_db.py")
    tct_parts = {
        "plasma": TCT_EVALUATE_CASE is not None,
        "controller": TCT_RUN_CONTROLLER is not None,
        "lithium_wall": TCT_LITHIUM_WALL_TEMPERATURE is not None,
    }
    print("TCT engine import:", f"{'enabled' if TCT_ENGINE_AVAILABLE else 'surrogate fallback'} {tct_parts} ({TCT_REPO_ROOT})")
    print()
    print(summarize(case_metrics, log_metrics_by_case=log_metrics_by_case))


def print_h_sweep() -> None:
    rows = [(s.name, simulate(s)) for s in h_conversion_sweep()]
    print()
    print("H conversion-efficiency sweep")
    print(format_table(rows, ["alpha_extraction_fraction", "pB11_alpha_yield", "direct_conversion_power", "pB11_net_delta", "proton_burnup_fraction", "tbr_proxy", "net_power_proxy", "ignition_margin_proxy"]))


def print_focus_sweep(reference: Scenario) -> None:
    axes = [
        ("TCT strength", ["none", "weak", "medium", "strong", "aggressive"]),
        ("Field reversal", ["none", "shallow reversed-shear", "medium reversed-shear", "strong local reversal"]),
        ("Counter-rotation", ["none", "weak", "medium", "strong"]),
        ("Compression", [0.0, 1.0, 3.0, 5.0, 10.0]),
        ("Plasma mirror", ["off", "weak", "medium", "strong"]),
        ("Boron density", ["low", "medium", "high", "extreme"]),
    ]
    print()
    print("One-way sensitivity sweeps around the full hybrid reference")
    for axis, values in axes:
        rows = []
        for value in values:
            kwargs = dataclasses.asdict(reference)
            if axis == "TCT strength":
                kwargs["tct_strength"] = value
            elif axis == "Field reversal":
                kwargs["field_reversal_depth"] = value
            elif axis == "Counter-rotation":
                kwargs["counter_rotation"] = value
            elif axis == "Compression":
                kwargs["compression_amplitude_pct"] = float(value)
            elif axis == "Plasma mirror":
                kwargs["plasma_mirror_drive"] = value
            elif axis == "Boron density":
                kwargs["boron_vapor_density"] = value
                kwargs["pB11_enabled"] = True
            rows.append((str(value), simulate(Scenario(**kwargs))))
        print()
        print(axis)
        print(format_table(rows, ["core_ion_temperature_keV", "core_electron_temperature_keV", "ti_te_ratio", "reconnection_tearing_elm_event_rate", "bremsstrahlung_proxy", "net_power_proxy", "ignition_margin_proxy"]))


def breakthrough_reference_scenario() -> Scenario:
    """Best constrained p-B11 breakthrough candidate found by the surrogate search."""
    return Scenario(
        name="Breakthrough reference: DT-TCT + edge p-B11",
        li_current=0.10,
        tct_mode="mild",
        tct_alpha=11.0,
        severity_scale=0.5,
        lithium_thickness_m=0.005,
        tct_strength="aggressive",
        field_reversal_depth="strong local reversal",
        counter_rotation="strong",
        compression_amplitude_pct=10.0,
        magnetic_ramp_timing="during compression",
        rf_timing="off",
        plasma_mirror_drive="strong",
        boron_vapor_density="extreme",
        proton_recirculation_quality="100k-pass",
        boron_areal_density=7.0,
        proton_energy_center_keV=180.0,
        proton_energy_spread_pct=8.0,
        proton_energy_recovery="aggressive",
        proton_driver_mode="autoresonant",
        pb11_cavity_q="high-Q",
        boron_vapor_control="magnetized",
        li_boron_mix_fraction="medium",
        boron_wall_loading="heavy",
        boron_wick_efficiency="capillary",
        alpha_channeling_to_protons="strong",
        alpha_to_li_capture_fraction=0.20,
        grazing_path_multiplier="strong",
        direct_converter_geometry="divertor-integrated",
        alpha_to_proton_coupling="weak",
        adaptive_electron_skimmer="off",
        dt_alpha_assist="strong",
        rf_grating="adaptive",
        plasma_mirror_duty=0.20,
        rf_grating_duty=0.10,
        electron_channel="off",
        electron_channel_duty=0.50,
        alpha_channel="strong",
        alpha_channel_duty=0.10,
        ash_channel="off",
        ash_channel_duty=1.0,
        channel_separation_quality=0.92,
        liquid_lithium_current="0",
        alpha_conversion_efficiency=0.85,
        pB11_enabled=True,
    )


def robustness_status(m: Metrics) -> str:
    checks = [
        m.pB11_net_delta >= 0.0,
        m.net_power_proxy >= 8.8,
        m.tbr_proxy >= 1.1,
        m.liquid_lithium_wall_heat_load <= 3.35,
        m.be_b4c_wall_heat_deposition <= 3.35,
        m.proton_burnup_fraction >= 0.005,
    ]
    return "pass" if all(checks) else "fail"


def outperform_reference_scenario() -> Scenario:
    return Scenario(
        name="Best full-DT auxiliary hybrid reference",
        tct_mode="aggressive",
        tct_strength="aggressive",
        field_reversal_depth="strong local reversal",
        counter_rotation="strong",
        plasma_spin_organization="phase-locked",
        compression_amplitude_pct=10.0,
        magnetic_ramp_timing="during compression",
        rf_timing="at peak compression",
        plasma_mirror_drive="strong",
        plasma_mirror_duty=1.0,
        dynamic_volume_compression="deep",
        volume_compression_timing="peak-burn",
        volume_compression_duty=0.35,
        edge_racetrack="off",
        racetrack_pitch="steep",
        racetrack_wall_clearance="nominal",
        racetrack_energy_rephase="off",
        boron_vapor_density="extreme",
        proton_recirculation_quality="100k-pass",
        boron_areal_density=10.0,
        proton_energy_center_keV=120.0,
        proton_energy_spread_pct=8.0,
        proton_energy_recovery="aggressive",
        proton_driver_mode="autoresonant",
        pb11_cavity_q="high-Q",
        boron_vapor_control="magnetized",
        li_boron_mix_fraction="rich",
        boron_wall_loading="heavy",
        pb11_wall_thickness="graded-bulk",
        pb11_wall_current="high",
        boron_wick_efficiency="capillary",
        alpha_channeling_to_protons="medium",
        alpha_to_li_capture_fraction=0.90,
        grazing_path_multiplier="none",
        direct_converter_geometry="divertor-integrated",
        alpha_to_proton_coupling="weak",
        adaptive_electron_skimmer="off",
        dt_alpha_assist="strong",
        rf_grating="adaptive",
        rf_grating_duty=0.10,
        electron_channel="off",
        electron_channel_duty=0.35,
        alpha_channel="strong",
        alpha_channel_duty=0.10,
        ash_channel="off",
        ash_channel_duty=0.50,
        channel_separation_quality=0.92,
        liquid_lithium_current="high",
        alpha_conversion_efficiency=0.85,
        dt_seed_fraction="full",
        boron_profile_shape="pulsed-sheet",
        proton_phase_cooling="magnetic-collimation",
        resonant_orbit_closure="strong",
        boron_sheet_quality="phase-locked",
        proton_phase_recovery="strong",
        converter_staging="adaptive",
        alpha_bootstrap_feedback="strong",
        graphene_heat_channels="aligned",
        aux_fuel="D-He3+D-Li6+pB11-wall",
        pB11_enabled=True,
    )


def stress_status(m: Metrics) -> str:
    checks = [
        m.net_power_proxy >= 8.639,
        m.ignition_margin_proxy >= 9.024,
        m.pB11_net_delta >= 0.0,
        m.pB11_power_fraction >= 0.18,
        m.tbr_proxy >= 1.1,
        m.liquid_lithium_wall_heat_load <= 4.8,
        m.be_b4c_wall_heat_deposition <= 4.8,
    ]
    return "pass" if all(checks) else "fail"


def print_outperform_uncertainty(reference: Scenario | None = None) -> None:
    base = reference or outperform_reference_scenario()
    fields = [
        "net_power_proxy",
        "ignition_margin_proxy",
        "pB11_net_delta",
        "pB11_gross_power",
        "pB11_power_fraction",
        "pB11_alpha_yield",
        "proton_burnup_fraction",
        "proton_energy_retention_norm",
        "proton_loss_fraction",
        "effective_proton_path_length_passes",
        "hardware_recirc_passes",
        "pb11_support_recirc_power",
        "racetrack_guidance_factor",
        "tbr_proxy",
        "liquid_lithium_wall_heat_load",
        "be_b4c_wall_heat_deposition",
    ]
    cases = [
        ("reference", {}),
        ("mirror medium", {"plasma_mirror_drive": "medium", "plasma_mirror_duty": 0.50}),
        ("mirror off", {"plasma_mirror_drive": "off"}),
        ("cavity resonant", {"pb11_cavity_q": "resonant"}),
        ("cavity guided", {"pb11_cavity_q": "guided"}),
        ("spread 15pct", {"proton_energy_spread_pct": 15.0}),
        ("spread 25pct", {"proton_energy_spread_pct": 25.0}),
        ("recirc 10k", {"proton_recirculation_quality": "10k-pass"}),
        ("recirc 1k", {"proton_recirculation_quality": "1k-pass"}),
        ("wall current medium", {"pb11_wall_current": "medium"}),
        ("wick structured", {"boron_wick_efficiency": "structured"}),
        ("wick shallow", {"boron_wick_efficiency": "shallow"}),
        ("alpha weak", {"alpha_channeling_to_protons": "weak", "alpha_channel": "weak"}),
        ("alpha off", {"alpha_channeling_to_protons": "off", "alpha_channel": "off", "alpha_to_proton_coupling": "off"}),
        ("graphene micro", {"graphene_heat_channels": "microchannel"}),
        ("graphene off", {"graphene_heat_channels": "off"}),
        ("resonant racetrack", {"edge_racetrack": "resonant", "racetrack_energy_rephase": "weak", "graphene_heat_channels": "microchannel"}),
        ("conservative stack", {
            "plasma_mirror_drive": "medium",
            "plasma_mirror_duty": 0.50,
            "pb11_cavity_q": "resonant",
            "proton_energy_spread_pct": 15.0,
            "boron_wick_efficiency": "structured",
            "alpha_channeling_to_protons": "weak",
            "alpha_channel": "weak",
            "alpha_to_proton_coupling": "off",
            "pb11_wall_current": "medium",
            "graphene_heat_channels": "microchannel",
        }),
        ("hard fail stack", {
            "plasma_mirror_drive": "weak",
            "pb11_cavity_q": "guided",
            "proton_energy_spread_pct": 25.0,
            "proton_recirculation_quality": "10k-pass",
            "boron_wick_efficiency": "shallow",
            "alpha_channeling_to_protons": "off",
            "alpha_channel": "off",
            "alpha_to_proton_coupling": "off",
            "pb11_wall_current": "medium",
            "graphene_heat_channels": "off",
        }),
    ]
    rows = []
    statuses = []
    for label, changes in cases:
        metrics = simulate(dataclasses.replace(base, name=label, **changes))
        rows.append((label, metrics))
        statuses.append((label, stress_status(metrics)))
    print()
    print("Outperform candidate uncertainty/stress matrix")
    print(format_table(rows, fields))
    print()
    print("Stress pass/fail")
    for label, status in statuses:
        print(f"{label}: {status}")


def print_penalty_sweep(reference: Scenario | None = None) -> None:
    base = reference or outperform_reference_scenario()
    base_m = simulate(base)
    rows = []
    configs = [
        ("nominal", 1.00, 1.00, 1.00),
        ("mild output loss", 0.85, 1.00, 1.00),
        ("medium output loss", 0.70, 1.00, 1.00),
        ("hard output loss", 0.50, 1.00, 1.00),
        ("support +25%", 1.00, 1.25, 1.00),
        ("support +50%", 1.00, 1.50, 1.00),
        ("support x2", 1.00, 2.00, 1.00),
        ("wall heat +25%", 1.00, 1.00, 1.25),
        ("wall heat +50%", 1.00, 1.00, 1.50),
        ("credible conservative", 0.85, 1.25, 1.15),
        ("severe conservative", 0.70, 1.50, 1.25),
        ("break case", 0.50, 2.00, 1.50),
    ]
    support_power = (
        base_m.pb11_support_recirc_power
        + base_m.pb11_support_areal_power
        + base_m.pb11_support_driver_power
        + base_m.pb11_support_control_power
        + base_m.racetrack_drive_power
        + base_m.boron_replenishment_power
        + base_m.li_boron_mhd_penalty
    )
    for label, output_scale, support_scale, wall_scale in configs:
        gross_loss = base_m.pB11_gross_power * (1.0 - output_scale)
        extra_support = support_power * (support_scale - 1.0)
        li_heat = base_m.liquid_lithium_wall_heat_load * wall_scale + 0.10 * gross_loss
        be_heat = base_m.be_b4c_wall_heat_deposition * wall_scale + 0.08 * gross_loss
        wall_penalty = 0.10 * max(0.0, li_heat + be_heat - 6.0)
        pbgross = base_m.pB11_gross_power * output_scale
        net = base_m.net_power_proxy - gross_loss - extra_support - wall_penalty
        ign = base_m.ignition_margin_proxy - 0.75 * gross_loss - 0.75 * extra_support - 0.5 * wall_penalty
        pbnet = base_m.pB11_net_delta - gross_loss - extra_support - wall_penalty
        pbfrac = pbgross / max(base_m.fusion_dt_power_proxy + pbgross, 1e-9)
        status = "pass" if (
            net >= 8.639
            and ign >= 9.024
            and pbnet >= 0.0
            and pbfrac >= 0.18
            and li_heat <= 4.8
            and be_heat <= 4.8
            and base_m.tbr_proxy >= 1.1
        ) else "fail"
        rows.append({
            "case": label,
            "out": output_scale,
            "support": support_scale,
            "wall": wall_scale,
            "net": round(net, 3),
            "ign": round(ign, 3),
            "pBnet": round(pbnet, 3),
            "pBgross": round(pbgross, 3),
            "pBfrac": round(pbfrac, 4),
            "LiHeat": round(li_heat, 3),
            "BeHeat": round(be_heat, 3),
            "status": status,
        })
    headers = ["case", "out", "support", "wall", "net", "ign", "pBnet", "pBgross", "pBfrac", "LiHeat", "BeHeat", "status"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row[h])))
    print()
    print("Outperform candidate pB11 penalty sweep")
    print(" | ".join(h.ljust(widths[h]) for h in headers))
    print("-+-".join("-" * widths[h] for h in headers))
    for row in rows:
        print(" | ".join(str(row[h]).ljust(widths[h]) for h in headers))


def print_breakthrough_robustness(reference: Scenario | None = None) -> None:
    base = reference or breakthrough_reference_scenario()
    base_m = simulate(base)
    fields = [
        "net_power_proxy",
        "pB11_net_delta",
        "proton_burnup_fraction",
        "pB11_alpha_yield",
        "alpha_channeling_power",
        "alpha_to_proton_power",
        "grazing_path_effective",
        "cavity_q_effective",
        "boron_vapor_radiation_penalty",
        "tbr_proxy",
        "liquid_lithium_wall_heat_load",
        "be_b4c_wall_heat_deposition",
    ]

    print()
    print("Breakthrough p-B11 robustness reference")
    print(format_table([("reference", base_m)], fields + ["ignition_margin_proxy"]))
    print(f"constraint_status={robustness_status(base_m)}")

    axes = [
        ("grazing_path_multiplier", ["extreme", "strong", "medium", "weak", "none"]),
        ("pb11_cavity_q", ["high-Q", "resonant", "guided", "open"]),
        ("alpha_to_proton_coupling", ["medium", "weak", "off"]),
        ("alpha_channeling_to_protons", ["strong", "medium", "weak", "off"]),
        ("li_boron_mix_fraction", ["rich", "medium", "low", "trace", "none"]),
        ("boron_wall_loading", ["heavy", "moderate", "thin", "none"]),
        ("boron_wick_efficiency", ["capillary", "structured", "shallow", "off"]),
        ("proton_recirculation_quality", ["10M-pass", "1M-pass", "100k-pass", "10k-pass", "1k-pass", "100-pass"]),
        ("boron_areal_density", [15.0, 10.0, 7.0, 4.0, 2.0, 1.0]),
        ("proton_energy_center_keV", [120.0, 180.0, 250.0, 320.0, 450.0, 600.0]),
        ("proton_energy_spread_pct", [8.0, 15.0, 25.0, 35.0, 55.0, 80.0]),
        ("plasma_mirror_duty", [0.10, 0.20, 0.35, 0.50, 0.75, 1.0]),
        ("dt_alpha_assist", ["strong", "medium", "weak", "off"]),
    ]
    for field, values in axes:
        rows = []
        for value in values:
            scenario = dataclasses.replace(base, name=f"{field}={value}", **{field: value})
            metrics = simulate(scenario)
            rows.append((str(value), metrics))
        print()
        print(f"Robustness axis: {field}")
        print(format_table(rows, fields + ["ignition_margin_proxy"]))
        passing = [str(value) for value, metrics in rows if robustness_status(metrics) == "pass"]
        print(f"passing_values={', '.join(passing) if passing else 'none'}")

    ablations = [
        ("no grazing", {"grazing_path_multiplier": "none"}),
        ("no high-Q cavity", {"pb11_cavity_q": "open"}),
        ("no alpha channeling", {"alpha_channeling_to_protons": "off"}),
        ("no alpha-to-proton", {"alpha_to_proton_coupling": "off"}),
        ("no Li-B mix", {"li_boron_mix_fraction": "none"}),
        ("no boron wall", {"boron_wall_loading": "none"}),
        ("no wick", {"boron_wick_efficiency": "off"}),
        ("no DT alpha assist", {"dt_alpha_assist": "off"}),
        ("no plasma mirror", {"plasma_mirror_drive": "off"}),
        ("all pB11 support off", {
            "grazing_path_multiplier": "none",
            "pb11_cavity_q": "open",
            "alpha_channeling_to_protons": "off",
            "alpha_to_proton_coupling": "off",
            "li_boron_mix_fraction": "none",
            "boron_wall_loading": "none",
            "boron_wick_efficiency": "off",
            "dt_alpha_assist": "off",
        }),
    ]
    rows = [("reference", base_m)]
    for label, changes in ablations:
        rows.append((label, simulate(dataclasses.replace(base, name=label, **changes))))
    print()
    print("Ablation scorecard")
    print(format_table(rows, fields + ["ignition_margin_proxy"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of tables")
    parser.add_argument("--no-sweeps", action="store_true", help="Skip the one-way sensitivity sweeps")
    parser.add_argument("--optimize", action="store_true", help="Run an optimizer seeded by the A-H cases")
    parser.add_argument("--population", type=int, default=48, help="Optimizer population size")
    parser.add_argument("--generations", type=int, default=10, help="Optimizer generation count")
    parser.add_argument("--elite-keep", type=int, default=12, help="Number of elite candidates retained per generation")
    parser.add_argument("--seed", type=int, default=11, help="Optimizer random seed")
    parser.add_argument("--top", type=int, default=10, help="Number of optimizer results to print")
    parser.add_argument("--require-pb11", action="store_true", help="Only rank candidates with an active p-B11 cavity and nonzero p-B11 yield")
    parser.add_argument("--aux-fuel", choices=["any"] + list(AUX_FUEL_PROFILES), default="any", help="Restrict the auxiliary edge-fuel candidate")
    parser.add_argument("--graphene", choices=["any"] + list(GRAPHENE_HEAT_CHANNELS), default="any", help="Restrict graphene-backed behind-wall heat channels")
    parser.add_argument("--spin", choices=["any"] + list(PLASMA_SPIN_ORGANIZATION), default="any", help="Restrict organized plasma spin mode")
    parser.add_argument("--dt-seed", choices=["any"] + list(DT_SEED_FRACTION), default="any", help="Restrict DT seed fraction")
    parser.add_argument("--edge-racetrack", choices=["any"] + list(EDGE_RACETRACK), default="any", help="Restrict guided edge-racetrack recirculation replacement")
    parser.add_argument("--objective", choices=["balanced", "burnup", "yield", "ignitability", "ignite_breakthrough", "pb11_primary", "pb11_20", "pb11_25", "pb11_25_net", "pb11_30", "pb11_40", "pb11_50", "outperform", "pb11_delta", "breakthrough"], default="balanced", help="Optimizer objective")
    parser.add_argument("--min-net", type=float, default=None, help="Filter optimizer results below this net power proxy")
    parser.add_argument("--min-tbr", type=float, default=None, help="Filter optimizer results below this TBR proxy")
    parser.add_argument("--max-li-wall", type=float, default=None, help="Filter optimizer results above this liquid-lithium wall heat proxy")
    parser.add_argument("--max-be-b4c-wall", type=float, default=None, help="Filter optimizer results above this Be/B4C wall heat proxy")
    parser.add_argument("--min-pb11-net-delta", type=float, default=None, help="Filter optimizer results below this p-B11 marginal net delta")
    parser.add_argument("--min-pb11-burnup", type=float, default=None, help="Filter optimizer results below this p-B11 burnup fraction")
    parser.add_argument("--min-aux-fraction", type=float, default=None, help="Filter optimizer results below this auxiliary-fuel gross power fraction")
    parser.add_argument("--robustness", action="store_true", help="Run targeted robustness sweeps around the best p-B11 breakthrough candidate")
    parser.add_argument("--uncertainty", action="store_true", help="Run stress tests around the best full-DT auxiliary outperform candidate")
    parser.add_argument("--penalty-sweep", action="store_true", help="Apply conservative p-B11 output, support-cost, and wall-heat penalties to the outperform candidate")
    parser.add_argument("--run-real-m3dc1", action="store_true", help="Prepare the M3DC1 case directory and run the local solver for one scenario")
    parser.add_argument("--export-best-m3dc1", action="store_true", help="Export the best full-DT auxiliary hybrid as an M3DC1/TCT handoff case without running it")
    parser.add_argument("--export-dir", default=str(ROOT / "m3dc1_case_runs" / "pb11_best_handoff"), help="Output directory for --export-best-m3dc1")
    parser.add_argument("--case", default="H", choices=sorted(case_definitions().keys()), help="Scenario key to use with --run-real-m3dc1")
    parser.add_argument("--keep-logs", action="store_true", help="Keep the copied M3DC1 run directory")
    parser.add_argument("--quick-init", action="store_true", help="Zero the initial perturbation amplitude when preparing the M3DC1 deck")
    args = parser.parse_args()

    cases = case_definitions()

    if args.robustness:
        print_breakthrough_robustness()
        return

    if args.uncertainty:
        print_outperform_uncertainty()
        return

    if args.penalty_sweep:
        print_penalty_sweep()
        return

    if args.export_best_m3dc1:
        result = export_m3dc1_case(outperform_reference_scenario(), Path(args.export_dir), quick_init=args.quick_init)
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if args.run_real_m3dc1:
        result = run_m3dc1_case(cases[args.case], keep_logs=args.keep_logs, quick_init=args.quick_init)
        metrics = {k: simulate(v) for k, v in cases.items()}
        log_metrics_by_case = {args.case: result.get("log_metrics", {})}
        print_bridge_notes(metrics, log_metrics_by_case=log_metrics_by_case)
        print()
        print("Real M3DC1 run summary")
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if args.optimize:
        aux_fuel_filter = None if args.aux_fuel == "any" else args.aux_fuel
        graphene_filter = None if args.graphene == "any" else args.graphene
        spin_filter = None if args.spin == "any" else args.spin
        dt_seed_filter = None if args.dt_seed == "any" else args.dt_seed
        edge_racetrack_filter = None if args.edge_racetrack == "any" else args.edge_racetrack
        if aux_fuel_filter is not None:
            SEARCH_SPACE["aux_fuel"] = [aux_fuel_filter]
        if graphene_filter is not None:
            SEARCH_SPACE["graphene_heat_channels"] = [graphene_filter]
        if spin_filter is not None:
            SEARCH_SPACE["plasma_spin_organization"] = [spin_filter]
        if dt_seed_filter is not None:
            SEARCH_SPACE["dt_seed_fraction"] = [dt_seed_filter]
        if edge_racetrack_filter is not None:
            SEARCH_SPACE["edge_racetrack"] = [edge_racetrack_filter]
        results = optimize_scenarios(
            population_size=max(8, args.population),
            generations=max(1, args.generations),
            elite_keep=max(1, args.elite_keep),
            seed=args.seed,
            require_pb11=args.require_pb11,
            objective=args.objective,
            aux_fuel_filter=aux_fuel_filter,
            graphene_filter=graphene_filter,
            spin_filter=spin_filter,
            dt_seed_filter=dt_seed_filter,
            edge_racetrack_filter=edge_racetrack_filter,
            constraints={
                "min_net": args.min_net,
                "min_tbr": args.min_tbr,
                "max_li_wall": args.max_li_wall,
                "max_be_b4c_wall": args.max_be_b4c_wall,
                "min_pb11_net_delta": args.min_pb11_net_delta,
                "min_pb11_burnup": args.min_pb11_burnup,
                "min_aux_fraction": args.min_aux_fraction,
            },
        )
        if args.json:
            print(optimization_json(results, args.top))
            return
        print("Optimizer search")
        print(f"seed={args.seed} population={max(8, args.population)} generations={max(1, args.generations)} elite_keep={max(1, args.elite_keep)} require_pb11={args.require_pb11} objective={args.objective} aux_fuel={args.aux_fuel} graphene={args.graphene} spin={args.spin} dt_seed={args.dt_seed}")
        active_constraints = {
            "min_net": args.min_net,
            "min_tbr": args.min_tbr,
            "max_li_wall": args.max_li_wall,
            "max_be_b4c_wall": args.max_be_b4c_wall,
            "min_pb11_net_delta": args.min_pb11_net_delta,
            "min_pb11_burnup": args.min_pb11_burnup,
            "min_aux_fraction": args.min_aux_fraction,
        }
        active_constraints = {k: v for k, v in active_constraints.items() if v is not None}
        if active_constraints:
            print(f"constraints={active_constraints}")
        print()
        print(optimization_table(results, args.top))
        return

    metrics = {k: simulate(v) for k, v in cases.items()}

    if args.json:
        print(json.dumps({k: asdict(v) for k, v in metrics.items()}, indent=2, sort_keys=True))
        return

    print_bridge_notes(metrics)
    print_h_sweep()
    if not args.no_sweeps:
        print_focus_sweep(cases["F"])


if __name__ == "__main__":
    main()

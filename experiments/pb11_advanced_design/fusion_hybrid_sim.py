#!/usr/bin/env python3
"""Parametric hybrid tokamak / p-B11 concept simulator.

This is a deliberately simplified control-oriented model. It compares a
conventional tokamak baseline against stacked control layers and a speculative
beam-driven plasma-mirror boundary primitive. The outputs are proxy metrics,
not engineering predictions.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
from dataclasses import dataclass, asdict
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


@dataclass(frozen=True)
class Scenario:
    name: str
    tct_strength: str = "none"
    field_reversal_depth: str = "none"
    counter_rotation: str = "none"
    compression_amplitude_pct: float = 0.0
    magnetic_ramp_timing: str = "before compression"
    rf_timing: str = "off"
    plasma_mirror_drive: str = "off"
    boron_vapor_density: str = "low"
    proton_recirculation_quality: str = "single-pass"
    liquid_lithium_current: str = "0"
    alpha_conversion_efficiency: float = 0.0
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
    vortex_channel_stability: float
    electron_exhaust_power: float
    bremsstrahlung_proxy: float
    alpha_extraction_fraction: float
    direct_conversion_power: float
    pB11_alpha_yield: float
    proton_burnup_fraction: float
    effective_proton_path_length_passes: float
    proton_energy_retention_norm: float
    liquid_lithium_wall_heat_load: float
    be_b4c_wall_heat_deposition: float
    net_power_proxy: float
    ignition_margin_proxy: float
    fusion_dt_power_proxy: float
    auxiliary_beam_power: float
    rf_power_proxy: float
    coil_power_proxy: float
    pump_power_proxy: float


STRENGTHS = {
    "none": 0.0,
    "weak": 0.25,
    "medium": 0.55,
    "strong": 0.85,
    "aggressive": 1.0,
}

REVERSAL = {
    "none": 0.0,
    "shallow reversed-shear": 0.22,
    "medium reversed-shear": 0.48,
    "strong local reversal": 0.78,
}

ROTATION = {
    "none": 0.0,
    "weak": 0.2,
    "medium": 0.5,
    "strong": 0.8,
}

RAMP_TIMING = {
    "before compression": 0.15,
    "during compression": 0.45,
    "after compression": -0.05,
}

RF_TIMING = {
    "off": 0.0,
    "before compression": 0.18,
    "at peak compression": 0.5,
    "after compression": -0.1,
}

PM_DRIVE = {
    "off": 0.0,
    "weak": 0.25,
    "medium": 0.55,
    "strong": 0.9,
}

BORON_DENSITY = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.78,
    "extreme": 1.0,
}

RECIRC = {
    "single-pass": 1.0,
    "10-pass": 10.0,
    "100-pass": 100.0,
    "1k-pass": 1000.0,
    "10k-pass": 10000.0,
    "100k-pass": 100000.0,
}

LI_CURRENT = {
    "0": 0.0,
    "low": 0.2,
    "medium": 0.55,
    "high": 0.9,
}


def scenario_factor(mapping: Dict[str, float], key: str) -> float:
    if key not in mapping:
        raise KeyError(f"Unknown setting {key!r}; known values: {sorted(mapping)}")
    return mapping[key]


def rf_to_ion_fraction(timing: str, compression: float, mirror: float) -> float:
    timing_gain = RF_TIMING[timing]
    return clamp((0.12 + 0.35 * compression + 0.2 * mirror) * timing_gain, 0.0, 0.85)


def mirror_stability(mirror: float, reversal: float, rotation: float, compression: float) -> float:
    if mirror <= 0.0:
        return 0.0
    coherence = 0.65 + 0.25 * reversal + 0.15 * rotation + 0.1 * compression
    penalty = 0.2 * max(0.0, mirror - 0.55) + 0.18 * max(0.0, compression - 0.05)
    return clamp(mirror * coherence - penalty, 0.0, 1.0)


def simulate(s: Scenario) -> Metrics:
    tct = scenario_factor(STRENGTHS, s.tct_strength)
    reversal = scenario_factor(REVERSAL, s.field_reversal_depth)
    rotation = scenario_factor(ROTATION, s.counter_rotation)
    compression = s.compression_amplitude_pct / 100.0
    ramp = scenario_factor(RAMP_TIMING, s.magnetic_ramp_timing)
    rf_timing = scenario_factor(RF_TIMING, s.rf_timing)
    pm = scenario_factor(PM_DRIVE, s.plasma_mirror_drive)
    boron = scenario_factor(BORON_DENSITY, s.boron_vapor_density)
    recirc = scenario_factor(RECIRC, s.proton_recirculation_quality)
    li = scenario_factor(LI_CURRENT, s.liquid_lithium_current)

    stability = mirror_stability(pm, reversal, rotation, compression)

    # Confinement and event suppression respond to stacked controls, but
    # excessive reversal and mirror drive add instability penalties.
    conf = (
        1.0
        + 0.30 * tct
        + 0.16 * rotation
        + 0.14 * reversal
        + 0.09 * compression
        + 0.06 * ramp
        + 0.05 * rf_timing
        + 0.08 * stability
        - 0.18 * max(0.0, reversal - 0.55)
        - 0.10 * max(0.0, pm - 0.7)
        - 0.06 * compression * max(0.0, pm - 0.4)
    )
    confinement_time_proxy = max(0.2, conf)

    event_rate = clamp(
        1.05
        - 0.30 * tct
        - 0.12 * rotation
        - 0.16 * reversal
        - 0.10 * compression
        - 0.06 * ramp
        - 0.08 * rf_timing
        - 0.12 * stability
        + 0.22 * max(0.0, reversal - 0.55)
        + 0.18 * max(0.0, pm - 0.7),
        0.02,
        1.8,
    )

    # Shear and sheet control.
    shear_profile = clamp(0.15 + 0.55 * rotation + 0.35 * reversal + 0.12 * compression, 0.0, 1.6)
    current_sheet_thickness_metric = clamp(
        1.0 - 0.22 * tct - 0.08 * rotation - 0.10 * reversal - 0.05 * compression + 0.10 * event_rate,
        0.25,
        1.5,
    )

    # Temperatures are proxy outputs in keV.
    core_ion_temperature_keV = max(
        2.0,
        11.0
        + 7.5 * tct
        + 3.8 * rotation
        + 3.2 * reversal
        + 3.5 * compression
        + 1.8 * ramp
        + 2.0 * rf_timing
        + 1.4 * stability,
    )

    electron_heating = (
        1.8
        + 1.1 * tct
        + 1.2 * rf_timing
        + 0.8 * compression
        + 0.7 * pm
        + 0.4 * stability
        + 0.8 * max(0.0, reversal - 0.55)
    )
    electron_cooling = (
        0.9 * tct
        + 1.5 * stability
        + 1.4 * pm
        + 0.5 * compression
        + 0.25 * rotation
    )
    core_electron_temperature_keV = max(1.5, 9.0 + electron_heating - electron_cooling)

    # RF energy is coupled mostly to ions near compression peaks, with a smaller
    # fraction to electrons.
    ion_rf_fraction = rf_to_ion_fraction(s.rf_timing, compression, pm)
    rf_power_proxy = 0.9 * rf_timing * (1.0 + 1.2 * compression + 0.4 * pm)
    auxiliary_beam_power = 0.6 * pm * (1.0 + 0.2 * compression)

    electron_exhaust_power = (
        0.25 * pm * (1.0 + 0.7 * stability + 0.4 * compression)
        + 0.15 * max(0.0, core_electron_temperature_keV - 8.5)
    )
    bremsstrahlung_proxy = max(
        0.08,
        (core_electron_temperature_keV / max(core_ion_temperature_keV, 1e-6))
        * (1.0 + 0.3 * event_rate)
        * (1.0 - 0.15 * clamp(pm, 0.0, 1.0)),
    )

    # Density proxy rises modestly with compression and stable reversal.
    density_norm = max(0.25, 1.0 + 0.10 * compression + 0.04 * rotation + 0.03 * reversal + 0.05 * tct)

    beta_proxy = clamp(0.38 + 0.06 * core_ion_temperature_keV / 10.0 + 0.05 * density_norm - 0.05 * event_rate, 0.0, 2.5)
    betaN_proxy = beta_proxy * (1.0 + 0.3 * confinement_time_proxy)

    # Fusion DT power proxy uses a soft threshold on ion temperature and
    # benefits from confinement, density, and compression.
    burn_factor = sigmoid((core_ion_temperature_keV - 8.5) / 2.5)
    fusion_dt_power_proxy = (
        6.0
        * density_norm
        * burn_factor
        * (1.0 + 0.55 * confinement_time_proxy)
        * (1.0 + 0.12 * compression)
        * (1.0 + 0.05 * ion_rf_fraction)
        * (1.0 - 0.14 * event_rate)
    )
    fusion_dt_power_proxy = max(0.0, fusion_dt_power_proxy)

    # p-B11 cavity behavior is only enabled in the divertor/edge region.
    # The divertor cavity is fed by a recirculating proton stream, so use a
    # dedicated proton-energy proxy instead of the thermal core temperature.
    proton_energy_keV = (
        140.0
        + 3.2 * core_ion_temperature_keV
        + 40.0 * compression
        + 18.0 * rf_timing
        + 12.0 * clamp(pm, 0.0, 1.0)
        + 9.0 * reversal
    )
    pB11_window_match = gaussian(proton_energy_keV, 260.0, 105.0)
    proton_energy_retention_norm = clamp(
        0.55
        + 0.15 * rotation
        + 0.12 * reversal
        + 0.10 * clamp(pm, 0.0, 1.0)
        + 0.08 * compression
        - 0.10 * electron_exhaust_power
        - 0.10 * event_rate,
        0.0,
        1.0,
    )
    effective_proton_path_length_passes = recirc * (
        0.7 + 0.22 * confinement_time_proxy + 0.12 * clamp(pm, 0.0, 1.0)
    )
    proton_burnup_fraction = 0.0
    pB11_alpha_yield = 0.0
    if s.pB11_enabled:
        # The burnup fraction is intentionally conservative and saturates hard.
        cavity_factor = 0.42 + 0.40 * boron + 0.15 * clamp(pm, 0.0, 1.0) + 0.10 * reversal
        path_factor = math.log10(max(2.0, effective_proton_path_length_passes)) / 6.0
        proton_burnup_fraction = clamp(
            0.020 * cavity_factor * path_factor * pB11_window_match * (0.4 + 0.6 * proton_energy_retention_norm),
            0.0,
            0.35,
        )
        pB11_alpha_yield = 0.0
        if proton_burnup_fraction > 0.0:
            # Normalize to "fusion power proxy" style units, not Joules.
            pB11_alpha_yield = (
                proton_burnup_fraction
                * (1.0 + 0.3 * boron)
                * (1.0 + 0.2 * clamp(pm, 0.0, 1.0))
                * (1.0 + 0.1 * clamp(s.alpha_conversion_efficiency, 0.0, 1.0))
                * 4.5
            )

    alpha_extraction_fraction = clamp(
        0.05
        + 0.22 * stability
        + 0.18 * reversal
        + 0.15 * clamp(pm, 0.0, 1.0)
        + 0.12 * compression
        + 0.20 * clamp(s.alpha_conversion_efficiency, 0.0, 1.0),
        0.0,
        0.98,
    )
    direct_conversion_power = pB11_alpha_yield * clamp(s.alpha_conversion_efficiency, 0.0, 1.0) * alpha_extraction_fraction

    # Wall heat is distributed between a liquid lithium shaping/heat sink layer
    # and the final Be/B4C attenuation surfaces.
    failed_beam_heat = auxiliary_beam_power * (1.0 - 0.45 * stability)
    xray_and_stray_heat = 0.18 * core_electron_temperature_keV * (1.0 + 0.25 * event_rate)
    alpha_thermalization = pB11_alpha_yield * (1.0 - alpha_extraction_fraction) * 0.55
    neutron_proxy_heat = 0.45 * fusion_dt_power_proxy

    liquid_lithium_wall_heat_load = (
        0.42 * neutron_proxy_heat
        + 0.50 * failed_beam_heat
        + 0.25 * xray_and_stray_heat
        + 0.20 * alpha_thermalization
        - 0.12 * li
    )
    be_b4c_wall_heat_deposition = (
        0.28 * neutron_proxy_heat
        + 0.45 * xray_and_stray_heat
        + 0.40 * alpha_thermalization
        + 0.12 * event_rate
        - 0.08 * li
    )

    # Coils and pumps rise with control complexity.
    coil_power_proxy = 0.35 * tct + 0.25 * reversal + 0.22 * rotation + 0.18 * compression + 0.28 * pm
    pump_power_proxy = 0.10 + 0.10 * li + 0.05 * compression + 0.04 * pm

    # Ignition margin proxy is a normalized balance of gain against internal loads.
    load_penalty = 0.55 * electron_exhaust_power + 0.18 * bremsstrahlung_proxy + 0.12 * event_rate
    ignition_margin_proxy = fusion_dt_power_proxy + 0.75 * direct_conversion_power - (
        rf_power_proxy + auxiliary_beam_power + coil_power_proxy + pump_power_proxy + load_penalty
    )

    net_power_proxy = (
        fusion_dt_power_proxy
        + direct_conversion_power
        - rf_power_proxy
        - auxiliary_beam_power
        - coil_power_proxy
        - pump_power_proxy
        - electron_exhaust_power
    )

    ti_te_ratio = core_ion_temperature_keV / max(core_electron_temperature_keV, 1e-6)

    return Metrics(
        core_ion_temperature_keV=round(core_ion_temperature_keV, 3),
        core_electron_temperature_keV=round(core_electron_temperature_keV, 3),
        ti_te_ratio=round(ti_te_ratio, 3),
        density_norm=round(density_norm, 3),
        beta_proxy=round(beta_proxy, 3),
        betaN_proxy=round(betaN_proxy, 3),
        confinement_time_proxy=round(confinement_time_proxy, 3),
        reconnection_tearing_elm_event_rate=round(event_rate, 3),
        current_sheet_thickness_metric=round(current_sheet_thickness_metric, 3),
        shear_profile=round(shear_profile, 3),
        vortex_channel_stability=round(stability, 3),
        electron_exhaust_power=round(electron_exhaust_power, 3),
        bremsstrahlung_proxy=round(bremsstrahlung_proxy, 3),
        alpha_extraction_fraction=round(alpha_extraction_fraction, 3),
        direct_conversion_power=round(direct_conversion_power, 3),
        pB11_alpha_yield=round(pB11_alpha_yield, 3),
        proton_burnup_fraction=round(proton_burnup_fraction, 5),
        effective_proton_path_length_passes=round(effective_proton_path_length_passes, 3),
        proton_energy_retention_norm=round(proton_energy_retention_norm, 3),
        liquid_lithium_wall_heat_load=round(liquid_lithium_wall_heat_load, 3),
        be_b4c_wall_heat_deposition=round(be_b4c_wall_heat_deposition, 3),
        net_power_proxy=round(net_power_proxy, 3),
        ignition_margin_proxy=round(ignition_margin_proxy, 3),
        fusion_dt_power_proxy=round(fusion_dt_power_proxy, 3),
        auxiliary_beam_power=round(auxiliary_beam_power, 3),
        rf_power_proxy=round(rf_power_proxy, 3),
        coil_power_proxy=round(coil_power_proxy, 3),
        pump_power_proxy=round(pump_power_proxy, 3),
    )


def case_definitions() -> Dict[str, Scenario]:
    return {
        "A": Scenario(
            name="A. Conventional tokamak baseline",
        ),
        "B": Scenario(
            name="B. Tokamak + TCT only",
            tct_strength="medium",
        ),
        "C": Scenario(
            name="C. TCT + counter-rotation",
            tct_strength="medium",
            counter_rotation="medium",
        ),
        "D": Scenario(
            name="D. TCT + field reversal / reversed shear",
            tct_strength="medium",
            field_reversal_depth="medium reversed-shear",
        ),
        "E": Scenario(
            name="E. TCT + vortex electron skimmer",
            tct_strength="medium",
            plasma_mirror_drive="weak",
        ),
        "F": Scenario(
            name="F. Full hybrid without plasma mirror",
            tct_strength="strong",
            field_reversal_depth="medium reversed-shear",
            counter_rotation="strong",
            compression_amplitude_pct=5.0,
            magnetic_ramp_timing="during compression",
            rf_timing="at peak compression",
            plasma_mirror_drive="off",
            liquid_lithium_current="medium",
            alpha_conversion_efficiency=0.0,
        ),
        "G": Scenario(
            name="G. Full hybrid with plasma mirror",
            tct_strength="strong",
            field_reversal_depth="medium reversed-shear",
            counter_rotation="strong",
            compression_amplitude_pct=5.0,
            magnetic_ramp_timing="during compression",
            rf_timing="at peak compression",
            plasma_mirror_drive="medium",
            liquid_lithium_current="medium",
            alpha_conversion_efficiency=0.0,
        ),
        "H": Scenario(
            name="H. Full hybrid + p-B11 cavity + direct conversion",
            tct_strength="strong",
            field_reversal_depth="medium reversed-shear",
            counter_rotation="strong",
            compression_amplitude_pct=5.0,
            magnetic_ramp_timing="during compression",
            rf_timing="at peak compression",
            plasma_mirror_drive="medium",
            boron_vapor_density="high",
            proton_recirculation_quality="100k-pass",
            liquid_lithium_current="high",
            alpha_conversion_efficiency=0.7,
            pB11_enabled=True,
        ),
    }


def efficiency_sweep_case_h() -> List[Scenario]:
    base = case_definitions()["H"]
    out = []
    for eff in (0.30, 0.50, 0.70, 0.85):
        out.append(dataclasses.replace(base, alpha_conversion_efficiency=eff, name=f"H @ {int(eff * 100)}% conversion"))
    return out


def format_table(rows: List[Tuple[str, Metrics]], fields: List[str]) -> str:
    headers = ["case"] + fields
    data = []
    for name, m in rows:
        row = [name]
        for f in fields:
            row.append(getattr(m, f))
        data.append(row)
    widths = [len(str(h)) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    lines = []
    lines.append(" | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)))
    lines.append("-+-".join("-" * w for w in widths))
    for row in data:
        lines.append(" | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def summarize(case_metrics: Dict[str, Metrics]) -> str:
    selected = [
        "core_ion_temperature_keV",
        "core_electron_temperature_keV",
        "ti_te_ratio",
        "confinement_time_proxy",
        "reconnection_tearing_elm_event_rate",
        "bremsstrahlung_proxy",
        "pB11_alpha_yield",
        "direct_conversion_power",
        "net_power_proxy",
        "ignition_margin_proxy",
    ]
    rows = [(k, case_metrics[k]) for k in case_metrics]
    return format_table(rows, selected)


def one_way_sweep(reference: Scenario) -> List[Tuple[str, Metrics]]:
    sweeps: List[Tuple[str, Metrics]] = []

    axes = {
        "TCT strength": ["none", "weak", "medium", "strong", "aggressive"],
        "Field reversal": ["none", "shallow reversed-shear", "medium reversed-shear", "strong local reversal"],
        "Counter-rotation": ["none", "weak", "medium", "strong"],
        "Compression": [0.0, 1.0, 3.0, 5.0, 10.0],
        "Mag timing": ["before compression", "during compression", "after compression"],
        "RF timing": ["off", "before compression", "at peak compression", "after compression"],
        "Plasma mirror": ["off", "weak", "medium", "strong"],
        "Boron density": ["low", "medium", "high", "extreme"],
        "Recirc": ["single-pass", "10-pass", "100-pass", "1k-pass", "10k-pass", "100k-pass"],
        "Li current": ["0", "low", "medium", "high"],
        "Conversion": [0.0, 0.30, 0.50, 0.70, 0.85],
    }

    for axis, values in axes.items():
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
            elif axis == "Mag timing":
                kwargs["magnetic_ramp_timing"] = value
            elif axis == "RF timing":
                kwargs["rf_timing"] = value
            elif axis == "Plasma mirror":
                kwargs["plasma_mirror_drive"] = value
            elif axis == "Boron density":
                kwargs["boron_vapor_density"] = value
                kwargs["pB11_enabled"] = True
            elif axis == "Recirc":
                kwargs["proton_recirculation_quality"] = value
                kwargs["pB11_enabled"] = True
            elif axis == "Li current":
                kwargs["liquid_lithium_current"] = value
            elif axis == "Conversion":
                kwargs["alpha_conversion_efficiency"] = float(value)
                kwargs["pB11_enabled"] = True
            kwargs["name"] = f"{axis}: {value}"
            sweeps.append((kwargs["name"], simulate(Scenario(**kwargs))))
    return sweeps


def print_case_comparison(case_metrics: Dict[str, Metrics]) -> None:
    print("Case comparison")
    print(summarize(case_metrics))
    print()
    print("Key interpretation")
    for key in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        m = case_metrics[key]
        print(
            f"{key}: Ti/Te={m.ti_te_ratio}, event_rate={m.reconnection_tearing_elm_event_rate}, "
            f"brems={m.bremsstrahlung_proxy}, net={m.net_power_proxy}, ignition_margin={m.ignition_margin_proxy}"
        )


def print_h_sweep() -> None:
    rows = []
    for scenario in efficiency_sweep_case_h():
        rows.append((scenario.name, simulate(scenario)))
    fields = [
        "alpha_extraction_fraction",
        "pB11_alpha_yield",
        "direct_conversion_power",
        "proton_burnup_fraction",
        "net_power_proxy",
        "ignition_margin_proxy",
    ]
    print()
    print("H conversion-efficiency sweep")
    print(format_table(rows, fields))


def print_focus_sweep(reference: Scenario) -> None:
    # Compress the large design space into one-way sweeps around the chosen
    # reference hybrid point so the output stays readable.
    selected_axes = [
        ("TCT strength", ["none", "weak", "medium", "strong", "aggressive"]),
        ("Field reversal", ["none", "shallow reversed-shear", "medium reversed-shear", "strong local reversal"]),
        ("Counter-rotation", ["none", "weak", "medium", "strong"]),
        ("Compression", [0.0, 1.0, 3.0, 5.0, 10.0]),
        ("Plasma mirror", ["off", "weak", "medium", "strong"]),
        ("Boron density", ["low", "medium", "high", "extreme"]),
    ]

    print()
    print("One-way sensitivity sweeps around the full hybrid reference")
    for axis, values in selected_axes:
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
        print(
            format_table(
                rows,
                [
                    "core_ion_temperature_keV",
                    "core_electron_temperature_keV",
                    "ti_te_ratio",
                    "reconnection_tearing_elm_event_rate",
                    "bremsstrahlung_proxy",
                    "net_power_proxy",
                    "ignition_margin_proxy",
                ],
            )
        )


def as_json(case_metrics: Dict[str, Metrics]) -> str:
    return json.dumps({k: asdict(v) for k, v in case_metrics.items()}, indent=2, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of tables")
    parser.add_argument("--no-sweeps", action="store_true", help="Skip the one-way sensitivity sweeps")
    args = parser.parse_args()

    cases = case_definitions()
    case_metrics = {key: simulate(scenario) for key, scenario in cases.items()}

    if args.json:
        print(as_json(case_metrics))
        return

    print_case_comparison(case_metrics)
    print_h_sweep()
    if not args.no_sweeps:
        print_focus_sweep(cases["F"])


if __name__ == "__main__":
    main()

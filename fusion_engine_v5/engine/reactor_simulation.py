from typing import Any, Dict

import numpy as np

from .plasma_model import evaluate_case
from .tct_control import run_tct_controller
from .lithium_wall import (
    lithium_wall_temperature,
    mhd_drag_power,
    pumping_power_from_heat,
)
from .power_balance import plant_power_balance
from .engineering_limits import engineering_penalty
from ..blanket.openmc_dataset_model import evaluate_blanket
from ..blanket.openmc_runner import run_openmc_validation


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _design_float(design: Dict[str, Any], key: str, default: float = 0.0) -> float:
    return _safe_float(design.get(key, default), default)


def _call_evaluate_blanket(design: Dict[str, Any], plasma: Dict[str, Any]) -> Any:
    """Support either evaluate_blanket(design) or evaluate_blanket(design, plasma)."""
    try:
        return evaluate_blanket(design, plasma)
    except TypeError:
        return evaluate_blanket(design)


def _normalize_blanket_output(blanket_raw: Any, fallback_model: str = "unknown") -> Dict[str, Any]:
    """
    Normalize blanket/OpenMC output into one dict.

    Handles dicts, (dict, meta) tuples, and legacy tuple/list scalar forms:
    (TBR, attenuation, front_heating_frac).
    """
    if blanket_raw is None:
        blanket: Dict[str, Any] = {}
    elif isinstance(blanket_raw, tuple):
        if blanket_raw and isinstance(blanket_raw[0], dict):
            blanket = dict(blanket_raw[0])
        else:
            blanket = {
                "TBR": _safe_float(blanket_raw[0], 0.0) if len(blanket_raw) > 0 else 0.0,
                "attenuation": _safe_float(blanket_raw[1], 0.0) if len(blanket_raw) > 1 else 0.0,
                "front_heating_frac": _safe_float(blanket_raw[2], 1.0) if len(blanket_raw) > 2 else 1.0,
            }
    elif isinstance(blanket_raw, list):
        blanket = {
            "TBR": _safe_float(blanket_raw[0], 0.0) if len(blanket_raw) > 0 else 0.0,
            "attenuation": _safe_float(blanket_raw[1], 0.0) if len(blanket_raw) > 1 else 0.0,
            "front_heating_frac": _safe_float(blanket_raw[2], 1.0) if len(blanket_raw) > 2 else 1.0,
        }
    elif isinstance(blanket_raw, dict):
        blanket = dict(blanket_raw)
    else:
        blanket = {}

    clean = {str(k): v for k, v in blanket.items() if k is not None and v is not None}

    # Normalize common aliases.
    if "tbr" in clean and "TBR" not in clean:
        clean["TBR"] = clean["tbr"]
    if "ATTN" in clean and "attenuation" not in clean:
        clean["attenuation"] = clean["ATTN"]
    if "front_heat" in clean and "front_heating_frac" not in clean:
        clean["front_heating_frac"] = clean["front_heat"]

    clean.setdefault("TBR", 0.0)
    clean.setdefault("attenuation", 0.0)
    clean.setdefault("front_heating_frac", 1.0)
    clean.setdefault("model", fallback_model)

    clean["TBR"] = _safe_float(clean.get("TBR"), 0.0)
    clean["attenuation"] = _safe_float(clean.get("attenuation"), 0.0)
    clean["front_heating_frac"] = _safe_float(clean.get("front_heating_frac"), 1.0)

    return clean


def _lithium_wall_modifier(thickness: float, velocity: float) -> float:
    """
    Heuristic modifier for effective wall loading.

    Kept bounded because this is an optimization proxy, not a validated MHD wall model.
    """
    thickness = max(_safe_float(thickness), 0.0)
    velocity = max(_safe_float(velocity), 0.0)
    return float(min(max(1.0 + 8.0 * thickness + 0.08 * velocity, 1.0), 2.5))


def _monte_carlo_plasma(tct: Dict[str, Any], samples: int = 30000) -> Dict[str, Any]:
    """Deterministic survivability proxy tied to the TCT controller state."""
    samples = max(int(samples or 30000), 1000)

    risk_R = _safe_float(tct.get("risk_R", tct.get("tct_risk_R", 0.25)), 0.25)
    risk_H = _safe_float(tct.get("risk_H", tct.get("tct_risk_H", 0.25)), 0.25)
    control = _safe_float(tct.get("control_strength", 0.0), 0.0)

    stability_obj = tct.get("stability", {})
    if isinstance(stability_obj, dict):
        stability = _safe_float(stability_obj.get("stability", tct.get("stability_metric", 0.85)), 0.85)
    else:
        stability = _safe_float(stability_obj, 0.85)

    base_risk = np.clip(0.55 * risk_R + 0.45 * risk_H, 0.0, 1.0)
    effective_risk = np.clip(base_risk * (1.0 - 0.75 * control), 0.0, 1.0)
    fail_rate = np.clip(
        0.002 + 0.08 * effective_risk + 0.04 * max(0.0, 0.85 - stability),
        0.0,
        1.0,
    )

    fail_count = int(round(samples * fail_rate))
    damage_per_event = _safe_float(tct.get("damage_per_event", 0.0), 0.0)
    total_damage = damage_per_event * fail_count

    return {
        "fail_rate": float(fail_rate),
        "fail_count": fail_count,
        "samples": samples,
        "damage_per_event": float(damage_per_event),
        "total_damage": float(total_damage),
        "damage_rate": float(total_damage / max(samples, 1)),
    }


def _extract_tct_stability(tct: Dict[str, Any], default: float = 1.0) -> float:
    stability_obj = tct.get("stability", default)
    if isinstance(stability_obj, dict):
        return _safe_float(stability_obj.get("stability", default), default)
    return _safe_float(stability_obj, default)


def _event_adjusted_power(plant: Dict[str, Any], tct: Dict[str, Any], mc: Dict[str, Any]) -> tuple[float, float, float, float]:
    net_electric_raw = _safe_float(plant.get("net_electric", 0.0), 0.0)
    fail_rate = _safe_float(mc.get("fail_rate", 0.0), 0.0)
    stability = _extract_tct_stability(tct, 1.0)
    tct_usage = _safe_float(tct.get("control_strength", tct.get("used", 0.0)), 0.0)

    event_severity = max(0.02, min(1.0, 1.0 - stability + 0.1 * tct_usage))
    if "damage_per_event" in mc:
        event_severity = max(0.02, min(1.0, _safe_float(mc.get("damage_per_event", 0.0), 0.0) * 1e5))

    event_loss_frac = max(0.0, min(0.60, 0.35 * fail_rate * event_severity))
    net_electric = max(0.0, net_electric_raw * (1.0 - event_loss_frac))
    return net_electric, net_electric_raw, event_severity, event_loss_frac


def estimate_capex_billion(design: Dict[str, Any], plant: Dict[str, Any], plasma: Dict[str, Any]) -> float:
    net_gw = max(_safe_float(plant.get("net_electric", 0.0)) / 1000.0, 0.0)
    base_cost = 6.0 * (net_gw ** 0.7)
    magnet_cost = 0.8 * (_design_float(design, "B0") / 6.0) ** 2
    size_cost = 0.25 * (_design_float(design, "R") / 6.0) ** 1.3
    return float(2.0 + base_cost + magnet_cost + size_cost)


def estimate_annual_revenue_musd(
    plant: Dict[str, Any],
    capacity_factor: float = 0.90,
    price_per_mwh: float = 50.0,
) -> float:
    net_mw = max(_safe_float(plant.get("net_electric", 0.0)), 0.0)
    return float(net_mw * 8760.0 * capacity_factor * price_per_mwh / 1_000_000.0)


def estimate_annualized_cost_musd(capex_billion: float, annual_om_fraction: float = 0.04) -> float:
    capex_billion = _safe_float(capex_billion)
    return float(capex_billion * 1000.0 / 20.0 + capex_billion * 1000.0 * annual_om_fraction)


def _evaluate_plasma(design: Dict[str, Any]) -> Dict[str, Any]:
    fallback_minor_radius = _safe_float(design.get("plasma_radius_cm", 60.0), 60.0) / 100.0
    return evaluate_case(
        _safe_float(design.get("R", fallback_minor_radius)),
        _safe_float(design.get("a", fallback_minor_radius)),
        _design_float(design, "kappa"),
        _design_float(design, "B0"),
        _design_float(design, "Ip"),
        _design_float(design, "Ti"),
        _design_float(design, "Te"),
        _design_float(design, "H98"),
        _design_float(design, "fG"),
        _design_float(design, "frac_cap"),
    )


def _evaluate_blanket(design: Dict[str, Any], plasma: Dict[str, Any], blanket_validate: bool) -> Dict[str, Any]:
    if blanket_validate:
        blanket_raw = run_openmc_validation(design, plasma)
        if blanket_raw is None:
            fallback = _call_evaluate_blanket(design, plasma)
            blanket = _normalize_blanket_output(fallback, fallback_model="dataset_fallback")
        else:
            blanket = _normalize_blanket_output(blanket_raw, fallback_model="openmc")
    else:
        blanket = _normalize_blanket_output(
            _call_evaluate_blanket(design, plasma),
            fallback_model="dataset",
        )
    return blanket


def simulate_reactor(design: Dict[str, Any], blanket_validate: bool = False) -> Dict[str, Any]:
    plasma = _evaluate_plasma(design)
    tct = run_tct_controller(plasma, design)
    mc = _monte_carlo_plasma(tct, samples=int(design.get("mc_samples", 30000)))

    raw_wall_load = _safe_float(plasma.get("wn_mw_m2", 1e9), 1e9)
    lithium_mod = _lithium_wall_modifier(
        design.get("lithium_thickness", 0.0),
        design.get("lithium_velocity", 0.0),
    )
    effective_wall_load = raw_wall_load / max(lithium_mod, 1e-6)

    wall_temp = lithium_wall_temperature(
        raw_wall_load,
        _design_float(design, "lithium_thickness"),
    )

    mhd_power = mhd_drag_power(
        _design_float(design, "B0"),
        _design_float(design, "lithium_velocity"),
        1.0e6,
        500.0,
        0.05,
        200.0,
    )

    pump_power = pumping_power_from_heat(_safe_float(plasma.get("pfus_mw", 0.0), 0.0))
    design = dict(design)
    design["pump_power_mw"] = float(pump_power)

    blanket = _evaluate_blanket(design, plasma, blanket_validate)
    plant = plant_power_balance(plasma, blanket, mhd_power, design)
    penalty_stress = engineering_penalty(plasma, plant, wall_temp, design, blanket=blanket)

    capex_billion = estimate_capex_billion(design, plant, plasma)
    annual_revenue_musd = estimate_annual_revenue_musd(plant)
    annual_cost_musd = estimate_annualized_cost_musd(capex_billion)
    net_electric, net_electric_raw, event_severity, event_loss_frac = _event_adjusted_power(plant, tct, mc)

    grid_penalty = 0.0
    if net_electric < 500.0:
        grid_penalty += 2000.0 + 500.0 * (500.0 - net_electric) ** 2
    if net_electric < 2500.0:
        grid_penalty += 0.7 * (2500.0 - net_electric)
    if net_electric > 4000.0:
        grid_penalty += 1.5 * (net_electric - 4000.0)

    R = _safe_float(design.get("R", _safe_float(design.get("plasma_radius_cm", 60.0), 60.0) / 100.0))
    a = _safe_float(design.get("a", _safe_float(design.get("plasma_radius_cm", 60.0), 60.0) / 100.0))
    size_penalty = 50.0 * max(R - 8.5, 0.0) ** 2 + 45.0 * max(a - 2.6, 0.0) ** 2

    complexity_penalty = (
        15.0 * max(_design_float(design, "B0") - 8.0, 0.0) ** 2
        + 3.0 * max(_design_float(design, "lithium_velocity") - 4.0, 0.0) ** 2
        + 80.0 * max(_design_float(design, "blanket_thickness") - 1.2, 0.0) ** 2
    )

    tbr = _safe_float(blanket.get("TBR", 0.0), 0.0)
    breeding_penalty = 15000.0 * max(1.15 - tbr, 0.0)
    wall_penalty = 3000.0 * max(effective_wall_load - 6.5, 0.0) ** 2 + 2000.0 * max(raw_wall_load - 24.0, 0.0) ** 2

    bootstrap_frac = _safe_float(plasma.get("bootstrap_frac", 0.0), 0.0)
    bootstrap_penalty = 20000.0 * max(0.65 - bootstrap_frac, 0.0)

    beta = _safe_float(plasma.get("beta", 0.03), 0.03)
    ip_ma = max(_safe_float(plasma.get("Ip_MA", _design_float(design, "Ip", 10.0)), 10.0), 0.1)
    betan = beta * _design_float(design, "B0") * a / ip_ma
    density_frac = _safe_float(design.get("fG", plasma.get("fG", 0.85)), 0.85)

    stability_penalty = 0.0
    if density_frac > 0.9 and betan < 1.0:
        stability_penalty += 12000.0 * ((density_frac / 0.9) - 1.0) ** 2
    if betan > 3.5:
        stability_penalty += 15000.0 * (betan - 3.5) ** 2

    hard_fail_penalty = 0.0
    if tbr < 0.95:
        hard_fail_penalty += 100000.0
    if net_electric < 1500.0:
        hard_fail_penalty += 50000.0 + 500.0 * (1500.0 - net_electric)

    tct_stability_score = _extract_tct_stability(tct, 0.0)
    score = (
        _safe_float(annual_revenue_musd)
        - _safe_float(annual_cost_musd)
        - _safe_float(penalty_stress)
        - grid_penalty
        - size_penalty
        - complexity_penalty
        - breeding_penalty
        - wall_penalty
        - bootstrap_penalty
        - hard_fail_penalty
        - stability_penalty
        + 600.0 * tct_stability_score
        - 200.0 * _safe_float(mc.get("fail_rate", 0.0), 0.0)
    )

    return {
        "score": float(score),
        "net_electric": float(net_electric),
        "net_electric_raw": float(net_electric_raw),
        "event_severity": float(event_severity),
        "event_loss_frac": float(event_loss_frac),
        "TBR": float(tbr),
        "fail_rate": float(_safe_float(mc.get("fail_rate", 0.0), 0.0)),
        "fail_count": int(mc.get("fail_count", 0)),
        "damage_per_event": float(_safe_float(mc.get("damage_per_event", 0.0), 0.0)),
        "total_damage": float(_safe_float(mc.get("total_damage", 0.0), 0.0)),
        "damage_rate": float(_safe_float(mc.get("damage_rate", 0.0), 0.0)),
        "wall_load": float(effective_wall_load),
        "raw_wall_load": float(raw_wall_load),
        "lithium_wall_modifier": float(lithium_mod),
        "performance_boost": float(lithium_mod),
        "bootstrap": float(bootstrap_frac),
        "wall_temp": float(_safe_float(wall_temp, 0.0)),
        "blanket_model": blanket.get("model", "unknown"),
        "blanket_attenuation": float(_safe_float(blanket.get("attenuation", 0.0), 0.0)),
        "blanket_front_heating_frac": float(_safe_float(blanket.get("front_heating_frac", 1.0), 1.0)),
        "capex_billion": float(capex_billion),
        "annual_revenue_musd": float(annual_revenue_musd),
        "annual_cost_musd": float(annual_cost_musd),
        "mc_samples": int(mc.get("samples", 0)),
        "tct_control_strength": float(_safe_float(tct.get("control_strength", 0.0), 0.0)),
        "tct_precursor": float(_safe_float(tct.get("precursor", 0.0), 0.0)),
        "tct_upstream_factor": float(_safe_float(tct.get("upstream_factor", 1.0), 1.0)),
        "tct_risk_R": float(_safe_float(tct.get("risk_R", tct.get("tct_risk_R", 0.0)), 0.0)),
        "tct_risk_H": float(_safe_float(tct.get("risk_H", tct.get("tct_risk_H", 0.0)), 0.0)),
        "tct_n_used": float(_safe_float(tct.get("n_used", plasma.get("n_e3", plasma.get("n_e", 0.0))), 0.0)),
        "tct_B_used": float(_safe_float(tct.get("B_used", plasma.get("B_t", 0.0)), 0.0)),
        "tct_Te_used": float(_safe_float(tct.get("Te_used", plasma.get("T_keV", plasma.get("Te_keV", 0.0))), 0.0)),
    }

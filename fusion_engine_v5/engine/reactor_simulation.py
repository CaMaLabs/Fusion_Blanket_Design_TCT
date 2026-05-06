import math
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


def _call_evaluate_blanket(design: Dict[str, Any], plasma: Dict[str, Any]) -> Dict[str, Any]:
    """
    Support either evaluate_blanket(design) or evaluate_blanket(design, plasma).
    """
    try:
        return evaluate_blanket(design, plasma)
    except TypeError:
        return evaluate_blanket(design)


def _normalize_blanket_output(blanket_raw: Any) -> Dict[str, Any]:
    """
    Normalize blanket/OpenMC output into a clean dict.

    Handles:
    - dict
    - (dict, meta) tuple from OpenMC runner
    - tuple/list scalar legacy forms like (TBR, attenuation, front_heating_frac)
    """
    blanket: Dict[str, Any]

    # Common OpenMC form: (result_dict, meta)
    if isinstance(blanket_raw, tuple):
        if len(blanket_raw) > 0 and isinstance(blanket_raw[0], dict):
            blanket = dict(blanket_raw[0])
        else:
            try:
                blanket = {
                    "TBR": _safe_float(blanket_raw[0], 0.0),
                    "attenuation": _safe_float(blanket_raw[1], 0.0) if len(blanket_raw) > 1 else 0.0,
                    "front_heating_frac": _safe_float(blanket_raw[2], 1.0) if len(blanket_raw) > 2 else 1.0,
                    "model": "openmc_raw",
                }
            except Exception:
                blanket = {"model": "openmc_invalid"}
    elif isinstance(blanket_raw, list):
        try:
            blanket = {
                "TBR": _safe_float(blanket_raw[0], 0.0),
                "attenuation": _safe_float(blanket_raw[1], 0.0) if len(blanket_raw) > 1 else 0.0,
                "front_heating_frac": _safe_float(blanket_raw[2], 1.0) if len(blanket_raw) > 2 else 1.0,
                "model": "openmc_raw",
            }
        except Exception:
            blanket = {"model": "openmc_invalid"}
    elif isinstance(blanket_raw, dict):
        blanket = dict(blanket_raw)
    else:
        blanket = {"model": "openmc_invalid"}

    # Drop None keys/values and stringify keys
    clean: Dict[str, Any] = {}
    for k, v in blanket.items():
        if k is None or v is None:
            continue
        clean[str(k)] = v
    blanket = clean

    # Sometimes OpenMC returns blanket_heat_mw; preserve it and derive front heating if needed.
    if "blanket_heat_mw" in blanket and "front_heating_frac" not in blanket:
        blanket["front_heating_frac"] = 1.0

    blanket.setdefault("TBR", 0.0)
    blanket.setdefault("attenuation", 0.0)
    blanket.setdefault("front_heating_frac", 1.0)
    blanket.setdefault("model", "openmc" if blanket.get("TBR", 0.0) != 0.0 else "unknown")

    return blanket


def _lithium_wall_modifier(thickness: float, velocity: float) -> float:
    """
    Heuristic modifier for effective wall loading when a direct helper is not exposed
    by lithium_wall.py. Tuned to stay in a sane range for your current design space.
    """
    thickness = max(_safe_float(thickness, 0.0), 0.0)
    velocity = max(_safe_float(velocity, 0.0), 0.0)
    mod = 1.0 + 8.0 * thickness + 0.08 * velocity
    return float(min(max(mod, 1.0), 2.5))


def _monte_carlo_plasma(tct: Dict[str, Any], samples: int = 30000) -> Dict[str, Any]:
    """
    Lightweight stochastic survivability proxy tied to the TCT controller state.
    """
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

    # keep fail rates in the realistic "small but meaningful" regime
    fail_rate = np.clip(0.002 + 0.08 * effective_risk + 0.04 * max(0.0, 0.85 - stability), 0.0, 1.0)

    # deterministic expectation rather than binomial draw for reproducibility
    fail_count = int(round(samples * fail_rate))

    # Optional damage_per_event passthrough if newer controller emits it
    damage_per_event = _safe_float(tct.get("damage_per_event", 0.0), 0.0)
    total_damage = damage_per_event * fail_count
    damage_rate = total_damage / max(samples, 1)

    return {
        "fail_rate": float(fail_rate),
        "fail_count": int(fail_count),
        "samples": int(samples),
        "damage_per_event": float(damage_per_event),
        "total_damage": float(total_damage),
        "damage_rate": float(damage_rate),
    }


def estimate_capex_billion(design: Dict[str, Any], plant: Dict[str, Any], plasma: Dict[str, Any]) -> float:
    net_gw = max(_safe_float(plant.get("net_electric", 0.0), 0.0) / 1000.0, 0.0)
    base_cost = 6.0 * (net_gw ** 0.7)
    magnet_cost = 0.8 * (_safe_float(design.get("B0", 0.0)) / 6.0) ** 2
    size_cost = 0.25 * (_safe_float(design.get("R", 0.0)) / 6.0) ** 1.3
    capex_billion = 2.0 + base_cost + magnet_cost + size_cost
    return float(capex_billion)


def estimate_annual_revenue_musd(
    plant: Dict[str, Any],
    capacity_factor: float = 0.90,
    price_per_mwh: float = 50.0,
) -> float:
    net_mw = max(_safe_float(plant.get("net_electric", 0.0), 0.0), 0.0)
    annual_mwh = net_mw * 8760.0 * capacity_factor
    return float(annual_mwh * price_per_mwh / 1_000_000.0)


def estimate_annualized_cost_musd(capex_billion: float, annual_om_fraction: float = 0.04) -> float:
    annualized_capex_musd = _safe_float(capex_billion, 0.0) * 1000.0 / 20.0
    annual_om_musd = _safe_float(capex_billion, 0.0) * 1000.0 * annual_om_fraction
    return float(annualized_capex_musd + annual_om_musd)


def simulate_reactor(design: Dict[str, Any], blanket_validate: bool = False) -> Dict[str, Any]:
    blanket_res = {}
    plasma = evaluate_case(
        _safe_float(design.get("R", design.get("plasma_radius_cm", 60.0) / 100.0)),
        _safe_float(design.get("a", design.get("plasma_radius_cm", 60.0) / 100.0)),
        _safe_float(design["kappa"]),
        _safe_float(design["B0"]),
        _safe_float(design["Ip"]),
        _safe_float(design["Ti"]),
        _safe_float(design["Te"]),
        _safe_float(design["H98"]),
        _safe_float(design["fG"]),
        _safe_float(design["frac_cap"]),
    )
    blanket_res = {}
    blanket_raw = None
    attenuation = 0.0
    gradient = 0.0
    front_heating_frac = 0.0

    tct = run_tct_controller(plasma, design)

    mc = _monte_carlo_plasma(
        tct,
        samples=int(design.get("mc_samples", 30000)),
    )

    raw_wall_load = _safe_float(plasma.get("wn_mw_m2", 1e9), 1e9)
    lithium_mod = _lithium_wall_modifier(
        _safe_float(design.get("lithium_thickness", 0.0)),
        _safe_float(design.get("lithium_velocity", 0.0)),
    )
    effective_wall_load = raw_wall_load / max(lithium_mod, 1e-6)

    wall_temp = lithium_wall_temperature(
        raw_wall_load,
        _safe_float(design.get("lithium_thickness", 0.0)),
    )

    mhd_power = mhd_drag_power(
        _safe_float(design.get("B0", 0.0)),
        _safe_float(design.get("lithium_velocity", 0.0)),
        1.0e6,
        500.0,
        0.05,
        200.0,
    )

    pump_power = pumping_power_from_heat(_safe_float(plasma.get("pfus_mw", 0.0), 0.0))

    design = dict(design)
    design["pump_power_mw"] = float(pump_power)

    if blanket_validate:
        blanket_raw = run_openmc_validation(design, plasma)

        if isinstance(blanket_res, tuple):
            blanket_raw = blanket_res[0]
        else:
            blanket_raw = blanket_res

        if blanket_raw is None:
            blanket_raw = {}

        attenuation = float(blanket_raw.get('attenuation', blanket_raw.get('ATTN', 0.0)))
        gradient = float(blanket_raw.get('gradient', blanket_raw.get('GRAD', 0.0)))
        front_heating_frac = float(blanket_raw.get('front_heating_frac', 0.0))
        print(f'[SIM PATCH] attn={attenuation:.6f} grad={gradient:.6f} front_heat={front_heating_frac:.6f}')


        if isinstance(blanket_res, tuple):
            blanket_res = blanket_res[0] if blanket_res[0] is not None else {}
        elif blanket_res is None:
            blanket_res = {}

        attenuation = float(blanket_res.get('attenuation', blanket_res.get('ATTN', 0.0)))
        gradient = float(blanket_res.get('gradient', blanket_res.get('GRAD', 0.0)))
        front_heating_frac = float(blanket_res.get('front_heating_frac', 0.0))
        tbr_openmc = float(blanket_res.get('TBR', blanket_res.get('tbr', 0.0)))

        if 'result' in locals() and isinstance(result, dict):
            result['ATTN'] = attenuation
            result['GRAD'] = gradient
            result['attenuation'] = attenuation
            result['gradient'] = gradient
            result['front_heating_frac'] = front_heating_frac
            if tbr_openmc > 0.0:
                result['TBR'] = tbr_openmc
                result['tbr'] = tbr_openmc

            blanket_res = {}

        attenuation = float(blanket_res.get('attenuation', blanket_res.get('ATTN', 0.0)))
        gradient = float(blanket_res.get('gradient', blanket_res.get('GRAD', 0.0)))
        front_heating_frac = float(blanket_res.get('front_heating_frac', 0.0))
        tbr_openmc = float(blanket_res.get('TBR', blanket_res.get('tbr', 0.0)))

        # inject into result dict (will override later if needed)
        try:
            result['ATTN'] = attenuation
            result['GRAD'] = gradient
            result['attenuation'] = attenuation
            result['gradient'] = gradient
            result['front_heating_frac'] = front_heating_frac
            if tbr_openmc > 0:
                result['TBR'] = tbr_openmc
        except Exception as e:
            pass
        if blanket_raw is None:
            blanket_raw = _call_evaluate_blanket(design, plasma)
            if isinstance(blanket_raw, dict):
                blanket_raw["model"] = "dataset_fallback"
        blanket = _normalize_blanket_output(blanket_raw)
    else:
        blanket = _normalize_blanket_output(_call_evaluate_blanket(design, plasma))

    plant = plant_power_balance(plasma, blanket, mhd_power, design)

    penalty_stress = engineering_penalty(
        plasma,
        plant,
        wall_temp,
        design,
        blanket=blanket,
    )

    capex_billion = estimate_capex_billion(design, plant, plasma)
    annual_revenue_musd = estimate_annual_revenue_musd(plant)
    annual_cost_musd = estimate_annualized_cost_musd(capex_billion)

    size_penalty = (
        50.0 * max(_safe_float(design.get("R", design.get("plasma_radius_cm", 60.0) / 100.0)) - 8.5, 0.0) ** 2
        + 45.0 * max(_safe_float(design.get("a", design.get("plasma_radius_cm", 60.0) / 100.0)) - 2.6, 0.0) ** 2
    )

    grid_penalty = 0.0

    # --- ORIGINAL RAW POWER ---
    net_electric_raw = _safe_float(plant.get("net_electric", 0.0), 0.0)

    # --- EVENT / INSTABILITY MODEL ---
    fail_rate = _safe_float(mc.get("fail_rate", 0.0), 0.0)

    stability_obj = tct.get("stability", {})
    if isinstance(stability_obj, dict):
        stability = _safe_float(stability_obj.get("stability", 1.0), 1.0)
    else:
        stability = _safe_float(stability_obj, 1.0)

    tct_usage = _safe_float(tct.get("used", 0.0), 0.0)

    # severity model (bounded, tunable)
    event_severity = max(0.02, min(1.0, 1.0 - stability + 0.1 * tct_usage))

    # if a real damage_per_event exists, let it override the proxy
    if "damage_per_event" in mc:
        event_severity = max(
            0.02,
            min(1.0, _safe_float(mc.get("damage_per_event", 0.0), 0.0) * 1e5),
        )

    # combined loss = frequency × severity
    event_loss_frac = max(0.0, min(0.60, 0.35 * fail_rate * event_severity))

    # adjusted power
    net_electric = max(0.0, net_electric_raw * (1.0 - event_loss_frac))

    if net_electric < 500.0:
        grid_penalty += 2000.0 + 500.0 * (500.0 - net_electric) ** 2
    if net_electric < 2500.0:
        grid_penalty += 0.7 * (2500.0 - net_electric)
    if net_electric > 4000.0:
        grid_penalty += 1.5 * (net_electric - 4000.0)

    complexity_penalty = (
        15.0 * max(_safe_float(design.get("B0", 0.0)) - 8.0, 0.0) ** 2
        + 3.0 * max(_safe_float(design.get("lithium_velocity", 0.0)) - 4.0, 0.0) ** 2
        + 80.0 * max(_safe_float(design.get("blanket_thickness", 0.0)) - 1.2, 0.0) ** 2
    )

    breeding_penalty = 0.0
    if _safe_float(blanket.get("TBR", 0.0), 0.0) < 1.15:
        breeding_penalty += 15000.0 * (1.15 - _safe_float(blanket.get("TBR", 0.0), 0.0))

    wall_penalty = 0.0
    if effective_wall_load > 6.5:
        wall_penalty += 3000.0 * (effective_wall_load - 6.5) ** 2
    if raw_wall_load > 24.0:
        wall_penalty += 2000.0 * (raw_wall_load - 24.0) ** 2

    bootstrap_penalty = 0.0
    bootstrap_frac = _safe_float(plasma.get("bootstrap_frac", 0.0), 0.0)
    if bootstrap_frac < 0.65:
        bootstrap_penalty += 20000.0 * (0.65 - bootstrap_frac)

    stability_penalty = 0.0
    betan = _safe_float(plasma.get("beta", 0.03), 0.03) * _safe_float(design.get("B0", 0.0), 0.0)
    ip_ma = max(_safe_float(plasma.get("Ip_MA", _safe_float(design.get("Ip", 10.0), 10.0)), 10.0), 0.1)
    betan = betan * _safe_float(design.get("a", 1.0), 1.0) / ip_ma
    density_frac = _safe_float(design.get("fG", plasma.get("fG", 0.85)), 0.85)

    if density_frac > 0.9 and betan < 1.0:
        stability_penalty += 12000.0 * ((density_frac / 0.9) - 1.0) ** 2
    if betan > 3.5:
        stability_penalty += 15000.0 * (betan - 3.5) ** 2

    hard_fail_penalty = 0.0
    if _safe_float(blanket.get("TBR", 0.0), 0.0) < 0.95:
        hard_fail_penalty += 100000.0
    if net_electric < 1500.0:
        hard_fail_penalty += 50000.0 + 500.0 * (1500.0 - net_electric)

    performance_boost = lithium_mod
    bootstrap_boost = bootstrap_frac

    score = (
        _safe_float(annual_revenue_musd, 0.0)
        - _safe_float(annual_cost_musd, 0.0)
        - _safe_float(penalty_stress, 0.0)
        - _safe_float(grid_penalty, 0.0)
        - _safe_float(size_penalty, 0.0)
        - _safe_float(complexity_penalty, 0.0)
        - _safe_float(breeding_penalty, 0.0)
        - _safe_float(wall_penalty, 0.0)
        - _safe_float(bootstrap_penalty, 0.0)
        - _safe_float(hard_fail_penalty, 0.0)
        - _safe_float(stability_penalty, 0.0)
        + 600.0 * _safe_float(
            tct.get("stability", {}).get("stability", 0.0)
            if isinstance(tct.get("stability", {}), dict)
            else _safe_float(tct.get("stability", 0.0), 0.0),
            0.0,
        )
        - 200.0 * _safe_float(mc.get("fail_rate", 0.0), 0.0)
    )

    return {
        "score": float(score),
        "net_electric": float(net_electric),
        "net_electric_raw": float(net_electric_raw),
        "event_severity": float(event_severity),
        "event_loss_frac": float(event_loss_frac),
        "TBR": float(_safe_float(blanket.get("TBR", 0.0), 0.0)),
        "fail_rate": float(_safe_float(mc.get("fail_rate", 0.0), 0.0)),
        "fail_count": int(mc.get("fail_count", 0)),
        "damage_per_event": float(_safe_float(mc.get("damage_per_event", 0.0), 0.0)),
        "total_damage": float(_safe_float(mc.get("total_damage", 0.0), 0.0)),
        "damage_rate": float(_safe_float(mc.get("damage_rate", 0.0), 0.0)),
        "wall_load": float(effective_wall_load),
        "raw_wall_load": float(raw_wall_load),
        "lithium_wall_modifier": float(lithium_mod),
        "performance_boost": float(performance_boost),
        "bootstrap": float(np.asarray(bootstrap_boost).reshape(-1)[0]),
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

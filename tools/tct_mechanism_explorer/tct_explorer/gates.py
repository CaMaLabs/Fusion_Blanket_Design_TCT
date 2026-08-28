from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from typing import Any


def almost_equal_metrics(
    base: list[dict[str, float]],
    other: list[dict[str, float]],
    tolerance: float,
) -> tuple[bool, float]:
    keys = [
        "W_sheet",
        "Jpk",
        "Jint_abs",
        "Jint_high",
        "roi_psi_span",
        "kinetic_energy",
        "magnetic_energy",
        "Reconnected_Flux",
    ]
    max_delta = 0.0
    for b, c in zip(base, other):
        for key in keys:
            x, y = b.get(key, math.nan), c.get(key, math.nan)
            if math.isnan(x) and math.isnan(y):
                continue
            max_delta = max(max_delta, abs(x - y))
    return max_delta <= tolerance, max_delta


def reachability_gate(metrics: dict[str, float], cfg: dict[str, Any]) -> bool:
    """Accept magnetic-field reachability or a real native momentum/flow response."""
    tol = float(cfg["stages"]["noise_abs_tolerance"])
    return (
        abs(metrics.get("final_psi_span_delta", 0.0)) > tol
        or abs(metrics.get("final_bz_proxy_delta", 0.0)) > tol
        or abs(metrics.get("final_kinetic_energy_delta", 0.0)) > tol
    )


def authority_gate(metrics: dict[str, float], cfg: dict[str, Any]) -> bool:
    """Require co-located favorable width, Jpk, and redistribution response."""
    return (
        metrics.get("peak_favorable_width_gain_pct", -math.inf)
        >= float(cfg["stages"]["authority_width_gain_pct"])
        and metrics.get("peak_favorable_jpk_change_pct", math.inf)
        <= float(cfg["stages"]["authority_peak_j_change_pct"])
        and metrics.get("peak_favorable_center_to_shoulder_change_pct", math.inf) < 0.0
    )


def sustained_gate(metrics: dict[str, float], cfg: dict[str, Any]) -> bool:
    return metrics.get("mean_active_width_gain_pct", -math.inf) >= float(
        cfg["stages"]["sustained_width_gain_pct"]
    )


def topology_gate(metrics: dict[str, float], cfg: dict[str, Any]) -> bool:
    tolerance = float(cfg["stages"]["topology_worsening_tolerance_pct"])
    observed = [
        x
        for x in [
            metrics.get("peak_reconnection_rate_change_pct", math.nan),
            metrics.get("final_reconnected_flux_change_pct", math.nan),
        ]
        if math.isfinite(x)
    ]
    return bool(observed) and max(observed) <= tolerance


def _load_ruzic(repo_root: Path):
    path = repo_root / "liquid_lithium_stability" / "ruzic_fiflis_2016.py"
    if not path.exists():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location("_tct_ruzic", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def physical_lithium_gate(candidate, cfg: dict[str, Any]) -> dict[str, Any]:
    mapping = cfg["physical_mapping"]
    if not mapping.get("enabled"):
        return {
            "classification": "LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED",
            "reason": "physical_mapping.enabled=false",
        }
    scale = mapping.get("mag_ctrl_amp_to_deltaB_T")
    if scale is None:
        return {
            "classification": "LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED",
            "reason": "mag_ctrl_amp_to_deltaB_T is not calibrated",
        }
    if "mag" not in candidate.mechanism:
        return {
            "classification": "LITHIUM_MAPPING_NOT_APPLICABLE",
            "reason": "candidate has no magnetic-control amplitude",
        }
    amp = candidate.params.get("amp", candidate.params.get("mag_amp"))
    if amp is None:
        return {"classification": "LITHIUM_MAPPING_NOT_APPLICABLE"}
    delta_b = abs(float(amp) * float(scale))
    mu0 = 4.0e-7 * math.pi
    surface_k = delta_b / mu0
    thickness = float(mapping["lithium_layer_thickness_m"])
    j_ka_m2 = surface_k / thickness / 1000.0
    ruzic = _load_ruzic(Path(cfg["paths"]["repo_root"]))
    inputs = ruzic.RuzicInputs(
        current_density_ka_m2=j_ka_m2,
        magnetic_field_t=float(mapping["background_B_T"]) + delta_b,
        plasma_tangential_velocity_km_s=float(mapping["lithium_velocity_km_s"]),
        trench_width_mm=float(mapping["trench_width_mm"]),
        jb_angle_deg=float(mapping["jb_angle_deg"]),
        wetted=bool(mapping["wetted"]),
    )
    result = ruzic.evaluate(inputs)
    return {
        "classification": (
            "LITHIUM_RUZIC_SURFACE_GATE_PASS"
            if result.stable_by_eq23
            else "LITHIUM_RUZIC_SURFACE_GATE_FAIL"
        ),
        "deltaB_T": delta_b,
        "surface_current_K_A_m": surface_k,
        "lithium_current_density_kA_m2": j_ka_m2,
        "normalized_plasma_impulse_x": result.normalized_plasma_impulse_x,
        "max_stable_width_mm": result.max_stable_width_mm,
        "width_margin_mm": result.width_margin_mm,
        "width_margin_fraction": result.width_margin_fraction,
        "domain_label": result.domain_label,
        "wetting_label": result.wetting_label,
        "claim_boundary": result.claim_boundary,
    }

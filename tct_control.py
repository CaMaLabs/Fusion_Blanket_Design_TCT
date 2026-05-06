import math
import numpy as np
from .config import CONSTS


def _pick_density(plasma):
    n = plasma.get("n_e3", None)
    if n is None:
        n = plasma.get("n_e", None)
    if n is None:
        n = plasma.get("n20", None)
    if n is None:
        n = 1.0
    return float(max(n, 1e-9))


def _pick_field(plasma):
    B = plasma.get("B0_T", None)
    if B is None:
        B = plasma.get("B_t", None)
    if B is None:
        B = plasma.get("B", None)
    if B is None:
        B = 5.0
    return float(max(B, 1e-9))


def _pick_temp(plasma):
    T = plasma.get("Te_keV", None)
    if T is None:
        T = plasma.get("T_keV", None)
    if T is None:
        T = plasma.get("Te", None)
    if T is None:
        T = 10.0
    return float(max(T, 1e-9))


def current_sheet_thickness(B_T, n_m3, Te_keV):
    wpe = math.sqrt(n_m3 * CONSTS.e_charge**2 / (CONSTS.me * CONSTS.eps0))
    de = 3e8 / max(wpe, 1e-9)
    beta = (2.0 * n_m3 * Te_keV * 1e3 * CONSTS.e_charge) / max(B_T**2 / (2.0 * CONSTS.mu0), 1e-12)
    return de * (1.0 + beta)


def alfven_speed(B_T, n_m3):
    return B_T / math.sqrt(max(CONSTS.mu0 * n_m3 * CONSTS.mi_dt, 1e-18))


def plasmoid_growth_rate(B_T, n_m3, delta_m):
    return alfven_speed(B_T, n_m3) / max(delta_m, 1e-9)


def confinement_risk(B_T, n_m3, Te_keV):
    delta = current_sheet_thickness(B_T, n_m3, Te_keV)
    gamma0 = plasmoid_growth_rate(B_T, n_m3, delta)
    return np.clip(gamma0 / 1e8, 0.0, 1.0)


def swim_speed(B_T, n_m3, Te_keV):
    return np.clip(alfven_speed(B_T, n_m3) / 1e7, 0.0, 1.0)


def tct_controller(plasma, reconn_trigger, conf_trigger):
    B_T = _pick_field(plasma)
    n = _pick_density(plasma)
    Te = _pick_temp(plasma)

    risk_R = swim_speed(B_T, n, Te)
    risk_H = confinement_risk(B_T, n, Te)

    base_risk = np.clip(risk_R + risk_H, 0.0, 1.0)
    precursor = np.clip(0.6 * risk_H + 0.4 * risk_R, 0.0, 1.0)

    upstream_factor = 1.0
    if precursor > conf_trigger:
        upstream_factor = 0.65
    elif precursor > reconn_trigger:
        upstream_factor = 0.80

    risk = np.clip(base_risk * upstream_factor, 0.0, 1.0)

    denom = max(conf_trigger - reconn_trigger, 1e-9)
    control_strength = np.clip((risk - reconn_trigger) / denom, 0.0, 1.0)

    return {
        "risk_R": float(risk_R),
        "risk_H": float(risk_H),
        "base_risk": float(base_risk),
        "precursor": float(precursor),
        "upstream_factor": float(upstream_factor),
        "risk": float(risk),
        "control_strength": float(control_strength),
        "B_used": float(B_T),
        "n_used": float(n),
        "Te_used": float(Te),
    }


def ctli_stability_metric(B_T, n_m3, Te_keV, control_strength):
    delta = current_sheet_thickness(B_T, n_m3, Te_keV)
    gamma0 = plasmoid_growth_rate(B_T, n_m3, delta)
    gamma_eff = gamma0 * (1.0 - 0.85 * control_strength)
    stability = 1.0 / (1.0 + gamma_eff / 1.0e8)

    return {
        "delta_m": delta,
        "gamma0": gamma0,
        "gamma_eff": gamma_eff,
        "stability": max(0.0, min(stability, 1.0)),
    }


def run_tct_controller(plasma, design, rng=None):
    ctrl_out = tct_controller(
        plasma,
        design["reconn_trigger"],
        design["conf_trigger"],
    )

    stability = ctli_stability_metric(
        ctrl_out["B_used"],
        ctrl_out["n_used"],
        ctrl_out["Te_used"],
        ctrl_out["control_strength"],
    )

    return {
        "engaged": ctrl_out["control_strength"] > 0.05,
        "control_strength": ctrl_out["control_strength"],
        "risk_R": ctrl_out["risk_R"],
        "risk_H": ctrl_out["risk_H"],
        "precursor": ctrl_out["precursor"],
        "upstream_factor": ctrl_out["upstream_factor"],
        "B_used": ctrl_out["B_used"],
        "n_used": ctrl_out["n_used"],
        "Te_used": ctrl_out["Te_used"],
        "stability": stability,
    }

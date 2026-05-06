import math
from .config import CONSTS

def plasma_volume(R, a, kappa):
    return 2.0 * (math.pi**2) * R * (a**2) * kappa

def first_wall_area(R, a):
    return 4.0 * (math.pi**2) * R * a

def greenwald_density(Ip_MA, a_m):
    return (Ip_MA / (math.pi * a_m * a_m)) * 1.0e20

def reactivity_dt_surrogate(T_kev):
    T = max(float(T_kev), 1e-9)
    return 5.0e-22 * (T**2) * math.exp(-19.94 / (T ** (1.0 / 3.0)))

def bootstrap_fraction(betaN, qstar, aspect_ratio):
    raw = 0.18 * betaN * max(0.4, min(aspect_ratio, 4.0)) / max(qstar, 1.2)
    return max(0.05, min(raw, 0.85))

def current_drive_power(Ip_MA, bootstrap_frac, cd_efficiency_MA_per_MW=0.18):
    required_MA = max(Ip_MA * (1.0 - bootstrap_frac), 0.0)
    return required_MA / max(cd_efficiency_MA_per_MW, 1e-6)

def evaluate_case(R_m, a_m, kappa, B0_T, Ip_MA, Ti_keV, Te_keV, H98, f_greenwald, frac_cap):
    V = plasma_volume(R_m, a_m, kappa)
    A_fw = first_wall_area(R_m, a_m)

    nG = greenwald_density(Ip_MA, a_m)
    ne = frac_cap * f_greenwald * nG
    sv = reactivity_dt_surrogate(Ti_keV)

    pfus_mw = (0.25 * ne**2 * sv * 17.6 * CONSTS.mev_j) * V / 1e6
    pbrem_mw = (5.35e-37 * ne**2 * math.sqrt(Te_keV * 1e3)) * V / 1e6

    Wth_density = 1.5 * (2.0 * ne * Ti_keV * 1e3) * CONSTS.e_charge
    tauE = H98 * 1.39
    ptr_mw = (Wth_density / tauE) * V / 1e6

    wn_mw_m2 = (0.8 * pfus_mw) / max(A_fw, 1e-12)

    p_pa = (2.0 * ne * Ti_keV * 1e3) * CONSTS.e_charge
    beta = (2.0 * CONSTS.mu0 * p_pa) / max(B0_T**2, 1e-12)
    betaN = 100.0 * beta * a_m * B0_T / max(Ip_MA, 1e-12)
    qstar = (5.0 * a_m**2 * B0_T) / max(R_m * Ip_MA, 1e-12) * (1.0 + kappa**2) / 2.0
    aspect_ratio = R_m / max(a_m, 1e-12)

    bstrap = bootstrap_fraction(betaN, qstar, aspect_ratio)
    pcd_mw = current_drive_power(Ip_MA, bstrap)

    return {
        "pfus_mw": pfus_mw,
        "pbrem_mw": pbrem_mw,
        "ptr_mw": ptr_mw,
        "wn_mw_m2": wn_mw_m2,
        "betaN": betaN,
        "qstar": qstar,
        "ne_m3": ne,
        "V_m3": V,
        "bootstrap_frac": bstrap,
        "current_drive_mw": pcd_mw,
        "aspect_ratio": aspect_ratio,
        "stored_energy_J": Wth_density * V,
        "B0_T": B0_T,
        "Te_keV": Te_keV,
    }

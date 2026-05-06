from .config import CONSTS

def magnet_stress_MPa(B0_T, R_m):
    magnetic_pressure = B0_T**2 / (2.0 * CONSTS.mu0)
    stress = magnetic_pressure * R_m
    return stress / 1e6

def engineering_penalty(plasma, plant, wall_temp_K, design, blanket=None):
    penalty = 0.0
    wall_limit = 10.0
    if plasma["wn_mw_m2"] > wall_limit:
        penalty += (plasma["wn_mw_m2"] - wall_limit) * 800.0

    stress = magnet_stress_MPa(design["B0"], design["R"])
    stress_limit = 700.0
    if stress > stress_limit:
        penalty += (stress - stress_limit) * 50.0

    if wall_temp_K > 1200.0:
        penalty += (wall_temp_K - 1200.0) * 2.0

    if plant["net_electric"] < 0.0:
        penalty += abs(plant["net_electric"]) * 10.0

    if blanket is not None:
        if blanket["TBR"] < 1.05:
            penalty += (1.05 - blanket["TBR"]) * 20000.0
        if blanket["front_heating_frac"] > 0.50:
            penalty += (blanket["front_heating_frac"] - 0.50) * 10000.0

    return penalty, stress

import math

def lithium_wall_temperature(heat_flux_mw_m2, thickness_m, conductivity_W_mK=84.0):
    q = heat_flux_mw_m2 * 1.0e6
    return q * thickness_m / max(conductivity_W_mK, 1e-9)

def hartmann_number(B_T, half_width_m, sigma_S_m, rho_kg_m3, nu_m2_s=1e-6):
    return B_T * half_width_m * math.sqrt(max(sigma_S_m / max(rho_kg_m3 * nu_m2_s, 1e-18), 1e-18))

def mhd_drag_power(B_T, velocity_m_s, conductivity_S_m, rho_kg_m3, half_width_m, wetted_area_m2=200.0):
    Ha = hartmann_number(B_T, half_width_m, conductivity_S_m, rho_kg_m3)
    pressure_drop = 0.5 * rho_kg_m3 * velocity_m_s**2 * (1.0 + 0.02 * Ha)
    volumetric_flow = velocity_m_s * 2.0 * half_width_m * wetted_area_m2
    power_W = pressure_drop * volumetric_flow
    return power_W / 1e6

def pumping_power_from_heat(thermal_power_mw, recirc_fraction=0.02):
    return thermal_power_mw * recirc_fraction

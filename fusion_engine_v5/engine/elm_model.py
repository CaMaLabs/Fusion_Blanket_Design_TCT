def simulate_elm(rng, plasma_energy_J, controller_strength):
    base_prob = 0.05
    if rng.random() > base_prob:
        return 0.0, False
    elm_fraction = rng.uniform(0.05, 0.15)
    elm_energy = plasma_energy_J * elm_fraction
    elm_energy *= (1.0 - 0.8 * controller_strength)
    strike_area_m2 = 10.0
    energy_density_MJ_m2 = elm_energy / strike_area_m2 / 1e6
    return energy_density_MJ_m2, True

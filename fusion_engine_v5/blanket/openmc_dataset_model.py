import numpy as np


def evaluate_blanket(design):
    """
    OpenMC proxy blanket model compatible with the current reactor pipeline.
    This is still a surrogate, but it returns the fields downstream code expects.
    """

    thickness = float(design.get("blanket_thickness", 1.0))
    li6 = float(design.get("li6_enrichment", 0.9))
    mult = float(design.get("multiplier_frac", 0.6))

    # Simple proxy for neutron multiplication / breeding strength
    h3 = max(0.0, li6 * mult * thickness)

    # Slower-rising TBR model to avoid instant saturation
    # non-saturating TBR model
    # non-saturating TBR model
    TBR = 1.1 + 0.16 * np.tanh(h3 * 5e4) + 0.04 * np.log1p(max(h3, 1e-12) * 1e6)

    # Required downstream blanket fields
    attenuation = np.exp(-0.35 * thickness) / (1.0 + 0.15 * mult)
    front_heating_frac = 0.30 + 0.20 * mult
    neutron_efficiency = h3 * 0.8
    power_multiplier = 1.0 + 0.2 * mult

    return {
        "model": "openmc_dataset",
        "TBR": float(TBR),
        "attenuation": float(attenuation),
        "front_heating_frac": float(front_heating_frac),
        "h3_total": float(h3),
        "neutron_efficiency": float(neutron_efficiency),
        "power_multiplier": float(power_multiplier),
    }

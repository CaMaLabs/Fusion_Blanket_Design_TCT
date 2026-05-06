import numpy as np

# -------------------------------------------------------------------
# Simplified neutron transport approximation
# (OpenMC-compatible placeholder if full MC is disabled)
# -------------------------------------------------------------------

def evaluate_blanket(thickness, li6_enrichment):
    """
    Estimate Tritium Breeding Ratio (TBR)

    thickness: blanket thickness (m)
    li6_enrichment: Li6 fraction
    """

    # neutron multiplication factor
    neutron_mult = 1.1 + 0.15 * thickness

    # Li6 absorption efficiency
    breeding_eff = 0.6 + 0.8 * li6_enrichment

    # leakage losses
    leakage = np.exp(-1.5 * thickness)

    # simplified TBR estimate
    tbr = neutron_mult * breeding_eff * (1 - leakage)

    # clamp physically realistic values
    tbr = max(0.5, min(tbr, 1.4))

    return float(tbr)

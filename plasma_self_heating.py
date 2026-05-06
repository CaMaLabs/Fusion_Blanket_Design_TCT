import math

# physical constants
MEV = 1.602e-13
ALPHA_ENERGY = 3.5 * MEV


def alpha_heating_power(pfus):

    """
    3.5 MeV alpha particles carry ~20% of DT energy
    """

    return 0.2 * pfus


def bootstrap_fraction(betaN):

    """
    bootstrap current fraction approximation
    """

    frac = 0.04 * betaN

    return max(0.0, min(frac, 0.9))


def plasma_equilibrium(plasma):

    """
    Solve simple power balance with alpha heating
    """

    pfus = plasma["pfus"]
    pbrem = plasma["pbrem"]
    ptr = plasma["ptr"]

    alpha = alpha_heating_power(pfus)

    heating = alpha

    losses = pbrem + ptr

    gain = heating - losses

    return {

        "alpha": alpha,
        "gain": gain
    }

import numpy as np


def current_sheet_thickness(B, n, Te):

    """
    Estimate reconnection current sheet thickness.
    """

    mu0 = 4*np.pi*1e-7
    me = 9.11e-31
    e = 1.602e-19

    wpe = np.sqrt((n*e**2)/(me*8.85e-12))

    de = 3e8 / wpe

    beta = (2*n*Te*1.602e-19)/(B**2/(2*mu0))

    delta = de * (1 + beta)

    return delta


def plasmoid_growth_rate(B, n, delta):

    """
    Simplified tearing mode / plasmoid growth scaling.
    """

    mu0 = 4*np.pi*1e-7

    VA = B / np.sqrt(mu0*n*2.5e-27)

    gamma = VA / delta

    return gamma


def tct_stability_metric(B, n, Te):

    delta = current_sheet_thickness(B,n,Te)

    gamma = plasmoid_growth_rate(B,n,delta)

    stability = 1 / (1 + gamma)

    return stability

import math
import numpy as np


def reactivity_dt(T):

    return 5e-22 * (T**2) * math.exp(-19.94 / (T**(1/3)))


def plasma_power(R, a, kappa, B0, Ip, Ti, Te, H98, fG):

    # plasma volume
    V = 2 * (math.pi**2) * R * (a**2) * kappa

    # surface area
    A = 4 * (math.pi**2) * R * a

    # Greenwald density
    nG = (Ip / (math.pi * a * a)) * 1e20

    ne = fG * nG

    # fusion reactivity
    sv = reactivity_dt(Ti)

    pfus = 0.25 * (ne**2) * sv * 17.6 * 1.602e-13 * V / 1e6

    # bremsstrahlung loss
    pbrem = 5.35e-37 * (ne**2) * (Te * 1e3)**0.5 * V / 1e6

    # plasma stored energy density
    W = 1.5 * (2 * ne * Ti * 1e3) * 1.602e-19

    tau = H98 * 1.39

    ptr = (W / tau) * V / 1e6

    # neutron wall load
    wall_load = (0.8 * pfus) / A

    # plasma beta
    beta = (2 * ne * Ti * 1e3 * 1.602e-19) / (B0**2 / (2 * 4e-7 * np.pi))

    # normalized beta
    betaN = beta * (Ip / (a * B0))

    return {
        "pfus": pfus,
        "pbrem": pbrem,
        "ptr": ptr,
        "wall": wall_load,
        "betaN": betaN
    }

import numpy as np
import cupy as cp
import math

from tct_sim_reactor_full import robustness_monte_carlo, base_params

def wall_area(R,a):
    return 4.0 * (math.pi**2) * R * a

def lithium_wall_temp(heat_flux, thickness):

    k_li = 84.0

    return float(cp.asarray(heat_flux) * thickness / k_li)


def plasma_stage(params):

    summary, _, _, _, _ = robustness_monte_carlo_TCT_v8(
        base_params=params,
        N=5000
    )

    return summary


def wall_stage(params, plasma):

    pfus = plasma["pnet_p50"]

    A = wall_area(params["R_m"],params["a_m"])

    heat_flux = 0.2 * pfus / A

    wall_temp = lithium_wall_temp(
        heat_flux,
        params["liquid_wall"]
    )

    return {
        "heat_flux":heat_flux,
        "wall_temp":wall_temp
    }


def structural_penalty(metrics):

    penalty = 0

    if metrics["heat_flux"] > 20:
        penalty += 10

    if metrics["wall_temp"] > 1200:
        penalty += 10

    return penalty


def evaluate_reactor(design):

    plasma = plasma_stage(design)

    wall = wall_stage(design,plasma)

    penalty = structural_penalty(wall)

    score = (
        plasma["fail_pnet_rate"]
        + penalty
        - plasma["pnet_p50"]*1e-4
    )

    return score

import math
import random
import numpy as np
import pandas as pd


#############################################
# Plasma physics model
#############################################

def volume(R, a, kappa):
    return 2.0 * (math.pi ** 2) * R * (a ** 2) * kappa


def first_wall_area(R, a):
    return 4.0 * (math.pi ** 2) * R * a


def greenwald(Ip_MA, a):
    return (Ip_MA / (math.pi * a * a)) * 1e20


def reactivity_dt(T):
    T = max(T, 1e-6)
    return 5e-22 * (T ** 2) * math.exp(-19.94 / (T ** (1 / 3)))


def evaluate_plasma(params):

    R = params["R"]
    a = params["a"]
    kappa = params["kappa"]
    B0 = params["B0"]
    Ip = params["Ip"]

    Ti = params["Ti"]
    Te = params["Te"]

    H98 = params["H98"]
    fG = params["f_greenwald"]

    V = volume(R, a, kappa)
    A = first_wall_area(R, a)

    nG = greenwald(Ip, a)
    ne = fG * nG

    sv = reactivity_dt(Ti)

    pfus = 0.25 * ne**2 * sv * 17.6 * 1.602e-13 * V / 1e6

    pbrem = 5.35e-37 * ne**2 * math.sqrt(Te * 1e3) * V / 1e6

    W = 1.5 * (2 * ne * Ti * 1e3) * 1.602e-19
    tau = H98 * 1.39

    ptr = (W / tau) * V / 1e6

    heat_wall = (0.8 * pfus) / A

    p_pa = (2 * ne * Ti * 1e3) * 1.602e-19

    beta = (2 * 4e-7 * math.pi * p_pa) / (B0**2)
    betaN = 100 * beta * a * B0 / Ip

    return {
        "pfus": pfus,
        "pbrem": pbrem,
        "ptr": ptr,
        "wall_load": heat_wall,
        "betaN": betaN,
        "ne": ne,
        "V": V,
    }


#############################################
# Liquid wall model
#############################################

def liquid_wall_model(thickness_mm, heat_flux):

    thickness_m = thickness_mm / 1000.0

    protection = 1 - math.exp(-thickness_m * 800)

    heat_limit = 10.0

    damage = max(0.0, (heat_flux - heat_limit) / heat_limit)

    return protection, damage


#############################################
# Tritium breeding approximation
#############################################

def tritium_breeding(blanket_thickness, li6_enrichment):

    tbr = 0.9 + 0.35 * (1 - math.exp(-blanket_thickness / 0.6))

    tbr *= (0.8 + 0.4 * li6_enrichment)

    return tbr


#############################################
# TCT Monte-Carlo stability model
#############################################

def monte_carlo_reactor(params, N=10000):

    plasma = evaluate_plasma(params)

    pfus0 = plasma["pfus"]
    pbrem0 = plasma["pbrem"]
    ptr0 = plasma["ptr"]
    wall_load = plasma["wall_load"]

    protection, damage_wall = liquid_wall_model(
        params["wall_thickness"],
        wall_load
    )

    tbr = tritium_breeding(
        params["blanket_thickness"],
        params["li6_enrichment"]
    )

    pnet_samples = []

    fail = 0
    wall_damage = 0

    for _ in range(N):

        H_mult = random.uniform(0.7, 1.05)
        reconnection = random.uniform(1.0, 2.5)

        burst = random.random() < 0.08

        burst_mult = 1.8 if burst else 1.0

        pfus = pfus0 * random.uniform(0.7, 1.0)

        losses = (
            pbrem0 * burst_mult
            + ptr0 / H_mult
            + 558 * reconnection
        )

        pnet = pfus - losses

        if burst:
            if random.random() > protection:
                wall_damage += 1

        if pnet < 0:
            fail += 1

        pnet_samples.append(pnet)

    pnet_samples = np.array(pnet_samples)

    return {
        "p50": np.median(pnet_samples),
        "fail_rate": fail / N,
        "wall_damage_rate": wall_damage / N,
        "TBR": tbr,
    }


#############################################
# Reactor optimizer
#############################################

POP = 30
GEN = 20


def random_design():

    return {
        "R": random.uniform(7.5, 9.0),
        "a": random.uniform(2.0, 3.0),
        "kappa": random.uniform(1.7, 2.2),
        "B0": random.uniform(5.5, 7.5),
        "Ip": random.uniform(18, 26),

        "Ti": random.uniform(25, 45),
        "Te": random.uniform(12, 18),

        "H98": random.uniform(1.0, 1.3),
        "f_greenwald": random.uniform(0.5, 0.8),

        "wall_thickness": random.uniform(0.5, 3.0),
        "blanket_thickness": random.uniform(0.6, 1.5),
        "li6_enrichment": random.uniform(0.3, 0.9),
    }


def mutate(d):

    child = dict(d)

    k = random.choice(list(child.keys()))

    child[k] *= random.uniform(0.9, 1.1)

    return child


def score(d):

    res = monte_carlo_reactor(d, 8000)

    penalty = 0

    if res["TBR"] < 1.15:
        penalty += 10

    score = (
        res["fail_rate"]
        + res["wall_damage_rate"]
        - res["p50"] * 1e-4
        + penalty
    )

    return score, res


def run_optimizer():

    pop = [random_design() for _ in range(POP)]

    best_rows = []

    for g in range(GEN):

        print("\n===== GENERATION", g, "=====")

        scored = []

        for d in pop:

            s, res = score(d)

            scored.append((s, d, res))

            print(
                "score:", round(s,4),
                "p50:", round(res["p50"],1),
                "fail:", round(res["fail_rate"],3),
                "damage:", round(res["wall_damage_rate"],3),
                "TBR:", round(res["TBR"],2),
            )

        scored.sort(key=lambda x: x[0])

        best = scored[0]

        print("\nBEST SCORE:", best[0])

        best_rows.append(best[2])

        elites = [x[1] for x in scored[:8]]

        new = elites.copy()

        while len(new) < POP:
            new.append(mutate(random.choice(elites)))

        pop = new

    df = pd.DataFrame(best_rows)

    df.to_csv("tct_reactor_designs.csv", index=False)

    print("\nOptimization complete.")
    print("Results written to tct_reactor_designs.csv")


if __name__ == "__main__":
    run_optimizer()

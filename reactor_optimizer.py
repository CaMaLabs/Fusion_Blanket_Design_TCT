import random
import pandas as pd

from tct_sim_reactor_full import robustness_monte_carlo, base_params


POP_SIZE = 24
GENERATIONS = 20
MC_SAMPLES = 8000


def random_design():
    d = dict(base_params)

    d["Ti_keV"] = random.uniform(20, 35)
    d["Te_keV"] = random.uniform(10, 20)

    d["H98"] = random.uniform(1.0, 1.35)

    d["f_greenwald"] = random.uniform(0.7, 0.95)

    d["reconn_trigger"] = random.uniform(0.60, 0.70)
    d["conf_trigger"] = random.uniform(0.60, 0.70)

    return d


def mutate(design):
    child = dict(design)

    key = random.choice(list(child.keys()))

    if isinstance(child[key], float):
        child[key] *= random.uniform(0.9, 1.1)

    return child


def score_design(design):

    plasma_params = dict(base_params)

    plasma_params["Ti_keV"] = design["Ti_keV"]
    plasma_params["Te_keV"] = design["Te_keV"]
    plasma_params["H98"] = design["H98"]
    plasma_params["f_greenwald"] = design["f_greenwald"]

    summary, _ = robustness_monte_carlo(
        plasma_params,
        N=MC_SAMPLES,
        reconn_trigger=design["reconn_trigger"],
        conf_trigger=design["conf_trigger"]
    )

    score = (
        summary["fail_rate"]
        + summary["wall_damage_rate"]
        - summary["pnet_p50"] * 1e-4
    )

    return score, summary

def run_optimizer():

    population = [random_design() for _ in range(POP_SIZE)]

    best_rows = []

    for gen in range(GENERATIONS):

        scored = []

        print("\n===== GENERATION", gen, "=====")

        for design in population:

            score, summary = score_design(design)

            scored.append((score, design, summary))

            print(
                "score:",
                round(score, 4),
                "p50:",
                round(summary["pnet_p50"], 2),
                "fail:",
                round(summary["fail_rate"], 3),
                "damage:",
                round(summary["wall_damage_rate"], 3)
            )

        scored.sort(key=lambda x: x[0])

        best_score, best_design, best_summary = scored[0]

        print("\nBEST DESIGN SCORE:", best_score)

        best_rows.append(best_summary)

        elites = [x[1] for x in scored[:8]]

        new_population = elites.copy()

        while len(new_population) < POP_SIZE:
            parent = random.choice(elites)
            new_population.append(mutate(parent))

        population = new_population

    df = pd.DataFrame(best_rows)

    df.to_csv("reactor_design_search.csv", index=False)

    print("\nOptimization complete.")
    print("Results written to reactor_design_search.csv")


if __name__ == "__main__":
    run_optimizer()

from multiprocessing import Pool, cpu_count
import pandas as pd

from ..engine.config import POP_SIZE, GENERATIONS, ELITE_KEEP, VALIDATION_TOP_N
from ..engine.reactor_simulation import simulate_reactor
from ..blanket.material_learning import MaterialLearner
from ..blanket.materials_db import BLANKET_CANDIDATES
from .genome import random_design
from .mutation import mutate
from .crossover import crossover

def _evaluate_surrogate(design):
    result = simulate_reactor(design, blanket_validate=False)
    result["design"] = design
    result["validated"] = False
    return result

def _evaluate_validated(design):
    result = simulate_reactor(design, blanket_validate=True)
    result["design"] = design
    result["validated"] = True
    return result

def optimize():
    learner = MaterialLearner(BLANKET_CANDIDATES)
    population = [random_design(learner.weights) for _ in range(POP_SIZE)]
    history = []

    for gen in range(GENERATIONS):
        print(f"GEN {gen}")
        with Pool(cpu_count()) as pool:
            results = pool.map(_evaluate_surrogate, population)

        results.sort(key=lambda r: r["score"], reverse=True)
        validate_designs = [r["design"] for r in results[:VALIDATION_TOP_N]]

        with Pool(min(cpu_count(), VALIDATION_TOP_N)) as pool:
            validated = pool.map(_evaluate_validated, validate_designs)

        validated.sort(key=lambda r: r["score"], reverse=True)
        merged = validated + results[VALIDATION_TOP_N:]
        merged.sort(key=lambda r: r["score"], reverse=True)

        best = merged[0]
        print("BEST", {
            "score": round(best["score"], 3),
            "net_electric": round(best["net_electric"], 3),
            "TBR": round(best["TBR"], 3),
            "fail_rate": round(best["fail_rate"], 6),
            "validated": best["validated"],
            "blanket_model": best["blanket_model"],
            "attenuation": round(best["blanket_attenuation"], 6),
            "front_heat": round(best["blanket_front_heating_frac"], 6),
        })

        history.append({k: best[k] for k in best if k != "design"})
        learner.update(merged[:10])

        elites = [r["design"] for r in merged[:ELITE_KEEP]]
        new_population = elites.copy()
        while len(new_population) < POP_SIZE:
            if len(elites) >= 2:
                child = crossover(elites[0], elites[1])
                child = mutate(child, learner.weights)
            else:
                child = mutate(elites[0], learner.weights)
            new_population.append(child)
        population = new_population

    pd.DataFrame(history).to_csv("reactor_design_history_v5.csv", index=False)
    print("Wrote reactor_design_history_v5.csv")

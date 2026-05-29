import csv
import json
import traceback
import math
import os
import random
import multiprocessing as mp
from copy import deepcopy
from pathlib import Path

mp.set_start_method("spawn", force=True)

from fusion_engine_v5.optimizer.genome import random_design
from fusion_engine_v5.engine.reactor_simulation import simulate_reactor

OUTDIR = Path("evo_reactor_runs")
OUTDIR.mkdir(exist_ok=True)

POP_SIZE = 48
GENERATIONS = 30
ELITES = 12
RANDOM_INJECT = 12
MUTATION_RATE = 0.45
MUTATION_SCALE = 0.25
SEED = 1337
WORKERS = max(1, (os.cpu_count() or 2) - 1)

random.seed(SEED)

BOUNDS = {
    "R": (4.0, 12.0),
    "a": (1.2, 2.8),
    "kappa": (1.4, 2.6),
    "B0": (4.0, 9.5),
    "Ip": (8.0, 30.0),
    "Ti": (8.0, 40.0),
    "Te": (6.0, 30.0),
    "H98": (0.85, 1.5),
    "fG": (0.35, 1.0),
    "frac_cap": (0.05, 0.95),
    "lithium_thickness": (0.0005, 0.03),
    "blanket_thickness": (0.4, 1.6),
    "lithium_velocity": (0.2, 6.0),
    "mc_samples": (50000, 300000),
}

OBJECTIVES = {
    # maximize
    "net_electric": "max",
    "bootstrap": "max",
    "TBR": "max",
    # minimize
    "wall_load": "min",
    "capex_billion": "min",
    "R": "min",
    "B0": "min",
}

HARD_LIMITS = {
    "TBR_min": 1.02,
    "wall_load_max": 20.0,
    "capex_max": 60.0,
    "net_electric_min": 200.0,
    "net_electric_max": 20000.0,
}


def clamp_value(key, value):
    if key not in BOUNDS:
        return value
    lo, hi = BOUNDS[key]
    if key == "mc_samples":
        return int(max(lo, min(hi, int(value))))
    return max(lo, min(hi, float(value)))


def sanitize_design(d):
    out = deepcopy(d)
    for k, v in list(out.items()):
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                v = random_design().get(k, 1.0)
            out[k] = clamp_value(k, v)
    return out


def crossover(a, b):
    child = {}
    keys = set(a.keys()) | set(b.keys())
    for k in keys:
        av = a.get(k)
        bv = b.get(k)
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            t = random.random()
            val = av * t + bv * (1.0 - t)
            child[k] = clamp_value(k, val)
        else:
            child[k] = deepcopy(av if random.random() < 0.5 else bv)
    return sanitize_design(child)


def mutate(d, mutation_scale=MUTATION_SCALE):
    child = deepcopy(d)

    for k, v in list(child.items()):
        if not isinstance(v, (int, float)):
            continue
        if random.random() > MUTATION_RATE:
            continue

        if k in BOUNDS:
            lo, hi = BOUNDS[k]
            span = hi - lo
            sigma = mutation_scale * span
            nv = float(v) + random.gauss(0.0, sigma)
            child[k] = clamp_value(k, nv)
        else:
            scale = max(abs(float(v)), 1.0)
            nv = float(v) + random.gauss(0.0, mutation_scale * scale)
            child[k] = nv

    # directed mutation toward coupled regime discovery
    if "lithium_thickness" in child and random.random() < 0.40:
        child["lithium_thickness"] = clamp_value(
            "lithium_thickness",
            child["lithium_thickness"] + abs(random.gauss(0.002, 0.004)),
        )

    if "lithium_velocity" in child and random.random() < 0.30:
        child["lithium_velocity"] = clamp_value(
            "lithium_velocity",
            child["lithium_velocity"] + abs(random.gauss(0.3, 0.8)),
        )

    if "B0" in child and random.random() < 0.25:
        child["B0"] = clamp_value(
            "B0",
            child["B0"] + abs(random.gauss(0.15, 0.35)),
        )

    if "R" in child and random.random() < 0.25:
        child["R"] = clamp_value(
            "R",
            child["R"] - abs(random.gauss(0.15, 0.35)),
        )

    if "blanket_thickness" in child and random.random() < 0.30:
        child["blanket_thickness"] = clamp_value(
            "blanket_thickness",
            child["blanket_thickness"] + abs(random.gauss(0.08, 0.20)),
        )
    return sanitize_design(child)


def evaluate(d):
    d = sanitize_design(d)

    try:
        r = simulate_reactor(d)
        base_score = float(r.get("score", -1e18))

        # --- TCT reward: useful mid-range control, penalize pegged saturation ---
        tct_strength = float(r.get("tct_control_strength", 0.0) or 0.0)
        tct_precursor = float(r.get("tct_precursor", 0.0) or 0.0)

        tct_bonus = 0.0
        if 0.05 < tct_strength < 0.85:
            tct_bonus += 0.5
        if tct_strength > 0.95:
            tct_bonus -= 0.8
        if tct_precursor < 0.5:
            tct_bonus += 0.5
        if tct_precursor > 0.95:
            tct_bonus -= 0.5

        # --- lithium wall reward ---
        li_mult = float(r.get("lithium_wall_modifier", 1.0) or 1.0)
        wall = float(r.get("wall_load", 1e9) or 1e9)
        raw_wall = float(r.get("raw_wall_load", wall) or wall)

        li_bonus = 0.0
        if li_mult > 1.0:
            li_bonus += min(li_mult - 1.0, 0.8)
        if raw_wall > wall:
            li_bonus += min(raw_wall - wall, 5.0) * 0.1
        if wall < 6.0:
            li_bonus += 0.2

        # --- TBR exploration pressure ---
        tbr = float(r.get("TBR", 0.0) or 0.0)
        tbr_bonus = 0.0
        if tbr > 1.15:
            tbr_bonus += (tbr - 1.15) * 120.0
        if tbr > 1.30:
            tbr_bonus += (tbr - 1.30) * 200.0

        wall_penalty = 0.0
        if wall > 8.0:
            wall_penalty += (wall - 8.0) * 80.0
        if wall > 12.0:
            wall_penalty += (wall - 12.0) * 200.0

        score = base_score + tct_bonus + li_bonus + tbr_bonus - wall_penalty

        result = {
            "ok": True,
            "design": d,
            "result": r,
            "score": float(score),
            "R": float(r.get("annual_revenue_musd", 0.0)),
        }
        result["objectives"] = extract_objectives(result)
        result["feasible"] = is_feasible(result)

        if not result["feasible"]:
            result["score"] = -1e12

        return result

    except Exception as e:
        return {
            "ok": False,
            "design": d,
            "result": {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "R": -1e18,
            },
            "score": -1e18,
            "feasible": False,
            "objectives": {
                "net_electric": -1e18,
                "wall_load": 1e18,
                "raw_wall_load": 1e18,
                "TBR": 0.0,
                "capex_billion": 1e18,
                "bootstrap": 0.0,
            },
            "crowding": 0.0,
            "rank": 9999,
        }


def is_feasible(item):
    if not item.get("ok", False):
        return False

    try:
        r = item["result"]
        tbr = float(r.get("TBR", 0.0))
        wl = float(r.get("wall_load", 1e9))
        capex = float(r.get("capex_billion", 1e9))
        net = float(r.get("net_electric", -1e9))

        if tbr < HARD_LIMITS["TBR_min"]:
            return False
        if wl > HARD_LIMITS["wall_load_max"]:
            return False
        if capex > HARD_LIMITS["capex_max"]:
            return False
        if net < HARD_LIMITS["net_electric_min"]:
            return False
        if net > HARD_LIMITS["net_electric_max"]:
            return False

        return True
    except Exception:
        return False


def extract_objectives(item):
    r = item.get("result", {})
    d = item.get("design", {})

    defaults = {
        "net_electric": -1e18,
        "wall_load": 1e18,
        "raw_wall_load": 1e18,
        "TBR": 0.0,
        "capex_billion": 1e18,
        "bootstrap": 0.0,
        "R": 0.0,
        "a": 1e18,
        "B0": 1e18,
        "kappa": 1e18,
        "Ip": 1e18,
        "Ti": 1e18,
        "Te": 1e18,
        "H98": 1e18,
        "fG": 1e18,
        "frac_cap": 1e18,
        "lithium_thickness": 1e18,
        "blanket_thickness": 1e18,
        "lithium_velocity": 1e18,
        "reconn_trigger": 1e18,
        "conf_trigger": 1e18,
    }

    out = {}
    for key in OBJECTIVES.keys():
        if key == "R":
            val = r.get("R", r.get("annual_revenue_musd", 0.0))
        elif key in r:
            val = r.get(key, defaults.get(key, 1e18))
        elif key in d:
            val = d.get(key, defaults.get(key, 1e18))
        else:
            val = defaults.get(key, 1e18)

        try:
            out[key] = float(val)
        except Exception:
            out[key] = float(defaults.get(key, 1e18))

    return out


def dominates(a, b):
    if a.get("feasible") and not b.get("feasible"):
        return True
    if not a.get("feasible") and b.get("feasible"):
        return False

    ao = a.get("objectives", {})
    bo = b.get("objectives", {})

    maximize_keys = {"R", "bootstrap", "TBR", "net_electric"}

    better_or_equal = True
    strictly_better = False

    for key, direction in OBJECTIVES.items():
        if key in maximize_keys or direction == "max":
            av = ao.get(key, 0.0)
            bv = bo.get(key, 0.0)
            if av < bv:
                better_or_equal = False
                break
            if av > bv:
                strictly_better = True
        else:
            av = ao.get(key, 1e18)
            bv = bo.get(key, 1e18)
            if av > bv:
                better_or_equal = False
                break
            if av < bv:
                strictly_better = True

    return better_or_equal and strictly_better


def non_dominated_sort(population):
    fronts = []
    S = {}
    n = {}
    first_front = []

    for i, p in enumerate(population):
        S[i] = []
        n[i] = 0
        p["rank"] = 9999
        p["crowding"] = 0.0
        for j, q in enumerate(population):
            if i == j:
                continue
            if dominates(p, q):
                S[i].append(j)
            elif dominates(q, p):
                n[i] += 1
        if n[i] == 0:
            p["rank"] = 0
            first_front.append(i)

    current = first_front
    rank = 0
    while current:
        fronts.append(current)
        next_front = []
        for i in current:
            for j in S[i]:
                n[j] -= 1
                if n[j] == 0:
                    population[j]["rank"] = rank + 1
                    next_front.append(j)
        rank += 1
        current = next_front

    return fronts


def crowding_distance(population, front):
    if not front:
        return []

    maximize_keys = {"R", "bootstrap", "TBR", "net_electric"}

    def get_obj(idx, key):
        obj = population[idx].get("objectives", {})
        if key in maximize_keys:
            return obj.get(key, 0.0)
        return obj.get(key, 1e18)

    n = len(front)
    distance = [0.0] * n

    if n <= 2:
        distance = [float("inf")] * n
        for idx, dist in zip(front, distance):
            population[idx]["crowding"] = dist
        return distance

    for key, direction in OBJECTIVES.items():
        front_sorted = sorted(front, key=lambda idx: get_obj(idx, key))
        values = [get_obj(idx, key) for idx in front_sorted]

        vmin = min(values)
        vmax = max(values)

        # boundaries always get infinite crowding distance
        distance[front.index(front_sorted[0])] = float("inf")
        distance[front.index(front_sorted[-1])] = float("inf")

        if vmax == vmin:
            continue

        for i in range(1, n - 1):
            prev_v = get_obj(front_sorted[i - 1], key)
            next_v = get_obj(front_sorted[i + 1], key)
            norm = (next_v - prev_v) / (vmax - vmin)

            pos = front.index(front_sorted[i])
            if distance[pos] != float("inf"):
                distance[pos] += norm

    for idx, dist in zip(front, distance):
        population[idx]["crowding"] = dist

    return distance


def pareto_select(population, target_size):
    fronts = non_dominated_sort(population)
    selected = []

    for front in fronts:
        crowding_distance(population, front)
        front_items = [population[i] for i in front]
        if len(selected) + len(front_items) <= target_size:
            selected.extend(front_items)
        else:
            front_items.sort(key=lambda x: x.get("crowding", 0.0), reverse=True)
            remaining = target_size - len(selected)
            selected.extend(front_items[:remaining])
            break

    return selected


def tournament(pop, k=4):
    picks = random.sample(pop, k=min(k, len(pop)))
    picks.sort(key=lambda x: (x.get("rank", 1e9), -x.get("crowding", 0.0)))
    return picks[0]


def save_generation(gen, ranked):
    gen_dir = OUTDIR / f"gen_{gen:03d}"
    gen_dir.mkdir(exist_ok=True)

    for i, item in enumerate(ranked[:10], 1):
        with open(gen_dir / f"reactor_{i:02d}.json", "w") as f:
            json.dump(item, f, indent=2)

    pareto_items = [x for x in ranked if x.get("rank", 9999) == 0]
    with open(gen_dir / "pareto_front.json", "w") as f:
        json.dump(pareto_items, f, indent=2)

    rows = []
    for i, item in enumerate(ranked[:25], 1):
        row = {
            "rank_order": i,
            "pareto_rank": item.get("rank"),
            "crowding": item.get("crowding"),
            "score": item.get("score"),
            "ok": item.get("ok"),
            "feasible": item.get("feasible"),
        }
        row.update(
            {
                f"design_{k}": v
                for k, v in item["design"].items()
                if isinstance(v, (int, float, str, bool))
            }
        )
        if isinstance(item["result"], dict):
            row.update(
                {
                    f"result_{k}": v
                    for k, v in item["result"].items()
                    if isinstance(v, (int, float, str, bool))
                }
            )
        rows.append(row)

    if rows:
        with open(gen_dir / "leaderboard.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def log_summary(gen, ranked):
    best_score = max(ranked, key=lambda x: x.get("score", -1e18))
    pareto_front = [x for x in ranked if x.get("rank", 9999) == 0]
    best_power = max(ranked, key=lambda x: x["objectives"]["net_electric"])
    best_low_capex = min(
        [x for x in ranked if x.get("feasible")],
        key=lambda x: x["objectives"]["capex_billion"],
        default=min(ranked, key=lambda x: x["objectives"]["capex_billion"]),
    )

    b = best_score
    print(
        f"GEN {gen:03d} | "
        f"front={len(pareto_front)} | "
        f"bestScore={b.get('score', None):.3f} | "
        f"P={b['result'].get('net_electric', None)} | "
        f"WL={b['result'].get('wall_load', None)} | "
        f"TBR={b['result'].get('TBR', None)} | "
        f"BS={b['result'].get('bootstrap', None)} | "
        f"CAPEX={b['result'].get('capex_billion', None)} | "
        f"R={b['design'].get('R', None)} "
        f"B0={b['design'].get('B0', None)} "
        f"lt={b['design'].get('lithium_thickness', None)} "
        f"bt={b['design'].get('blanket_thickness', None)}"
    )

    print(
        f"  Pareto-best-power: P={best_power['result'].get('net_electric', None)} "
        f"WL={best_power['result'].get('wall_load', None)} "
        f"TBR={best_power['result'].get('TBR', None)} "
        f"CAPEX={best_power['result'].get('capex_billion', None)} "
        f"R={best_power['design'].get('R', None)} "
        f"B0={best_power['design'].get('B0', None)}"
    )

    print(
        f"  Pareto-low-capex: P={best_low_capex['result'].get('net_electric', None)} "
        f"WL={best_low_capex['result'].get('wall_load', None)} "
        f"TBR={best_low_capex['result'].get('TBR', None)} "
        f"CAPEX={best_low_capex['result'].get('capex_billion', None)} "
        f"R={best_low_capex['design'].get('R', None)} "
        f"B0={best_low_capex['design'].get('B0', None)}"
    )


def main():
    mutation_scale = MUTATION_SCALE
    population = [sanitize_design(random_design()) for _ in range(POP_SIZE)]
    history = []

    for gen in range(GENERATIONS):
        if gen > 0 and gen % 10 == 0:
            mutation_scale = min(mutation_scale * 1.15, 0.6)

        with mp.Pool(WORKERS) as pool:
            evaluated = pool.map(evaluate, population)

        feasible_count = sum(1 for x in evaluated if x.get("feasible"))
        print(f"GEN {gen:03d} | feasible={feasible_count}/{len(evaluated)}")

        if feasible_count == 0:
            shown = 0
            for x in evaluated:
                if not x.get("ok", False):
                    print("EVAL_ERROR:", x.get("result", {}).get("error"))
                    tb = x.get("result", {}).get("traceback", "")
                    if tb:
                        print(tb.splitlines()[-8:])
                    shown += 1
                    if shown >= 3:
                        break

        selected = pareto_select(evaluated, len(evaluated))

        if not selected:
            print(f"GEN {gen:03d} | no feasible candidates, reseeding")
            population = [sanitize_design(random_design()) for _ in range(POP_SIZE)]
            continue

        # --- anti-collapse diversity filter ---
        unique_keys = set()
        diverse = []

        for x in selected:
            r = x.get("result", {})
            key = (
                round(float(r.get("net_electric", 0.0)), -2),
                round(float(r.get("wall_load", 0.0)), 1),
                round(float(r.get("TBR", 0.0)), 3),
                round(float(r.get("capex_billion", 0.0)), 1),
            )
            if key not in unique_keys:
                unique_keys.add(key)
                diverse.append(x)

        selected = diverse

        selected.sort(key=lambda x: (x.get("rank", 1e9), -x.get("crowding", 0.0), -x.get("score", -1e18)))

        best_score = max(selected, key=lambda x: x.get("score", -1e18))
        pareto_front = [x for x in selected if x.get("rank", 9999) == 0]

        history.append(
            {
                "generation": gen,
                "front_size": len(pareto_front),
                "best_score": best_score["score"],
                "net_electric": best_score["result"].get("net_electric"),
                "wall_load": best_score["result"].get("wall_load"),
                "raw_wall_load": best_score["result"].get("raw_wall_load"),
                "bootstrap": best_score["result"].get("bootstrap"),
                "TBR": best_score["result"].get("TBR"),
                "capex_billion": best_score["result"].get("capex_billion"),
                "R": best_score["design"].get("R"),
                "B0": best_score["design"].get("B0"),
                "lithium_thickness": best_score["design"].get("lithium_thickness"),
                "blanket_thickness": best_score["design"].get("blanket_thickness"),
                "mutation_scale": mutation_scale,
            }
        )

        log_summary(gen, selected)
        save_generation(gen, selected)

        elites = [deepcopy(x["design"]) for x in selected[:ELITES]]
        front_designs = [deepcopy(x["design"]) for x in pareto_front[:max(4, min(12, len(pareto_front)))]]

        new_population = []
        new_population.extend(elites)
        new_population.extend(front_designs)

        for _ in range(RANDOM_INJECT):
            new_population.append(sanitize_design(random_design()))

        breeding_pool = selected[:max(20, len(selected) // 2)]

        while len(new_population) < POP_SIZE:
            p1 = tournament(breeding_pool)["design"]
            p2 = tournament(breeding_pool)["design"]
            child = crossover(p1, p2)
            child = mutate(child, mutation_scale)
            new_population.append(child)

        population = new_population[:POP_SIZE]

    if history:
        with open(OUTDIR / "history.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=history[0].keys())
            writer.writeheader()
            writer.writerows(history)
    else:
        print("No feasible results collected — skipping CSV write.")

    all_front = []
    for gen_dir in sorted(OUTDIR.glob("gen_*")):
        fp = gen_dir / "pareto_front.json"
        if fp.exists():
            with open(fp) as f:
                all_front.extend(json.load(f))

    # dedupe approximate duplicates by rounded core metrics
    seen = set()
    unique_front = []
    for item in all_front:
        r = item.get("result", {})
        d = item.get("design", {})
        key = (
            round(float(r.get("net_electric", -9999)), 1),
            round(float(r.get("wall_load", 9999)), 3),
            round(float(r.get("TBR", -9999)), 3),
            round(float(r.get("capex_billion", 9999)), 3),
            round(float(d.get("R", 9999)), 3),
            round(float(d.get("B0", 9999)), 3),
        )
        if key not in seen:
            seen.add(key)
            unique_front.append(item)

    # rank combined front again
    for item in unique_front:
        item["feasible"] = is_feasible(item)
        item["objectives"] = extract_objectives(item)
    combined = pareto_select(unique_front, len(unique_front))
    combined.sort(key=lambda x: (x.get("rank", 1e9), -x.get("crowding", 0.0), -x.get("score", -1e18)))

    with open(OUTDIR / "pareto_front.json", "w") as f:
        json.dump([x for x in combined if x.get("rank", 9999) == 0], f, indent=2)

    if combined:
        best_score = max(combined, key=lambda x: x.get("score", -1e18))
        with open(OUTDIR / "best_overall.json", "w") as f:
            json.dump(best_score, f, indent=2)

    print(f"\nDone. Outputs in: {OUTDIR}")


if __name__ == "__main__":
    main()

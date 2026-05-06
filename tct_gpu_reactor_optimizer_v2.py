import random
import math
from multiprocessing import Pool, cpu_count

# -----------------------------
# GLOBAL SETTINGS
# -----------------------------

POPULATION = 64
GENERATIONS = 40
ELITE_COUNT = 10

# physics constants
MU0 = 4e-7 * math.pi
SIGMA_LI = 1e6       # conductivity liquid lithium (S/m)
DAMAGE_SCALE = 2e-22 # neutron damage scaling

# -----------------------------
# RANDOM DESIGN
# -----------------------------

def random_design():

    return {
        "major_radius": random.uniform(3.0,7.0),
        "minor_radius": random.uniform(0.8,2.0),
        "blanket": random.uniform(0.3,1.2),
        "magnetic_field": random.uniform(4,14),
        "plasma_current": random.uniform(5e6,20e6),
        "lithium_velocity": random.uniform(0.2,2.0),
        "boron_fraction": random.uniform(0.05,0.3),
        "aspect_ratio": random.uniform(2.5,4.5)
    }

# -----------------------------
# NEUTRON DAMAGE MODEL
# -----------------------------

def neutron_damage(design):

    flux = design["magnetic_field"] * 1e18
    blanket = design["blanket"]

    attenuation = math.exp(-blanket*2)

    damage = flux * attenuation * DAMAGE_SCALE

    return damage

# -----------------------------
# TRITIUM BREEDING
# -----------------------------

def tritium_breeding(design):

    blanket = design["blanket"]
    boron = design["boron_fraction"]

    base = 0.9 + blanket*0.5
    reflection = boron*0.4

    return base + reflection

# -----------------------------
# MHD DRAG MODEL
# -----------------------------

def mhd_drag(design):

    B = design["magnetic_field"]
    v = design["lithium_velocity"]
    L = design["blanket"]

    drag = SIGMA_LI * B**2 * v * L

    return drag * 1e-6

# -----------------------------
# PUMP POWER
# -----------------------------

def pump_power(design):

    v = design["lithium_velocity"]
    blanket = design["blanket"]

    flow = v * blanket * 10

    return flow * 5

# -----------------------------
# CURRENT DRIVE POWER
# -----------------------------

def current_drive(design):

    Ip = design["plasma_current"]
    B = design["magnetic_field"]

    efficiency = 0.35

    return (Ip/B)/efficiency * 1e-6

# -----------------------------
# STRUCTURAL STRESS
# -----------------------------

def wall_stress(design):

    B = design["magnetic_field"]
    r = design["major_radius"]

    pressure = B**2/(2*MU0)

    return pressure * r

# -----------------------------
# ELECTRIC POWER
# -----------------------------

def net_electric(design):

    fusion = design["magnetic_field"]**2 * design["minor_radius"] * 500

    thermal = fusion * 0.35

    return thermal

# -----------------------------
# SIMULATION
# -----------------------------

def simulate(design):

    damage = neutron_damage(design)
    TBR = tritium_breeding(design)
    mhd = mhd_drag(design)
    pump = pump_power(design)
    cd = current_drive(design)
    stress = wall_stress(design)
    pnet = net_electric(design)

    penalty = 0

    if stress > 600e6:
        penalty += 200

    if TBR < 1.1:
        penalty += 200

    return {

        "pnet":pnet,
        "damage":damage,
        "TBR":TBR,
        "stress":stress,
        "mhd":mhd,
        "pump":pump,
        "current_drive":cd,
        "penalty":penalty,
        "wall":design["blanket"],
        "bootstrap":0.6
    }

# -----------------------------
# SCORING
# -----------------------------

def score(result):

    penalty = result["penalty"]

    pump_penalty = result["pump"] * 0.05
    mhd_penalty = result["mhd"] * 0.02
    cd_penalty = result["current_drive"] * 0.1

    return (
        result["damage"]
        - result["pnet"]*1e-4
        + pump_penalty
        + mhd_penalty
        + cd_penalty
        + penalty
    )

# -----------------------------
# MUTATION
# -----------------------------

def mutate(parent):

    child = parent.copy()

    key = random.choice(list(child.keys()))

    child[key] *= random.uniform(0.8,1.2)

    return child

# -----------------------------
# OPTIMIZER
# -----------------------------

def optimize():

    population = [random_design() for _ in range(POPULATION)]

    history = []

    for generation in range(GENERATIONS):

        print("\n===== GENERATION",generation,"=====")

        with Pool(cpu_count()) as pool:
            results = pool.map(simulate,population)

        scored = []

        for design,result in zip(population,results):

            s = score(result)

            scored.append((s,design,result))

            print(
                "score",round(s,3),
                "net_elec",round(result["pnet"],1),
                "wall",round(result["wall"],2),
                "stress",round(result["stress"]/1e6,1),"MPa",
                "TBR",round(result["TBR"],2),
                "CD",round(result["current_drive"],1),
                "MHD",round(result["mhd"],1),
                "pump",round(result["pump"],1)
            )

        scored.sort(key=lambda x:x[0])

        best = scored[0]

        print("\nBEST SCORE:",best[0])

        history.append({

            "score":best[0],
            "pnet":best[2]["pnet"],
            "wall":best[2]["wall"],
            "stress":best[2]["stress"],
            "TBR":best[2]["TBR"]
        })

        elites = [x[1] for x in scored[:ELITE_COUNT]]

        new_population = elites.copy()

        while len(new_population) < POPULATION:

            parent = random.choice(elites)

            child = mutate(parent)

            new_population.append(child)

        population = new_population

    return history


if __name__ == "__main__":

    optimize()

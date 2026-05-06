import random
import math
from multiprocessing import Pool, cpu_count

# ------------------------------------------------
# GLOBAL SETTINGS
# ------------------------------------------------

POPULATION = 96
GENERATIONS = 60
ELITE_COUNT = 20

BASE_MUTATION = 0.35
STRUCTURAL_MUTATION = 0.08

MU0 = 4e-7 * math.pi

MAX_WALL_LOAD = 10
MAX_MAGNET_STRESS = 8e8
MAX_BLANKET_HEAT = 2000

DAMAGE_SCALE = 2e-22

NEUTRON_ENERGY = 14.1


# ------------------------------------------------
# MATERIAL LIBRARY
# ------------------------------------------------

materials = {

    "Li2O": {
        "fast_capture": 0.10,
        "thermal_capture": 0.30,
        "scatter": 0.35,
        "breed": 1.05,
        "mult": 1.0,
        "conductivity": 1e3
    },

    "Li4SiO4": {
        "fast_capture": 0.08,
        "thermal_capture": 0.28,
        "scatter": 0.30,
        "breed": 1.0,
        "mult": 1.0,
        "conductivity": 1e3
    },

    "PbLi": {
        "fast_capture": 0.05,
        "thermal_capture": 0.20,
        "scatter": 0.40,
        "breed": 0.85,
        "mult": 1.15,
        "conductivity": 8e5
    },

    "LiMetal": {
        "fast_capture": 0.12,
        "thermal_capture": 0.35,
        "scatter": 0.30,
        "breed": 1.15,
        "mult": 1.0,
        "conductivity": 1e6
    },

    "W_Ti_B4C": {
        "fast_capture": 0.02,
        "thermal_capture": 0.15,
        "scatter": 0.60,
        "breed": 0.0,
        "mult": 1.2,
        "conductivity": 2e6
    }
}

material_keys = list(materials.keys())


# ------------------------------------------------
# RANDOM DESIGN
# ------------------------------------------------

def random_design():

    layers = [
        {"material": "Li2O", "thickness": random.uniform(0.25, 0.45)},
        {"material": "W_Ti_B4C", "thickness": random.uniform(0.05, 0.15)},
        {"material": "Li2O", "thickness": random.uniform(0.25, 0.45)}
    ]

    return {
        "major_radius": random.uniform(4, 7),
        "minor_radius": random.uniform(1.0, 2.0),
        "magnetic_field": random.uniform(6, 14),
        "elongation": random.uniform(1.6, 2.2),
        "triangularity": random.uniform(0.2, 0.6),
        "bootstrap_fraction": random.uniform(0.4, 0.8),
        "current_drive_power": random.uniform(10, 60),
        "lithium_velocity": random.uniform(0.2, 1.2),
        "blanket_layers": layers
    }


# ------------------------------------------------
# TWO GROUP NEUTRON TRANSPORT
# ------------------------------------------------

def neutron_transport(design):

    fast_flux = 1.0
    thermal_flux = 0.0

    breeding = 0
    heat = 0

    for layer in design["blanket_layers"]:

        mat = materials[layer["material"]]
        thickness = layer["thickness"]

        fast_capture = mat["fast_capture"] * thickness
        thermal_capture = mat["thermal_capture"] * thickness
        scatter = mat["scatter"] * thickness

        fast_absorb = fast_flux * fast_capture
        scatter_to_thermal = fast_flux * scatter * 0.6

        fast_flux -= fast_absorb + scatter_to_thermal
        thermal_flux += scatter_to_thermal

        thermal_absorb = thermal_flux * thermal_capture
        thermal_flux -= thermal_absorb

        breeding += mat["breed"] * (thermal_absorb + fast_absorb) * 1.1
        heat += (fast_absorb + thermal_absorb) * NEUTRON_ENERGY * mat["mult"]

        fast_flux = max(fast_flux, 0.01)
        thermal_flux = max(thermal_flux, 0.01)

    return fast_flux, thermal_flux, breeding, heat


# ------------------------------------------------
# MHD DRAG
# ------------------------------------------------

def mhd_drag(design):

    B = design["magnetic_field"]
    v = design["lithium_velocity"]

    drag = 0

    for layer in design["blanket_layers"]:
        mat = materials[layer["material"]]
        drag += mat["conductivity"] * B**2 * v * layer["thickness"]

    return drag * 6e-9


# ------------------------------------------------
# PUMP POWER
# ------------------------------------------------

def pump_power(design):
    return design["lithium_velocity"] * 30


# ------------------------------------------------
# MAGNET STRESS
# ------------------------------------------------

def magnet_stress(design):

    B = design["magnetic_field"]
    R = design["major_radius"]

    pressure = B**2 / (2 * MU0)

    return pressure * R


# ------------------------------------------------
# CONFINEMENT MODEL
# ------------------------------------------------

def tct_confinement(design):

    B = design["magnetic_field"]
    a = design["minor_radius"]

    kappa = design["elongation"]
    delta = design["triangularity"]

    bootstrap = design["bootstrap_fraction"]

    base = B**2 * a * (1 + 0.5 * kappa + 0.4 * delta) * 0.03
    bootstrap_gain = base * bootstrap * 0.35

    return base + bootstrap_gain


# ------------------------------------------------
# WALL LOADING
# ------------------------------------------------

def wall_loading(power, design):

    R = design["major_radius"]
    a = design["minor_radius"]

    surface = 4 * math.pi * R * a * 2.2

    return power / surface


# ------------------------------------------------
# NEUTRON LIFETIME
# ------------------------------------------------

def neutron_lifetime(damage):
    return 18 / (damage * 3e5 + 0.0008)


# ------------------------------------------------
# SIMULATION
# ------------------------------------------------

def simulate(design):

    fast, thermal, TBR, heat = neutron_transport(design)

    flux = fast + thermal
    damage = flux * DAMAGE_SCALE

    fusion = tct_confinement(design)

    pump = pump_power(design)
    mhd = mhd_drag(design)

    stress = magnet_stress(design)

    wall = wall_loading(fusion + heat, design)

    life = neutron_lifetime(damage)

    pnet = fusion * 0.35 - pump - design["current_drive_power"] * (1 - design["bootstrap_fraction"])

    if heat > MAX_BLANKET_HEAT:
        pnet -= (heat - MAX_BLANKET_HEAT) * 0.5

    if TBR < 1.1:
        pnet -= (1.1 - TBR) * 300

    valid = True

    if stress > MAX_MAGNET_STRESS:
        valid = False

    if wall > MAX_WALL_LOAD:
        valid = False

    return {
        "pnet": pnet,
        "TBR": TBR,
        "life": life,
        "mhd": mhd,
        "wall": wall,
        "heat": heat,
        "valid": valid
    }


# ------------------------------------------------
# PARETO
# ------------------------------------------------

def dominates(a, b):

    if (
        a["pnet"] >= b["pnet"]
        and a["TBR"] >= b["TBR"]
        and a["life"] >= b["life"]
        and a["mhd"] <= b["mhd"]
    ):
        return a != b

    return False


def pareto_front(results):

    front = []

    for i, a in enumerate(results):

        dominated = False

        for j, b in enumerate(results):
            if j != i and dominates(b, a):
                dominated = True
                break

        if not dominated:
            front.append(i)

    return front


# ------------------------------------------------
# MUTATION
# ------------------------------------------------

def mutate_value(v, p):
    return v * random.uniform(1 - p, 1 + p)


def mutate(parent, generation):

    pressure = BASE_MUTATION * (1 - generation / GENERATIONS)

    child = {}

    for k, v in parent.items():
        if k == "blanket_layers":
            child[k] = [dict(x) for x in v]
        else:
            child[k] = v

    for key in child:

        if key == "blanket_layers":
            continue

        if random.random() < pressure:
            child[key] = mutate_value(child[key], pressure)

    for layer in child["blanket_layers"]:

        if random.random() < pressure:

            layer["thickness"] = mutate_value(layer["thickness"], pressure)

            if random.random() < 0.4:
                layer["material"] = random.choice(material_keys)

    if random.random() < STRUCTURAL_MUTATION:

        if random.random() < 0.5 and len(child["blanket_layers"]) < 6:

            child["blanket_layers"].append({
                "material": random.choice(material_keys),
                "thickness": random.uniform(0.05, 0.3)
            })

        elif len(child["blanket_layers"]) > 3:

            child["blanket_layers"].pop(
                random.randrange(len(child["blanket_layers"]))
            )

    return child


# ------------------------------------------------
# OPTIMIZER
# ------------------------------------------------

def optimize():

    population = [random_design() for _ in range(POPULATION)]

    for gen in range(GENERATIONS):

        print("\n===== GENERATION", gen, "=====")

        with Pool(cpu_count()) as pool:
            results = pool.map(simulate, population)

        for r, d in zip(results, population):

            print(
                "net", round(r["pnet"], 1),
                "TBR", round(r["TBR"], 2),
                "life", round(r["life"], 2),
                "MHD", round(r["mhd"], 2),
                "wall", round(r["wall"], 2),
                "heat", round(r["heat"], 1),
                "layers", len(d["blanket_layers"])
            )

        front_idx = pareto_front(results)

        elites = [population[i] for i in front_idx]

        if len(elites) > ELITE_COUNT:
            elites = random.sample(elites, ELITE_COUNT)

        new_population = elites.copy()

        while len(new_population) < POPULATION:

            parent = random.choice(elites)

            new_population.append(mutate(parent, gen))

        population = new_population


if __name__ == "__main__":
    optimize()

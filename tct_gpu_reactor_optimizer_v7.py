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

DAMAGE_SCALE = 2e-22

# ------------------------------------------------
# MATERIAL LIBRARY
# ------------------------------------------------

materials = {

    "Li2O": {
        "sigma_capture":0.22,
        "sigma_scatter":0.35,
        "breeding":1.05,
        "conductivity":1e3
    },

    "Li4SiO4": {
        "sigma_capture":0.20,
        "sigma_scatter":0.30,
        "breeding":1.00,
        "conductivity":1e3
    },

    "PbLi": {
        "sigma_capture":0.18,
        "sigma_scatter":0.40,
        "breeding":0.85,
        "conductivity":8e5
    },

    "LiMetal": {
        "sigma_capture":0.25,
        "sigma_scatter":0.30,
        "breeding":1.15,
        "conductivity":1e6
    },

    "W_Ti_B4C": {
        "sigma_capture":0.05,
        "sigma_scatter":0.60,
        "breeding":0.0,
        "conductivity":2e6
    }

}

material_keys = list(materials.keys())

# ------------------------------------------------
# RANDOM DESIGN
# ------------------------------------------------

def random_design():

    layers = [
        {"material":"Li2O","thickness":random.uniform(0.25,0.45)},
        {"material":"W_Ti_B4C","thickness":random.uniform(0.05,0.15)},
        {"material":"Li2O","thickness":random.uniform(0.25,0.45)}
    ]

    return {

        "major_radius":random.uniform(4,7),
        "minor_radius":random.uniform(1.0,2.0),

        "magnetic_field":random.uniform(6,14),
        "plasma_current":random.uniform(6e6,20e6),

        "elongation":random.uniform(1.6,2.2),
        "triangularity":random.uniform(0.2,0.6),
        "safety_q":random.uniform(2.5,5),

        "bootstrap_fraction":random.uniform(0.4,0.8),

        "current_drive_power":random.uniform(10,60),

        "lithium_velocity":random.uniform(0.2,1.2),

        "blanket_layers":layers
    }

# ------------------------------------------------
# NEUTRON TRANSPORT
# ------------------------------------------------

def neutron_transport(design):

    flux = 1.0
    breeding = 0

    for layer in design["blanket_layers"]:

        mat = materials[layer["material"]]

        capture = mat["sigma_capture"]
        scatter = mat["sigma_scatter"]

        thickness = layer["thickness"]

        attenuation = math.exp(-(capture + scatter) * thickness)

        breeding += mat["breeding"] * thickness * flux * 0.9

        flux *= attenuation

    return flux, breeding

# ------------------------------------------------
# MHD DRAG
# ------------------------------------------------

def mhd_drag(design):

    B = design["magnetic_field"]
    v = design["lithium_velocity"]

    drag = 0

    for layer in design["blanket_layers"]:

        mat = materials[layer["material"]]

        sigma = mat["conductivity"]
        L = layer["thickness"]

        drag += sigma * B**2 * v * L

    return drag * 5e-8

# ------------------------------------------------
# PUMP POWER
# ------------------------------------------------

def pump_power(design):

    flow = design["lithium_velocity"] * 12

    return flow * 3

# ------------------------------------------------
# WALL STRESS
# ------------------------------------------------

def wall_stress(design):

    B = design["magnetic_field"]
    R = design["major_radius"]

    pressure = B**2 / (2 * MU0)

    return pressure * R

# ------------------------------------------------
# TCT CONFINEMENT
# ------------------------------------------------

def tct_confinement(design):

    B = design["magnetic_field"]
    a = design["minor_radius"]

    kappa = design["elongation"]
    delta = design["triangularity"]
    q = design["safety_q"]

    bootstrap = design["bootstrap_fraction"]

    base = B**2 * a * (1 + 0.5*kappa + 0.4*delta) * 0.08

    stability = base * (1 - 1/(q+1))

    bootstrap_gain = stability * bootstrap * 0.35

    return stability + bootstrap_gain

# ------------------------------------------------
# WALL LOADING
# ------------------------------------------------

def wall_loading(power, design):

    R = design["major_radius"]
    a = design["minor_radius"]

    surface = 4 * math.pi * R * a * 0.6

    return power / surface

# ------------------------------------------------
# NEUTRON LIFETIME
# ------------------------------------------------

def neutron_lifetime(damage):

    return 15 / (damage*1e4 + 1e-4)

# ------------------------------------------------
# SIMULATION
# ------------------------------------------------

def simulate(design):

    flux, TBR = neutron_transport(design)

    damage = flux * DAMAGE_SCALE

    mhd = mhd_drag(design)
    pump = pump_power(design)

    stress = wall_stress(design)

    fusion = tct_confinement(design)

    pnet = fusion*0.35 - pump - design["current_drive_power"]*0.2

    wall = wall_loading(fusion, design)

    life = neutron_lifetime(damage)

    valid = True

    if TBR < 1.1: valid = False
    if stress > 700e6: valid = False
    if wall > MAX_WALL_LOAD: valid = False

    return {

        "pnet":pnet,
        "TBR":TBR,
        "life":life,
        "mhd":mhd,
        "pump":pump,
        "wall":wall,
        "valid":valid

    }

# ------------------------------------------------
# PARETO DOMINANCE
# ------------------------------------------------

def dominates(a, b):

    if a["pnet"] >= b["pnet"] and \
       a["TBR"] >= b["TBR"] and \
       a["life"] >= b["life"] and \
       a["mhd"] <= b["mhd"] and \
       a["pump"] <= b["pump"]:

        if a != b:
            return True

    return False

# ------------------------------------------------
# PARETO FRONT
# ------------------------------------------------

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

    return v * random.uniform(1-p, 1+p)

def mutate(parent, generation):

    pressure = BASE_MUTATION * (1 - generation / GENERATIONS)

    child = {}

    for k,v in parent.items():

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

        if random.random() < 0.5 and len(child["blanket_layers"]) < 5:

            child["blanket_layers"].append({
                "material":random.choice(material_keys),
                "thickness":random.uniform(0.05,0.3)
            })

        elif len(child["blanket_layers"]) > 3:

            child["blanket_layers"].pop(random.randrange(len(child["blanket_layers"])))

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

        for r,d in zip(results,population):

            print(
                "net",round(r["pnet"],1),
                "TBR",round(r["TBR"],2),
                "life",round(r["life"],2),
                "MHD",round(r["mhd"],2),
                "wall",round(r["wall"],2),
                "layers",len(d["blanket_layers"])
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

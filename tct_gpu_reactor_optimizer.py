import random
import math
from multiprocessing import Pool, cpu_count

# --------------------------------------------------
# GLOBAL SETTINGS
# --------------------------------------------------

POPULATION = 96
GENERATIONS = 60
ELITE_COUNT = 12

MUTATION_RATE = 0.35
STRUCTURAL_MUTATION_RATE = 0.08

MU0 = 4e-7 * math.pi
DAMAGE_SCALE = 2e-22

# --------------------------------------------------
# MATERIAL LIBRARY
# --------------------------------------------------

materials = {

    "Li2O": {
        "sigma_capture": 0.22,
        "sigma_scatter": 0.35,
        "breeding": 1.05,
        "conductivity": 1e3
    },

    "Li4SiO4": {
        "sigma_capture": 0.20,
        "sigma_scatter": 0.30,
        "breeding": 1.00,
        "conductivity": 1e3
    },

    "PbLi": {
        "sigma_capture": 0.18,
        "sigma_scatter": 0.40,
        "breeding": 0.85,
        "conductivity": 8e5
    },

    "LiMetal": {
        "sigma_capture": 0.25,
        "sigma_scatter": 0.30,
        "breeding": 1.15,
        "conductivity": 1e6
    },

    "W_Ti_B4C": {
        "sigma_capture": 0.05,
        "sigma_scatter": 0.60,
        "breeding": 0.0,
        "conductivity": 2e6
    }

}

material_keys = list(materials.keys())

# --------------------------------------------------
# RANDOM DESIGN
# --------------------------------------------------

def random_design():

    layers = [
        {"material": "Li2O", "thickness": random.uniform(0.25,0.45)},
        {"material": "W_Ti_B4C", "thickness": random.uniform(0.05,0.15)},
        {"material": "Li2O", "thickness": random.uniform(0.25,0.45)}
    ]

    return {

        "major_radius": random.uniform(4,7),
        "minor_radius": random.uniform(1.0,2.0),

        "magnetic_field": random.uniform(6,14),
        "plasma_current": random.uniform(6e6,20e6),

        "elongation": random.uniform(1.6,2.2),
        "triangularity": random.uniform(0.2,0.6),
        "safety_q": random.uniform(2.5,5),

        "bootstrap_fraction": random.uniform(0.4,0.8),

        "current_drive_power": random.uniform(10,60),

        "lithium_velocity": random.uniform(0.2,1.2),

        "blanket_layers": layers
    }

# --------------------------------------------------
# NEUTRON TRANSPORT
# --------------------------------------------------

def neutron_transport(design):

    flux = 1.0
    breeding = 0

    for layer in design["blanket_layers"]:

        mat = materials[layer["material"]]

        capture = mat["sigma_capture"]
        scatter = mat["sigma_scatter"]

        thickness = layer["thickness"]

        attenuation = math.exp(-(capture + scatter) * thickness)

        # boosted breeding scaling
        breeding += mat["breeding"] * thickness * flux * 2.5

        flux *= attenuation

    return flux, breeding

# --------------------------------------------------
# MHD DRAG
# --------------------------------------------------

def mhd_drag(design):

    B = design["magnetic_field"]
    v = design["lithium_velocity"]

    drag = 0

    for layer in design["blanket_layers"]:

        mat = materials[layer["material"]]

        sigma = mat["conductivity"]
        L = layer["thickness"]

        drag += sigma * B**2 * v * L

    return drag * 1e-6

# --------------------------------------------------
# PUMP POWER
# --------------------------------------------------

def pump_power(design):

    flow = design["lithium_velocity"] * 12

    return flow * 3

# --------------------------------------------------
# STRUCTURAL STRESS
# --------------------------------------------------

def wall_stress(design):

    B = design["magnetic_field"]
    R = design["major_radius"]

    pressure = B**2 / (2*MU0)

    return pressure * R

# --------------------------------------------------
# TCT CONFINEMENT
# --------------------------------------------------

def tct_confinement(design):

    B = design["magnetic_field"]
    a = design["minor_radius"]

    kappa = design["elongation"]
    delta = design["triangularity"]

    q = design["safety_q"]

    bootstrap = design["bootstrap_fraction"]

    base = B**2 * a * (1 + 0.5*kappa + 0.4*delta)

    stability = base * (1 - 1/(q+1))

    bootstrap_gain = stability * bootstrap * 0.3

    return stability + bootstrap_gain

# --------------------------------------------------
# SIMULATION
# --------------------------------------------------

def simulate(design):

    flux, breeding = neutron_transport(design)

    damage = flux * DAMAGE_SCALE
    TBR = breeding

    mhd = mhd_drag(design)

    pump = pump_power(design)

    stress = wall_stress(design)

    fusion = tct_confinement(design)

    pnet = fusion*0.35 - pump - design["current_drive_power"]

    penalty = 0

    if TBR < 1.1:
        penalty += 200

    if stress > 700e6:
        penalty += 200

    return {

        "pnet":pnet,
        "damage":damage,
        "TBR":TBR,
        "stress":stress,
        "mhd":mhd,
        "pump":pump,
        "penalty":penalty
    }

# --------------------------------------------------
# SCORE
# --------------------------------------------------

def score(result, design):

    pump_penalty = result["pump"] * 0.05
    mhd_penalty = result["mhd"] * 0.02
    cd_penalty = design["current_drive_power"] * 0.1

    return (

        result["damage"]
        - result["pnet"]*1e-4
        + pump_penalty
        + mhd_penalty
        + cd_penalty
        + result["penalty"]

    )

# --------------------------------------------------
# MUTATION FUNCTIONS
# --------------------------------------------------

def mutate_numeric(v):

    return v * random.uniform(0.85,1.15)

def mutate_layer(layer):

    if random.random() < 0.4:

        layer["material"] = random.choice(material_keys)

    layer["thickness"] = mutate_numeric(layer["thickness"])

# --------------------------------------------------

def mutate(parent):

    child = {}

    for k,v in parent.items():

        if k == "blanket_layers":

            child[k] = [dict(layer) for layer in v]

        else:

            child[k] = v

    for key in child:

        if key == "blanket_layers":
            continue

        if random.random() < MUTATION_RATE:

            child[key] = mutate_numeric(child[key])

    for layer in child["blanket_layers"]:

        if random.random() < MUTATION_RATE:

            mutate_layer(layer)

    # structural mutations
    if random.random() < STRUCTURAL_MUTATION_RATE:

        if random.random() < 0.5 and len(child["blanket_layers"]) < 5:

            child["blanket_layers"].append({

                "material": random.choice(material_keys),
                "thickness": random.uniform(0.05,0.3)

            })

        elif len(child["blanket_layers"]) > 3:

            child["blanket_layers"].pop(random.randrange(len(child["blanket_layers"])))

    return child

# --------------------------------------------------
# OPTIMIZER
# --------------------------------------------------

def optimize():

    population = [random_design() for _ in range(POPULATION)]

    for generation in range(GENERATIONS):

        print("\n===== GENERATION",generation,"=====")

        with Pool(cpu_count()) as pool:

            results = pool.map(simulate,population)

        scored = []

        for design,result in zip(population,results):

            s = score(result,design)

            scored.append((s,design,result))

            print(
                "score",round(s,3),
                "net",round(result["pnet"],1),
                "TBR",round(result["TBR"],2),
                "MHD",round(result["mhd"],1),
                "pump",round(result["pump"],1),
                "layers",len(design["blanket_layers"])
            )

        scored.sort(key=lambda x:x[0])

        best = scored[0]

        print("\nBEST SCORE:",best[0])

        elites = [x[1] for x in scored[:ELITE_COUNT]]

        new_population = elites.copy()

        while len(new_population) < POPULATION:

            parent = random.choice(elites)

            new_population.append(mutate(parent))

        population = new_population

# --------------------------------------------------

if __name__ == "__main__":

    optimize()

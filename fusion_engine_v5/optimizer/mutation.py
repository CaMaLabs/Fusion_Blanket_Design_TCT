import random
from .genome import random_material_layer, random_split

def mutate(design, material_weights=None):
    child = dict(design)
    scalar_keys = ["R","a","kappa","B0","Ip","Ti","Te","H98","fG","frac_cap","reconn_trigger","conf_trigger",
                   "lithium_thickness","lithium_velocity","liquid_wall_li6_enrich","blanket_thickness",
                   "li6_frac","mult_frac","cooling_eff","coolant_outlet_K","mc_samples"]
    for k in scalar_keys:
        if random.random() < 0.30:
            child[k] = child[k] * random.uniform(0.9, 1.1)
    if random.random() < 0.30:
        child["split"] = random_split()
    for layer in ["l1","l2","l3","l4"]:
        if random.random() < 0.25:
            m, li6, pack = random_material_layer(material_weights)
            child[layer] = m
            child[f"{layer}_li6"] = li6
            child[f"{layer}_pack"] = pack
    return child

import random
from ..engine.config import DEFAULT_DESIGN
from ..blanket.materials_db import BLANKET_CANDIDATES, uses_lithium, porous_ok

def random_material_layer(material_weights=None):
    if material_weights:
        mats = list(material_weights.keys())
        weights = list(material_weights.values())
        m = random.choices(mats, weights=weights, k=1)[0]
    else:
        m = random.choice(BLANKET_CANDIDATES)
    li6 = random.choice([0.3, 0.6, 0.9]) if uses_lithium(m) else 0.0
    pack = random.uniform(0.6, 1.0) if porous_ok(m) else 1.0
    return m, li6, pack

def random_split():
    r = [random.random() for _ in range(4)]
    s = sum(r)
    return tuple(x / s for x in r)

def random_design(material_weights=None):
    d = dict(DEFAULT_DESIGN)
    l1,l1_li6,l1_pack = random_material_layer(material_weights)
    l2,l2_li6,l2_pack = random_material_layer(material_weights)
    l3,l3_li6,l3_pack = random_material_layer(material_weights)
    l4,l4_li6,l4_pack = random_material_layer(material_weights)
    d.update({
        "R": random.uniform(5.0, 9.0),
        "a": random.uniform(1.5, 3.2),
        "kappa": random.uniform(1.6, 2.4),
        "B0": random.uniform(5.0, 12.0),
        "Ip": random.uniform(15.0, 28.0),
        "Ti": random.uniform(15.0, 40.0),
        "Te": random.uniform(10.0, 25.0),
        "H98": random.uniform(0.9, 1.4),
        "fG": random.uniform(0.6, 0.95),
        "frac_cap": random.uniform(0.5, 0.85),
        "reconn_trigger": random.uniform(0.55, 0.8),
        "conf_trigger": random.uniform(0.55, 0.8),
        "lithium_thickness": random.uniform(0.0005, 0.003),
        "lithium_velocity": random.uniform(1.0, 8.0),
        "liquid_wall_li6_enrich": random.uniform(0.6, 0.95),
        "blanket_thickness": random.uniform(0.5, 1.5),
        "l1": l1, "l1_li6": l1_li6, "l1_pack": l1_pack,
        "l2": l2, "l2_li6": l2_li6, "l2_pack": l2_pack,
        "l3": l3, "l3_li6": l3_li6, "l3_pack": l3_pack,
        "l4": l4, "l4_li6": l4_li6, "l4_pack": l4_pack,
        "split": random_split(),
        "li6_frac": random.uniform(0.1, 0.95),
        "mult_frac": random.uniform(0.05, 0.6),
        "cooling_eff": random.uniform(0.30, 0.50),
        "coolant_outlet_K": random.uniform(750.0, 1050.0),
        "mc_samples": 300000,
    })
    return d

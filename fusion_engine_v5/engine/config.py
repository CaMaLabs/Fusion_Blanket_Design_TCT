from dataclasses import dataclass

POP_SIZE = 64
GENERATIONS = 30
ELITE_KEEP = 16

OPENMC_BATCHES = 80
OPENMC_PARTICLES = 300000

MC_SAMPLES = 300000
VALIDATION_TOP_N = 5

YZ_HALF = 5.0
N_MESH_X = 160
SOURCE_ENERGY_EV = 14.1e6

ENERGY_BINS = [0.0, 1.0e3, 1.0e5, 1.0e6, 5.0e6, 10.0e6, 14.2e6, 20.0e6]

@dataclass(frozen=True)
class PhysicalConstants:
    e_charge: float = 1.602176634e-19
    eps0: float = 8.8541878128e-12
    mu0: float = 4.0e-7 * 3.141592653589793
    me: float = 9.1093837015e-31
    mi_dt: float = 2.5 * 1.66053906660e-27
    mev_j: float = 1.602176634e-13

CONSTS = PhysicalConstants()

DEFAULT_DESIGN = {
    "R": 8.0,
    "a": 2.5,
    "kappa": 2.0,
    "B0": 6.0,
    "Ip": 22.0,
    "Ti": 25.0,
    "Te": 15.0,
    "H98": 1.2,
    "fG": 0.8,
    "frac_cap": 0.7,
    "reconn_trigger": 0.65,
    "conf_trigger": 0.65,
    "lithium_thickness": 0.0015,
    "lithium_velocity": 3.0,
    "liquid_wall_li6_enrich": 0.9,
    "blanket_thickness": 1.0,
    "l1": "Li2TiO3",
    "l1_li6": 0.9,
    "l1_pack": 0.85,
    "l2": "Be12Ti",
    "l2_li6": 0.0,
    "l2_pack": 0.9,
    "l3": "Li4SiO4",
    "l3_li6": 0.9,
    "l3_pack": 0.85,
    "l4": "W_Ti_B4C_60_30_10_wt",
    "l4_li6": 0.0,
    "l4_pack": 1.0,
    "split": (0.2, 0.25, 0.25, 0.3),
    "li6_frac": 0.6,
    "mult_frac": 0.25,
    "cooling_eff": 0.42,
    "coolant_outlet_K": 900.0,
}

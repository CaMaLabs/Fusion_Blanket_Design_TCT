import csv
import math
import os
import random
import subprocess
import warnings
from pathlib import Path
import multiprocessing as mp

import openmc

warnings.filterwarnings("ignore")

BASE_DIR = Path.cwd()
RUNS_DIR = BASE_DIR / "runs_evo_blanket_v6"
RUNS_DIR.mkdir(exist_ok=True)

random.seed(1337)

THREADS = max(1, os.cpu_count() or 1)
POOL_WORKERS = max(1, THREADS // 2)

# -----------------------------
# Base material templates
# -----------------------------
# "porous_ok" means we can scale density by packing/porosity.
MATERIALS = {
    "W": {
        "density": 19.3,
        "porous_ok": False,
        "components": [
            ("nuclide", "W182", 0.265, "ao"),
            ("nuclide", "W183", 0.143, "ao"),
            ("nuclide", "W184", 0.306, "ao"),
            ("nuclide", "W186", 0.286, "ao"),
        ],
    },
    "Be": {
        "density": 1.85,
        "porous_ok": True,
        "components": [
            ("nuclide", "Be9", 1.0, "ao"),
        ],
    },
    "Be12Ti": {
        "density": 2.24,
        "porous_ok": True,
        "components": [
            ("nuclide", "Be9", 12.0, "ao"),
            ("element", "Ti", 1.0, "ao"),
        ],
    },
    "B4C": {
        "density": 2.52,
        "porous_ok": True,
        "components": [
            ("element", "B", 4.0, "ao"),
            ("element", "C", 1.0, "ao"),
        ],
    },
    "SiC": {
        "density": 3.21,
        "porous_ok": True,
        "components": [
            ("element", "Si", 1.0, "ao"),
            ("element", "C", 1.0, "ao"),
        ],
    },
    "TiB2": {
        "density": 4.52,
        "porous_ok": True,
        "components": [
            ("element", "Ti", 1.0, "ao"),
            ("element", "B", 2.0, "ao"),
        ],
    },
    "Pb": {
        "density": 11.34,
        "porous_ok": False,
        "components": [
            ("element", "Pb", 1.0, "ao"),
        ],
    },
    "PbLi": {
        "density": 9.8,
        "porous_ok": False,
        "components": [
            ("element", "Pb", 0.83, "ao"),
            ("nuclide", "Li6", 0.153, "ao"),
            ("nuclide", "Li7", 0.017, "ao"),
        ],
    },
    "Li": {
        "density": 0.534,
        "porous_ok": False,
        "components": [
            ("nuclide", "Li6", 0.90, "ao"),
            ("nuclide", "Li7", 0.10, "ao"),
        ],
    },
    "Li2O": {
        "density": 2.01,
        "porous_ok": True,
        "components": [
            ("nuclide", "Li6", 1.8, "ao"),
            ("nuclide", "Li7", 0.2, "ao"),
            ("element", "O", 1.0, "ao"),
        ],
    },
    "Li2TiO3": {
        "density": 3.43,
        "porous_ok": True,
        "components": [
            ("nuclide", "Li6", 1.8, "ao"),
            ("nuclide", "Li7", 0.2, "ao"),
            ("element", "Ti", 1.0, "ao"),
            ("element", "O", 3.0, "ao"),
        ],
    },
    "Li4SiO4": {
        "density": 2.39,
        "porous_ok": True,
        "components": [
            ("nuclide", "Li6", 3.6, "ao"),
            ("nuclide", "Li7", 0.4, "ao"),
            ("element", "Si", 1.0, "ao"),
            ("element", "O", 4.0, "ao"),
        ],
    },
    "W_Ti_B4C_60_30_10_wt": {
        "density": 13.45,
        "porous_ok": False,
        "components": [
            ("element", "W", 0.60, "wo"),
            ("element", "Ti", 0.30, "wo"),
            ("element", "B", 0.07826, "wo"),
            ("element", "C", 0.02174, "wo"),
        ],
    },
    "W_Ti_B4C_Cr_55_25_10_10_wt": {
        "density": 12.78,
        "porous_ok": False,
        "components": [
            ("element", "W", 0.55, "wo"),
            ("element", "Ti", 0.25, "wo"),
            ("element", "B", 0.07826, "wo"),
            ("element", "C", 0.02174, "wo"),
            ("element", "Cr", 0.10, "wo"),
        ],
    },
    "W_Ti_B4C_Al2O3_55_25_10_10_wt": {
        "density": 11.84,
        "porous_ok": False,
        "components": [
            ("element", "W", 0.55, "wo"),
            ("element", "Ti", 0.25, "wo"),
            ("element", "B", 0.07826, "wo"),
            ("element", "C", 0.02174, "wo"),
            ("element", "Al", 0.0529, "wo"),
            ("element", "O", 0.0471, "wo"),
        ],
    },
}

CANDIDATES = list(MATERIALS.keys())

TOTAL_THICKNESS_CHOICES = [10.0, 15.0, 20.0]

SPLIT_CHOICES = [
    (0.10, 0.20, 0.30, 0.40),
    (0.15, 0.20, 0.25, 0.40),
    (0.15, 0.25, 0.25, 0.35),
    (0.20, 0.20, 0.20, 0.40),
    (0.20, 0.25, 0.25, 0.30),
]

LI6_ENRICH_CHOICES = [0.30, 0.60, 0.90]
PACKING_CHOICES = [0.60, 0.70, 0.80, 0.90, 1.00]

POP_SIZE = 28
GENERATIONS = 12
ELITE_KEEP = 8

BATCHES = 80
PARTICLES = 300000

YZ_HALF = 5.0
N_MESH_X = 160
SOURCE_ENERGY_EV = 14.1e6
ENERGY_BINS = [0.0, 1.0e3, 1.0e5, 1.0e6, 5.0e6, 10.0e6, 14.2e6, 20.0e6]


def material_uses_lithium(name: str) -> bool:
    for comp in MATERIALS[name]["components"]:
        if comp[0] == "nuclide" and comp[1] in ("Li6", "Li7"):
            return True
    return False


def material_is_multiplier(name: str) -> bool:
    return name in ("Be", "Be12Ti")


# ---------- MATERIAL BUILD ----------

def build_material(name: str, li6_enrich: float = 0.90, packing: float = 1.0) -> openmc.Material:
    spec = MATERIALS[name]
    m = openmc.Material(name=name)

    density = spec["density"]
    if spec.get("porous_ok", False):
        density *= packing
    m.set_density("g/cm3", density)

    for kind, sym, frac, pct in spec["components"]:
        if kind == "element":
            m.add_element(sym, frac, percent_type=pct)
        elif kind == "nuclide":
            if sym not in ("Li6", "Li7"):
                m.add_nuclide(sym, frac, percent_type=pct)

    li6_base = 0.0
    li7_base = 0.0
    for kind, sym, frac, pct in spec["components"]:
        if kind == "nuclide" and sym == "Li6":
            li6_base += frac
        elif kind == "nuclide" and sym == "Li7":
            li7_base += frac

    li_total = li6_base + li7_base
    if li_total > 0.0:
        m.add_nuclide("Li6", li_total * li6_enrich, percent_type="ao")
        m.add_nuclide("Li7", li_total * (1.0 - li6_enrich), percent_type="ao")

    return m


# ---------- OPENMC SETUP ----------

def write_settings(run_dir: Path) -> None:
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.001, 0.0, 0.0))
    source.angle = openmc.stats.Monodirectional((1.0, 0.0, 0.0))
    source.energy = openmc.stats.Discrete([SOURCE_ENERGY_EV], [1.0])

    settings = openmc.Settings()
    settings.run_mode = "fixed source"
    settings.source = source
    settings.batches = BATCHES
    settings.inactive = 0
    settings.particles = PARTICLES
    settings.export_to_xml(run_dir / "settings.xml")


def write_tallies(run_dir: Path, thickness_cm: float, cells: list[openmc.Cell]) -> None:
    mesh = openmc.RegularMesh()
    mesh.dimension = (N_MESH_X, 1, 1)
    mesh.lower_left = (0.0, -YZ_HALF, -YZ_HALF)
    mesh.upper_right = (thickness_cm, YZ_HALF, YZ_HALF)

    flux_mesh = openmc.Tally(name="flux_mesh")
    flux_mesh.filters = [openmc.MeshFilter(mesh)]
    flux_mesh.scores = ["flux"]

    flux_energy = openmc.Tally(name="flux_energy")
    flux_energy.filters = [openmc.MeshFilter(mesh), openmc.EnergyFilter(ENERGY_BINS)]
    flux_energy.scores = ["flux"]

    h3_prod = openmc.Tally(name="h3_prod_by_layer")
    h3_prod.filters = [openmc.CellFilter(cells)]
    h3_prod.scores = ["H3-production"]

    heating = openmc.Tally(name="heating_by_layer")
    heating.filters = [openmc.CellFilter(cells)]
    heating.scores = ["heating-local"]

    tallies = openmc.Tallies([flux_mesh, flux_energy, h3_prod, heating])
    tallies.export_to_xml(run_dir / "tallies.xml")


# ---------- GEOMETRY ----------

def build_stack_case(design: dict, run_dir: Path) -> None:
    mats = [
        build_material(design["l1"], design["l1_li6"], design["l1_pack"]),
        build_material(design["l2"], design["l2_li6"], design["l2_pack"]),
        build_material(design["l3"], design["l3_li6"], design["l3_pack"]),
        build_material(design["l4"], design["l4_li6"], design["l4_pack"]),
    ]
    openmc.Materials(mats).export_to_xml(run_dir / "materials.xml")

    f1, f2, f3, f4 = design["split"]
    total_cm = design["total_cm"]

    x1v = total_cm * f1
    x2v = total_cm * (f1 + f2)
    x3v = total_cm * (f1 + f2 + f3)

    x0 = openmc.XPlane(x0=0.0, boundary_type="vacuum")
    x1 = openmc.XPlane(x0=x1v)
    x2 = openmc.XPlane(x0=x2v)
    x3 = openmc.XPlane(x0=x3v)
    x4 = openmc.XPlane(x0=total_cm, boundary_type="vacuum")

    y0 = openmc.YPlane(y0=-YZ_HALF, boundary_type="vacuum")
    y1 = openmc.YPlane(y0=YZ_HALF, boundary_type="vacuum")
    z0 = openmc.ZPlane(z0=-YZ_HALF, boundary_type="vacuum")
    z1 = openmc.ZPlane(z0=YZ_HALF, boundary_type="vacuum")

    c1 = openmc.Cell(region=+x0 & -x1 & +y0 & -y1 & +z0 & -z1, fill=mats[0])
    c2 = openmc.Cell(region=+x1 & -x2 & +y0 & -y1 & +z0 & -z1, fill=mats[1])
    c3 = openmc.Cell(region=+x2 & -x3 & +y0 & -y1 & +z0 & -z1, fill=mats[2])
    c4 = openmc.Cell(region=+x3 & -x4 & +y0 & -y1 & +z0 & -z1, fill=mats[3])

    openmc.Geometry([c1, c2, c3, c4]).export_to_xml(run_dir / "geometry.xml")

    write_settings(run_dir)
    write_tallies(run_dir, total_cm, [c1, c2, c3, c4])


# ---------- RUN OPENMC ----------

def run_case(run_dir: Path) -> tuple[bool, str]:
    try:
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(THREADS)

        result = subprocess.run(
            ["openmc"],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=7200,
            env=env,
        )

        ok = result.returncode == 0
        msg = (result.stdout[-1200:] if ok else (result.stderr[-1200:] or result.stdout[-1200:])).replace("\n", " | ")

        return ok, msg

    except subprocess.TimeoutExpired:
        return False, "Timed out after 7200 s"


# ---------- POSTPROCESS ----------

def postprocess_case(run_dir: Path, design: dict) -> dict:
    sp_files = sorted(run_dir.glob("statepoint.*.h5"))
    if not sp_files:
        raise FileNotFoundError("No statepoint file found")

    sp = openmc.StatePoint(str(sp_files[-1]))

    flux_mesh = sp.get_tally(name="flux_mesh").mean.flatten()
    flux_energy = sp.get_tally(name="flux_energy").mean.reshape((N_MESH_X, len(ENERGY_BINS) - 1))
    h3_prod = sp.get_tally(name="h3_prod_by_layer").mean.flatten()
    heating = sp.get_tally(name="heating_by_layer").mean.flatten()

    front_flux = float(flux_mesh[0])
    back_flux = float(flux_mesh[-1])

    att_back = back_flux / front_flux if front_flux > 0 else math.nan

    h3_total = float(sum(h3_prod))
    heat_total = float(sum(heating))

    heat_frac_l1 = heating[0] / heat_total if heat_total > 0 else 0

    score = att_back / (1 + 200 * h3_total) * (1 + heat_frac_l1)

    return {
        "front_flux": front_flux,
        "back_flux": back_flux,
        "attenuation_back_vs_front": att_back,
        "h3_total": h3_total,
        "heat_frac_l1": heat_frac_l1,
        "score": score,
    }


# ---------- CSV ----------

def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return

    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


# ---------- EVOLUTION ----------

def random_layer():
    mat = random.choice(CANDIDATES)
    li6 = random.choice(LI6_ENRICH_CHOICES) if material_uses_lithium(mat) else 0
    pack = random.choice(PACKING_CHOICES) if MATERIALS[mat].get("porous_ok", False) else 1
    return mat, li6, pack


def random_design():
    l1, l1_li6, l1_pack = random_layer()
    l2, l2_li6, l2_pack = random_layer()
    l3, l3_li6, l3_pack = random_layer()
    l4, l4_li6, l4_pack = random_layer()

    return {
        "l1": l1, "l1_li6": l1_li6, "l1_pack": l1_pack,
        "l2": l2, "l2_li6": l2_li6, "l2_pack": l2_pack,
        "l3": l3, "l3_li6": l3_li6, "l3_pack": l3_pack,
        "l4": l4, "l4_li6": l4_li6, "l4_pack": l4_pack,
        "total_cm": random.choice(TOTAL_THICKNESS_CHOICES),
        "split": random.choice(SPLIT_CHOICES),
    }


def mutate_layer(design: dict, layer_name: str) -> None:
    mat, li6, pack = random_layer()
    design[layer_name] = mat
    design[f"{layer_name}_li6"] = li6
    design[f"{layer_name}_pack"] = pack


def mutate_design(parent: dict) -> dict:
    child = dict(parent)

    choice = random.choice(["l1", "l2", "l3", "l4", "total_cm", "split"])

    if choice in ("l1", "l2", "l3", "l4"):
        mutate_layer(child, choice)

    elif choice == "total_cm":
        child["total_cm"] = random.choice(TOTAL_THICKNESS_CHOICES)

    elif choice == "split":
        child["split"] = random.choice(SPLIT_CHOICES)

    return child


def crossover(a: dict, b: dict) -> dict:
    child = {}

    for lname in ("l1", "l2", "l3", "l4"):
        src = random.choice([a, b])
        child[lname] = src[lname]
        child[f"{lname}_li6"] = src[f"{lname}_li6"]
        child[f"{lname}_pack"] = src[f"{lname}_pack"]

    child["total_cm"] = random.choice([a["total_cm"], b["total_cm"]])
    child["split"] = random.choice([a["split"], b["split"]])

    return child


def row_to_design(row: dict) -> dict:
    return {
        "l1": row["l1"],
        "l1_li6": float(row["l1_li6"]),
        "l1_pack": float(row["l1_pack"]),
        "l2": row["l2"],
        "l2_li6": float(row["l2_li6"]),
        "l2_pack": float(row["l2_pack"]),
        "l3": row["l3"],
        "l3_li6": float(row["l3_li6"]),
        "l3_pack": float(row["l3_pack"]),
        "l4": row["l4"],
        "l4_li6": float(row["l4_li6"]),
        "l4_pack": float(row["l4_pack"]),
        "total_cm": float(row["total_thickness_cm"]),
        "split": tuple(float(x) / 100 for x in row["split"].split("_")),
    }


# ---------- MAIN ----------

def run_design_wrapper(args):
    return run_design(*args)


def run_design(design: dict, generation: int, idx: int) -> dict:
    split_tag = "_".join(str(int(x * 100)) for x in design["split"])

    run_name = (
        f"gen{generation:02d}_{idx:03d}__"
        f"{design['l1']}__{design['l2']}__{design['l3']}__{design['l4']}__"
        f"{str(design['total_cm']).replace('.', 'p')}cm__{split_tag}"
    )

    run_dir = RUNS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Building {run_name} ===")

    build_stack_case(design, run_dir)

    print(f"=== Running {run_name} with {THREADS} threads ===")

    ok, msg = run_case(run_dir)

    row = {
        "generation": generation,
        "run_name": run_name,
        "l1": design["l1"],
        "l1_li6": design["l1_li6"],
        "l1_pack": design["l1_pack"],
        "l2": design["l2"],
        "l2_li6": design["l2_li6"],
        "l2_pack": design["l2_pack"],
        "l3": design["l3"],
        "l3_li6": design["l3_li6"],
        "l3_pack": design["l3_pack"],
        "l4": design["l4"],
        "l4_li6": design["l4_li6"],
        "l4_pack": design["l4_pack"],
        "total_thickness_cm": design["total_cm"],
        "split": split_tag,
        "ok": ok,
        "message": msg,
    }

    if ok:
        try:
            row.update(postprocess_case(run_dir, design))
            print(f"done: score={row['score']:.6g}")
        except Exception as e:
            row["ok"] = False
            row["message"] = f"Postprocess failed: {e}"

    return row


def main():
    all_rows = []
    population = []

    while len(population) < POP_SIZE:
        population.append(random_design())

    for gen in range(GENERATIONS):

        print(f"\n================ GENERATION {gen} ================")

        tasks = [(design, gen, i) for i, design in enumerate(population)]

        with mp.Pool(POOL_WORKERS) as pool:
            results = pool.map(run_design_wrapper, tasks)

        gen_rows = results

        for row in gen_rows:
            all_rows.append(row)

        write_csv(BASE_DIR / "evo_blanket_results_v6.csv", all_rows)

        good = [r for r in gen_rows if r["ok"]]
        good.sort(key=lambda r: float(r["score"]))

        print("\nTop generation designs:")

        for r in good[:8]:
            print(
                f"{r['l1']} | {r['l2']} | {r['l3']} | {r['l4']} | "
                f"score={r['score']:.6g}"
            )

        population = []

        for r in good[:ELITE_KEEP]:
            population.append(row_to_design(r))

        while len(population) < POP_SIZE:
            if random.random() < 0.5:
                population.append(mutate_design(random.choice(population)))
            else:
                population.append(crossover(random.choice(population), random.choice(population)))

    final_good = [r for r in all_rows if r["ok"]]
    final_good.sort(key=lambda r: float(r["score"]))

    print("\nTop 25 blanket candidates overall:")

    for r in final_good[:25]:
        print(
            f"gen{r['generation']:02d} | "
            f"{r['l1']} | {r['l2']} | {r['l3']} | {r['l4']} | "
            f"{r['total_thickness_cm']} cm | split {r['split']} | "
            f"score={r['score']:.6g}"
        )

    print("\nFinished. Wrote evo_blanket_results_v6.csv")


if __name__ == "__main__":
    main()

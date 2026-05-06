import csv
import math
import os
import random
import subprocess
from pathlib import Path

import openmc


BASE_DIR = Path.cwd()
RUNS_DIR = BASE_DIR / "runs_evo_blanket_v2"
RUNS_DIR.mkdir(exist_ok=True)

random.seed(1337)

# Use all CPU cores unless you want to cap it manually
THREADS = max(1, os.cpu_count() or 1)

# -------------------------------------------------
# Materials
# -------------------------------------------------
# No Be / F here, since your current library doesn't support them.
# Lithium-bearing materials use explicit Li6/Li7 enrichment.
# Atom ratios are approximate screening compositions, not fabrication-ready specs.
MATERIALS = {
    "W": {
        "density": 19.3,
        "kind": "manual",
        "components": [("nuclide", "W182", 0.265), ("nuclide", "W183", 0.143),
                       ("nuclide", "W184", 0.306), ("nuclide", "W186", 0.286)],
    },
    "B4C": {
        "density": 2.52,
        "kind": "elemental",
        "components": [("element", "B", 4.0, "ao"), ("element", "C", 1.0, "ao")],
    },
    "SiC": {
        "density": 3.21,
        "kind": "elemental",
        "components": [("element", "Si", 1.0, "ao"), ("element", "C", 1.0, "ao")],
    },
    "TiB2": {
        "density": 4.52,
        "kind": "elemental",
        "components": [("element", "Ti", 1.0, "ao"), ("element", "B", 2.0, "ao")],
    },
    "Pb": {
        "density": 11.34,
        "kind": "elemental",
        "components": [("element", "Pb", 1.0, "ao")],
    },
    "PbLi": {
        "density": 9.8,
        "kind": "manual",
        "components": [
            ("element", "Pb", 0.83, "ao"),
            ("nuclide", "Li6", 0.153, "ao"),
            ("nuclide", "Li7", 0.017, "ao"),
        ],
    },
    "Li2O": {
        "density": 2.01,
        "kind": "manual",
        "components": [
            ("nuclide", "Li6", 1.8, "ao"),
            ("nuclide", "Li7", 0.2, "ao"),
            ("element", "O", 1.0, "ao"),
        ],
    },
    "Li2TiO3": {
        "density": 3.43,
        "kind": "manual",
        "components": [
            ("nuclide", "Li6", 1.8, "ao"),
            ("nuclide", "Li7", 0.2, "ao"),
            ("element", "Ti", 1.0, "ao"),
            ("element", "O", 3.0, "ao"),
        ],
    },
    "Li4SiO4": {
        "density": 2.39,
        "kind": "manual",
        "components": [
            ("nuclide", "Li6", 3.6, "ao"),
            ("nuclide", "Li7", 0.4, "ao"),
            ("element", "Si", 1.0, "ao"),
            ("element", "O", 4.0, "ao"),
        ],
    },
    "W_Ti_B4C_60_30_10_wt": {
        "density": 13.45,
        "kind": "elemental",
        "components": [
            ("element", "W", 0.60, "wo"),
            ("element", "Ti", 0.30, "wo"),
            ("element", "B", 0.07826, "wo"),
            ("element", "C", 0.02174, "wo"),
        ],
    },
    "W_Ti_B4C_Cr_55_25_10_10_wt": {
        "density": 12.78,
        "kind": "elemental",
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
        "kind": "elemental",
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

# -------------------------------------------------
# Search controls
# -------------------------------------------------
TOTAL_THICKNESS_CHOICES = [10.0, 15.0]
SPLIT_CHOICES = [
    (0.20, 0.30, 0.50),
    (0.25, 0.25, 0.50),
    (0.33, 0.33, 0.34),
    (0.15, 0.35, 0.50),
]

POP_SIZE = 24
GENERATIONS = 8
ELITE_KEEP = 8

BATCHES = 60
PARTICLES = 200000

YZ_HALF = 5.0
N_MESH_X = 120
SOURCE_ENERGY_EV = 14.1e6
ENERGY_BINS = [0.0, 1.0e3, 1.0e5, 1.0e6, 5.0e6, 10.0e6, 14.2e6, 20.0e6]


def build_material(name: str) -> openmc.Material:
    spec = MATERIALS[name]
    m = openmc.Material(name=name)
    m.set_density("g/cm3", spec["density"])

    for item in spec["components"]:
        if item[0] == "element":
            _, sym, frac, pct = item
            m.add_element(sym, frac, percent_type=pct)
        elif item[0] == "nuclide":
            if len(item) == 4:
                _, nuc, frac, pct = item
            else:
                _, nuc, frac = item
                pct = "ao"
            m.add_nuclide(nuc, frac, percent_type=pct)
        else:
            raise ValueError(f"Unknown component type in {name}: {item}")

    return m


def write_settings(run_dir: Path):
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


def write_tallies(run_dir: Path, thickness_cm: float, cells: list[openmc.Cell]):
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

    # Direct Li6 breeding proxy:
    # Li6(n,alpha)t and Li6(n,t)alpha are the same physical reaction channel.
    # In OpenMC, tallying Li6 (n,a) works as a direct breeding-rate proxy.
    li6_breed = openmc.Tally(name="li6_breed_by_layer")
    li6_breed.filters = [openmc.CellFilter(cells)]
    li6_breed.nuclides = ["Li6"]
    li6_breed.scores = ["(n,a)"]

    tallies = openmc.Tallies([flux_mesh, flux_energy, li6_breed])
    tallies.export_to_xml(run_dir / "tallies.xml")


def build_stack_case(front: str, middle: str, back: str, total_cm: float, split: tuple[float, float, float], run_dir: Path):
    mats = [build_material(front), build_material(middle), build_material(back)]
    openmc.Materials(mats).export_to_xml(run_dir / "materials.xml")

    f1, f2, f3 = split
    x_a = total_cm * f1
    x_b = total_cm * (f1 + f2)

    x0 = openmc.XPlane(x0=0.0, boundary_type="vacuum")
    x1 = openmc.XPlane(x0=x_a)
    x2 = openmc.XPlane(x0=x_b)
    x3 = openmc.XPlane(x0=total_cm, boundary_type="vacuum")
    y0 = openmc.YPlane(y0=-YZ_HALF, boundary_type="vacuum")
    y1 = openmc.YPlane(y0=YZ_HALF, boundary_type="vacuum")
    z0 = openmc.ZPlane(z0=-YZ_HALF, boundary_type="vacuum")
    z1 = openmc.ZPlane(z0=YZ_HALF, boundary_type="vacuum")

    c1 = openmc.Cell(region=+x0 & -x1 & +y0 & -y1 & +z0 & -z1, fill=mats[0])
    c2 = openmc.Cell(region=+x1 & -x2 & +y0 & -y1 & +z0 & -z1, fill=mats[1])
    c3 = openmc.Cell(region=+x2 & -x3 & +y0 & -y1 & +z0 & -z1, fill=mats[2])

    openmc.Geometry([c1, c2, c3]).export_to_xml(run_dir / "geometry.xml")
    write_settings(run_dir)
    write_tallies(run_dir, total_cm, [c1, c2, c3])


def run_case(run_dir: Path):
    try:
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(THREADS)
        result = subprocess.run(
            ["openmc"],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=3600,
            env=env,
        )
        ok = result.returncode == 0
        msg = (result.stdout[-1000:] if ok else (result.stderr[-1000:] or result.stdout[-1000:])).replace("\n", " | ")
        return ok, msg
    except subprocess.TimeoutExpired:
        return False, "Timed out after 3600 s"


def postprocess_case(run_dir: Path):
    sp_files = sorted(run_dir.glob("statepoint.*.h5"))
    if not sp_files:
        raise FileNotFoundError("No statepoint file found")

    sp = openmc.StatePoint(str(sp_files[-1]))
    flux_mesh = sp.get_tally(name="flux_mesh").mean.flatten()
    flux_energy = sp.get_tally(name="flux_energy").mean.reshape((N_MESH_X, len(ENERGY_BINS) - 1))
    li6_breed = sp.get_tally(name="li6_breed_by_layer").mean.flatten()

    front_flux = float(flux_mesh[0])
    mid_flux = float(flux_mesh[len(flux_mesh) // 2])
    back_flux = float(flux_mesh[-1])

    att_mid = mid_flux / front_flux if front_flux > 0 else math.nan
    att_back = back_flux / front_flux if front_flux > 0 else math.nan

    front_spec = flux_energy[0, :]
    back_spec = flux_energy[-1, :]

    front_total = float(front_spec.sum())
    back_total = float(back_spec.sum())

    high_front = float(front_spec[-2:].sum())
    high_back = float(back_spec[-2:].sum())

    low_front = float(front_spec[:2].sum())
    low_back = float(back_spec[:2].sum())

    high_survival = high_back / high_front if high_front > 0 else math.nan
    soften = (low_back / back_total) / (low_front / front_total) if front_total > 0 and back_total > 0 and low_front > 0 else math.nan

    # direct Li6 reaction information by layer
    li6_front = float(li6_breed[0]) if len(li6_breed) > 0 else 0.0
    li6_middle = float(li6_breed[1]) if len(li6_breed) > 1 else 0.0
    li6_back = float(li6_breed[2]) if len(li6_breed) > 2 else 0.0
    li6_total = li6_front + li6_middle + li6_back

    # weight earlier breeding a bit more favorably
    li6_weighted = 1.0 * li6_front + 0.9 * li6_middle + 0.6 * li6_back

    # lower is better
    score = att_back
    if not math.isnan(high_survival):
        score *= (1.0 + high_survival)
    if not math.isnan(soften):
        score /= max(soften, 1e-12)

    # reward direct Li6 reactions
    score /= (1.0 + 50.0 * li6_weighted)

    return {
        "front_flux": front_flux,
        "mid_flux": mid_flux,
        "back_flux": back_flux,
        "attenuation_mid_vs_front": att_mid,
        "attenuation_back_vs_front": att_back,
        "high_energy_survival": high_survival,
        "spectrum_softening_factor": soften,
        "li6_breed_front": li6_front,
        "li6_breed_middle": li6_middle,
        "li6_breed_back": li6_back,
        "li6_breed_total": li6_total,
        "li6_breed_weighted": li6_weighted,
        "score": score,
    }


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def random_design():
    return {
        "front": random.choice(CANDIDATES),
        "middle": random.choice(CANDIDATES),
        "back": random.choice(CANDIDATES),
        "total_cm": random.choice(TOTAL_THICKNESS_CHOICES),
        "split": random.choice(SPLIT_CHOICES),
    }


def mutate_design(parent: dict):
    child = dict(parent)
    choice = random.choice(["front", "middle", "back", "total_cm", "split", "swap"])
    if choice in ("front", "middle", "back"):
        child[choice] = random.choice(CANDIDATES)
    elif choice == "total_cm":
        child["total_cm"] = random.choice(TOTAL_THICKNESS_CHOICES)
    elif choice == "split":
        child["split"] = random.choice(SPLIT_CHOICES)
    elif choice == "swap":
        a, b = random.sample(["front", "middle", "back"], 2)
        child[a], child[b] = child[b], child[a]
    return child


def crossover(a: dict, b: dict):
    return {
        "front": random.choice([a["front"], b["front"]]),
        "middle": random.choice([a["middle"], b["middle"]]),
        "back": random.choice([a["back"], b["back"]]),
        "total_cm": random.choice([a["total_cm"], b["total_cm"]]),
        "split": random.choice([a["split"], b["split"]]),
    }


def design_key(d: dict):
    return (d["front"], d["middle"], d["back"], d["total_cm"], d["split"])


def run_design(design: dict, generation: int, idx: int):
    split_tag = f"{int(design['split'][0]*100)}_{int(design['split'][1]*100)}_{int(design['split'][2]*100)}"
    run_name = f"gen{generation:02d}_{idx:03d}__{design['front']}__{design['middle']}__{design['back']}__{str(design['total_cm']).replace('.', 'p')}cm__{split_tag}"
    run_dir = RUNS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Building {run_name} ===")
    build_stack_case(design["front"], design["middle"], design["back"], design["total_cm"], design["split"], run_dir)

    print(f"=== Running {run_name} with {THREADS} threads ===")
    ok, msg = run_case(run_dir)

    row = {
        "generation": generation,
        "run_name": run_name,
        "front": design["front"],
        "middle": design["middle"],
        "back": design["back"],
        "total_thickness_cm": design["total_cm"],
        "split": split_tag,
        "ok": ok,
        "message": msg,
    }

    if ok:
        try:
            row.update(postprocess_case(run_dir))
            print(
                f"done: score={row['score']:.6g}, "
                f"back/front={row['attenuation_back_vs_front']:.6g}, "
                f"high_survival={row['high_energy_survival']:.6g}, "
                f"li6_total={row['li6_breed_total']:.6g}"
            )
        except Exception as e:
            row["ok"] = False
            row["message"] = f"Postprocess failed: {e}"
            print(row["message"])
    else:
        print("failed:", msg)

    return row


def main():
    all_rows = []
    population = []
    seen = set()

    while len(population) < POP_SIZE:
        d = random_design()
        k = design_key(d)
        if k not in seen:
            seen.add(k)
            population.append(d)

    for gen in range(GENERATIONS):
        print(f"\n================ GENERATION {gen} ================")
        gen_rows = []

        for i, design in enumerate(population):
            row = run_design(design, gen, i)
            gen_rows.append(row)
            all_rows.append(row)
            write_csv(BASE_DIR / "evo_blanket_results_v2.csv", all_rows)

        good = [r for r in gen_rows if r["ok"] is True]
        good.sort(key=lambda r: float(r["score"]))

        print(f"\nTop generation {gen} designs:")
        for r in good[:8]:
            print(
                f"{r['front']} | {r['middle']} | {r['back']} | "
                f"{r['total_thickness_cm']} cm | split {r['split']} | "
                f"score={r['score']:.6g} | back/front={r['attenuation_back_vs_front']:.6g} | "
                f"li6_total={r['li6_breed_total']:.6g}"
            )

        elites = good[:ELITE_KEEP]
        next_population = []
        next_seen = set()

        for r in elites:
            d = {
                "front": r["front"],
                "middle": r["middle"],
                "back": r["back"],
                "total_cm": float(r["total_thickness_cm"]),
                "split": tuple(float(x) / 100.0 for x in r["split"].split("_")),
            }
            k = design_key(d)
            if k not in next_seen:
                next_seen.add(k)
                next_population.append(d)

        elite_designs = list(next_population)

        while len(next_population) < POP_SIZE:
            if len(elite_designs) >= 2 and random.random() < 0.65:
                a, b = random.sample(elite_designs, 2)
                child = crossover(a, b)
            else:
                a = random.choice(elite_designs if elite_designs else population)
                child = mutate_design(a)

            if random.random() < 0.35:
                child = mutate_design(child)

            k = design_key(child)
            if k not in next_seen:
                next_seen.add(k)
                next_population.append(child)

        population = next_population

    final_good = [r for r in all_rows if r["ok"] is True]
    final_good.sort(key=lambda r: float(r["score"]))

    print("\nTop 25 blanket candidates overall:")
    for r in final_good[:25]:
        print(
            f"gen{r['generation']:02d} | {r['front']} | {r['middle']} | {r['back']} | "
            f"{r['total_thickness_cm']} cm | split {r['split']} | "
            f"score={r['score']:.6g} | back/front={r['attenuation_back_vs_front']:.6g} | "
            f"high_survival={r['high_energy_survival']:.6g} | "
            f"li6_total={r['li6_breed_total']:.6g}"
        )

    print("\nFinished. Wrote evo_blanket_results_v2.csv")


if __name__ == "__main__":
    main()

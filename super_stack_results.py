import csv
import math
import subprocess
from itertools import product
from pathlib import Path

import openmc


BASE_DIR = Path.cwd()
RUNS_DIR = BASE_DIR / "runs_super"
RUNS_DIR.mkdir(exist_ok=True)

# Keep this list tight so the search stays useful and not stupidly large
MATERIALS = {
    "W": {
        "density": 19.3,
        "elements": [("W", 1.0, "ao")],
    },
    "B4C": {
        "density": 2.52,
        "elements": [("B", 4.0, "ao"), ("C", 1.0, "ao")],
    },
    "SiC": {
        "density": 3.21,
        "elements": [("Si", 1.0, "ao"), ("C", 1.0, "ao")],
    },
    "TiB2": {
        "density": 4.52,
        "elements": [("Ti", 1.0, "ao"), ("B", 2.0, "ao")],
    },
    "Pb": {
        "density": 11.34,
        "elements": [("Pb", 1.0, "ao")],
    },
    "W_Ti_B4C_60_30_10_wt": {
        "density": 13.45,
        "elements": [("W", 0.60, "wo"), ("Ti", 0.30, "wo"), ("B", 0.07826, "wo"), ("C", 0.02174, "wo")],
    },
    "W_Ti_B4C_Cr_55_25_10_10_wt": {
        "density": 12.78,
        "elements": [("W", 0.55, "wo"), ("Ti", 0.25, "wo"), ("B", 0.07826, "wo"), ("C", 0.02174, "wo"), ("Cr", 0.10, "wo")],
    },
    "W_Ti_B4C_Al2O3_55_25_10_10_wt": {
        "density": 11.84,
        "elements": [("W", 0.55, "wo"), ("Ti", 0.25, "wo"), ("B", 0.07826, "wo"), ("C", 0.02174, "wo"), ("Al", 0.0529, "wo"), ("O", 0.0471, "wo")],
    },
}

# Search space
TOTAL_THICKNESSES_CM = [5.0, 10.0]
# Fractions for front/mid/back
SPLITS = [
    (0.20, 0.30, 0.50),
    (0.25, 0.25, 0.50),
    (0.33, 0.33, 0.34),
]

# Keep cases meaningful: ordered 3-layer stacks
CANDIDATES = list(MATERIALS.keys())

# Simulation controls
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
    for el, frac, pct_type in spec["elements"]:
        m.add_element(el, frac, percent_type=pct_type)
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


def write_tallies(run_dir: Path, thickness_cm: float):
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

    tallies = openmc.Tallies([flux_mesh, flux_energy])
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
    write_tallies(run_dir, total_cm)


def run_case(run_dir: Path):
    try:
        result = subprocess.run(
            ["openmc"],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=3600,
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
    low_build = low_back / low_front if low_front > 0 else math.nan
    soften = (low_back / back_total) / (low_front / front_total) if front_total > 0 and back_total > 0 and low_front > 0 else math.nan

    # lower is better
    score = att_back
    if not math.isnan(high_survival):
        score *= (1.0 + high_survival)
    if not math.isnan(soften):
        score /= max(soften, 1e-12)

    return {
        "front_flux": front_flux,
        "mid_flux": mid_flux,
        "back_flux": back_flux,
        "attenuation_mid_vs_front": att_mid,
        "attenuation_back_vs_front": att_back,
        "high_energy_survival": high_survival,
        "low_energy_build_ratio": low_build,
        "spectrum_softening_factor": soften,
        "score": score,
    }


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def main():
    rows = []

    for total_cm in TOTAL_THICKNESSES_CM:
        for split in SPLITS:
            split_tag = f"{int(split[0]*100)}_{int(split[1]*100)}_{int(split[2]*100)}"
            for front, middle, back in product(CANDIDATES, CANDIDATES, CANDIDATES):
                run_name = f"{front}__{middle}__{back}__{str(total_cm).replace('.', 'p')}cm__{split_tag}"
                run_dir = RUNS_DIR / run_name
                run_dir.mkdir(parents=True, exist_ok=True)

                print(f"\n=== Building {run_name} ===")
                build_stack_case(front, middle, back, total_cm, split, run_dir)

                print(f"=== Running {run_name} ===")
                ok, msg = run_case(run_dir)

                row = {
                    "run_name": run_name,
                    "front": front,
                    "middle": middle,
                    "back": back,
                    "total_thickness_cm": total_cm,
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
                            f"soften={row['spectrum_softening_factor']:.6g}"
                        )
                    except Exception as e:
                        row["ok"] = False
                        row["message"] = f"Postprocess failed: {e}"
                        print(row["message"])
                else:
                    print("failed:", msg)

                rows.append(row)
                write_csv(BASE_DIR / "super_stack_results.csv", rows)

    good = [r for r in rows if r["ok"] is True]
    good.sort(key=lambda r: float(r["score"]))

    print("\nTop 20 super-stacks:")
    for r in good[:20]:
        print(
            f"{r['front']} | {r['middle']} | {r['back']} | "
            f"{r['total_thickness_cm']} cm | split {r['split']} | "
            f"score={r['score']:.6g} | back/front={r['attenuation_back_vs_front']:.6g}"
        )

    print("\nFinished. Wrote super_stack_results.csv")


if __name__ == "__main__":
    main()

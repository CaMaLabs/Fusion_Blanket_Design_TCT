import csv
import math
import subprocess
from pathlib import Path

import openmc


BASE_DIR = Path.cwd()
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

# -----------------------------
# Materials
# -----------------------------
MATERIALS = {
    "W": {
        "density": 19.3,
        "elements": [("W", 1.0, "ao")],
    },
    "Ti": {
        "density": 4.5,
        "elements": [("Ti", 1.0, "ao")],
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
    "W_Ti_70_30_wt": {
        "density": 14.86,
        "elements": [("W", 0.70, "wo"), ("Ti", 0.30, "wo")],
    },
    "W_B4C_70_30_wt": {
        "density": 14.23,
        "elements": [("W", 0.70, "wo"), ("B", 0.2348, "wo"), ("C", 0.0652, "wo")],
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

# -----------------------------
# Overnight campaign definition
# -----------------------------
SINGLE_THICKNESSES_CM = [0.5, 1.0, 2.0, 5.0, 10.0]
STACK_THICKNESSES_CM = [2.0, 5.0, 10.0]

# Good initial stack ideas
STACKS = [
    ("W", "B4C"),
    ("W", "SiC"),
    ("W", "TiB2"),
    ("W", "Pb"),
    ("W", "W_Ti_B4C_60_30_10_wt"),
    ("W", "W_Ti_B4C_Cr_55_25_10_10_wt"),
    ("W", "W_Ti_B4C_Al2O3_55_25_10_10_wt"),
    ("Pb", "B4C"),
    ("Pb", "SiC"),
    ("Ti", "B4C"),
]

BATCHES = 80
PARTICLES = 300000

YZ_HALF = 5.0
N_MESH_X = 120
SOURCE_ENERGY_EV = 14.1e6

# Energy groups for insight, not just one scalar
ENERGY_BINS = [
    0.0,
    1.0e3,
    1.0e5,
    1.0e6,
    5.0e6,
    10.0e6,
    14.2e6,
    20.0e6,
]


def build_material(name: str) -> openmc.Material:
    spec = MATERIALS[name]
    m = openmc.Material(name=name)
    m.set_density("g/cm3", spec["density"])
    for el, frac, pct_type in spec["elements"]:
        m.add_element(el, frac, percent_type=pct_type)
    return m


def build_single_case(material_name: str, thickness_cm: float, run_dir: Path):
    mat = build_material(material_name)
    materials = openmc.Materials([mat])
    materials.export_to_xml(run_dir / "materials.xml")

    x0 = openmc.XPlane(x0=0.0, boundary_type="vacuum")
    x1 = openmc.XPlane(x0=thickness_cm, boundary_type="vacuum")
    y0 = openmc.YPlane(y0=-YZ_HALF, boundary_type="vacuum")
    y1 = openmc.YPlane(y0=YZ_HALF, boundary_type="vacuum")
    z0 = openmc.ZPlane(z0=-YZ_HALF, boundary_type="vacuum")
    z1 = openmc.ZPlane(z0=YZ_HALF, boundary_type="vacuum")

    cell = openmc.Cell(region=+x0 & -x1 & +y0 & -y1 & +z0 & -z1, fill=mat)
    geometry = openmc.Geometry([cell])
    geometry.export_to_xml(run_dir / "geometry.xml")

    _write_settings(run_dir)
    _write_tallies(run_dir, thickness_cm)


def build_stack_case(front_name: str, back_name: str, total_thickness_cm: float, run_dir: Path):
    front = build_material(front_name)
    back = build_material(back_name)
    materials = openmc.Materials([front, back])
    materials.export_to_xml(run_dir / "materials.xml")

    split = total_thickness_cm * 0.5

    x0 = openmc.XPlane(x0=0.0, boundary_type="vacuum")
    x1 = openmc.XPlane(x0=split)
    x2 = openmc.XPlane(x0=total_thickness_cm, boundary_type="vacuum")
    y0 = openmc.YPlane(y0=-YZ_HALF, boundary_type="vacuum")
    y1 = openmc.YPlane(y0=YZ_HALF, boundary_type="vacuum")
    z0 = openmc.ZPlane(z0=-YZ_HALF, boundary_type="vacuum")
    z1 = openmc.ZPlane(z0=YZ_HALF, boundary_type="vacuum")

    cell1 = openmc.Cell(region=+x0 & -x1 & +y0 & -y1 & +z0 & -z1, fill=front)
    cell2 = openmc.Cell(region=+x1 & -x2 & +y0 & -y1 & +z0 & -z1, fill=back)
    geometry = openmc.Geometry([cell1, cell2])
    geometry.export_to_xml(run_dir / "geometry.xml")

    _write_settings(run_dir)
    _write_tallies(run_dir, total_thickness_cm)


def _write_settings(run_dir: Path):
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


def _write_tallies(run_dir: Path, thickness_cm: float):
    mesh = openmc.RegularMesh()
    mesh.dimension = (N_MESH_X, 1, 1)
    mesh.lower_left = (0.0, -YZ_HALF, -YZ_HALF)
    mesh.upper_right = (thickness_cm, YZ_HALF, YZ_HALF)

    flux_mesh = openmc.Tally(name="flux_mesh")
    flux_mesh.filters = [openmc.MeshFilter(mesh)]
    flux_mesh.scores = ["flux"]

    flux_energy = openmc.Tally(name="flux_energy")
    flux_energy.filters = [
        openmc.MeshFilter(mesh),
        openmc.EnergyFilter(ENERGY_BINS),
    ]
    flux_energy.scores = ["flux"]

    tallies = openmc.Tallies([flux_mesh, flux_energy])
    tallies.export_to_xml(run_dir / "tallies.xml")


def run_case(run_dir: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["openmc"],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        ok = result.returncode == 0
        msg = (result.stdout[-1500:] if ok else (result.stderr[-1500:] or result.stdout[-1500:])).replace("\n", " | ")
        return ok, msg
    except subprocess.TimeoutExpired:
        return False, "Timed out after 3600 s"


def postprocess_case(run_dir: Path) -> dict:
    sp_files = sorted(run_dir.glob("statepoint.*.h5"))
    if not sp_files:
        raise FileNotFoundError("No statepoint file found")

    sp = openmc.StatePoint(str(sp_files[-1]))

    flux_mesh = sp.get_tally(name="flux_mesh").mean.flatten()
    flux_energy = sp.get_tally(name="flux_energy").mean

    front_flux = float(flux_mesh[0])
    mid_flux = float(flux_mesh[len(flux_mesh) // 2])
    back_flux = float(flux_mesh[-1])

    attenuation_mid = mid_flux / front_flux if front_flux > 0 else math.nan
    attenuation_back = back_flux / front_flux if front_flux > 0 else math.nan

    # reshape energy tally: [mesh_x, energy_groups]
    n_groups = len(ENERGY_BINS) - 1
    flux_energy = flux_energy.reshape((N_MESH_X, n_groups))

    front_spec = flux_energy[0, :]
    back_spec = flux_energy[-1, :]

    front_total = float(front_spec.sum())
    back_total = float(back_spec.sum())

    # high-energy survives?
    high_front = float(front_spec[-2:].sum())
    high_back = float(back_spec[-2:].sum())

    # low-energy buildup?
    low_front = float(front_spec[:2].sum())
    low_back = float(back_spec[:2].sum())

    high_survival = high_back / high_front if high_front > 0 else math.nan
    low_build = low_back / low_front if low_front > 0 else math.nan
    spectrum_softening = (low_back / back_total) / (low_front / front_total) if front_total > 0 and back_total > 0 and low_front > 0 else math.nan

    # crude combined score: lower is better
    score = attenuation_back
    if not math.isnan(high_survival):
        score *= (1.0 + high_survival)
    if not math.isnan(spectrum_softening):
        score /= max(spectrum_softening, 1e-12)

    return {
        "front_flux": front_flux,
        "mid_flux": mid_flux,
        "back_flux": back_flux,
        "attenuation_mid_vs_front": attenuation_mid,
        "attenuation_back_vs_front": attenuation_back,
        "high_energy_survival": high_survival,
        "low_energy_build_ratio": low_build,
        "spectrum_softening_factor": spectrum_softening,
        "composite_score": score,
    }


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict]):
    good = [r for r in rows if r["ok"] == True]
    if not good:
        print("\nNo successful runs yet.")
        return

    good_sorted = sorted(good, key=lambda r: float(r["composite_score"]))
    print("\nTop 10 runs by composite_score:")
    for r in good_sorted[:10]:
        print(
            f"{r['run_name']:<40} "
            f"score={r['composite_score']:.6g} "
            f"back/front={r['attenuation_back_vs_front']:.6g} "
            f"soften={r['spectrum_softening_factor']:.6g}"
        )


def main():
    rows = []

    # Phase 1: single materials
    for material_name in MATERIALS:
        for thickness_cm in SINGLE_THICKNESSES_CM:
            run_name = f"single__{material_name}__{str(thickness_cm).replace('.', 'p')}cm"
            run_dir = RUNS_DIR / run_name
            run_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n=== Building {run_name} ===")
            build_single_case(material_name, thickness_cm, run_dir)

            print(f"=== Running {run_name} ===")
            ok, msg = run_case(run_dir)

            row = {
                "campaign": "single",
                "run_name": run_name,
                "front_material": material_name,
                "back_material": "",
                "thickness_cm": thickness_cm,
                "ok": ok,
                "message": msg,
            }

            if ok:
                try:
                    row.update(postprocess_case(run_dir))
                    print(
                        f"done: back/front={row['attenuation_back_vs_front']:.6g}, "
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
            write_csv(BASE_DIR / "overnight_summary.csv", rows)

    # Phase 2: 2-layer stacks
    for front_name, back_name in STACKS:
        for thickness_cm in STACK_THICKNESSES_CM:
            run_name = f"stack__{front_name}__{back_name}__{str(thickness_cm).replace('.', 'p')}cm"
            run_dir = RUNS_DIR / run_name
            run_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n=== Building {run_name} ===")
            build_stack_case(front_name, back_name, thickness_cm, run_dir)

            print(f"=== Running {run_name} ===")
            ok, msg = run_case(run_dir)

            row = {
                "campaign": "stack",
                "run_name": run_name,
                "front_material": front_name,
                "back_material": back_name,
                "thickness_cm": thickness_cm,
                "ok": ok,
                "message": msg,
            }

            if ok:
                try:
                    row.update(postprocess_case(run_dir))
                    print(
                        f"done: back/front={row['attenuation_back_vs_front']:.6g}, "
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
            write_csv(BASE_DIR / "overnight_summary.csv", rows)

    summarize(rows)
    print("\nFinished. Wrote overnight_summary.csv")


if __name__ == "__main__":
    main()

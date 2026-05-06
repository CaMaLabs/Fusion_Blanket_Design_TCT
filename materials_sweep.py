import csv
import math
import subprocess
from pathlib import Path

import openmc


BASE_DIR = Path.cwd()
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

# Only uses elements you already downloaded
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
    "Pb": {
        "density": 11.34,
        "elements": [("Pb", 1.0, "ao")],
    },
}

THICKNESSES_CM = [0.5, 1.0, 2.0, 5.0, 10.0]
BATCHES = 60
PARTICLES = 200000

YZ_HALF = 5.0
N_MESH_X = 100
SOURCE_ENERGY_EV = 14.1e6


def build_material(name: str, spec: dict) -> openmc.Material:
    m = openmc.Material(name=name)
    m.set_density("g/cm3", spec["density"])
    for el, frac, pct_type in spec["elements"]:
        m.add_element(el, frac, percent_type=pct_type)
    return m


def build_case(material_name: str, thickness_cm: float, run_dir: Path) -> None:
    # materials
    mat = build_material(material_name, MATERIALS[material_name])
    materials = openmc.Materials([mat])
    materials.export_to_xml(run_dir / "materials.xml")

    # geometry
    x0 = openmc.XPlane(x0=0.0, boundary_type="vacuum")
    x1 = openmc.XPlane(x0=thickness_cm, boundary_type="vacuum")
    y0 = openmc.YPlane(y0=-YZ_HALF, boundary_type="vacuum")
    y1 = openmc.YPlane(y0=YZ_HALF, boundary_type="vacuum")
    z0 = openmc.ZPlane(z0=-YZ_HALF, boundary_type="vacuum")
    z1 = openmc.ZPlane(z0=YZ_HALF, boundary_type="vacuum")

    cell = openmc.Cell(region=+x0 & -x1 & +y0 & -y1 & +z0 & -z1, fill=mat)
    geometry = openmc.Geometry([cell])
    geometry.export_to_xml(run_dir / "geometry.xml")

    # source/settings
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

    # tally only on mesh; use last mesh bin as transmitted flux
    mesh = openmc.RegularMesh()
    mesh.dimension = (N_MESH_X, 1, 1)
    mesh.lower_left = (0.0, -YZ_HALF, -YZ_HALF)
    mesh.upper_right = (thickness_cm, YZ_HALF, YZ_HALF)

    flux_mesh = openmc.Tally(name="flux_mesh")
    flux_mesh.filters = [openmc.MeshFilter(mesh)]
    flux_mesh.scores = ["flux"]

    tallies = openmc.Tallies([flux_mesh])
    tallies.export_to_xml(run_dir / "tallies.xml")


def run_case(run_dir: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["openmc"],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        ok = result.returncode == 0
        msg = (result.stdout[-2000:] if ok else (result.stderr[-2000:] or result.stdout[-2000:])).replace("\n", " | ")
        return ok, msg
    except subprocess.TimeoutExpired:
        return False, "Timed out after 1800 s"


def postprocess_case(run_dir: Path) -> dict:
    sp_files = sorted(run_dir.glob("statepoint.*.h5"))
    if not sp_files:
        raise FileNotFoundError("No statepoint file found")

    sp = openmc.StatePoint(str(sp_files[-1]))
    flux_mesh = sp.get_tally(name="flux_mesh").mean.flatten()

    front_flux = float(flux_mesh[0])
    mid_flux = float(flux_mesh[len(flux_mesh) // 2])
    back_mesh_flux = float(flux_mesh[-1])

    attenuation_mid_vs_front = mid_flux / front_flux if front_flux > 0 else math.nan
    attenuation_back_vs_front = back_mesh_flux / front_flux if front_flux > 0 else math.nan

    return {
        "front_flux": front_flux,
        "mid_flux": mid_flux,
        "back_mesh_flux": back_mesh_flux,
        "attenuation_mid_vs_front": attenuation_mid_vs_front,
        "attenuation_back_vs_front": attenuation_back_vs_front,
    }


def main() -> None:
    summary_rows = []

    for material_name in MATERIALS:
        for thickness_cm in THICKNESSES_CM:
            run_name = f"{material_name}__{str(thickness_cm).replace('.', 'p')}cm"
            run_dir = RUNS_DIR / run_name
            run_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n=== Building {run_name} ===")
            build_case(material_name, thickness_cm, run_dir)

            print(f"=== Running {run_name} ===")
            ok, msg = run_case(run_dir)

            row = {
                "run_name": run_name,
                "material": material_name,
                "thickness_cm": thickness_cm,
                "ok": ok,
                "message": msg,
            }

            if ok:
                try:
                    metrics = postprocess_case(run_dir)
                    row.update(metrics)
                    print(
                        f"done: back/front={row['attenuation_back_vs_front']:.6g}, "
                        f"mid/front={row['attenuation_mid_vs_front']:.6g}"
                    )
                except Exception as e:
                    row["ok"] = False
                    row["message"] = f"Postprocess failed: {e}"
                    print(row["message"])
            else:
                print("failed:", msg)

            summary_rows.append(row)

            with open(BASE_DIR / "sweep_summary.csv", "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
                writer.writeheader()
                writer.writerows(summary_rows)

    print("\nFinished. Wrote sweep_summary.csv")


if __name__ == "__main__":
    main()

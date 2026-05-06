from pathlib import Path
from ..engine.config import YZ_HALF, N_MESH_X, SOURCE_ENERGY_EV, OPENMC_BATCHES, OPENMC_PARTICLES

try:
    import openmc
except Exception:
    openmc = None

from .materials_db import MATERIALS

def build_material(name, li6_enrich=0.9, packing=1.0):
    spec = MATERIALS[name]
    m = openmc.Material(name=name)
    density = spec["density"]
    if spec.get("porous_ok"):
        density *= packing
    m.set_density("g/cm3", density)

    li6_base = 0.0
    li7_base = 0.0
    for kind, sym, frac, pct in spec["components"]:
        if kind == "element":
            m.add_element(sym, frac, percent_type=pct)
        elif kind == "nuclide":
            if sym == "Li6":
                li6_base += frac
            elif sym == "Li7":
                li7_base += frac
            else:
                m.add_nuclide(sym, frac, percent_type=pct)
    li_total = li6_base + li7_base
    if li_total > 0.0:
        m.add_nuclide("Li6", li_total * li6_enrich, "ao")
        m.add_nuclide("Li7", li_total * (1.0 - li6_enrich), "ao")
    return m

def write_settings(run_dir: Path):
    src = openmc.IndependentSource()
    src.space = openmc.stats.Point((0.001,0,0))
    src.angle = openmc.stats.Monodirectional((1,0,0))
    src.energy = openmc.stats.Discrete([SOURCE_ENERGY_EV],[1])

    s = openmc.Settings()
    s.run_mode = "fixed source"
    s.source = src
    s.batches = OPENMC_BATCHES
    s.inactive = 0
    s.particles = OPENMC_PARTICLES
    s.export_to_xml(run_dir / "settings.xml")

def write_tallies(run_dir, thickness_cm, cells):
    mesh = openmc.RegularMesh()
    mesh.dimension = (N_MESH_X,1,1)
    mesh.lower_left = (0,-YZ_HALF,-YZ_HALF)
    mesh.upper_right = (thickness_cm,YZ_HALF,YZ_HALF)

    flux = openmc.Tally(name="flux_mesh")
    flux.filters = [openmc.MeshFilter(mesh)]
    flux.scores = ["flux"]

    h3 = openmc.Tally(name="h3_prod_by_layer")
    h3.filters = [openmc.CellFilter(cells)]
    h3.scores = ["H3-production"]

    heat = openmc.Tally(name="heating_by_layer")
    heat.filters = [openmc.CellFilter(cells)]
    heat.scores = ["heating-local"]

    openmc.Tallies([flux,h3,heat]).export_to_xml(run_dir / "tallies.xml")

def build_stack_case(design, run_dir):
    mats = [
        build_material("Li", design.get("liquid_wall_li6_enrich", 0.90), 1.0),
        build_material(design["l1"], design["l1_li6"], design["l1_pack"]),
        build_material(design["l2"], design["l2_li6"], design["l2_pack"]),
        build_material(design["l3"], design["l3_li6"], design["l3_pack"]),
        build_material(design["l4"], design["l4_li6"], design["l4_pack"]),
    ]
    openmc.Materials(mats).export_to_xml(run_dir / "materials.xml")

    total_cm = design.get("blanket_thickness", 1.0) * 100.0
    split = design.get("split", (0.20, 0.25, 0.25, 0.30))
    liquid_wall_cm = design.get("lithium_thickness", 0.0014) * 100.0

    f1,f2,f3,f4 = split
    x1 = liquid_wall_cm
    x2 = x1 + total_cm * f1
    x3 = x1 + total_cm * (f1 + f2)
    x4 = x1 + total_cm * (f1 + f2 + f3)
    x5 = x1 + total_cm

    x0 = openmc.XPlane(x0=0, boundary_type="vacuum")
    x1p = openmc.XPlane(x0=x1)
    x2p = openmc.XPlane(x0=x2)
    x3p = openmc.XPlane(x0=x3)
    x4p = openmc.XPlane(x0=x4)
    x5p = openmc.XPlane(x0=x5, boundary_type="vacuum")

    y0 = openmc.YPlane(y0=-YZ_HALF, boundary_type="vacuum")
    y1 = openmc.YPlane(y0=YZ_HALF, boundary_type="vacuum")
    z0 = openmc.ZPlane(z0=-YZ_HALF, boundary_type="vacuum")
    z1 = openmc.ZPlane(z0=YZ_HALF, boundary_type="vacuum")

    c0 = openmc.Cell(region=+x0 & -x1p & +y0 & -y1 & +z0 & -z1, fill=mats[0])
    c1 = openmc.Cell(region=+x1p & -x2p & +y0 & -y1 & +z0 & -z1, fill=mats[1])
    c2 = openmc.Cell(region=+x2p & -x3p & +y0 & -y1 & +z0 & -z1, fill=mats[2])
    c3 = openmc.Cell(region=+x3p & -x4p & +y0 & -y1 & +z0 & -z1, fill=mats[3])
    c4 = openmc.Cell(region=+x4p & -x5p & +y0 & -y1 & +z0 & -z1, fill=mats[4])

    openmc.Geometry([c0,c1,c2,c3,c4]).export_to_xml(run_dir / "geometry.xml")
    write_settings(run_dir)
    write_tallies(run_dir, x5, [c0,c1,c2,c3,c4])

from pathlib import Path
from ..engine.config import SOURCE_ENERGY_EV

try:
    import openmc
except Exception:
    openmc = None

from .materials_db import MATERIALS

CYL_HALF_HEIGHT_CM = 400.0
DEFAULT_PLASMA_RADIUS_CM = 50.0
DEBUG_GEOM = True


def _safe_float(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return float(d)


def _safe_material_name(name, fallback):
    return name if name in MATERIALS else fallback


def _li6_or_default(design, key, default=0.90):
    val = _safe_float(design.get(key, default), default)
    return float(default if val <= 0.0 else val)


def _pack_or_default(design, key, default=1.0):
    val = _safe_float(design.get(key, default), default)
    return float(default if val <= 0.0 else val)


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


def _family_defaults(design):
    fam = str(design.get("blanket_family", "Li2O_W_Be_Li2O")).strip()

    # 5 radial shells:
    # l1 = inner breeder / slowing shell
    # l2 = moderator / multiplier
    # l3 = main breeder
    # l4 = shaping / reflector shell
    # l5 = outer breeder / capture shell
    if fam == "Li2O_W_Be_Li2O":
        return {
            "l1": "Li2O",
            "l2": "Be12Ti",
            "l3": "Li2O",
            "l4": "W_Ti_B4C_60_30_10_wt",
            "l5": "Li2O",
            "split": (0.25, 0.20, 0.35, 0.10, 0.10),
        }

    return {
        "l1": "Li2O",
        "l2": "Be12Ti",
        "l3": "Li2O",
        "l4": "W_Ti_B4C_60_30_10_wt",
        "l5": "Li2O",
        "split": (0.25, 0.20, 0.35, 0.10, 0.10),
    }


def _split5(design, defaults):
    split = design.get("split", defaults["split"])
    if not isinstance(split, (list, tuple)) or len(split) != 5:
        split = defaults["split"]

    vals = [max(0.0, _safe_float(v, 0.0)) for v in split]
    vals[0] = max(vals[0], 0.20)
    vals[2] = max(vals[2], 0.30)

    s = sum(vals)
    if s <= 0.0:
        vals = list(defaults["split"])
        s = sum(vals)

    return tuple(v / s for v in vals)


def write_settings(run_dir: Path):
    src = openmc.IndependentSource()
    src.space = openmc.stats.Point((0.0, 0.0, 0.0))
    src.angle = openmc.stats.Isotropic()
    src.energy = openmc.stats.Discrete([SOURCE_ENERGY_EV], [1.0])

    s = openmc.Settings()
    s.run_mode = "fixed source"
    s.source = src
    s.batches = 12
    s.inactive = 0
    s.particles = 4000
    s.export_to_xml(run_dir / "settings.xml")


def write_tallies(run_dir: Path, outer_radius_cm: float, z_extent_cm: float, cells):
    nr = 24
    r_grid = [outer_radius_cm * i / nr for i in range(nr + 1)]

    mesh = openmc.CylindricalMesh(
        r_grid=r_grid,
        z_grid=[-z_extent_cm, z_extent_cm],
        phi_grid=[0.0, 6.283185307179586],
    )

    flux = openmc.Tally(name="flux_mesh")
    flux.filters = [openmc.MeshFilter(mesh)]
    flux.scores = ["flux"]

    h3 = openmc.Tally(name="h3_prod_by_layer")
    h3.filters = [openmc.CellFilter(cells)]
    h3.scores = ["H3-production"]

    heat = openmc.Tally(name="heating_by_layer")
    heat.filters = [openmc.CellFilter(cells)]
    heat.scores = ["heating-local"]

    openmc.Tallies([flux, h3, heat]).export_to_xml(run_dir / "tallies.xml")

    if DEBUG_GEOM:
        print("[GEOM DEBUG] radial mesh bins:", nr)
        print("[GEOM DEBUG] outer_radius_cm:", outer_radius_cm)
        print("[GEOM DEBUG] z_extent_cm:", z_extent_cm)
        print("[GEOM DEBUG] r_grid first/last:", r_grid[:4], "...", r_grid[-4:])


def build_stack_case(design, run_dir):
    if openmc is None:
        raise RuntimeError("openmc import failed")

    defaults = _family_defaults(design)
    split = _split5(design, defaults)

    plasma_radius_cm = max(
        _safe_float(design.get("plasma_radius_cm", DEFAULT_PLASMA_RADIUS_CM), DEFAULT_PLASMA_RADIUS_CM),
        5.0,
    )
    # meters -> cm
    blanket_thickness_cm = max(_safe_float(design.get("blanket_thickness", 0.5), 0.5), 0.05) * 100.0
    lithium_thickness_cm = max(_safe_float(design.get("lithium_thickness", 0.002), 0.002), 0.0005) * 100.0

    axial_inner_cap_cm = max(_safe_float(design.get("axial_inner_cap_thickness", 0.8), 0.8), 0.05) * 100.0
    axial_outer_cap_cm = max(_safe_float(design.get("axial_outer_cap_thickness", 0.4), 0.4), 0.05) * 100.0

    l1_name = _safe_material_name(str(design.get("l1", defaults["l1"])).strip(), defaults["l1"])
    l2_name = _safe_material_name(str(design.get("l2", defaults["l2"])).strip(), defaults["l2"])
    l3_name = _safe_material_name(str(design.get("l3", defaults["l3"])).strip(), defaults["l3"])
    l4_name = _safe_material_name(str(design.get("l4", defaults["l4"])).strip(), defaults["l4"])
    l5_name = _safe_material_name(str(design.get("l5", defaults["l5"])).strip(), defaults["l5"])

    axial_inner_name = _safe_material_name(
        str(design.get("axial_inner_material", "Be12Ti")).strip(),
        "Be12Ti",
    )
    axial_outer_name = _safe_material_name(
        str(design.get("axial_outer_material", "W_Ti_B4C_60_30_10_wt")).strip(),
        "W_Ti_B4C_60_30_10_wt",
    )

    plasma = openmc.Material(name="plasma_void")
    plasma.set_density("g/cm3", 1e-12)
    plasma.add_nuclide("H1", 1.0)

    li = build_material("Li", _li6_or_default(design, "liquid_wall_li6_enrich", 0.95), 1.0)
    l1 = build_material(l1_name, _li6_or_default(design, "l1_li6", 0.95), _pack_or_default(design, "l1_pack", 1.0))
    l2 = build_material(l2_name, _li6_or_default(design, "l2_li6", 0.90), _pack_or_default(design, "l2_pack", 1.0))
    l3 = build_material(l3_name, _li6_or_default(design, "l3_li6", 0.98), _pack_or_default(design, "l3_pack", 1.25))
    l4 = build_material(l4_name, _li6_or_default(design, "l4_li6", 0.90), _pack_or_default(design, "l4_pack", 1.0))
    l5 = build_material(l5_name, _li6_or_default(design, "l5_li6", 0.95), _pack_or_default(design, "l5_pack", 1.0))
    axial_inner = build_material(axial_inner_name, _li6_or_default(design, "axial_inner_li6", 0.90), _pack_or_default(design, "axial_inner_pack", 1.0))
    axial_outer = build_material(axial_outer_name, _li6_or_default(design, "axial_outer_li6", 0.90), _pack_or_default(design, "axial_outer_pack", 1.0))

    mats = [plasma, li, l1, l2, l3, l4, l5, axial_inner, axial_outer]
    openmc.Materials(mats).export_to_xml(run_dir / "materials.xml")

    # radial shells
    r0 = plasma_radius_cm
    r1 = r0 + lithium_thickness_cm
    r2 = r1 + blanket_thickness_cm * split[0]
    r3 = r2 + blanket_thickness_cm * split[1]
    r4 = r3 + blanket_thickness_cm * split[2]
    r5 = r4 + blanket_thickness_cm * split[3]
    r6 = r5 + blanket_thickness_cm * split[4]

    # axial zones
    z1 = CYL_HALF_HEIGHT_CM
    z2 = z1 + axial_inner_cap_cm
    z3 = z2 + axial_outer_cap_cm

    zmin_outer = openmc.ZPlane(z0=-z3, boundary_type="vacuum")
    zmin_inner = openmc.ZPlane(z0=-z2)
    zmin_core = openmc.ZPlane(z0=-z1)

    zmax_core = openmc.ZPlane(z0=z1)
    zmax_inner = openmc.ZPlane(z0=z2)
    zmax_outer = openmc.ZPlane(z0=z3, boundary_type="vacuum")

    c0 = openmc.ZCylinder(r=r0)
    c1 = openmc.ZCylinder(r=r1)
    c2 = openmc.ZCylinder(r=r2)
    c3 = openmc.ZCylinder(r=r3)
    c4 = openmc.ZCylinder(r=r4)
    c5 = openmc.ZCylinder(r=r5)
    c6 = openmc.ZCylinder(r=r6, boundary_type="vacuum")

    core_axial = +zmin_core & -zmax_core
    top_inner_axial = +zmax_core & -zmax_inner
    top_outer_axial = +zmax_inner & -zmax_outer
    bot_inner_axial = +zmin_inner & -zmin_core
    bot_outer_axial = +zmin_outer & -zmin_inner

    cells = [
        openmc.Cell(name="plasma", region=-c0 & core_axial, fill=plasma),
        openmc.Cell(name="liquid_wall", region=+c0 & -c1 & core_axial, fill=li),
        openmc.Cell(name="l1_inner_breeder", region=+c1 & -c2 & core_axial, fill=l1),
        openmc.Cell(name="l2_multiplier", region=+c2 & -c3 & core_axial, fill=l2),
        openmc.Cell(name="l3_main_breeder", region=+c3 & -c4 & core_axial, fill=l3),
        openmc.Cell(name="l4_outer_shape", region=+c4 & -c5 & core_axial, fill=l4),
        openmc.Cell(name="l5_outer_breeder", region=+c5 & -c6 & core_axial, fill=l5),
        openmc.Cell(name="top_cap_inner", region=-c6 & top_inner_axial, fill=axial_inner),
        openmc.Cell(name="bot_cap_inner", region=-c6 & bot_inner_axial, fill=axial_inner),
        openmc.Cell(name="top_cap_outer", region=-c6 & top_outer_axial, fill=axial_outer),
        openmc.Cell(name="bot_cap_outer", region=-c6 & bot_outer_axial, fill=axial_outer),
    ]

    geom = openmc.Geometry(cells)
    geom.export_to_xml(run_dir / "geometry.xml")

    blanket_cells = [cells[i] for i in range(1, len(cells))]
    write_settings(run_dir)
    write_tallies(run_dir, r6, z3, blanket_cells)

    if DEBUG_GEOM:
        print("[GEOM DEBUG] plasma_radius_cm:", plasma_radius_cm)
        print("[GEOM DEBUG] blanket_thickness_cm:", blanket_thickness_cm)
        print("[GEOM DEBUG] lithium_thickness_cm:", lithium_thickness_cm)
        print("[GEOM DEBUG] axial caps cm:", axial_inner_cap_cm, axial_outer_cap_cm)
        print("[GEOM DEBUG] split:", split)
        print("[GEOM DEBUG] materials:", l1_name, l2_name, l3_name, l4_name, l5_name)
        print("[GEOM DEBUG] axial materials:", axial_inner_name, axial_outer_name)
        print("[GEOM DEBUG] radii cm:", {"r0": r0, "r1": r1, "r2": r2, "r3": r3, "r4": r4, "r5": r5, "r6": r6})
        print("[GEOM DEBUG] cell names:", [c.name for c in cells])

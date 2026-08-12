#!/usr/bin/env python3
"""Engineering-degradation OpenMC study for the be_outer_kill blanket family.

This is deliberately separate from the historical ordering/baseline scripts.
It preserves an idealized be_outer_kill control, then introduces explicit
engineering parasitics in sensitivity cases:

- reduced ferritic-steel structural skins that consume blanket volume,
- explicit axial helium coolant channels,
- finite radial diagnostic/heating port voids,
- an explicit borated-steel outer shield,
- breeder packing / Li-6 sensitivity envelopes,
- repeated OpenMC transport seeds with reported tally uncertainty.

The study quantifies degradation relative to the local idealized control. It is
NOT an engineering-complete reactor model and does not close D by itself.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from fusion_engine_v5.blanket.materials_db import MATERIALS

DEFAULT_RUN_DIR = REPO / "validation_runs" / "be_outer_kill_engineering_default"
STATUS = "ENGINEERING_DEGRADATION_SCREEN_ONLY"
SOURCE_ENERGY_EV = 14.1e6
PLASMA_RADIUS_CM = 50.0
LIQUID_LITHIUM_THICKNESS_CM = 0.3
BLANKET_THICKNESS_CM = 100.0
CORE_HALF_HEIGHT_CM = 400.0
AXIAL_INNER_CAP_CM = 80.0
AXIAL_OUTER_CAP_CM = 40.0
SPLIT = (0.15, 0.25, 0.35, 0.15, 0.10)
MATERIAL_ORDER = ("Be", "Li2O", "Li2O", "W_Ti_B4C_60_30_10_wt", "Be")
BASE_LI6 = (0.90, 0.95, 0.98, 0.95, 0.90)
BASE_PACK = (1.0, 1.0, 1.25, 1.0, 1.0)


@dataclass(frozen=True)
class EngineeringCase:
    name: str
    description: str
    structural_fraction: float
    coolant_channel_count: int
    coolant_channel_radius_cm: float
    port_count: int
    port_radius_cm: float
    shield_thickness_cm: float
    breeder_packing_scale: float
    li6_enrichment_scale: float


def case_matrix() -> list[EngineeringCase]:
    """Return the frozen sensitivity family.

    The numerical engineering fractions are sensitivity assumptions, not claimed
    final reactor dimensions. They are intentionally exposed in the output plan.
    """
    return [
        EngineeringCase(
            name="idealized_control",
            description="Local be_outer_kill control matching the existing five-layer material order without engineering parasitics.",
            structural_fraction=0.0,
            coolant_channel_count=0,
            coolant_channel_radius_cm=0.0,
            port_count=0,
            port_radius_cm=0.0,
            shield_thickness_cm=0.0,
            breeder_packing_scale=1.0,
            li6_enrichment_scale=1.0,
        ),
        EngineeringCase(
            name="engineering_low_parasitics",
            description="Low-parasitic engineering sensitivity case.",
            structural_fraction=0.04,
            coolant_channel_count=16,
            coolant_channel_radius_cm=0.6,
            port_count=2,
            port_radius_cm=7.5,
            shield_thickness_cm=25.0,
            breeder_packing_scale=1.0,
            li6_enrichment_scale=1.0,
        ),
        EngineeringCase(
            name="engineering_nominal",
            description="Nominal engineering sensitivity case with explicit structure, coolant, ports, and shield.",
            structural_fraction=0.07,
            coolant_channel_count=24,
            coolant_channel_radius_cm=0.8,
            port_count=2,
            port_radius_cm=10.0,
            shield_thickness_cm=30.0,
            breeder_packing_scale=0.95,
            li6_enrichment_scale=0.98,
        ),
        EngineeringCase(
            name="engineering_high_parasitics",
            description="Adverse engineering sensitivity case with larger parasitic fractions and penetrations.",
            structural_fraction=0.10,
            coolant_channel_count=32,
            coolant_channel_radius_cm=1.0,
            port_count=4,
            port_radius_cm=15.0,
            shield_thickness_cm=40.0,
            breeder_packing_scale=0.90,
            li6_enrichment_scale=0.95,
        ),
    ]


def parse_ints(text: str) -> list[int]:
    values = [int(x.strip()) for x in text.split(",") if x.strip()]
    if not values:
        raise ValueError("at least one seed is required")
    return values


def validate_plan(cases: list[EngineeringCase], seeds: list[int]) -> None:
    names = [case.name for case in cases]
    assert names[0] == "idealized_control"
    assert len(names) == len(set(names))
    assert len(seeds) >= 2, "seed sweep requires at least two seeds"
    assert math.isclose(sum(SPLIT), 1.0, abs_tol=1e-12)
    for case in cases:
        assert 0.0 <= case.structural_fraction < 0.5
        assert case.coolant_channel_count >= 0
        assert case.port_count >= 0 and case.port_count % 2 == 0
        assert case.shield_thickness_cm >= 0.0
        assert 0.0 < case.breeder_packing_scale <= 1.0
        assert 0.0 < case.li6_enrichment_scale <= 1.0
    nominal = next(case for case in cases if case.name == "engineering_nominal")
    assert nominal.structural_fraction > 0.0
    assert nominal.coolant_channel_count > 0
    assert nominal.port_count > 0
    assert nominal.shield_thickness_cm > 0.0


def build_existing_material(openmc: Any, name: str, li6_enrich: float, packing: float):
    spec = MATERIALS[name]
    material = openmc.Material(name=name)
    density = float(spec["density"])
    if spec.get("porous_ok"):
        density *= float(packing)
    material.set_density("g/cm3", density)

    li6_base = 0.0
    li7_base = 0.0
    for kind, symbol, fraction, pct in spec["components"]:
        if kind == "element":
            material.add_element(symbol, fraction, percent_type=pct)
        elif kind == "nuclide":
            if symbol == "Li6":
                li6_base += float(fraction)
            elif symbol == "Li7":
                li7_base += float(fraction)
            else:
                material.add_nuclide(symbol, fraction, percent_type=pct)
    li_total = li6_base + li7_base
    if li_total > 0.0:
        enrich = max(0.0, min(1.0, float(li6_enrich)))
        material.add_nuclide("Li6", li_total * enrich, "ao")
        material.add_nuclide("Li7", li_total * (1.0 - enrich), "ao")
    return material


def build_engineering_materials(openmc: Any, case: EngineeringCase) -> dict[str, Any]:
    mats: dict[str, Any] = {}

    mats["plasma"] = openmc.Material(name="plasma_void_proxy")
    mats["plasma"].set_density("g/cm3", 1e-12)
    mats["plasma"].add_nuclide("H1", 1.0)

    mats["liquid_wall"] = build_existing_material(openmc, "Li", 0.95 * case.li6_enrichment_scale, 1.0)

    for idx, name in enumerate(MATERIAL_ORDER):
        li6 = min(0.999, BASE_LI6[idx] * case.li6_enrichment_scale)
        pack = BASE_PACK[idx]
        if name == "Li2O":
            pack *= case.breeder_packing_scale
        mats[f"layer_{idx + 1}"] = build_existing_material(openmc, name, li6, pack)

    structure = openmc.Material(name="reduced_ferritic_steel")
    structure.set_density("g/cm3", 7.75)
    structure.add_element("Fe", 0.89, percent_type="wo")
    structure.add_element("Cr", 0.09, percent_type="wo")
    structure.add_element("W", 0.02, percent_type="wo")
    mats["structure"] = structure

    coolant = openmc.Material(name="helium_coolant_proxy")
    coolant.set_density("g/cm3", 0.005)
    coolant.add_nuclide("He4", 1.0, percent_type="ao")
    mats["coolant"] = coolant

    shield = openmc.Material(name="borated_steel_shield_proxy")
    shield.set_density("g/cm3", 7.2)
    shield.add_element("Fe", 0.83, percent_type="wo")
    shield.add_element("Cr", 0.08, percent_type="wo")
    shield.add_element("W", 0.02, percent_type="wo")
    shield.add_element("B", 0.05, percent_type="wo")
    shield.add_element("C", 0.02, percent_type="wo")
    mats["shield"] = shield

    return mats


def channel_centers(case: EngineeringCase, r1: float, r6: float) -> list[tuple[float, float]]:
    n = case.coolant_channel_count
    if n <= 0:
        return []
    rings = [r1 + 0.35 * (r6 - r1), r1 + 0.72 * (r6 - r1)]
    counts = [n // 2, n - n // 2]
    centers: list[tuple[float, float]] = []
    for ring_r, count in zip(rings, counts):
        for idx in range(count):
            angle = 2.0 * math.pi * idx / count + (0.5 * math.pi / count if count else 0.0)
            centers.append((ring_r * math.cos(angle), ring_r * math.sin(angle)))
    return centers


def _union(regions: list[Any]) -> Any | None:
    if not regions:
        return None
    out = regions[0]
    for region in regions[1:]:
        out = out | region
    return out


def build_model(openmc: Any, case: EngineeringCase, run_dir: Path, seed: int, particles: int, batches: int):
    mats = build_engineering_materials(openmc, case)

    r0 = PLASMA_RADIUS_CM
    r1 = r0 + LIQUID_LITHIUM_THICKNESS_CM
    layer_thicknesses = [BLANKET_THICKNESS_CM * frac for frac in SPLIT]
    bounds = [r1]
    for thickness in layer_thicknesses:
        bounds.append(bounds[-1] + thickness)
    r6 = bounds[-1]
    r_outer = r6 + case.shield_thickness_cm

    z1 = CORE_HALF_HEIGHT_CM
    z2 = z1 + AXIAL_INNER_CAP_CM
    z3 = z2 + AXIAL_OUTER_CAP_CM

    zmin_outer = openmc.ZPlane(z0=-z3, boundary_type="vacuum")
    zmin_inner = openmc.ZPlane(z0=-z2)
    zmin_core = openmc.ZPlane(z0=-z1)
    zmax_core = openmc.ZPlane(z0=z1)
    zmax_inner = openmc.ZPlane(z0=z2)
    zmax_outer = openmc.ZPlane(z0=z3, boundary_type="vacuum")

    c0 = openmc.ZCylinder(r=r0)
    c1 = openmc.ZCylinder(r=r1)
    c6 = openmc.ZCylinder(r=r6, boundary_type="vacuum" if case.shield_thickness_cm <= 0.0 else "transmission")
    if case.shield_thickness_cm > 0.0:
        c_outer = openmc.ZCylinder(r=r_outer, boundary_type="vacuum")
    else:
        c_outer = c6

    core_axial = +zmin_core & -zmax_core
    whole_axial = +zmin_outer & -zmax_outer
    top_inner_axial = +zmax_core & -zmax_inner
    top_outer_axial = +zmax_inner & -zmax_outer
    bot_inner_axial = +zmin_inner & -zmin_core
    bot_outer_axial = +zmin_outer & -zmin_inner

    coolant_regions: list[Any] = []
    for x0, y0 in channel_centers(case, r1, r6):
        tube = openmc.ZCylinder(x0=x0, y0=y0, r=case.coolant_channel_radius_cm)
        coolant_regions.append(-tube)
    coolant_union = _union(coolant_regions)

    port_regions: list[Any] = []
    if case.port_count > 0:
        pair_count = case.port_count // 2
        if pair_count == 1:
            z_positions = [0.0]
        else:
            span = 0.30 * z1
            z_positions = [(-span + 2.0 * span * i / (pair_count - 1)) for i in range(pair_count)]
        x_pos_start = openmc.XPlane(x0=r0)
        x_pos_end = openmc.XPlane(x0=r_outer)
        x_neg_start = openmc.XPlane(x0=-r_outer)
        x_neg_end = openmc.XPlane(x0=-r0)
        for z0 in z_positions:
            tube = openmc.XCylinder(y0=0.0, z0=z0, r=case.port_radius_cm)
            port_regions.append(-tube & +x_pos_start & -x_pos_end & core_axial)
            port_regions.append(-tube & +x_neg_start & -x_neg_end & core_axial)
    port_union = _union(port_regions)

    def subtract_parasitics(region: Any, include_coolant: bool = True) -> Any:
        out = region
        if include_coolant and coolant_union is not None:
            out = out & ~coolant_union
        if port_union is not None:
            out = out & ~port_union
        return out

    cells: list[Any] = []
    material_cells: list[Any] = []

    plasma_cell = openmc.Cell(name="plasma", region=-c0 & core_axial, fill=mats["plasma"])
    cells.append(plasma_cell)

    liquid_region = subtract_parasitics(+c0 & -c1 & core_axial, include_coolant=False)
    liquid_cell = openmc.Cell(name="liquid_wall", region=liquid_region, fill=mats["liquid_wall"])
    cells.append(liquid_cell)
    material_cells.append(liquid_cell)

    for idx, (layer_inner, layer_outer) in enumerate(zip(bounds[:-1], bounds[1:])):
        layer_total = layer_outer - layer_inner
        structural_thickness = layer_total * case.structural_fraction
        functional_outer = layer_outer - structural_thickness

        inner_surface = openmc.ZCylinder(r=layer_inner)
        functional_outer_surface = openmc.ZCylinder(r=functional_outer)
        functional_region = subtract_parasitics(+inner_surface & -functional_outer_surface & core_axial)
        functional_cell = openmc.Cell(
            name=f"l{idx + 1}_{MATERIAL_ORDER[idx]}_functional",
            region=functional_region,
            fill=mats[f"layer_{idx + 1}"],
        )
        cells.append(functional_cell)
        material_cells.append(functional_cell)

        if structural_thickness > 0.0:
            outer_surface = openmc.ZCylinder(r=layer_outer)
            structural_region = subtract_parasitics(+functional_outer_surface & -outer_surface & core_axial)
            structural_cell = openmc.Cell(
                name=f"l{idx + 1}_structural_skin",
                region=structural_region,
                fill=mats["structure"],
            )
            cells.append(structural_cell)
            material_cells.append(structural_cell)

    coolant_cell = None
    if coolant_union is not None:
        coolant_region = coolant_union & +c1 & -c6 & core_axial
        if port_union is not None:
            coolant_region = coolant_region & ~port_union
        coolant_cell = openmc.Cell(name="helium_coolant_channels", region=coolant_region, fill=mats["coolant"])
        cells.append(coolant_cell)
        material_cells.append(coolant_cell)

    port_cell = None
    if port_union is not None:
        port_cell = openmc.Cell(name="radial_port_voids", region=port_union, fill=None)
        cells.append(port_cell)

    top_inner = openmc.Cell(name="top_cap_inner", region=-c6 & top_inner_axial, fill=mats["layer_1"])
    bot_inner = openmc.Cell(name="bot_cap_inner", region=-c6 & bot_inner_axial, fill=mats["layer_1"])
    top_outer = openmc.Cell(name="top_cap_outer", region=-c6 & top_outer_axial, fill=mats["layer_5"])
    bot_outer = openmc.Cell(name="bot_cap_outer", region=-c6 & bot_outer_axial, fill=mats["layer_5"])
    for cap in (top_inner, bot_inner, top_outer, bot_outer):
        cells.append(cap)
        material_cells.append(cap)

    shield_cell = None
    if case.shield_thickness_cm > 0.0:
        shield_region = +c6 & -c_outer & whole_axial
        if port_union is not None:
            shield_region = shield_region & ~port_union
        shield_cell = openmc.Cell(name="outer_borated_steel_shield", region=shield_region, fill=mats["shield"])
        cells.append(shield_cell)
        material_cells.append(shield_cell)

    openmc.Materials(list(mats.values())).export_to_xml(run_dir / "materials.xml")
    openmc.Geometry(cells).export_to_xml(run_dir / "geometry.xml")

    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.Discrete([SOURCE_ENERGY_EV], [1.0])

    settings = openmc.Settings()
    settings.run_mode = "fixed source"
    settings.source = source
    settings.batches = int(batches)
    settings.inactive = 0
    settings.particles = int(particles)
    settings.seed = int(seed)
    settings.export_to_xml(run_dir / "settings.xml")

    h3 = openmc.Tally(name="h3_prod_engineering")
    h3.filters = [openmc.CellFilter(material_cells)]
    h3.scores = ["H3-production"]

    heat = openmc.Tally(name="heating_engineering")
    heat.filters = [openmc.CellFilter(material_cells)]
    heat.scores = ["heating-local"]

    nr = 72
    r_grid = [r_outer * i / nr for i in range(nr + 1)]
    mesh = openmc.CylindricalMesh(
        r_grid=r_grid,
        z_grid=[-z3, z3],
        phi_grid=[0.0, 2.0 * math.pi],
    )
    flux = openmc.Tally(name="radial_flux_engineering")
    flux.filters = [openmc.MeshFilter(mesh)]
    flux.scores = ["flux"]

    tallies = [h3, heat, flux]
    if port_cell is not None:
        port_flux = openmc.Tally(name="port_tracklength_flux")
        port_flux.filters = [openmc.CellFilter([port_cell])]
        port_flux.scores = ["flux"]
        tallies.append(port_flux)
    if shield_cell is not None:
        shield_flux = openmc.Tally(name="shield_tracklength_flux")
        shield_flux.filters = [openmc.CellFilter([shield_cell])]
        shield_flux.scores = ["flux"]
        tallies.append(shield_flux)

    openmc.Tallies(tallies).export_to_xml(run_dir / "tallies.xml")

    manifest = {
        "case": asdict(case),
        "seed": seed,
        "particles": particles,
        "batches": batches,
        "geometry": {
            "plasma_radius_cm": r0,
            "liquid_lithium_thickness_cm": LIQUID_LITHIUM_THICKNESS_CM,
            "blanket_thickness_cm": BLANKET_THICKNESS_CM,
            "material_order": MATERIAL_ORDER,
            "split": SPLIT,
            "blanket_outer_radius_cm": r6,
            "model_outer_radius_cm": r_outer,
            "core_half_height_cm": z1,
            "axial_caps_cm": [AXIAL_INNER_CAP_CM, AXIAL_OUTER_CAP_CM],
            "coolant_channel_centers": channel_centers(case, r1, r6),
        },
        "claim_boundary": "Engineering degradation/sensitivity model only; not engineering-complete blanket validation.",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"r0": r0, "r6": r6, "r_outer": r_outer, "nr": nr, "material_cells": material_cells}


def _sum_with_sigma(tally: Any) -> tuple[float, float]:
    import numpy as np

    mean = np.asarray(tally.mean, dtype=float).reshape(-1)
    sigma = np.asarray(tally.std_dev, dtype=float).reshape(-1)
    total = float(np.sum(mean))
    total_sigma = float(math.sqrt(float(np.sum(sigma**2))))
    return total, total_sigma


def extract_result(openmc: Any, statepoint_path: Path, case: EngineeringCase, seed: int, geom: dict[str, Any]) -> dict[str, Any]:
    import numpy as np

    with openmc.StatePoint(str(statepoint_path)) as sp:
        tbr, tbr_sigma = _sum_with_sigma(sp.get_tally(name="h3_prod_engineering"))
        heating_ev, heating_sigma_ev = _sum_with_sigma(sp.get_tally(name="heating_engineering"))

        flux_tally = sp.get_tally(name="radial_flux_engineering")
        flux = np.asarray(flux_tally.mean, dtype=float).reshape(-1)
        flux_sigma = np.asarray(flux_tally.std_dev, dtype=float).reshape(-1)
        nr = int(geom["nr"])
        centers = [(geom["r_outer"] * (i + 0.5) / nr) for i in range(nr)]
        front_index = next((i for i, center in enumerate(centers) if center >= geom["r0"]), 0)
        back_index = len(flux) - 1
        front_flux = float(flux[front_index])
        back_flux = float(flux[back_index])
        attenuation = 1.0 - back_flux / front_flux if front_flux > 0.0 else float("nan")

        port_flux_value = float("nan")
        if case.port_count > 0:
            port_flux_value = float(np.asarray(sp.get_tally(name="port_tracklength_flux").mean).reshape(-1)[0])

        shield_flux_value = float("nan")
        if case.shield_thickness_cm > 0.0:
            shield_flux_value = float(np.asarray(sp.get_tally(name="shield_tracklength_flux").mean).reshape(-1)[0])

    return {
        "case": case.name,
        "seed": seed,
        "structural_fraction": case.structural_fraction,
        "coolant_channel_count": case.coolant_channel_count,
        "coolant_channel_radius_cm": case.coolant_channel_radius_cm,
        "port_count": case.port_count,
        "port_radius_cm": case.port_radius_cm,
        "shield_thickness_cm": case.shield_thickness_cm,
        "breeder_packing_scale": case.breeder_packing_scale,
        "li6_enrichment_scale": case.li6_enrichment_scale,
        "TBR": tbr,
        "TBR_sigma": tbr_sigma,
        "TBR_rel_sigma": (tbr_sigma / abs(tbr)) if tbr else float("nan"),
        "heating_ev_per_source": heating_ev,
        "heating_sigma_ev_per_source": heating_sigma_ev,
        "front_flux": front_flux,
        "front_flux_sigma": float(flux_sigma[front_index]),
        "back_flux": back_flux,
        "back_flux_sigma": float(flux_sigma[back_index]),
        "radial_attenuation": attenuation,
        "port_tracklength_flux": port_flux_value,
        "shield_tracklength_flux": shield_flux_value,
    }


def run_case(case: EngineeringCase, seed: int, run_dir: Path, particles: int, batches: int, cross_sections: str | None) -> dict[str, Any]:
    try:
        import openmc
    except Exception as exc:  # pragma: no cover - environment-specific
        return {"case": case.name, "seed": seed, "returncode": 127, "error": f"openmc_import_failed: {exc!r}"}

    case_dir = run_dir / case.name / f"seed_{seed}"
    case_dir.mkdir(parents=True, exist_ok=True)
    geom = build_model(openmc, case, case_dir, seed, particles, batches)

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = env.get("OMP_NUM_THREADS", str(max(1, os.cpu_count() or 1)))
    if cross_sections:
        env["OPENMC_CROSS_SECTIONS"] = cross_sections

    executable = shutil.which("openmc")
    if not executable:
        return {"case": case.name, "seed": seed, "returncode": 127, "error": "openmc_executable_not_found"}

    proc = subprocess.run(
        [executable],
        cwd=case_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    (case_dir / "openmc.log").write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        return {
            "case": case.name,
            "seed": seed,
            "returncode": proc.returncode,
            "error": "openmc_run_failed",
            "log": str(case_dir / "openmc.log"),
        }

    statepoints = sorted(case_dir.glob("statepoint.*.h5"))
    if not statepoints:
        return {"case": case.name, "seed": seed, "returncode": 2, "error": "statepoint_missing"}

    result = extract_result(openmc, statepoints[-1], case, seed, geom)
    result["returncode"] = 0
    result["statepoint"] = str(statepoints[-1])
    return result


def finite(values: list[float]) -> list[float]:
    return [x for x in values if math.isfinite(x)]


def aggregate(rows: list[dict[str, Any]], cases: list[EngineeringCase]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for case in cases:
        subset = [row for row in rows if row.get("case") == case.name and row.get("returncode") == 0]
        if not subset:
            out.append({"case": case.name, "successful_seeds": 0})
            continue
        tbrs = finite([float(row["TBR"]) for row in subset])
        attenuations = finite([float(row["radial_attenuation"]) for row in subset])
        heating = finite([float(row["heating_ev_per_source"]) for row in subset])
        rel_sigmas = finite([float(row["TBR_rel_sigma"]) for row in subset])
        port_flux = finite([float(row["port_tracklength_flux"]) for row in subset])
        shield_flux = finite([float(row["shield_tracklength_flux"]) for row in subset])
        out.append(
            {
                "case": case.name,
                "successful_seeds": len(subset),
                "TBR_mean": statistics.fmean(tbrs),
                "TBR_seed_stdev": statistics.stdev(tbrs) if len(tbrs) > 1 else 0.0,
                "TBR_mean_reported_rel_sigma": statistics.fmean(rel_sigmas) if rel_sigmas else float("nan"),
                "radial_attenuation_mean": statistics.fmean(attenuations) if attenuations else float("nan"),
                "heating_ev_per_source_mean": statistics.fmean(heating) if heating else float("nan"),
                "port_tracklength_flux_mean": statistics.fmean(port_flux) if port_flux else float("nan"),
                "shield_tracklength_flux_mean": statistics.fmean(shield_flux) if shield_flux else float("nan"),
            }
        )

    control = next((row for row in out if row["case"] == "idealized_control" and row.get("successful_seeds", 0) > 0), None)
    if control:
        for row in out:
            if row.get("successful_seeds", 0) <= 0:
                continue
            c_tbr = float(control["TBR_mean"])
            c_heat = float(control["heating_ev_per_source_mean"])
            row["TBR_delta_fraction_vs_control"] = (float(row["TBR_mean"]) - c_tbr) / c_tbr if c_tbr else float("nan")
            row["heating_delta_fraction_vs_control"] = (
                (float(row["heating_ev_per_source_mean"]) - c_heat) / c_heat if c_heat else float("nan")
            )
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any, digits: int = 6) -> str:
    try:
        number = float(value)
        if not math.isfinite(number):
            return "n/a"
        return f"{number:.{digits}g}"
    except Exception:
        return str(value)


def write_report(path: Path, aggregates: list[dict[str, Any]], failures: list[dict[str, Any]], particles: int, batches: int, seeds: list[int]) -> None:
    lines = [
        "# be_outer_kill Engineering OpenMC Degradation Report",
        "",
        f"Status: `{STATUS}`",
        "",
        "This family measures how explicit engineering parasitics change the local `be_outer_kill` OpenMC control. It does not claim an engineering-complete blanket.",
        "",
        f"Transport: {particles} particles/batch × {batches} batches per seed; seeds `{','.join(str(s) for s in seeds)}`.",
        "",
        "| Case | Seeds | TBR mean | seed σ | tally rel σ | ΔTBR vs control | attenuation | heating eV/source |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregates:
        lines.append(
            "| {case} | {n} | {tbr} | {seed_sd} | {tally_sd} | {dtbr} | {attn} | {heat} |".format(
                case=row["case"],
                n=row.get("successful_seeds", 0),
                tbr=fmt(row.get("TBR_mean")),
                seed_sd=fmt(row.get("TBR_seed_stdev")),
                tally_sd=fmt(row.get("TBR_mean_reported_rel_sigma")),
                dtbr=fmt(row.get("TBR_delta_fraction_vs_control")),
                attn=fmt(row.get("radial_attenuation_mean")),
                heat=fmt(row.get("heating_ev_per_source_mean")),
            )
        )
    lines.extend(
        [
            "",
            "## What changed relative to the control",
            "",
            "- Each functional radial layer gives up the configured thickness fraction to an explicit reduced ferritic-steel skin.",
            "- Helium coolant channels are explicit Z-oriented cylindrical void/material regions cut through the blanket layers.",
            "- Radial diagnostic/heating penetrations are explicit finite X-oriented void channels cut through blanket and shield.",
            "- The engineering cases add an explicit borated-steel radial shield.",
            "- Breeder packing and Li-6 enrichment are varied only as declared sensitivity-envelope assumptions.",
            "",
            "## Remaining D limitations",
            "",
            "This is still a reduced cylindrical engineering-degradation model. It does not yet include a CAD-derived tokamak blanket, real port shapes and sector coverage, manifolds, first-wall support mechanics, magnet/shield integration, coolant thermohydraulics, tritium extraction, activation/DPA/He production, thermal stress, or manufacturing tolerances. The outer shield is radial and simplified. Therefore a favorable result narrows D but does not close it.",
        ]
    )
    if failures:
        lines.extend(["", "## Failed runs", ""])
        for failure in failures:
            lines.append(f"- `{failure.get('case')}` seed `{failure.get('seed')}`: `{failure.get('error')}` (return code {failure.get('returncode')})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--particles", type=int, default=8000)
    parser.add_argument("--batches", type=int, default=20)
    parser.add_argument("--seeds", default="104729,130363,169087")
    parser.add_argument("--case", action="append", help="run only named case; may be repeated")
    parser.add_argument("--cross-sections", default=os.environ.get("OPENMC_CROSS_SECTIONS"))
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    all_cases = case_matrix()
    selected = all_cases
    if args.case:
        wanted = set(args.case)
        selected = [case for case in all_cases if case.name in wanted]
        missing = sorted(wanted - {case.name for case in selected})
        if missing:
            raise SystemExit(f"unknown case(s): {', '.join(missing)}")
    seeds = parse_ints(args.seeds)
    validate_plan(all_cases, seeds)

    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "status": STATUS,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "material_order": MATERIAL_ORDER,
        "split": SPLIT,
        "particles": args.particles,
        "batches": args.batches,
        "seeds": seeds,
        "selected_cases": [asdict(case) for case in selected],
        "claim_boundary": "Engineering degradation/sensitivity model only; not engineering-complete blanket validation.",
    }
    (run_dir / "engineering_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    if args.check:
        assert args.particles > 0 and args.batches > 0
        assert selected
        print("plan check: PASS")
    if args.plan_only:
        print(json.dumps(plan, indent=2))
        return 0

    rows: list[dict[str, Any]] = []
    for case in selected:
        for seed in seeds:
            print(f"[run] {case.name} seed={seed}", flush=True)
            result = run_case(case, seed, run_dir, args.particles, args.batches, args.cross_sections)
            rows.append(result)
            if result.get("returncode") != 0:
                print(f"[fail] {case.name} seed={seed}: {result.get('error')}", flush=True)
                if args.strict:
                    write_csv(run_dir / "engineering_seed_results.csv", rows)
                    return 1
            else:
                print(
                    f"[ok] {case.name} seed={seed} TBR={result['TBR']:.6g} "
                    f"rel_sigma={result['TBR_rel_sigma']:.3g} attenuation={result['radial_attenuation']:.6g}",
                    flush=True,
                )

    write_csv(run_dir / "engineering_seed_results.csv", rows)
    aggregates = aggregate(rows, selected)
    write_csv(run_dir / "engineering_case_summary.csv", aggregates)
    failures = [row for row in rows if row.get("returncode") != 0]

    summary = {
        "status": STATUS,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "successful_runs": sum(row.get("returncode") == 0 for row in rows),
        "failed_runs": len(failures),
        "cases": aggregates,
        "claim_boundary": plan["claim_boundary"],
    }
    (run_dir / "engineering_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    write_report(run_dir / "BE_OUTER_KILL_ENGINEERING_REPORT.md", aggregates, failures, args.particles, args.batches, seeds)

    print(json.dumps(summary, indent=2, allow_nan=True))
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

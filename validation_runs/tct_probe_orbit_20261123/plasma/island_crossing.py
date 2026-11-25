"""Aim the modeled solid core across the seeded island axis."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import json
from math import pi
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.optimize import brentq, root

from field_window import DISK_POINTS
from measure import GUARD_RADIUS, sampler
from run import integrate
from settled_pass import METERS_PER_UNIT, SECONDS_PER_UNIT
from slip_sweep import SOURCE_STRENGTH, core_and_field
from source import sweep_mhd as mhd
from steered_replay import Flyby, ROOT, report_frame

HALF_TRAVEL = .70
CROSSING = 1.8
AFTER = .6
CADENCE = .1
FADE = .3
OFFSET = .46
AXIAL_CUT = .17
MESHES = ((64, 52, 52), (80, 64, 64), (80, 64, 64))
CHECKPOINTS = (0., FADE, CROSSING, CROSSING + AFTER / 2, CROSSING + AFTER)
CASES = {
    "unforced": (False, False, 0.),
    "centered_solid": (True, False, 0.),
    "offset_solid": (True, False, OFFSET),
    "centered_field": (False, True, 0.),
    "centered_combined": (True, True, 0.),
    "wide_centered_solid": (True, False, 0.),
}
WIDE_RADIUS = .30


class CrossIsland(Flyby):
    def __init__(self, target, x_offset):
        self.target = target
        self.x = target[0] + x_offset

    def at(self, time):
        q = np.clip(time / CROSSING, 0., 1.)
        fraction = q**3 * (10 - 15*q + 6*q*q)
        speed = -2 * HALF_TRAVEL / CROSSING * 30 * q*q * (1 - q)**2
        return (np.array([self.x, self.target[1] + HALF_TRAVEL * (1 - 2*fraction), AXIAL_CUT]),
                np.array([0., speed, 0.]))


def coupling(time):
    q = np.clip(min(time, CROSSING - time) / FADE, 0., 1.)
    return q*q * (3 - 2*q)


def crossing_model(path):
    def model(grid, time, solid, magnet):
        weight = coupling(time)
        source, mask, center, velocity = core_and_field(
            path, grid, time, solid and bool(weight), magnet and bool(weight),
            source_strength=SOURCE_STRENGTH*weight,
        )
        if mask is not None:
            mask *= weight
        return source, mask, center, velocity

    return model


def periodic_distance(a, b):
    return float(np.linalg.norm(mhd.wrapped(np.asarray(a) - np.asarray(b), mhd.LENGTH[:2])))


def fixed_points(grid, total, target, axial_steps, slice_seeds=()):
    seeds = {"axis": target.copy(), "saddle": np.array([0., 0.])}
    for dx, dy in product((-.95, -.6, -.32, -.12, 0., .12, .32, .6, .95), (-.16, 0., .16)):
        seeds[f"near_{dx:+.2f}_{dy:+.2f}"] = target + [dx, dy]
    for index, xy in enumerate(slice_seeds):
        seeds[f"slice_{index}"] = np.array(xy)
    mapping, _ = mhd.field_line_map(grid, total, seeds, axial_steps=axial_steps)
    if "status" in mapping:
        return mapping
    distinct = []
    for point in mapping.values():
        if point["status"] == "tracked" and all(periodic_distance(point["xy"], p["xy"]) > .025 for p in distinct):
            distinct.append(point)
    return dict(
        status="searched",
        original_axis=mapping["axis"],
        original_saddle=mapping["saddle"],
        elliptic=[p for p in distinct if p["classification"] == "elliptic"],
        hyperbolic=[p for p in distinct if p["classification"] == "hyperbolic"],
        unresolved_seed_count=sum(p["status"] != "tracked" or p.get("classification") == "stability_unresolved"
                                  for p in mapping.values()),
        total_seed_count=len(mapping),
    )


def projected_flux(grid, field):
    # Axial vector potential for the in-plane solenoidal projection.
    return grid.curl(field)[2] * grid.i_kxy2


def slice_points(grid, field, target, reference_saddle):
    potential = projected_flux(grid, field)
    x, y, _ = grid.k
    values = sampler(grid.physical(potential))
    gradient = [sampler(grid.physical(1j*k*potential)) for k in (x, y)]
    hessian = [sampler(grid.physical(-a*b*potential)) for a, b in ((x, x), (x, y), (y, y))]

    def at(function, xy):
        return float(function(np.array([xy[0], xy[1], AXIAL_CUT])))

    def grad(xy):
        return [at(f, xy) for f in gradient]

    def hess(xy):
        xx, xy, yy = (at(f, xy) for f in hessian)
        return [[xx, xy], [xy, yy]]

    seeds = [target, reference_saddle] + [target + [dx, dy]
             for dx, dy in product(np.linspace(-.95, .95, 11), (-.2, -.1, 0., .1, .2))]
    distinct = []
    for guess in seeds:
        solution = root(grad, guess, jac=hess)
        if np.linalg.norm(solution.fun) > 1e-6 or periodic_distance(solution.x, guess) > .6:
            continue
        location = mhd.wrapped(solution.x, mhd.LENGTH[:2])
        if any(periodic_distance(location, p["xy"]) <= .025 for p in distinct):
            continue
        curvature = float(np.linalg.det(hess(location)))
        if abs(curvature) < 1e-6:
            continue
        distinct.append(dict(xy=location.tolist(), kind="O" if curvature > 0 else "X",
                             projected_flux=at(values, location)))
    return dict(points=distinct)


def original_flux_contrast(row, target, saddle):
    points = row["slice_map"]["points"]
    axis = min((p for p in points if p["kind"] == "O"),
               key=lambda p: periodic_distance(p["xy"], target), default=None)
    saddle_point = min((p for p in points if p["kind"] == "X"),
                       key=lambda p: periodic_distance(p["xy"], saddle), default=None)
    if (axis is None or saddle_point is None or periodic_distance(axis["xy"], target) > .3
            or periodic_distance(saddle_point["xy"], saddle) > .3):
        return None
    return abs(axis["projected_flux"] - saddle_point["projected_flux"])


def initial_target(grid, field, guard_radius=GUARD_RADIUS):
    guesses = {"O": np.array([-pi, 0.]), "X": np.array([0., 0.])}
    topology, _ = mhd.field_line_map(grid, grid.physical(field), guesses)
    assert topology["O"]["classification"] == "elliptic"
    assert topology["X"]["classification"] == "hyperbolic"
    axis = np.array(topology["O"]["xy"])
    saddle = np.array(topology["X"]["xy"])
    sample = sampler(grid.physical(projected_flux(grid, field)))
    level = float(sample(np.array([*saddle, AXIAL_CUT])))

    def separatrix(y):
        return float(sample(np.array([axis[0], y, AXIAL_CUT]))) - level

    lower = brentq(separatrix, axis[1] - .55, axis[1] - .05)
    upper = brentq(separatrix, axis[1] + .05, axis[1] + .55)
    assert min(HALF_TRAVEL + lower - axis[1], HALF_TRAVEL + axis[1] - upper) > guard_radius
    return axis, saddle, (lower, upper)


def simulate(name, level):
    core, field, offset = CASES[name]
    mesh = MESHES[level]
    grid = mhd.Grid(mesh, "island", "sphere")
    radius = WIDE_RADIUS if name == "wide_centered_solid" else mhd.CORE_RADIUS
    grid.axes *= radius / mhd.CORE_RADIUS
    guard = radius * (1 + mhd.MASK_HALF_WIDTH)
    initial = np.array(mhd.initial_state(grid))
    target, saddle, separatrix = initial_target(grid, initial[1], guard)
    path = CrossIsland(target, offset)
    shift = np.array([*target, 0.])
    dt = CADENCE / (80 if level == 2 else 40)
    count = round((CROSSING + AFTER) / dt)
    model = crossing_model(path)

    def inspect(gr, state, time, mode):
        center, velocity = path.at(time)
        plasma = state[1]
        current = -gr.physical(gr.curl(plasma)[2])
        sample = sampler(current)

        def local(points):
            return sample(np.asarray(points) + shift)

        report = report_frame(current, local, local(DISK_POINTS), center-shift, velocity, time,
                              peak_points=DISK_POINTS,
                              guard_radius=guard if core and coupling(time) > 0 else 0.)
        row = dict(time_s=time * SECONDS_PER_UNIT, center_m=(center*METERS_PER_UNIT).tolist(),
                   speed_m_s=float(velocity[1]*METERS_PER_UNIT/SECONDS_PER_UNIT),
                   distance_to_initial_axis_m=periodic_distance(center[:2], target)*METERS_PER_UNIT,
                   peak_sampled_current=report["annulus_peak_j"], profiles=report["profiles"])
        if any(abs(time - t) < 1e-9 for t in CHECKPOINTS):
            source, _, _, _ = model(gr, time, core, field)
            total = plasma if source is None else plasma + source
            row["slice_map"] = slice_points(gr, total, target, saddle)
            candidates = [p["xy"] for p in row["slice_map"]["points"]] if level else []
            row["field_line_map"] = fixed_points(gr, gr.physical(total), target,
                                                 128 if level == 2 else 64, candidates)
        return row

    with np.errstate(over="raise", invalid="raise"):
        rows = integrate(grid, dt, name, initial, 0, count, model=model, inspect=inspect,
                         cadence=CADENCE, core=core, field=field)
    assert len(rows) == round((CROSSING + AFTER) / CADENCE) + 1
    assert len([r for r in rows if "field_line_map" in r]) == len(CHECKPOINTS)
    midpoint = rows[round(CROSSING / (2 * CADENCE))]
    return dict(
        case=name, mesh=list(mesh), dt_s=dt*SECONDS_PER_UNIT,
        aim_point_m=(np.array([*target, AXIAL_CUT])*METERS_PER_UNIT).tolist(),
        initial_saddle_m=(saddle * METERS_PER_UNIT).tolist(),
        initial_separatrix_y_m=(np.asarray(separatrix)*METERS_PER_UNIT).tolist(),
        closest_sample_to_axis_m=midpoint["distance_to_initial_axis_m"],
        normal_travel_m=2*HALF_TRAVEL*METERS_PER_UNIT, core_diameter_m=2*radius*METERS_PER_UNIT,
        initial_trajectory_offset_m=offset*METERS_PER_UNIT, solid=core, prescribed_field=field, rows=rows,
    )


def compute(names, levels, cache, jobs):
    records = {}
    pending = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for name, level in product(names, levels):
            key = name, level
            path = cache / f"{name}_{level}.json"
            if path.exists():
                records[key] = json.loads(path.read_text())
            else:
                pending[pool.submit(simulate, name, level)] = key, path
        for task in as_completed(pending):
            key, path = pending[task]
            records[key] = task.result()
            draft = path.with_suffix(f".{os.getpid()}.tmp")
            draft.write_text(json.dumps(records[key], allow_nan=False) + "\n")
            draft.replace(path)
            print("Completed", *key, flush=True)
    return records


def result(names, levels, cache, jobs):
    cases = compute(names, levels, cache, jobs)
    output = {}
    for name in names:
        output[name] = {}
        for level in levels:
            case = cases[name, level]
            control = cases["unforced", level]
            target = np.asarray(case["aim_point_m"][:2]) / METERS_PER_UNIT
            saddle = np.asarray(case.get("initial_saddle_m", [0., 0.])) / METERS_PER_UNIT
            rows = []
            for state, reference in zip(case["rows"], control["rows"], strict=True):
                assert abs(state["time_s"] - reference["time_s"]) < 1e-12
                row = {k: v for k, v in state.items() if k != "profiles"}
                cleared = state["time_s"] >= CROSSING * SECONDS_PER_UNIT - 1e-12
                if cleared:
                    row["peak_current_change_pct"] = 100 * (
                        state["peak_sampled_current"] / reference["peak_sampled_current"] - 1
                    )
                    values = [(a["width"], b["width"]) for a, b in zip(state["profiles"], reference["profiles"])
                              if a["width"] is not None and b["width"] is not None]
                    row["common_width_profiles"] = len(values)
                    row["mean_width_change_pct"] = (100*(sum(a for a, _ in values)/sum(b for _, b in values)-1)
                                                    if values else None)
                if "slice_map" in row:
                    a = original_flux_contrast(row, target, saddle)
                    b = original_flux_contrast(reference, target, saddle)
                    row["slice_map"] = dict(points=row["slice_map"]["points"],
                                            original_pair_projected_flux_contrast=a)
                    row["projected_flux_change_pct"] = 100*(a/b - 1) if a is not None and b else None
                rows.append(row)
            output[name][str(level)] = dict(case, rows=rows)
    return dict(
        crossing_duration_s=CROSSING*SECONDS_PER_UNIT,
        recovery_duration_s=AFTER*SECONDS_PER_UNIT,
        physical_scope="Prescribed crossing in periodic incompressible resistive MHD with a solid momentum mask. "
                       "Magnetic field evolves inside the mask. Topology is checked after coupling falls to zero.",
        cases=output,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=tuple(CASES))
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--jobs", type=int, default=5)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    names = tuple(dict.fromkeys(("unforced", *args.cases)))
    levels = (0, 1, 2) if args.refine else (0,)
    if args.cache is not None:
        args.cache.mkdir(parents=True, exist_ok=True)
        receipt = result(names, levels, args.cache, args.jobs)
    else:
        with TemporaryDirectory(prefix="tct-island-") as cache:
            receipt = result(names, levels, Path(cache), args.jobs)
    args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

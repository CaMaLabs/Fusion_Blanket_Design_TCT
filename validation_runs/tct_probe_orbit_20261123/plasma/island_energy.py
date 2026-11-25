"""Close the resolved MHD energy budget for the intentional island crossings."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.integrate import trapezoid

from island_crossing import (AFTER, AXIAL_CUT, CADENCE, CASES, CROSSING, CrossIsland,
                             MESHES, WIDE_RADIUS, crossing_model, initial_target)
from run import integrate
from settled_pass import METERS_PER_UNIT, SECONDS_PER_UNIT
from source import sweep_mhd as mhd

SAMPLE_CADENCE = .025
LOCAL_RADIUS = .75
LOCAL_HALF_HEIGHT = .50
POWER_KEYS = ("ohmic", "viscous", "local_ohmic", "body_work", "penalty_slip", "mask_work")


def spectral_norm(grid):
    """Construct a volume-integrated squared norm for the real FFT layout."""
    weights = np.full(grid.shape[-1] // 2 + 1, 2.)
    weights[0] = 1.
    if grid.shape[-1] % 2 == 0:
        weights[-1] = 1.
    weights *= grid.volume / np.prod(grid.shape)**2

    def norm(coefficients, multiplier=1.):
        squared = coefficients.real**2 + coefficients.imag**2
        return float(np.sum(squared * (weights * multiplier)))

    return norm


def energy_probe(grid, model, solid, target):
    norm = spectral_norm(grid)
    x = mhd.wrapped(grid.x - target[0], mhd.LENGTH[0])
    y = mhd.wrapped(grid.y - target[1], mhd.LENGTH[1])
    z = mhd.wrapped(grid.z - AXIAL_CUT, mhd.LENGTH[2])
    region = (x*x + z*z <= LOCAL_RADIUS**2) & (abs(y) <= LOCAL_HALF_HEIGHT)
    cell_volume = grid.volume / np.prod(grid.shape)

    def observe(grid, state, time, _mode):
        velocity_hat, field_hat = state
        j = grid.physical(grid.curl(field_hat))
        local_j = j[:, region]
        local_ohmic = mhd.ETA * cell_volume * np.einsum("ij,ij->", local_j, local_j)
        row = dict(
            time=float(time), time_s=float(time * SECONDS_PER_UNIT),
            kinetic=.5 * norm(velocity_hat), magnetic=.5 * norm(field_hat),
            ohmic=mhd.ETA * norm(field_hat, grid.k2), viscous=mhd.NU * norm(velocity_hat, grid.k2),
            local_ohmic=float(local_ohmic), body_work=0., penalty_slip=0., mask_work=0.,
        )
        if solid and 0. < time < CROSSING:
            _, mask, _, body_speed = model(grid, time, True, False)
            if mask is not None:
                velocity = grid.physical(velocity_hat)
                v_body = body_speed[:, None, None, None]
                difference = v_body - velocity
                force = mask / mhd.PENALTY_TIME * difference
                row["body_work"] = float(cell_volume * np.sum(v_body * force))
                row["penalty_slip"] = float(cell_volume * np.sum(difference * force))
                row["mask_work"] = float(cell_volume * np.sum(velocity * force))
                np.testing.assert_allclose(row["body_work"] - row["penalty_slip"], row["mask_work"],
                                           atol=1e-12, rtol=1e-11)
        return row

    return observe


def simulate(name, level):
    solid, field, offset = CASES[name]
    mesh = MESHES[level]
    grid = mhd.Grid(mesh, "island", "sphere")
    radius = WIDE_RADIUS if name == "wide_centered_solid" else mhd.CORE_RADIUS
    grid.axes *= radius / mhd.CORE_RADIUS
    initial = np.array(mhd.initial_state(grid))
    target, _, _ = initial_target(grid, initial[1], radius * (1 + mhd.MASK_HALF_WIDTH))
    model = crossing_model(CrossIsland(target, offset))
    dt = CADENCE / (80 if level == 2 else 40)
    count = round((CROSSING + AFTER) / dt)
    with np.errstate(over="raise", invalid="raise"):
        rows = integrate(grid, dt, name, initial, 0, count, model=model,
                         inspect=energy_probe(grid, model, solid, target),
                         cadence=SAMPLE_CADENCE, core=solid, field=field)
    assert len(rows) == round((CROSSING + AFTER) / SAMPLE_CADENCE) + 1
    return dict(case=name, mesh=list(mesh), dt_s=dt*SECONDS_PER_UNIT, rows=rows)


def budget(rows):
    time = [r["time"] for r in rows]
    integrals = {name: float(trapezoid([r[name] for r in rows], x=time)) for name in POWER_KEYS}
    initial, last = rows[0], rows[-1]
    change = (last["kinetic"] - initial["kinetic"]) + (last["magnetic"] - initial["magnetic"])
    expected = integrals["mask_work"] - integrals["ohmic"] - integrals["viscous"]
    error = change-expected
    scale = abs(integrals["body_work"]) + integrals["penalty_slip"] + integrals["ohmic"] + integrals["viscous"]
    return dict(integrals=integrals, resolved_energy_change=change, closure_error=error,
                closure_error_fraction_of_budget=abs(error)/scale)


def summarize(case, reference):
    split = round(CROSSING / SAMPLE_CADENCE)
    np.testing.assert_array_equal([row["time"] for row in case["rows"]],
                                  [row["time"] for row in reference["rows"]])
    intervals = {
        "crossing": slice(0, split + 1),
        "after_clearance": slice(split, None),
        "full": slice(None),
    }
    result = {}
    for name, window in intervals.items():
        values = budget(case["rows"][window])
        control = budget(reference["rows"][window])
        for entry in (values, control):
            if entry["closure_error_fraction_of_budget"] > .002:
                raise ArithmeticError(f"Energy balance outside tolerance for {case['case']} {name}: {entry}")
        values["comparison"] = {
            f"{key}_excess": values["integrals"][key] - control["integrals"][key]
            for key in ("ohmic", "local_ohmic", "viscous")
        }
        for key in ("ohmic", "local_ohmic", "viscous"):
            base = control["integrals"][key]
            values["comparison"][f"{key}_change_pct"] = 100. * values["comparison"][f"{key}_excess"] / base if base else None
        result[name] = values
    return result


def run(args, cache):
    names = tuple(dict.fromkeys(("unforced", *args.cases)))
    levels = (0, 1, 2) if args.refine else (0,)
    runs = {}
    queue = {}
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for name, level in product(names, levels):
            key = name, level
            file = cache / f"{name}_{level}.json"
            if file.exists():
                runs[key] = json.loads(file.read_text())
            else:
                queue[pool.submit(simulate, name, level)] = key, file
        for task in as_completed(queue):
            key, file = queue[task]
            runs[key] = task.result()
            staged = file.with_suffix(f".{os.getpid()}.tmp")
            staged.write_text(json.dumps(runs[key], allow_nan=False) + "\n")
            staged.replace(file)
            print("Completed", *key, flush=True)
    cases = {}
    for name in names:
        cases[name] = {}
        for level in levels:
            case = runs[name, level]
            cases[name][str(level)] = dict(case, windows=summarize(case, runs["unforced", level]))
    result = dict(
        scope="Normalized incompressible resistive MHD with a periodic domain",
        energy_units="Normalized MHD volume-integrated energy",
        sample_cadence_s=SAMPLE_CADENCE*SECONDS_PER_UNIT,
        resistivity=mhd.ETA,
        viscosity=mhd.NU,
        energy_identity="Delta(E_kinetic + E_magnetic_plasma) = W_body - E_penalty_slip - E_ohmic - E_viscous",
        local_region=dict(radius_m=LOCAL_RADIUS*METERS_PER_UNIT, half_height_m=LOCAL_HALF_HEIGHT*METERS_PER_UNIT,
                          location="Centered on the initial island axis at the crossing axial plane"),
        crossing_s=CROSSING*SECONDS_PER_UNIT, after_clearance_s=AFTER*SECONDS_PER_UNIT,
        cases=cases,
    )
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=tuple(CASES))
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.cache is not None:
        args.cache.mkdir(parents=True, exist_ok=True)
        run(args, args.cache)
    else:
        with TemporaryDirectory(prefix="tct-island-energy-") as folder:
            run(args, Path(folder))


if __name__ == "__main__":
    main()

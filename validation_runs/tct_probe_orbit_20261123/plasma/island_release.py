"""Couple the island crossing to an evolving pressure layer and outer heat loss."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import json
import os
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

from island_crossing import AXIAL_CUT, CASES, CROSSING, CrossIsland, WIDE_RADIUS, crossing_model, initial_target
from island_energy import spectral_norm
from settled_pass import SECONDS_PER_UNIT
from source import sweep_mhd as mhd

END = 3.6
SAMPLE = .025
LEVELS = (((48, 40, 40), .005), ((64, 52, 52), .0025), ((64, 52, 52), .00125))
CURVATURE = 24.
CHI_ISO = .003
HEAT_FLOOR = .085
EXHAUST_RATE = 3.
EXHAUST_CENTER = .64
EXHAUST_WIDTH = .23
NO_DRIVE_SUFFIX = "_no_curvature"
NO_DRIVE = "unforced" + NO_DRIVE_SUFFIX
SOLID_NO_DRIVE = tuple(name + NO_DRIVE_SUFFIX for name in ("centered_solid", "wide_centered_solid"))
RATES = ("exhaust", "body_work", "penalty_slip", "ohmic_heat", "viscous_heat", "curvature_work")


def initial_heat(grid):
    displacement = .035 * (np.cos(5*grid.x + .3) * (1 + .22*np.cos(2*(grid.z-AXIAL_CUT)))
                          + .27*np.sin(7*grid.x + 2*grid.z + .5))
    return HEAT_FLOOR + .50 * .5 * (1 - np.tanh(np.sin(2*(grid.y + .06 + displacement))/.32))


def transport_heat(heat, velocity, spacing):
    """Conservative limited upwind flux and centered cross-cell diffusion."""
    result = np.zeros_like(heat)
    for axis, (component, width) in enumerate(zip(velocity, spacing, strict=True)):
        forward = np.roll(heat, -1, axis=axis) - heat
        backward = np.roll(forward, 1, axis=axis)
        slope = np.where(forward*backward > 0.,
                         np.sign(forward)*np.minimum(abs(forward), abs(backward)), 0.)
        face = .5*(component + np.roll(component, -1, axis=axis))
        left = heat + .5*slope
        right = np.roll(heat - .5*slope, -1, axis=axis)
        flux = face*np.where(face >= 0., left, right) - CHI_ISO*forward/width
        result -= (flux - np.roll(flux, 1, axis=axis))/width
    return result


def exhaust_profile(grid, center=EXHAUST_CENTER):
    return EXHAUST_RATE * np.exp(-((grid.y-center)/EXHAUST_WIDTH)**2)


def equations(grid, model, solid, field, drive, *, exhaust_center=EXHAUST_CENTER):
    curvature = drive * (.5 * (1 + np.cos(2*grid.y)))**4
    exhaust_mask = exhaust_profile(grid, exhaust_center)
    cell = grid.volume / np.prod(grid.shape)
    spacing = mhd.LENGTH / grid.shape

    def evaluate(state, t):
        velocity_hat, plasma_hat, heat = state
        velocity, total, current, omega, force, mask, relative = mhd.fluid_terms(
            grid, state[:2], t, solid, field, mhd.PENALTY_TIME, model)
        buoyancy = curvature * heat
        force[1] += buoyancy - buoyancy.mean()
        exchange = buoyancy * (velocity[1] - velocity[1].mean())
        j_heat = mhd.ETA * np.einsum("ixyz,ixyz->xyz", current, current)
        v_heat = mhd.NU * np.einsum("ixyz,ixyz->xyz", omega, omega)
        exhaust = exhaust_mask * np.maximum(heat - HEAT_FLOOR, 0.)

        thermal = transport_heat(heat, velocity, spacing) + j_heat + v_heat - exchange - exhaust
        derivatives = (
            grid.project(grid.transform(force)) - mhd.NU*grid.k2*velocity_hat,
            grid.curl(grid.transform(mhd.cross(velocity, total))) - mhd.ETA*grid.k2*plasma_hat,
            thermal,
        )
        slip = body_work = 0.
        if mask is not None:
            penalty_force = mask/mhd.PENALTY_TIME * relative
            slip = float(cell * np.sum(relative * penalty_force))
            body_work = slip + float(cell * np.sum(velocity * penalty_force))
        rates = np.array([cell*np.sum(exhaust), body_work, slip, cell*np.sum(j_heat),
                          cell*np.sum(v_heat), cell*np.sum(exchange)])
        return derivatives, rates, float(heat.min())

    return evaluate


def simulate(name, level, drive=CURVATURE, *, exhaust_center=EXHAUST_CENTER, observer=None):
    base_case = name.removesuffix(NO_DRIVE_SUFFIX)
    solid, field, offset = CASES[base_case]
    mesh, dt = LEVELS[level]
    grid = mhd.Grid(mesh, "island", "sphere")
    radius = WIDE_RADIUS if base_case == "wide_centered_solid" else mhd.CORE_RADIUS
    grid.axes *= radius / mhd.CORE_RADIUS
    velocity, plasma_field = mhd.initial_state(grid)
    axis, _, _ = initial_target(grid, plasma_field, radius*(1+mhd.MASK_HALF_WIDTH))
    model = crossing_model(CrossIsland(axis, offset))
    state = (velocity, plasma_field, initial_heat(grid))
    evaluate = equations(grid, model, solid, field, drive if base_case == name else 0.,
                         exhaust_center=exhaust_center)
    norm = spectral_norm(grid)
    integration = np.zeros(len(RATES))
    output = []
    count = round(END/dt)
    stride = round(SAMPLE/dt)
    cell = grid.volume / np.prod(grid.shape)
    minimum_heat = float("inf")
    with np.errstate(over="raise", invalid="raise"):
        for step in range(count+1):
            t = step*dt
            k1, powers, heat_min = evaluate(state, t)
            minimum_heat = min(minimum_heat, heat_min)
            if step % stride == 0:
                output.append(dict(
                    time=float(t), time_ms=1000*t*SECONDS_PER_UNIT, kinetic=.5*norm(state[0]),
                    magnetic=.5*norm(state[1]), thermal=float(cell*np.sum(state[2])),
                    exhaust_power=float(powers[0]), cumulative=dict(zip(RATES, integration.tolist(), strict=True)),
                ))
                if observer is not None:
                    observer(grid, state, model, solid, field, t)
            if step == count:
                break
            predictor = tuple(value + dt*rate for value, rate in zip(state, k1, strict=True))
            k2, next_powers, predicted_heat_min = evaluate(predictor, t+dt)
            minimum_heat = min(minimum_heat, predicted_heat_min)
            integration += .5*dt*(powers + next_powers)
            for value, current, future in zip(state, k1, k2, strict=True):
                value += .5*dt*(current + future)

    assert len(output) == round(END/SAMPLE)+1
    assert all(np.isfinite(value).all() for value in state)
    for vector in state[:2]:
        divergence = grid.physical(1j * sum(k_i*f_i for k_i, f_i in zip(grid.k, vector, strict=True)))
        assert np.max(np.abs(divergence)) < 1e-9
    initial, final = output[0], output[-1]
    energy_change = sum(final[key] - initial[key] for key in ("thermal", "kinetic", "magnetic"))
    expected = integration[1] - integration[2] - integration[0]
    scale = sum(abs(integration[i]) for i in (0, 1, 2))
    closure = float(abs(energy_change - expected)/scale)
    if closure > .004 or minimum_heat <= 0:
        raise ArithmeticError(f"{name} level {level}: heat min {minimum_heat:.6g}, budget residual {closure:.6g}")
    print("Completed", name, level, "final exhaust", integration[0], "heat minimum", minimum_heat, flush=True)
    return dict(case=name, level=level, mesh=mesh, dt_s=dt*SECONDS_PER_UNIT, initial_heat_floor=HEAT_FLOOR,
                minimum_heat=minimum_heat, energy_balance_error_fraction=closure, rows=output)


def analyze(results):
    controls = {r["level"]: r for r in results if r["case"] == "unforced"}
    cases = {(r["case"], r["level"]): r for r in results}
    clearance = round(CROSSING/SAMPLE)
    for result in results:
        control = controls[result["level"]]
        rows = result["rows"]
        powers = np.array([r["exhaust_power"] for r in rows])
        max_idx = int(np.argmax(powers))
        unforced_peak = max(r["exhaust_power"] for r in control["rows"])
        peaks, _ = find_peaks(powers, prominence=.1*unforced_peak, distance=round(.20/SAMPLE))
        cumulative = rows[-1]["cumulative"]["exhaust"]
        base = control["rows"][-1]["cumulative"]["exhaust"]
        pre_clearance = rows[clearance]["cumulative"]["exhaust"]
        base_pre_clearance = control["rows"][clearance]["cumulative"]["exhaust"]
        result["summary"] = dict(
            escape_energy=cumulative, escape_change_pct=100.*(cumulative/base-1.),
            escape_at_clearance=pre_clearance,
            escape_at_clearance_change_pct=100.*(pre_clearance/base_pre_clearance-1.),
            peak_power=float(powers[max_idx]), peak_change_pct=100.*(powers[max_idx]/unforced_peak-1.),
            peak_time_ms=rows[max_idx]["time_ms"], final_power=float(powers[-1]),
            peak_at_window_end=max_idx == len(rows)-1,
            resolved_local_peaks_ms=[rows[i]["time_ms"] for i in peaks],
        )
        drive_off = cases.get((result["case"] + NO_DRIVE_SUFFIX, result["level"]))
        if drive_off is not None:
            off_energy = drive_off["rows"][-1]["cumulative"]["exhaust"]
            result["summary"]["escape_change_from_enabling_curvature"] = cumulative - off_energy


def save_case(cache, name, level, *, exhaust_center=EXHAUST_CENTER):
    path = cache / f"{name}_{level}.json"
    if path.is_file():
        return json.loads(path.read_text())
    result = simulate(name, level, exhaust_center=exhaust_center)
    staged = path.with_name(f".{path.stem}-{os.getpid()}.json")
    try:
        staged.write_text(json.dumps(result, allow_nan=False) + "\n")
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", choices=(*CASES, NO_DRIVE, *SOLID_NO_DRIVE),
                        default=[*CASES, *SOLID_NO_DRIVE])
    parser.add_argument("--levels", nargs="+", type=int, choices=(0,1,2), default=[0])
    parser.add_argument("--jobs", type=int, default=7)
    parser.add_argument("--exhaust-center", type=float, default=EXHAUST_CENTER,
                        help="outward displacement of the loss region in normalized length units")
    args = parser.parse_args()
    if not 0. < args.exhaust_center < mhd.LENGTH[1]/2:
        parser.error("--exhaust-center must lie on the outer half of the domain")
    cache = args.cache if args.exhaust_center == EXHAUST_CENTER else args.cache / args.exhaust_center.hex()
    cache.mkdir(parents=True, exist_ok=True)
    names = tuple(dict.fromkeys(("unforced", NO_DRIVE, *args.cases)))
    results = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        pending = [pool.submit(save_case, cache, name, level, exhaust_center=args.exhaust_center)
                   for level, name in product(args.levels, names)]
        for task in as_completed(pending):
            results.append(task.result())
    results.sort(key=lambda r: (r["level"], names.index(r["case"])))
    analyze(results)
    receipt = dict(
        model="Pressure-coupled normalized periodic slab with a localized sink representing open-edge heat loss",
        choices=dict(curvature=CURVATURE, chi_iso=CHI_ISO,
                     exhaust_rate=EXHAUST_RATE, exhaust_center=args.exhaust_center, exhaust_width=EXHAUST_WIDTH),
        crossing_ms=1000*CROSSING*SECONDS_PER_UNIT, horizon_ms=1000*END*SECONDS_PER_UNIT, results=results,
    )
    args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

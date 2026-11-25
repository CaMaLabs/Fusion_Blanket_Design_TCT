"""Map a matched passive heat pulse to two absorbing plates in the island replay."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import product
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.special import erfc, ndtr, ndtri
from scipy.stats import qmc

from island_crossing import AXIAL_CUT, CASES, CROSSING, MESHES
from island_heat_snapshots import RELEASE_TIMES, snapshot_path
from settled_pass import METERS_PER_UNIT, SECONDS_PER_UNIT
from source.sweep_mhd import LENGTH

PACKETS = {"narrow": (.12, .06), "broad": (.24, .12)}
HALF_GAPS = (.80, np.pi/2)
DIFFUSION_TIMES = np.array([.125, .25, .5, 1., 2., 4.])
REFERENCE_TIME = int(np.flatnonzero(DIFFUSION_TIMES == 1.)[0])
MAX_LENGTH = 6.
FOOTPRINT_SIGMA = .10
PIXELS = (128, 64)
TIMES_AT_CLEARANCE = np.asarray(RELEASE_TIMES[1:]) - CROSSING


def packet_seeds(power):
    unit_square = qmc.Sobol(d=2, scramble=True, seed=617).random_base2(power)
    limit = ndtr(-2.5)
    gaussian = ndtri(limit + (1 - 2*limit) * unit_square).T
    xy = np.concatenate([np.array([[-np.pi], [0.]]) + np.asarray(sigma)[:, None]*gaussian
                         for sigma in PACKETS.values()], axis=1)
    return np.vstack((xy, np.full(xy.shape[1], AXIAL_CUT)))


def connections(field, seeds, half_gap, ds, sign, *, axial_center=AXIAL_CUT, maximum_length=MAX_LENGTH):
    """Follow unit-speed field lines to their first plate intersection."""
    scale = np.asarray(field.shape[1:])[:, None] / LENGTH[:, None]
    center = LENGTH[:, None] / 2

    def tangent(position):
        index = (position + center) * scale
        values = np.stack([map_coordinates(b, index, order=1, mode="grid-wrap", prefilter=False)
                           for b in field])
        norm = np.linalg.norm(values, axis=0)
        return sign * values / np.maximum(norm, 1e-12)

    position = seeds.copy()
    ids = np.arange(seeds.shape[1])
    lengths = np.full(len(ids), np.inf)
    plate = np.zeros(len(ids), dtype=int)
    landing = np.zeros((2, len(ids)))
    for i in range(round(maximum_length/ds)):
        if not ids.size:
            break
        next_position = position + ds*tangent(position + .5*ds*tangent(position))
        crossed = abs(next_position[2] - axial_center) >= half_gap
        if np.any(crossed):
            found = ids[crossed]
            side = np.sign(next_position[2, crossed] - axial_center)
            z_plate = axial_center + side*half_gap
            fraction = (z_plate - position[2, crossed]) / (next_position[2, crossed] - position[2, crossed])
            lengths[found] = (i + fraction)*ds
            plate[found] = side.astype(int)
            landing[:, found] = position[:2, crossed] + fraction*(next_position[:2, crossed] - position[:2, crossed])
        ids, position = ids[~crossed], next_position[:, ~crossed]
    return lengths, plate, landing


def first_passage(distance, connection_length, half_gap):
    """Cumulative diffusion flux at one absorbing endpoint via image sources."""
    scale = 2*half_gap*np.sqrt(DIFFUSION_TIMES[:, None])
    cdf = np.zeros((len(DIFFUSION_TIMES), len(distance)))
    for image in range(-7, 8):
        location = distance + 2*image*connection_length
        cdf += np.sign(location) * erfc(abs(location) / scale)
    return cdf


def plate_fluence(branches, weights):
    """Return both plate maps in units of inverse square meters per unit input."""
    maps = np.zeros((2, *PIXELS))
    pixel_size = LENGTH[:2] / PIXELS
    for (_, plate, landing), heat in zip(branches, weights, strict=True):
        wrapped = (landing.T + LENGTH[:2]/2) % LENGTH[:2]
        for i, side in enumerate((-1, 1)):
            items = plate == side
            maps[i] += np.histogram2d(*wrapped[items].T, bins=PIXELS,
                                      range=((0, LENGTH[0]), (0, LENGTH[1])), weights=heat[items])[0]
    area = np.prod(pixel_size*METERS_PER_UNIT)
    return gaussian_filter(maps, sigma=(0., *(FOOTPRINT_SIGMA / pixel_size)), mode="wrap") / area


def deposit(branches, half_gap):
    both = np.isfinite(branches[0][0]) & np.isfinite(branches[1][0])
    unresolved = float(1. - np.mean(both))
    count = len(both)
    branches = [(lengths[both], side[both], xy[:, both]) for lengths, side, xy in branches]
    lengths = [branch[0] for branch in branches]
    total_length = lengths[0] + lengths[1]
    eventual = [(1. - length/total_length)/count for length in lengths]
    cumulative = [first_passage(length, total_length, half_gap)/count for length in lengths]
    cumulative_total = sum(heat.sum(axis=1) for heat in cumulative)
    if (np.any(np.diff(cumulative_total) < -1e-12) or np.any(cumulative_total > 1. - unresolved + 1e-12)
            or any(np.any(h < -1e-12) or np.any(h > w + 1e-12) for h, w in zip(cumulative, eventual, strict=True))):
        raise ArithmeticError("Invalid absorbing-boundary heat budget")
    full_maps = plate_fluence(branches, eventual)
    np.testing.assert_allclose(full_maps.sum() * np.prod(LENGTH[:2]*METERS_PER_UNIT/PIXELS),
                               1. - unresolved, rtol=0., atol=2e-11)
    early_maps = plate_fluence(branches, [heat[REFERENCE_TIME] for heat in cumulative])
    absorbed = [sum(float(np.sum(w[branch[1] == side])) for branch, w in zip(branches, eventual, strict=True))
                for side in (-1, 1)]
    return dict(
        unresolved_fraction=unresolved,
        eventual_plate_fractions=absorbed,
        cumulative_both_plate_fractions=cumulative_total.tolist(),
        mean_exit_theta_resolved=float(.5*np.mean(lengths[0]*lengths[1])/half_gap**2)
            if lengths[0].size else None,
        worst_plate_fluence_per_m2=float(full_maps.max()),
        worst_plate_fluence_at_theta_1_per_m2=float(early_maps.max()),
    )


def sanity_check():
    guide = np.zeros((3, 8, 8, 8))
    guide[2] = 1.
    half_gap = HALF_GAPS[0]
    seeds = packet_seeds(6)
    uniform = [connections(guide, seeds, half_gap, .03125, sign) for sign in (-1, 1)]
    for (lengths, side, point), sign in zip(uniform, (-1, 1), strict=True):
        np.testing.assert_allclose(lengths, half_gap, rtol=0., atol=1e-12)
        np.testing.assert_array_equal(side, sign)
        np.testing.assert_array_equal(point, seeds[:2])
    result = deposit(uniform, half_gap)
    np.testing.assert_allclose(result["eventual_plate_fractions"], [.5, .5], rtol=0., atol=1e-12)
    np.testing.assert_allclose(result["mean_exit_theta_resolved"], .5, rtol=0., atol=1e-12)
    k = np.arange(1., 60., 2.)[:, None]
    series = (-1.)**((k-1.)/2.) * np.exp(-k*k*np.pi**2*DIFFUSION_TIMES/4.)/k
    np.testing.assert_allclose(result["cumulative_both_plate_fractions"], 1.-4./np.pi*series.sum(axis=0),
                               rtol=0., atol=3e-13)
    guide[0] = .75
    tilted = connections(guide, seeds, half_gap, .03125, 1.)
    np.testing.assert_allclose(tilted[0], 1.25*half_gap, rtol=0., atol=1e-12)
    offsets = np.array([[.75*half_gap], [0.]])
    np.testing.assert_allclose(tilted[2], seeds[:2] + offsets, rtol=0., atol=1e-12)
    asymmetric = [(uniform[0][0], uniform[0][1], uniform[0][2]),
                  (3*uniform[1][0], uniform[1][1], uniform[1][2])]
    np.testing.assert_allclose(deposit(asymmetric, half_gap)["eventual_plate_fractions"], [.75, .25],
                               rtol=0., atol=1e-12)


def replay(cache, case, level):
    power, ds = ((13, .04), (15, .02))[level]
    seeds = packet_seeds(power)
    with np.load(snapshot_path(cache, case, level)) as states:
        np.testing.assert_allclose(states["time"], RELEASE_TIMES, rtol=0., atol=1e-10)
        dt_s = float(states["dt_s"])
        targets = []
        for frame, history in enumerate(states["field"][1:]):
            time_ms = float(1000*TIMES_AT_CLEARANCE[frame]*SECONDS_PER_UNIT)
            for half_gap in HALF_GAPS:
                branches = [connections(history, seeds, half_gap, ds, sign) for sign in (-1., 1.)]
                for i, packet in enumerate(PACKETS):
                    span = slice(i*(2**power), (i+1)*(2**power))
                    selected = [(lengths[span], plates[span], landing[:, span])
                                for lengths, plates, landing in branches]
                    targets.append(dict(time_after_clearance_ms=time_ms, half_gap_m=half_gap*METERS_PER_UNIT,
                                        packet=packet, **deposit(selected, half_gap)))
    print("Finished heat replay", case, level, flush=True)
    return dict(case=case, level=level, mesh=MESHES[level], mhd_dt_s=dt_s, samples_per_packet=2**power,
                field_line_step_m=ds*METERS_PER_UNIT, targets=targets)


def match_controls(runs):
    controls = {run["level"]: run["targets"] for run in runs if run["case"] == "unforced"}
    for run in runs:
        for treated, control in zip(run["targets"], controls[run["level"]], strict=True):
            assert all(treated[key] == control[key] for key in ("time_after_clearance_ms", "half_gap_m", "packet"))
            treated["comparison"] = dict(
                change_in_both_plate_fraction_at_theta_1=
                    treated["cumulative_both_plate_fractions"][REFERENCE_TIME]
                    - control["cumulative_both_plate_fractions"][REFERENCE_TIME],
                eventual_peak_fluence_change_pct=100.*(
                    treated["worst_plate_fluence_per_m2"] / control["worst_plate_fluence_per_m2"] - 1.),
                peak_fluence_at_theta_1_change_pct=100.*(
                    treated["worst_plate_fluence_at_theta_1_per_m2"]
                    / control["worst_plate_fluence_at_theta_1_per_m2"] - 1.),
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", choices=CASES, required=True)
    parser.add_argument("--levels", nargs="+", type=int, choices=(0, 1), default=[0, 1])
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    sanity_check()
    names = tuple(dict.fromkeys(("unforced", *args.cases)))
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        pending = [pool.submit(replay, args.cache, case, level) for case, level in product(names, args.levels)]
        results = [task.result() for task in pending]
    match_controls(results)
    output = dict(
        model="Frozen periodic MHD field, constant-area parallel diffusion on traced lines, two absorbing axial plates",
        normalization="Unit pulse energy, no conversion to tokamak ELM joules",
        diffusion_time_theta="chi_parallel * elapsed_time / plate_half_gap**2",
        theta=DIFFUSION_TIMES.tolist(),
        transverse_packet_sigma_m={k: (np.asarray(v)*METERS_PER_UNIT).tolist() for k, v in PACKETS.items()},
        footprint_sigma_m=FOOTPRINT_SIGMA*METERS_PER_UNIT,
        maximum_trace_length_each_direction_m=MAX_LENGTH*METERS_PER_UNIT,
        results=results,
    )
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

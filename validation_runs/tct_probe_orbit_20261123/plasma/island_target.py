"""Route self-evolving plasma exhaust to ideal absorbing targets."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import json
from pathlib import Path

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.special import erfc
from scipy.stats import qmc

from island_crossing import AXIAL_CUT
from island_heat import connections, first_passage
from island_target_snapshots import CASES, SNAPSHOT_INTERVAL, snapshot_path
from settled_pass import METERS_PER_UNIT, SECONDS_PER_UNIT
from source.sweep_mhd import LENGTH

HALF_GAP = LENGTH[2]/2
CUTS = {"original": AXIAL_CUT, "shifted": AXIAL_CUT + LENGTH[2]/4}
DIFFUSION_SCALE_MS = (.25, 1., 3., 10., 30.)
LAGS = np.unique(np.r_[0., .5, 1., 2., np.geomspace(1e-6, 512., 410)])
MAX_LENGTH = 12.
OBSERVATION_STEP_S = 2e-5


def exhaust_seeds(density, uniforms, axial_center):
    """Sample heat removed per unit volume, with uniform subcell offsets."""
    volume_cdf = np.cumsum(density.ravel())
    cells = np.searchsorted(volume_cdf, uniforms[:, 0]*volume_cdf[-1], side="right")
    coordinates = np.array(np.unravel_index(cells, density.shape), dtype=float)
    coordinates += uniforms[:, 1:].T - .5
    coordinates = (coordinates/np.asarray(density.shape)[:, None] - .5)*LENGTH[:, None]
    z = coordinates[2] - axial_center
    coordinates[2] = axial_center + (z + HALF_GAP) % (2*HALF_GAP) - HALF_GAP
    return coordinates


def both_plate_cdf(left, right, lag):
    """Exit probability for diffusion on a constant-area path with two absorbing ends."""
    length = left + right
    position = left/length
    ratio = lag[:, None] * (HALF_GAP/length)**2
    cdf = np.zeros_like(ratio)
    # Image sources converge at short times. The odd sine series for the
    # survival probability converges rapidly once chi*t/L^2 exceeds one tenth.
    rows, cols = np.nonzero((ratio > 0.) & (ratio <= .10))
    x = position[cols]
    scale = 2.*np.sqrt(ratio[rows, cols])
    early = np.zeros_like(x)
    for offset in (-2, -1, 0, 1, 2):
        for distance in (x + 2*offset, 1 - x + 2*offset):
            early += np.sign(distance)*erfc(np.abs(distance)/scale)
    cdf[rows, cols] = early
    rows, cols = np.nonzero(ratio > .10)
    x = position[cols]
    v = ratio[rows, cols]
    survival = sum(np.sin(n*np.pi*x)*np.exp(-n*n*np.pi**2*v)/n for n in (1, 3, 5))
    cdf[rows, cols] = 1. - 4./np.pi * survival
    return cdf


class HeatKernel:
    def __init__(self, cdf, resolved):
        if np.any(np.diff(cdf) < -1e-11) or not np.isclose(cdf[-1], resolved, atol=2e-7, rtol=0.):
            raise ValueError("The arrival curve failed monotonicity or the terminal energy limit")
        self.resolved = resolved
        self.cdf = np.maximum.accumulate(np.clip(cdf, 0., resolved))
        self.cdf[-1] = resolved
        self.integral = cumulative_trapezoid(self.cdf, LAGS, initial=0.)
        self.slopes = np.diff(self.cdf)/np.diff(LAGS)

    def evaluate(self, lag):
        bounded = np.clip(lag, 0., LAGS[-1])
        index = np.searchsorted(LAGS, bounded, side="right").clip(1, len(LAGS)-1) - 1
        delta = bounded - LAGS[index]
        cdf = self.cdf[index] + delta*self.slopes[index]
        integral = self.integral[index] + delta*(self.cdf[index] + .5*delta*self.slopes[index])
        integral += np.maximum(lag-LAGS[-1], 0.) * self.resolved
        return cdf, integral


def estimate_kernel(magnetic, exhaust, uniforms, center, ds):
    seeds = exhaust_seeds(exhaust, uniforms, center)
    distances = [connections(magnetic, seeds, HALF_GAP, ds, sign, axial_center=center,
                             maximum_length=MAX_LENGTH)[0] for sign in (-1., 1.)]
    resolved = np.isfinite(distances[0]) & np.isfinite(distances[1])
    left, right = (distance[resolved] for distance in distances)
    cdf = both_plate_cdf(left, right, LAGS).sum(axis=1)/seeds.shape[1]
    return HeatKernel(cdf, float(resolved.mean()))


def wall_response(time, edges, energy, groups, kernels, scale):
    power = np.zeros_like(time)
    accumulated = np.zeros_like(time)
    rates = energy/np.diff(edges)
    for i, kernel in enumerate(kernels):
        span = groups == i
        start = (time[:, None] - edges[:-1][span])/scale
        end = (time[:, None] - edges[1:][span])/scale
        start_cdf, start_integral = kernel.evaluate(start)
        end_cdf, end_integral = kernel.evaluate(end)
        power += (start_cdf-end_cdf) @ rates[span]
        accumulated += scale * ((start_integral-end_integral) @ rates[span])
    return power, accumulated


def arrival_metrics(edges, energy, groups, kernels, scale_ms):
    scale = scale_ms/1000.
    horizon = edges[-1]
    resolved = float(np.dot(energy, [kernels[i].resolved for i in groups]))
    early_times = np.linspace(0., horizon + 6*scale, 1 + int(np.ceil((horizon + 6*scale)/OBSERVATION_STEP_S)))
    late_times = horizon + np.geomspace(6., LAGS[-1], 260)[1:]*scale
    times = np.r_[early_times, late_times]
    power, accumulated = wall_response(times, edges, energy, groups, kernels, scale)
    escape_window = wall_response(np.array([horizon]), edges, energy, groups, kernels, scale)[1][0]
    if np.any(power < -1e-9) or np.any(np.diff(accumulated) < -1e-9):
        raise ArithmeticError("Nonphysical heat-flow history")
    np.testing.assert_allclose(accumulated[-1], resolved, atol=1e-9, rtol=0.)
    peak = int(np.argmax(power))
    if peak >= len(early_times)-1:
        raise ArithmeticError("Target power peaks in the sparsely sampled tail")
    percentiles = 1000.*np.interp(np.array([.1, .5, .9])*resolved, accumulated, times)
    return dict(diffusion_scale_ms=scale_ms, arrival_during_release_window=float(escape_window),
                eventual_arrived_energy_lower=resolved, eventual_arrived_energy_upper=float(energy.sum()),
                peak_target_power=float(power[peak]), peak_time_ms=float(1000.*times[peak]),
                t10_ms=float(percentiles[0]), t50_ms=float(percentiles[1]), t90_ms=float(percentiles[2]))


def sanity_check():
    theta = np.array([.125, .25, .5, 1., 2., 4.])
    left = HALF_GAP*np.array([.10, 1., .98])
    right = HALF_GAP*np.array([1.90, 1., 1.02])
    existing = first_passage(left, left+right, HALF_GAP) + first_passage(right, left+right, HALF_GAP)
    np.testing.assert_allclose(both_plate_cdf(left, right, theta), existing, atol=3e-12, rtol=0.)
    kernel = HeatKernel(np.minimum(LAGS, 1.), 1.)
    edges = np.array([0., .001, .002])
    t = np.array([0., .0005, .001, .0015, .002, .0025, .003])
    power, cumulative = wall_response(t, edges, np.array([.002, .002]), np.array([0, 0]), [kernel], .001)
    np.testing.assert_allclose(power, [0., 1., 2., 2., 2., 1., 0.], atol=2e-12, rtol=0.)
    np.testing.assert_allclose(cumulative[-1], .004, atol=1e-13, rtol=0.)


def analyze(cache, case, level):
    power, ds = ((10, .04), (12, .02))[level]
    uniforms = qmc.Sobol(4, scramble=True, seed=937).random_base2(power)
    with np.load(snapshot_path(cache, case, level)) as archive:
        time = archive["time"]
        total = archive["cumulative"]
        magnetic, exhaust = archive["magnetic"], archive["exhaust"]
    edges = time*SECONDS_PER_UNIT
    energy = np.diff(total)
    groups = np.floor(.5*(time[:-1] + time[1:])/SNAPSHOT_INTERVAL).astype(int)
    assert len(magnetic) == len(exhaust) == int(groups.max())+1
    assert np.all(energy > 0.)
    placements = {}
    for name, center in CUTS.items():
        kernels = [estimate_kernel(field, heat, uniforms, center, ds)
                   for field, heat in zip(magnetic, exhaust, strict=True)]
        placements[name] = [arrival_metrics(edges, energy, groups, kernels, scale)
                            for scale in DIFFUSION_SCALE_MS]
    print("Mapped target arrivals", case, level, flush=True)
    return dict(case=case, level=level, mesh=list(exhaust.shape[1:]), samples_per_snapshot=2**power,
                traced_step_m=ds*METERS_PER_UNIT, release_window_ms=float(edges[-1]*1000.),
                escaped_energy=float(total[-1]), targets=placements)


def match_controls(runs):
    control = {run["level"]: run for run in runs if run["case"] == "unforced"}
    for run in runs:
        for placement, series in run["targets"].items():
            for row, baseline in zip(series, control[run["level"]]["targets"][placement], strict=True):
                assert row["diffusion_scale_ms"] == baseline["diffusion_scale_ms"]
                row["peak_target_power_change_pct"] = 100.*(row["peak_target_power"]/baseline["peak_target_power"]-1.)
                row["release_window_arrival_change_pct"] = 100.*(
                    row["arrival_during_release_window"]/baseline["arrival_during_release_window"]-1.)
                row["t50_shift_ms"] = row["t50_ms"] - baseline["t50_ms"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--levels", nargs="+", type=int, choices=(0, 1), default=[0, 1])
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    sanity_check()
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        tasks = [pool.submit(analyze, args.cache, case, level) for case, level in product(CASES, args.levels)]
        runs = [task.result() for task in as_completed(tasks)]
    runs.sort(key=lambda run: (run["level"], CASES.index(run["case"])))
    match_controls(runs)
    result = dict(
        scope="Reduced pressure-release histories routed to two idealized absorbing planes",
        energy_units="Normalized model energy",
        assumed_half_gap_diffusion_time_ms=DIFFUSION_SCALE_MS, plate_half_gap_m=HALF_GAP*METERS_PER_UNIT,
        plane_midpoints_m={name: center*METERS_PER_UNIT for name, center in CUTS.items()},
        maximum_trace_length_m=MAX_LENGTH*METERS_PER_UNIT,
        release_state_snapshot_interval_ms=1000.*SNAPSHOT_INTERVAL*SECONDS_PER_UNIT, results=runs,
    )
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

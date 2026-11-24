"""Compare a translating core and a localized self-field across sheet-relative speeds."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import json
from pathlib import Path
import tempfile

import numpy as np

from analyze import PEAK, WIDTH, delta, margin, paired_width
from measure import STATIONS, sampler, verify
from run import PEAK_POINTS, integrate
from settled_pass import SECONDS_PER_UNIT, SettledPass
from source import sweep_mhd as mhd
from steered_replay import ROOT, report_frame

MAX_EXPOSURE_S = .00245
SOURCE_STRENGTH = .5 * mhd.AMPLITUDE
FRAMES = 8
MESHES = ((64, 52, 52), (80, 64, 64), (80, 64, 64))
CONFIGS = {"baseline": (False, False), "core": (True, False),
           "field": (False, True), "combined": (True, True)}
CASES = {
    "near_comoving": {"relative_speed": 10.},
    "stationary_pattern": {"sheet_speed": 0.},
    "slip_minus_500": {"relative_speed": -500.},
    "slip_minus_5000": {"relative_speed": -5000.},
    "pattern_follows_exb_fit": None,
}


def core_and_field(path, grid, time, core, field):
    _, mask, center, velocity = path.body(grid, time, core, False)
    source = None
    if field:
        x, y, z = (mhd.wrapped(coordinate - offset, length)
                   for coordinate, offset, length in zip((grid.x, grid.y, grid.z), center, mhd.LENGTH))
        envelope = SOURCE_STRENGTH * np.exp(-(x*x + y*y + z*z) / (2 * mhd.SOURCE_WIDTH**2))
        potential = np.array([-y * envelope, x * envelope, np.zeros_like(envelope)])
        source = grid.curl(grid.transform(potential))
    return source, mask, center, velocity


def simulate(spec):
    name, speeds, track, level, configuration, ramp_s = spec
    path = SettledPass(track, **speeds, max_exposure_s=MAX_EXPOSURE_S)
    shape = MESHES[level]
    grid = mhd.Grid(shape, "xpoint", "sphere")
    intervals = max(8, int(np.ceil(path.duration / (.0025 * FRAMES))))
    steps = FRAMES * intervals * (2 if level == 2 else 1)
    dt = path.duration / steps
    initial = np.array(mhd.initial_state(grid))
    core, field = CONFIGS[configuration]

    def model(gr, time, has_core, has_field):
        source, mask, center, velocity = core_and_field(path, gr, time, has_core, has_field)
        if ramp_s:
            progress = min(1., time * SECONDS_PER_UNIT / ramp_s)
            smooth = progress**2 * (3 - 2 * progress)
            if source is not None:
                source *= smooth
            if mask is not None:
                mask *= smooth
        return source, mask, center, velocity

    def inspect(gr, state, time, mode):
        current = -gr.physical(gr.curl(state[1])[2])
        sample = sampler(current)
        center, velocity = path.at(time)
        report = report_frame(current, sample, sample(PEAK_POINTS), center, velocity, time)
        if level == 2 and (time == 0. or np.isclose(time, path.duration / 2)
                           or np.isclose(time, path.duration)):
            source, _, _, _ = model(gr, time, core, field)
            total = state[1] if source is None else state[1] + source
            report["seeded_field_lines"], _ = mhd.field_line_map(
                gr, gr.physical(total), {"X": np.array([0., 0.]), "O": np.array([-np.pi, 0.])}
            )
        return report

    with np.errstate(over="raise", invalid="raise"):
        records = integrate(grid, dt, configuration, initial, 0, steps, model=model, inspect=inspect,
                            cadence=path.duration / FRAMES, core=core, field=field)
    assert len(records) == FRAMES + 1
    return dict(case=name, level=level, configuration=configuration, mesh=shape, steps=steps,
                step_s=dt * SECONDS_PER_UNIT, geometry=path.metadata, records=records)


def assess(records, comparison, floors):
    treatment, reference = comparison
    frames = []
    for index in range(FRAMES + 1):
        pairs = [(group[treatment]["records"][index], group[reference]["records"][index]) for group in records]
        for a, b in pairs:
            assert (a["t"], a["center"], a["valid_peak_points"]) == (b["t"], b["center"], b["valid_peak_points"])
        widths, stations = paired_width(pairs, "width")
        counts, integral_stations = paired_width(pairs, "integral_width")
        peaks = [float(delta(a["annulus_peak_j"], b["annulus_peak_j"])) for a, b in pairs]
        widths = [v["mean"] for v in widths]
        conservative_width = None
        if stations:
            allowance = margin(widths) if len(records) == 3 else 0.
            conservative_width = widths[-1] - allowance - max(floors)
        conservative_peak = peaks[-1] + (margin(peaks) if len(records) == 3 else 0.)
        gate = (index > 0 and stations == len(STATIONS) and conservative_width is not None
                and conservative_width > WIDTH and conservative_peak <= PEAK)
        frames.append(dict(
            time_since_entry_s=pairs[-1][0]["t"] * SECONDS_PER_UNIT, fwhm_pct=widths,
            fwhm_stations=stations, integral_width_pct=[v["mean"] for v in counts],
            integral_width_stations=integral_stations, peak_current_pct=peaks,
            adjusted_width_pct=conservative_width, adjusted_peak_pct=conservative_peak, passes_gate=gate,
            seeded_field_lines={label: record["seeded_field_lines"] for label, record in
                                zip(comparison, pairs[-1]) if "seeded_field_lines" in record},
        ))
    return frames


def compute(requests, cache, jobs):
    completed = {}
    pending = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for request in requests:
            name, _, _, level, configuration, _ = request
            key = (name, level, configuration)
            path = cache / f"{name}_{level}_{configuration}.json"
            if path.exists():
                completed[key] = json.loads(path.read_text())
            else:
                pending[pool.submit(simulate, request)] = key, path
        failures = []
        for task in as_completed(pending):
            key, path = pending[task]
            try:
                result = task.result()
            except Exception as exc:
                failures.append((key, str(exc)))
                continue
            completed[key] = result
            path.write_text(json.dumps(result, allow_nan=False) + "\n")
            print(*key, result["steps"], "steps", flush=True)
        if failures:
            raise ArithmeticError(failures)
    return completed


def sweep(args, cache):
    orbit_runs = ROOT.parent / "orbit" / "runs"
    track = json.loads((orbit_runs / "targeted_approach_replay_track.json").read_text())
    fit = json.loads((orbit_runs / "shot_flow.json").read_text())["flow_at_orbit_m_s"]
    levels = (0, 1, 2) if args.refine else (0,)
    cases = tuple(dict.fromkeys(args.cases or CASES))
    requests = [(name, CASES[name] or {"sheet_speed": fit}, track, level, cfg, args.ramp_s)
                for name, level, cfg in product(cases, levels, CONFIGS)]
    records = compute(requests, cache, args.jobs)
    benchmarks = [verify(MESHES[level]) for level in levels]
    floors = [row["max_false_width_gain_pct"] for row in benchmarks]
    comparisons = tuple((name, "baseline") for name in ("core", "field", "combined")) + (("combined", "core"),)
    output = {}
    for name in cases:
        sets = [{cfg: records[name, level, cfg] for cfg in CONFIGS} for level in levels]
        series = {}
        for a, b in comparisons:
            label = f"{a}_vs_{b}"
            series[label] = assess(sets, (a, b), floors)
            print(name, label, sum(frame["passes_gate"] for frame in series[label]),
                  "of", FRAMES, "post-entry frames pass", flush=True)
        output[name] = dict(
            geometry=sets[0]["baseline"]["geometry"],
            numerics=[{key: group["baseline"][key] for key in ("mesh", "steps", "step_s")} for group in sets],
            comparisons=series,
        )
    result = dict(
        source_track=track["case"], stage="refined" if args.refine else "single-grid screen",
        model="Periodic incompressible resistive MHD with the reference fluid at rest in the pattern frame",
        max_exposure_s=MAX_EXPOSURE_S, activation_ramp_s=args.ramp_s, field_potential_amplitude=SOURCE_STRENGTH,
        field_width_units=mhd.SOURCE_WIDTH, width_pct_gate_exclusive=WIDTH, peak_pct_gate_inclusive=PEAK,
        benchmarks=benchmarks, cases=output,
    )
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES)
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--ramp-s", type=float, default=0., help="Smooth activation time for the core and field")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache", type=Path, help="Per-run scratch output. Use a fresh path for changed inputs.")
    args = parser.parse_args()
    if not np.isfinite(args.ramp_s) or args.ramp_s < 0.:
        parser.error("--ramp-s must be a finite, nonnegative time")
    if args.cache is not None:
        cache = args.cache / f"ramp_{args.ramp_s.hex()}" if args.ramp_s else args.cache
        cache.mkdir(parents=True, exist_ok=True)
        sweep(args, cache)
    else:
        with tempfile.TemporaryDirectory(prefix="tct-slip-") as tmp:
            sweep(args, Path(tmp))


if __name__ == "__main__":
    main()

"""Resolve the field-only width and current gates throughout a local sweep."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from analyze import PEAK, WIDTH, delta
from measure import sampler, verify
from run import PEAK_POINTS, PEAK_Y, angle_grid, integrate, radii, x_grid, z_grid
from settled_pass import METERS_PER_UNIT, SECONDS_PER_UNIT, SettledPass
from slip_sweep import MAX_EXPOSURE_S, SOURCE_STRENGTH, assess, core_and_field
from source import sweep_mhd as mhd
from steered_replay import ROOT, report_frame

INTERVALS = 24
MESHES = ((64, 52, 52), (80, 64, 64), (80, 64, 64))
DIAGNOSTICS = ("legacy_annulus", "unmasked_disk")
SHEAR_HALF_WIDTH = .25
disk = radii <= .75
DISK_POINTS = np.stack(np.broadcast_arrays(
    x_grid[disk, None], PEAK_Y[None, :], z_grid[disk, None] + .17,
), axis=-1)
ANNULUS = angle_grid[disk]
np.testing.assert_array_equal(DISK_POINTS[ANNULUS], PEAK_POINTS)


@dataclass(frozen=True)
class Drive:
    scale: float = 1.
    relative_m_s: float | None = None
    rise_s: float = 0.
    fall_s: float = 0.
    coast_s: float = 0.


CASES = {
    "nominal": Drive(),
    "half_strength": Drive(scale=.5),
    "higher_strength": Drive(scale=1.5),
    "smooth_entry": Drive(rise_s=.0006125),
    "pulse_and_decay": Drive(rise_s=.00030625, fall_s=.00030625, coast_s=.0006125),
    "slower_40": Drive(relative_m_s=40.),
    "faster_130": Drive(relative_m_s=130.),
    "reverse_86": Drive(relative_m_s=-85.70024749158394),
}
SCREEN_CASES = tuple(CASES)
CASES["long_decay"] = Drive(rise_s=.00030625, fall_s=.00030625, coast_s=.00245)


def envelope(time_s, active_s, drive):
    if time_s >= active_s and drive.fall_s:
        return 0.
    progress = min(1., time_s / drive.rise_s) if drive.rise_s else 1.
    if drive.fall_s:
        progress = min(progress, max(0., (active_s - time_s) / drive.fall_s))
    return progress**2 * (3 - 2 * progress)


def guide_velocity_amplitude(shear_m_s):
    """Normalized sinusoid amplitude for a signed velocity jump across the sheet."""
    return shear_m_s * SECONDS_PER_UNIT / (2 * METERS_PER_UNIT * np.sin(2 * SHEAR_HALF_WIDTH))


def simulate(track, drive, level, applied, shear_m_s=0.):
    speeds = {"sheet_speed": 0.} if drive.relative_m_s is None else {"relative_speed": drive.relative_m_s}
    path = SettledPass(track, **speeds, max_exposure_s=MAX_EXPOSURE_S)
    active_s = path.duration * SECONDS_PER_UNIT
    cadence = path.duration / INTERVALS
    tail_frames = round(drive.coast_s / (cadence * SECONDS_PER_UNIT))
    np.testing.assert_allclose(tail_frames * cadence * SECONDS_PER_UNIT, drive.coast_s, atol=1e-12)
    velocity_amplitude = guide_velocity_amplitude(shear_m_s)
    max_step = .0025
    if velocity_amplitude:
        # Keep the step small for advection at the finest retained axial wavenumber.
        axial_wavenumber = 2 * ((MESHES[-1][2] - 1) // 3)
        max_step = min(max_step, .45 / (axial_wavenumber * abs(velocity_amplitude)))
    interval_steps = int(np.ceil(cadence / max_step)) * (2 if level == 2 else 1)
    dt = cadence / interval_steps
    shape = MESHES[level]
    grid = mhd.Grid(shape, "xpoint", "sphere")
    initial = np.array(mhd.initial_state(grid))
    if velocity_amplitude:
        flow = np.zeros((3, *shape))
        flow[2] = velocity_amplitude * np.sin(2 * grid.y)
        initial[0] = grid.transform(flow)

    def model(gr, t, core, field):
        at = min(t, path.duration)
        weight = envelope(t * SECONDS_PER_UNIT, active_s, drive) if field else 0.
        source, mask, center, velocity = core_and_field(
            path, gr, at, False, bool(weight), source_strength=SOURCE_STRENGTH * drive.scale * weight,
        )
        return source, mask, center, velocity if t <= path.duration else np.zeros(3)

    def inspect(gr, state, t, mode):
        current = -gr.physical(gr.curl(state[1])[2])
        sample = sampler(current)
        values = sample(DISK_POINTS)
        center, velocity = path.at(min(t, path.duration))
        if t > path.duration + 1e-12:
            velocity = np.zeros(3)
        profiles = {
            "legacy_annulus": report_frame(current, sample, values[ANNULUS], center, velocity, t),
            "unmasked_disk": report_frame(current, sample, values, center, velocity, t,
                                          peak_points=DISK_POINTS, guard_radius=0.),
        }
        if level == 2 and any(abs(t - k * cadence) < 1.e-10
                              for k in (0, INTERVALS // 2, INTERVALS, INTERVALS + tail_frames)):
            source, _, _, _ = model(gr, t, False, applied)
            total = state[1] if source is None else state[1] + source
            topology, _ = mhd.field_line_map(
                gr, gr.physical(total), {"X": np.array([0., 0.]), "O": np.array([-np.pi, 0.])}
            )
            for diagnostic in profiles.values():
                diagnostic["seeded_field_lines"] = topology
        return profiles

    final = (INTERVALS + tail_frames) * interval_steps
    with np.errstate(over="raise", invalid="raise"):
        rows = integrate(grid, dt, "field" if applied else "baseline", initial, 0, final,
                         model=model, inspect=inspect, cadence=cadence, core=False, field=applied)
    assert len(rows) == INTERVALS + tail_frames + 1
    return dict(mesh=shape, steps=final, step_s=dt * SECONDS_PER_UNIT, active_s=active_s,
                sample_spacing_s=cadence * SECONDS_PER_UNIT, geometry=path.metadata,
                diagnostics={key: {"records": [row[key] for row in rows]} for key in DIAGNOSTICS})


def baseline_name(drive):
    return f"baseline_{drive.relative_m_s}_{drive.coast_s}"


def shear_name(name, shear_m_s):
    return f"{name}_shear_{shear_m_s:+.17g}" if shear_m_s else name


def compute(track, names, shears, levels, cache, jobs):
    specs = {}
    for name in names:
        drive = CASES[name]
        baseline = Drive(relative_m_s=drive.relative_m_s, coast_s=drive.coast_s)
        for shear in shears:
            specs[shear_name(baseline_name(drive), shear)] = baseline, False, shear
            specs[shear_name(name, shear)] = drive, True, shear
    completed = {}
    futures = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for name, (drive, applied, shear) in specs.items():
            for index in levels:
                key = name, index
                file = cache / f"{name}_{index}.json"
                if file.exists():
                    completed[key] = json.loads(file.read_text())
                else:
                    futures[pool.submit(simulate, track, drive, index, applied, shear)] = key, file
        for future in as_completed(futures):
            key, file = futures[future]
            value = future.result()
            draft = file.with_suffix(f".{os.getpid()}.tmp")
            draft.write_text(json.dumps(value, allow_nan=False) + "\n")
            draft.replace(file)
            completed[key] = value
            print(*key, value["steps"], "steps", flush=True)
    return completed


def windows(frames):
    result = []
    current = []
    for index, frame in enumerate(frames):
        if frame["passes_gate"]:
            current.append(index)
        if current and (not frame["passes_gate"] or index == len(frames) - 1):
            selected = [frames[i] for i in current]
            enter, leave = (x["time_since_entry_s"] for x in (selected[0], selected[-1]))
            result.append(dict(first_s=enter, last_s=leave, sampled_span_s=leave-enter, count=len(current),
                               min_adjusted_width_pct=min(x["adjusted_width_pct"] for x in selected),
                               max_adjusted_peak_pct=max(x["adjusted_peak_pct"] for x in selected),
                               reaches_last_sample=current[-1] == len(frames) - 1))
            current = []
    return result


def station_summary(frame, pairs, index):
    profiles = [(pair["field"]["records"][index]["profiles"],
                 pair["baseline"]["records"][index]["profiles"]) for pair in pairs]
    fine, reference = profiles[-1]
    changes = [float(delta(a["width"], b["width"])) for j, (a, b) in enumerate(zip(fine, reference, strict=True))
               if all(pair[j]["width"] is not None for comparison in profiles for pair in comparison)]
    assert len(changes) == frame["fwhm_stations"]
    return dict(
        stations_above_width_threshold=sum(value > WIDTH for value in changes),
        median_width_change_pct=float(np.median(changes)) if changes else None,
        minimum_width_change_pct=min(changes, default=None),
        maximum_width_change_pct=max(changes, default=None),
    )


def sweep(args, cache):
    orbit = ROOT.parent / "orbit" / "runs"
    track = json.loads((orbit / "targeted_approach_replay_track.json").read_text())
    levels = (0, 1, 2) if args.refine else (0,)
    records = compute(track, args.cases, args.shear_m_s, levels, cache, args.jobs)
    benchmarks = [verify(MESHES[level]) for level in levels]
    floors = [row["max_false_width_gain_pct"] for row in benchmarks]
    result = {}
    for name, shear in ((name, shear) for name in args.cases for shear in args.shear_m_s):
        key_name = shear_name(name, shear)
        treatments = [records[key_name, level] for level in levels]
        baselines = [records[shear_name(baseline_name(CASES[name]), shear), level] for level in levels]
        reference = treatments[0]
        diagnostics = {}
        for key in DIAGNOSTICS:
            paired = [{"field": a["diagnostics"][key], "baseline": b["diagnostics"][key]}
                      for a, b in zip(treatments, baselines, strict=True)]
            frames = assess(paired, ("field", "baseline"), floors)
            for index, frame in enumerate(frames):
                frame["fine_station_widths"] = station_summary(frame, paired, index)
            diagnostics[key] = dict(frames=frames, windows=windows(frames))
            print(key_name, key, sum(f["passes_gate"] for f in frames), "/", len(frames)-1, flush=True)
        result[key_name] = dict(
            drive=asdict(CASES[name]), geometry=reference["geometry"], active_s=reference["active_s"],
            sample_spacing_s=reference["sample_spacing_s"],
            numerics=[{k: row[k] for k in ("mesh", "steps", "step_s")} for row in treatments],
            diagnostics=diagnostics,
        )
        if shear:
            result[key_name]["initial_guide_velocity_jump_m_s"] = shear
            result[key_name]["initial_velocity_jump_span_m"] = 2 * SHEAR_HALF_WIDTH * METERS_PER_UNIT
    payload = dict(
        stage="refined" if args.refine else "single-grid screen", baseline_track=track["case"],
        nominal_field_potential_coefficient=SOURCE_STRENGTH, normalized_source_width=mhd.SOURCE_WIDTH,
        width_pct_gate_exclusive=WIDTH, peak_pct_gate_inclusive=PEAK, benchmarks=benchmarks, cases=result,
    )
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=SCREEN_CASES)
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--shear-m-s", nargs="+", type=float, default=(0.,),
                        help="Signed initial guide velocity jump across 50 mm at the sheet")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache", type=Path, help="Scratch directory for this run and its refinements")
    args = parser.parse_args()
    if not np.isfinite(args.shear_m_s).all():
        parser.error("--shear-m-s must be finite")
    if args.cache is not None:
        args.cache.mkdir(parents=True, exist_ok=True)
        sweep(args, args.cache)
    else:
        with TemporaryDirectory(prefix="tct-field-") as cache:
            sweep(args, Path(cache))


if __name__ == "__main__":
    main()

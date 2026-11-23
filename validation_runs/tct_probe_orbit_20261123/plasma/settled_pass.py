"""Replay a passing trajectory in an assumed local current-sheet frame."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import product
import json

import numpy as np
from scipy.interpolate import CubicHermiteSpline
from scipy.optimize import brentq

from analyze import PEAK, WIDTH, delta, margin, paired_width
from measure import STATIONS, sampler, verify
from run import PEAK_POINTS, integrate
from source import sweep_mhd as mhd
from steered_replay import Flyby, HALF_PATCH, ROOT, report_frame

METERS_PER_UNIT = .10
SECONDS_PER_UNIT = .004078528423054922
STAND_OFF = .42
MESHES = ((64, 52, 52), (96, 80, 80), (96, 80, 80))
STATIONARY_STEPS = (240, 240, 480)
ROTATING_STEPS = (120, 120, 240)
FRAMES = 12


class SettledPass(Flyby):
    def __init__(self, track, sheet_speed):
        knots = np.array(track["history"])
        midpoint = track["center_time_s"]
        reference_radius, reference_height = track["target_RZ_m"]
        guide = np.array(track["field_R_phi_Z_T"])
        normal = np.array([guide[2], 0., -guide[0]])
        normal *= np.sign(normal[0]) / np.linalg.norm(normal)
        guide *= np.sign(guide[1]) / np.linalg.norm(guide)
        frame = np.array([np.cross(normal, guide), normal, guide])
        np.testing.assert_allclose(frame @ frame.T, np.eye(3), atol=1e-13)
        assert np.linalg.det(frame) > 0.
        times = knots[:, 0]
        toroidal_angle = CubicHermiteSpline(times, knots[:, 2], knots[:, 5] / knots[:, 1])
        relative_displacement = (
            reference_radius * (knots[:, 2] - toroidal_angle(midpoint))
            - sheet_speed * (times - midpoint)
        )
        position = np.column_stack((
            knots[:, 1] - reference_radius, relative_displacement, knots[:, 3] - reference_height,
        ))
        velocity = knots[:, 4:].copy()
        velocity[:, 1] *= reference_radius / knots[:, 1]
        velocity[:, 1] -= sheet_speed
        self.path = CubicHermiteSpline(times, position @ frame.T / METERS_PER_UNIT,
                                      velocity @ frame.T / METERS_PER_UNIT, extrapolate=False)
        center = self.path(midpoint)
        self.origin = np.array([-center[0], STAND_OFF, .17 - center[2]])
        relative_sign = np.sign(reference_radius * toroidal_angle(midpoint, 1) - sheet_speed)

        def distance(time):
            return relative_sign * (
                reference_radius * (toroidal_angle(time) - toroidal_angle(midpoint))
                - sheet_speed * (time - midpoint)
            )

        self.start = brentq(lambda time: distance(time) + HALF_PATCH * METERS_PER_UNIT,
                            times[0], midpoint, xtol=1e-14)
        self.end = brentq(lambda time: distance(time) - HALF_PATCH * METERS_PER_UNIT,
                          midpoint, times[-1], xtol=1e-14)
        self.duration = (self.end - self.start) / SECONDS_PER_UNIT
        self.metadata = dict(
            sheet_speed_m_s=sheet_speed, midpoint_relative_toroidal_speed_m_s=
            reference_radius * toroidal_angle(midpoint, 1) - sheet_speed,
            meters_per_length_unit=METERS_PER_UNIT, seconds_per_time_unit=SECONDS_PER_UNIT,
            travel_m=2 * HALF_PATCH * METERS_PER_UNIT, transit_s=self.end - self.start,
            stand_off_from_commanded_target_units=STAND_OFF, field_frame=frame.tolist(),
            physical_interval_s=[self.start, self.end],
        )

    def at(self, time):
        physical_time = self.start + time * SECONDS_PER_UNIT
        return self.origin + self.path(physical_time), SECONDS_PER_UNIT * self.path(physical_time, 1)


def run_case(spec):
    track, sheet_speed, level = spec
    path = SettledPass(track, sheet_speed)
    shape = MESHES[level]
    steps = (STATIONARY_STEPS if sheet_speed == 0. else ROTATING_STEPS)[level]
    grid = mhd.Grid(shape, "xpoint", "sphere")
    assert (steps % FRAMES) == 0
    dt = path.duration / steps
    state = np.array(mhd.initial_state(grid))
    topology_guesses = {"X": np.array([0., 0.]), "O": np.array([-np.pi, 0.])}

    def inspect(gr, current_state, time, mode):
        current = -gr.physical(gr.curl(current_state[1])[2])
        sample = sampler(current)
        center, velocity = path.at(time)
        report = report_frame(current, sample, sample(PEAK_POINTS), center, velocity, time)
        if level == len(MESHES) - 1 and (time == 0 or np.isclose(time, path.duration / 2)
                                         or np.isclose(time, path.duration)):
            total = gr.physical(current_state[1])
            topology, _ = mhd.field_line_map(gr, total, topology_guesses)
            report["seeded_field_lines"] = topology
        return report

    with np.errstate(over="raise", invalid="raise"):
        pairs = {name: integrate(grid, dt, name, state.copy(), 0, steps, model=path.body,
                                 inspect=inspect, cadence=path.duration / FRAMES)
                 for name in ("baseline", "core")}
    assert len(pairs["core"]) == len(pairs["baseline"]) == FRAMES + 1
    print(f"Sheet speed {sheet_speed:.2f} m/s, mesh {shape}, {steps} steps", flush=True)
    return dict(level=level, shape=shape, steps=steps, seconds_per_step=dt * SECONDS_PER_UNIT,
                benchmark=verify(shape), geometry=path.metadata, **pairs)


def compare(runs):
    width_floor = max(run["benchmark"]["max_false_width_gain_pct"] for run in runs)
    frames = []
    for i in range(FRAMES + 1):
        pairs = [(run["core"][i], run["baseline"][i]) for run in runs]
        for a, b in pairs:
            assert a["t"] == b["t"] and a["center"] == b["center"]
            assert a["valid_peak_points"] == b["valid_peak_points"]
        widths, stations = paired_width(pairs, "width")
        integral_widths, integral_stations = paired_width(pairs, "integral_width")
        peak = [float(delta(a["annulus_peak_j"], b["annulus_peak_j"])) for a, b in pairs]
        width = [value["mean"] for value in widths]
        conservative_width = width[-1] - margin(width) - width_floor if stations else None
        conservative_peak = peak[-1] + margin(peak)
        gate = (stations == len(STATIONS) and conservative_width is not None
                and conservative_width > WIDTH and conservative_peak <= PEAK)
        a, b = pairs[-1]
        frames.append(dict(
            time_since_entry_s=a["t"] * SECONDS_PER_UNIT, fwhm_pct=width, fwhm_stations=stations,
            integral_width_pct=[value["mean"] for value in integral_widths],
            integral_width_stations=integral_stations, peak_current_pct=peak,
            adjusted_width_pct=conservative_width, adjusted_peak_pct=conservative_peak, passes_gate=gate,
            seeded_field_lines={kind: r["seeded_field_lines"] for kind, r in zip(("core", "baseline"), (a, b))
                                if "seeded_field_lines" in r},
        ))
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=("installed", "supplemental", "replay"))
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    orbit_runs = ROOT.parent / "orbit" / "runs"
    track = json.loads((orbit_runs / f"targeted_approach_{args.group}_track.json").read_text())
    fit_speed = json.loads((orbit_runs / "shot_flow.json").read_text())["flow_at_orbit_m_s"]
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        work = ((track, sheet_speed, level) for sheet_speed, level in product(
            (0., fit_speed), range(len(MESHES))
        ))
        records = list(pool.map(run_case, work))

    cases = {}
    for label, speed in (("stationary_pattern", 0.), ("pattern_follows_toroidal_ExB_fit", fit_speed)):
        runs = [run for run in records if run["geometry"]["sheet_speed_m_s"] == speed]
        frames = compare(runs)
        geometry = runs[0]["geometry"]
        cases[label] = dict(geometry=geometry, numerics=[
            {key: run[key] for key in ("shape", "steps", "seconds_per_step", "benchmark")} for run in runs
        ], frames=frames)
        print(label, geometry["transit_s"], "s,", sum(frame["passes_gate"] for frame in frames),
              "/", len(frames), "pass", flush=True)

    receipt = dict(
        trajectory_case=track["case"], trajectory_field_grid=track["field_grid"],
        width_pct_gate_exclusive=WIDTH, peak_pct_gate_inclusive=PEAK,
        core_model="Translating spherical momentum-penalty mask without self-field",
        sheet_model="Periodic local resistive MHD with assumed stand-off, transport and units",
        topology_scope="Continuation of the seeded one-turn X and O lines at entry, midpoint and exit",
        cases=cases,
    )
    (ROOT / "runs" / f"settled_pass_{args.group}.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()

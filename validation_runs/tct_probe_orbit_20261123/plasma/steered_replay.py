"""Replay an unwrapped, field-oriented segment of the steered DIII-D orbit."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicHermiteSpline

from measure import GUARD_RADIUS, STATIONS, read_sheet, sampler, verify
from run import CADENCE, END, LEVELS, PEAK_POINTS, PEAK_Y, integrate, prescribed_body
from source import sweep_mhd as mhd

ROOT = Path(__file__).resolve().parent
REPLAY_LEVELS = {**LEVELS, "fine_quarter_step": (LEVELS["fine_mesh"][0], .0015625)}
CASE_CONFIGS = {
    "forward_near": ("forward", .42, .10),
    "reverse_near": ("reverse", .42, .10),
    "forward_far": ("forward", .55, .10),
    "forward_large_scale": ("forward", .42, .20),
}
HALF_PATCH = 1.05


class Flyby:
    def __init__(self, history, metadata, radius, stand_off, length_scale):
        self.length_scale = length_scale
        self.stand_off = stand_off
        reference = metadata["refined_case"]
        self.kick_time = reference["kick_time_s"]
        kick_index = int(np.argmin(abs(history[:, 0] - self.kick_time)))
        assert abs(history[kick_index, 0] - self.kick_time) < 1e-10
        guide = np.array(metadata["reference_field_R_phi_Z_T"])
        normal = np.array([guide[2], 0., -guide[0]])
        normal *= np.sign(normal[0]) / np.linalg.norm(normal)
        guide *= np.sign(guide[1]) / np.linalg.norm(guide)
        frame = np.array([np.cross(normal, guide), normal, guide])
        np.testing.assert_allclose(frame @ frame.T, np.eye(3), atol=1e-13)
        assert np.linalg.det(frame) > 0.
        position = history[:, 1:4].copy()
        position[:, 0] -= radius
        position[:, 1] = radius * (position[:, 1] - position[kick_index, 1])
        position[:, 2] -= reference["reference_height_m"]
        velocity = history[:, 4:7].copy() * np.sqrt(reference["kappa_Am2_kg"])
        velocity[:, 1] *= radius / history[:, 1]
        self.time_scale = HALF_PATCH * length_scale / (abs(velocity[kick_index, 1]) * END / 2)
        self.origin = np.array([0., stand_off, .17])
        local_position = position @ frame.T / length_scale
        for axis in (0, 2):
            self.origin[axis] -= local_position[kick_index, axis]
        local_velocity = velocity @ frame.T / length_scale
        times = history[:, 0]
        left_velocity = local_velocity[:kick_index + 1].copy()
        kick = np.array(metadata["archived_case"]["kick_m_s"])
        assert kick[1] == 0
        left_velocity[-1] -= frame @ kick / length_scale
        left = slice(None, kick_index + 1)
        right = slice(kick_index, None)
        self.branches = [
            CubicHermiteSpline(times[left], local_position[left], left_velocity, extrapolate=False),
            CubicHermiteSpline(times[right], local_position[right], local_velocity[right], extrapolate=False),
        ]
        endpoints = self.kick_time + self.time_scale * np.array([-END / 2, END / 2])
        assert times[0] < endpoints[0] < self.kick_time < endpoints[1] < times[-1]
        self.metadata = dict(
            physical_interval_s=endpoints.tolist(), meters_per_length_unit=length_scale,
            seconds_per_time_unit=self.time_scale, assumed_normal_stand_off=stand_off, frame=frame.tolist(),
            kick_normalized_time=END / 2, phase_deg=reference["phase_deg"], direction=reference["direction"],
        )

    def at(self, time):
        physical_time = self.kick_time + (time - END / 2) * self.time_scale
        branch = self.branches[time >= END / 2]
        return self.origin + branch(physical_time), self.time_scale * branch(physical_time, 1)

    def body(self, grid, time, core, field):
        center, velocity = self.at(time)
        if not core:
            return None, None, center, velocity
        displacement = [
            mhd.wrapped(coordinate - offset, length) / axis
            for coordinate, offset, length, axis in zip(
                (grid.x, grid.y, grid.z), center, mhd.LENGTH, grid.axes, strict=True
            )
        ]
        radial = np.sqrt(sum(delta**2 for delta in displacement))
        width = mhd.MASK_HALF_WIDTH
        weight = np.clip((1 + width - radial) / (2 * width), 0, 1)
        return None, weight**2 * (3 - 2 * weight), center, velocity


def load_flybys():
    input_path = ROOT / "input"
    metadata = json.loads((input_path / "orbit_tracks.json").read_text())
    with np.load(input_path / "orbit_tracks.npz") as arrays:
        return {
            case: Flyby(arrays[direction], metadata["cases"][direction], metadata["radius_m"], stand_off, scale)
            for case, (direction, stand_off, scale) in CASE_CONFIGS.items()
        }


def report_frame(current, sample, peak_values, center, velocity, time):
    distance = mhd.wrapped(PEAK_POINTS - center, mhd.LENGTH)
    valid = np.einsum("...i,...i->...", distance, distance) >= GUARD_RADIUS**2
    ix, iy = np.unravel_index(int(np.argmax(np.where(valid, peak_values, -np.inf))), peak_values.shape)
    assert valid[ix, iy]
    position = PEAK_POINTS[ix, iy].copy()
    peak = float(peak_values[ix, iy])
    if 0 < iy < len(PEAK_Y) - 1 and valid[ix, iy - 1:iy + 2].all():
        left, _, right = peak_values[ix, iy - 1:iy + 2]
        curvature = left - 2 * peak + right
        if curvature < 0:
            fraction = np.clip((left - right) / (2 * curvature), -.5, .5)
            candidate = position.copy()
            candidate[1] += fraction * (PEAK_Y[1] - PEAK_Y[0])
            if np.linalg.norm(mhd.wrapped(candidate - center, mhd.LENGTH)) >= GUARD_RADIUS:
                position = candidate
                peak += float(.5 * (right - left) * fraction + .5 * curvature * fraction**2)
    return dict(
        t=time, center=center.tolist(), velocity=velocity.tolist(), annulus_peak_j=peak,
        annulus_peak_xyz=position.tolist(), valid_peak_points=int(valid.sum()),
        profiles=read_sheet(current, center, sample=sample),
    )


def evaluate(level, case):
    shape, dt = REPLAY_LEVELS[level]
    grid = mhd.Grid(shape, "xpoint", "sphere")
    verification = verify(shape)
    state = np.array(mhd.initial_state(grid))
    last = round(END / dt)
    flybys = {} if case == "hold" else load_flybys()

    def hold_body(gr, time, core, field):
        src, mask, center, speed = prescribed_body(gr, time, "hold")
        return src, mask, center, np.array([0., speed, 0.])

    def inspect(gr, current_state, time, mode):
        current = -gr.physical(gr.curl(current_state[1])[2])
        sample = sampler(current)
        values = sample(PEAK_POINTS)
        geometries = {name: flyby.at(time) for name, flyby in flybys.items() if mode in (name, "baseline")}
        if mode == "hold":
            _, _, center, velocity = hold_body(gr, time, True, False)
            geometries["hold"] = center, velocity
        return {name: report_frame(current, sample, values, center, velocity, time)
                for name, (center, velocity) in geometries.items()}

    model = hold_body if case == "hold" else flybys[case].body if case in flybys else None
    with np.errstate(over="raise", invalid="raise"):
        frames = integrate(grid, dt, case, state, 0, last, model=model, inspect=inspect)
    assert len(frames) == round(END / CADENCE) + 1
    output = ROOT / "runs"
    output.mkdir(exist_ok=True)
    for name in frames[0]:
        result = dict(case=case, mesh=shape, dt=dt, stations=STATIONS.tolist(),
                      diagnostic_benchmark=verification, geometry=flybys[name].metadata if name in flybys else None,
                      records=[frame[name] for frame in frames])
        (output / f"{level}_{case}_{name}.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(level, case, name, len(frames), "frames", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", choices=REPLAY_LEVELS)
    parser.add_argument("case", choices=("baseline", "hold", *CASE_CONFIGS))
    args = parser.parse_args()
    evaluate(args.level, args.case)

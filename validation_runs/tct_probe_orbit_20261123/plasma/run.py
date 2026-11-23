"""Test the core effect with and without motion, followed by a stop-and-hold branch."""
import argparse
import json
from pathlib import Path

import numpy as np

from measure import GUARD_RADIUS, STATIONS, read_sheet, sampler, verify
from source import sweep_mhd as mhd

ROOT = Path(__file__).resolve().parent
END = 0.60
CADENCE = 0.0125
BRAKE_START = 0.25
BRAKE_END = 0.35
LEVELS = {
    "archive_mesh": ((64, 52, 52), 0.00625),
    "fine_mesh": ((96, 80, 80), 0.00625),
    "fine_half_step": ((96, 80, 80), 0.003125),
}

x = np.linspace(-0.75, 0.75, 49)
x_grid, z_grid = np.meshgrid(x, x, indexing="ij")
radii = np.hypot(x_grid, z_grid)
angle_grid = (radii >= 0.32) & (radii <= 0.75)
PEAK_Y = np.linspace(-0.4, 0.4, 161)
assert radii[angle_grid].min() > GUARD_RADIUS
PEAK_POINTS = np.stack(np.broadcast_arrays(
    x_grid[angle_grid, None], PEAK_Y[None], z_grid[angle_grid, None] + 0.17
), axis=-1)


def prescribed_body(grid, t, mode):
    _, _, original_center, original_speed = mhd.probe(grid, t, False, False)
    if mode == "baseline":
        return None, None, original_center, original_speed
    if mode == "moving" or (mode == "hold" and t <= BRAKE_START):
        return mhd.probe(grid, t, True, False)
    if mode == "fixed":
        return mhd.probe(grid, 0.0, True, False)
    if mode == "fixed_near":
        return prescribed_body(grid, BRAKE_END, "hold")

    _, _, start, initial_velocity = mhd.probe(grid, BRAKE_START, False, False)
    q = BRAKE_START/mhd.END
    initial_acceleration = -0.80/mhd.END**2 * 60*q*(1-q)*(1-2*q)
    duration = BRAKE_END - BRAKE_START
    u = min((t - BRAKE_START) / duration, 1.)
    speed = initial_velocity*(2*u**3-3*u*u+1) + duration*initial_acceleration*(u**3-2*u*u+u)
    center = start.copy()
    center[1] += duration * (
        initial_velocity*(0.5*u**4-u**3+u)
        + duration*initial_acceleration*(0.25*u**4-(2/3)*u**3+0.5*u*u)
    )
    x, y, z = (mhd.wrapped(coord - offset, length) for coord, offset, length
               in zip((grid.x, grid.y, grid.z), center, mhd.LENGTH, strict=True))
    normalized_radius = np.sqrt((x/grid.axes[0])**2 + (y/grid.axes[1])**2 + (z/grid.axes[2])**2)
    h = mhd.MASK_HALF_WIDTH
    weight = np.clip((1+h-normalized_radius)/(2*h), 0, 1)
    return None, weight**2*(3-2*weight), center, speed


def observe(grid, state, t, mode):
    _, _, center, speed = prescribed_body(grid, t, mode)
    jz = -grid.physical(grid.curl(state[1])[2])
    sample = sampler(jz)
    # This annular peak remains available if the FWHM geometry becomes ambiguous.
    peak_values = sample(PEAK_POINTS)
    ix, iy = np.unravel_index(int(np.argmax(peak_values)), peak_values.shape)
    position = PEAK_POINTS[ix, iy]
    peak = float(peak_values[ix, iy])
    if 0 < iy < len(PEAK_Y)-1:
        left, _, right = peak_values[ix, iy-1:iy+2]
        curvature = left-2*peak+right
        if curvature < 0:
            fraction = np.clip((left-right)/(2*curvature), -0.5, 0.5)
            position = position.copy()
            position[1] += fraction*(PEAK_Y[1]-PEAK_Y[0])
            peak += float(0.5*(right-left)*fraction + 0.5*curvature*fraction*fraction)
    return dict(
        t=t, center=center.tolist(), velocity=speed, annulus_peak_j=peak,
        annulus_peak_xyz=position.tolist(), profiles=read_sheet(jz, center, sample=sample),
    )


def integrate(grid, dt, mode, state, start, end, *, include_start=True, model=None, inspect=None):
    def probe_model(current_grid, t, core, field):
        return prescribed_body(current_grid, t, mode)

    if model is not None:
        probe_model = model
    if inspect is None:
        inspect = observe
    steps_per_output = round(CADENCE/dt)
    records = []
    for step in range(start, end+1):
        t = step * dt
        if step % steps_per_output == 0 and (include_start or step != start):
            records.append(inspect(grid, state, t, mode))
        if step < end:
            k1 = mhd.rhs(grid, state, t, mode != "baseline", False, mhd.PENALTY_TIME, probe_model)
            midpoint = state + 0.5*dt*k1
            state += dt*mhd.rhs(grid, midpoint, t+0.5*dt, mode != "baseline",
                                False, mhd.PENALTY_TIME, probe_model)
    if not np.isfinite(state).all():
        raise ArithmeticError("Nonfinite MHD state")
    divergence = max(float(np.max(np.abs(grid.physical(
        1j * sum(k*f for k, f in zip(grid.k, field))
    )))) for field in state)
    if divergence > 1e-9:
        raise ArithmeticError(f"End state divergence {divergence}")
    return records


def run(level, group):
    shape, dt = LEVELS[level]
    grid = mhd.Grid(shape, "xpoint", "sphere")
    verification = verify(shape)
    state = np.array(mhd.initial_state(grid))
    last = round(END/dt)
    records = {}
    if group == "motion":
        join = round(BRAKE_START/dt)
        shared = integrate(grid, dt, "moving", state, 0, join)
        for mode in ("moving", "hold"):
            records[mode] = shared + integrate(grid, dt, mode, state.copy(), join, last,
                                               include_start=False)
    else:
        records[group] = integrate(grid, dt, group, state, 0, last)

    for case, trace in records.items():
        assert len(trace) == round(END / CADENCE)+1
        result = dict(case=case, mesh=shape, dt=dt, stations=STATIONS.tolist(),
                      diagnostic_benchmark=verification, records=trace)
        (ROOT / "runs" / f"{level}_{case}.json").write_text(
            json.dumps(result, indent=2, allow_nan=False) + "\n"
        )
        print(f"{level}/{case}: {len(trace)} frames", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("level", choices=LEVELS)
    p.add_argument("group", choices=("baseline", "fixed", "fixed_near", "motion"))
    args = p.parse_args()
    (ROOT/"runs").mkdir(exist_ok=True)
    run(args.level, args.group)

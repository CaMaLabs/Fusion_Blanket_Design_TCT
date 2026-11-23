"""Track the inward approach with bounded control allocation and test a virtual actuator."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import product
import json
from multiprocessing import get_context

import numpy as np
from scipy.optimize import lsq_linear

from fields import FieldMap, RADIUS, ROOT
from orbit import trajectory
from reachable_approach import DISTANCE, START, measure_tracking, reference_path

MODEL = None
CASE = None
CUTOFF_HZ = 100
DURATIONS = (.05, .10, .20)
PHASES = (0, 90, 180, 270)
STEP_COUNTS = (576, 1152)
PROFILES = {
    "balanced": ((1., 1., 1.), .8, .35, .65),
    "normal_priority": ((4., 1., 2.), 1.8, .65, .85),
    "toroidal_priority": ((2., 4., 2.), 1.8, .65, .85),
}
DEFAULT_PROFILE = "toroidal_priority"
SUPPLEMENTAL_CAPACITIES = (.00010, .00020, .00025, .00030, .00040)
REPLAY_FIELD_GRID = (144, 15, 48)


class BoundedControl:
    def __init__(self, profile):
        weights, stiffness, damping, momentum_gain = PROFILES[profile]
        self.weights = np.array(weights)
        self.stiffness = stiffness
        self.damping = damping
        self.momentum_gain = momentum_gain

    def __call__(self, local, state, reference, gravity, drag, limit):
        radius, _, height, vr, vt, vz = state
        position, velocity, acceleration, momentum, momentum_rate = reference
        transverse = (
            acceleration - self.stiffness * (np.array([radius, height]) - position)
            - self.damping * (np.array([vr, vz]) - velocity)
        )
        desired = np.array([
            transverse[0] - vt**2 / radius,
            momentum_rate / radius + self.momentum_gain * (momentum / radius - vt) + drag,
            transverse[1] + gravity,
        ])
        base, response = local
        enabled = limit > 0
        coefficients = response[:, enabled] * limit[enabled] * self.weights[:, None]
        target = (desired - base) * self.weights
        regularization = 5e-6
        fraction = coefficients.T @ np.linalg.solve(
            coefficients @ coefficients.T + regularization**2 * np.eye(3), target
        )
        if np.any(abs(fraction) > 1.):
            penalty = regularization * np.eye(len(fraction))
            result = lsq_linear(np.vstack((coefficients, penalty)),
                                np.concatenate((target, np.zeros(len(fraction)))),
                                bounds=(-1., 1.), method="bvls", tol=1e-10, max_iter=64)
            if not result.success:
                raise ArithmeticError(result.message)
            fraction = result.x
        current = np.zeros_like(limit)
        current[enabled] = limit[enabled] * fraction
        return current


def simulate(spec):
    profile, load, capacity, duration, direction, phase, steps = spec
    at, center, normal = reference_path(MODEL, CASE, duration, direction)
    drag = load * CASE["drag_at_nominal_speed_T_m"]
    row, trace = trajectory(
        MODEL, CASE["mode"], CASE["kappa_Am2_kg"], True, phase, (0., 0., 1.), CUTOFF_HZ,
        steps_per_lap=steps, traces=True, balanced_height=center[1], direction=direction,
        drag_per_moment=drag, compensate_drag=True, reference_at=at, control_policy=BoundedControl(profile),
        supplemental_toroidal_gradient=capacity,
    )
    measure_tracking(row, trace, at, center, normal, duration)
    row.update(profile=profile, drag_fraction=load, drag_at_nominal_speed_T_m=drag,
               supplemental_capacity_T_m=capacity)
    return row, trace


def case_specs(group, profile):
    if group == "screen":
        return product(PROFILES, (0., .5, 1.), (0.,), (.20,), (1, -1), (0, 180), (576,))
    if group == "installed":
        return product((profile,), (0., .5, 1.), (0.,), DURATIONS, (1, -1), PHASES, STEP_COUNTS)
    if group == "replay":
        return product((profile,), (.5,), (0.,), (.2,), (1,), PHASES, (1152,))
    return product((profile,), (1.,), SUPPLEMENTAL_CAPACITIES, (.20,), (1, -1), PHASES, STEP_COUNTS)


def groups(rows):
    keys = ("profile", "drag_fraction", "supplemental_capacity_T_m", "duration_s", "steps_per_lap")
    for parameters in sorted({tuple(row[key] for key in keys) for row in rows}):
        runs = [row for row in rows if tuple(row[key] for key in keys) == parameters]
        errors = [row["settled_error_m"] for row in runs if row["settled_error_m"] is not None]
        speeds = [row["settled_speed_m_s"] for row in runs if row["settled_speed_m_s"] is not None]
        yield dict(zip(keys, parameters), cases=len(runs),
                   tracking_passes=sum(row["tracking_pass"] for row in runs),
                   completed_laps=sum(row["outcome"] == "completed" for row in runs),
                   worst_settled_error_m=max(errors, default=None),
                   worst_settled_speed_m_s=max(speeds, default=None),
                   min_corridor_margin_m=min(row["corridor_margin_m"] for row in runs))


def save_track(records, group, path, field_grid):
    winners = [(row, trace) for row, trace in records if row["tracking_pass"]
               and row["steps_per_lap"] == 1152 and row["duration_s"] == .2 and row["direction"] == 1]
    if not winners:
        return
    row, trace = min(winners, key=lambda item: (
        item[0]["supplemental_capacity_T_m"], -item[0]["drag_fraction"], item[0]["settled_error_m"]
    ))
    center_time = START + row["duration_s"] + .11
    history = trace[abs(trace[:, 0] - center_time) <= .012].copy()
    assert history[0, 0] < center_time < history[-1, 0]
    history[:, 4:] *= np.sqrt(row["kappa_Am2_kg"])
    _, center, normal = reference_path(MODEL, CASE, row["duration_s"], 1)
    target = center - DISTANCE * normal
    payload = dict(source_group=group, field_grid=field_grid, case=row, center_time_s=center_time, radius_m=RADIUS,
                   target_RZ_m=target.tolist(), field_R_phi_Z_T=MODEL.field(*target).tolist(),
                   columns=["time_s", "R_m", "phi_rad", "Z_m", "v_R_m_s", "v_phi_m_s", "v_Z_m_s"],
                   history=history.tolist())
    (path / f"targeted_approach_{group}_track.json").write_text(json.dumps(payload, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=("screen", "installed", "supplemental", "replay"))
    parser.add_argument("--profile", choices=PROFILES, default=DEFAULT_PROFILE)
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    global MODEL, CASE
    source = json.loads((ROOT / "runs/reachable_approach.json").read_text())
    archival = json.loads((ROOT / "runs/weight_shape_fine_compound_speed_scaled_drag_momentum.json").read_text())
    CASE = source["input_case"]
    field_grid = REPLAY_FIELD_GRID if args.group == "replay" else archival["field_grid"]
    MODEL = FieldMap(*field_grid)
    print(f"Running {args.group} trajectory sweep", flush=True)
    with ProcessPoolExecutor(max_workers=args.jobs, mp_context=get_context("fork")) as pool:
        records = list(pool.map(simulate, case_specs(args.group, args.profile)))
    rows = [row for row, _ in records]
    summary = list(groups(rows))
    for row in summary:
        print(row, flush=True)
    payload = dict(input_case=CASE, field_grid=field_grid, cutoff_hz=CUTOFF_HZ,
                   start_s=START, displacement_m=DISTANCE, max_settled_error_m=.0005,
                   max_settled_speed_m_s=.02, summaries=summary, trajectories=rows)
    path = ROOT / "runs"
    label = args.group
    if args.group != "screen" and args.profile != DEFAULT_PROFILE:
        label = f"{label}_{args.profile}"
    (path / f"targeted_approach_{label}.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    if args.group != "screen":
        save_track(records, label, path, field_grid)


if __name__ == "__main__":
    main()

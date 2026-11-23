"""Screen coil-limited motion toward the flux surface while maintaining the orbit."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import product
import json
from multiprocessing import get_context

import numpy as np

from fields import FieldMap, HALF_WIDTH, RADIUS, ROOT
from orbit import trajectory
from weight_shape import CONTROLLERS

DISTANCE = .002083984375
START = .04
MODEL = None
INPUT = None


def reference_path(duration, direction):
    kappa = INPUT["kappa_Am2_kg"]
    center = np.array([RADIUS, INPUT["reference_height_m"]])
    field = MODEL.field(*center)
    normal = np.array([field[2], -field[0]])
    normal *= np.sign(normal[0]) / np.linalg.norm(normal)
    shift = -DISTANCE * normal

    def momentum(position):
        radius, height = position
        circular_speed = np.sqrt(-radius * MODEL.ambient(radius, height)[1][0])
        return direction * radius * circular_speed

    initial_momentum = momentum(center)
    momentum_change = momentum(center + shift) - initial_momentum
    root_kappa = np.sqrt(kappa)

    def at(time):
        s = np.clip((time - START) / duration, 0., 1.)
        progress = s**3 * (10 + s * (-15 + 6 * s))
        speed = 30 * s**2 * (1 - s)**2 / duration
        acceleration = 60 * s * (1 - s) * (1 - 2 * s) / duration**2
        return (center + shift * progress, shift * speed / root_kappa,
                shift * acceleration / kappa, initial_momentum + momentum_change * progress,
                momentum_change * speed / root_kappa)

    return at, center, normal


def simulate(spec):
    treatment, duration, direction, phase, steps = spec
    at, center, normal = reference_path(duration, direction)
    drag = 0. if treatment == "no_drag" else INPUT["drag_at_nominal_speed_T_m"]
    row, trace = trajectory(
        MODEL, INPUT["mode"], INPUT["kappa_Am2_kg"], True, phase, (0., 0., 1.), 100,
        steps_per_lap=steps, traces=True, balanced_height=center[1], direction=direction,
        drag_per_moment=drag, compensate_drag=treatment == "drag_feedforward",
        guide_weights=CONTROLLERS["momentum"],
        hold_angular_momentum=True, reference_at=at,
    )
    time = trace[:, 0]
    position = (trace[:, [1, 3]] - center) @ normal
    speed = (trace[:, [4, 6]] @ normal) * np.sqrt(INPUT["kappa_Am2_kg"])
    target = np.array([(at(t)[0] - center) @ normal for t in time])
    settled = time >= START + duration + .05
    error = abs(position - target)
    settled_error = float(error[settled].max()) if settled.any() else None
    settled_speed = float(abs(speed[settled]).max()) if settled.any() else None
    passed = (row["outcome"] == "completed" and settled_error is not None
              and settled_error <= .0005 and settled_speed <= .02)
    row.update(treatment=treatment, drag_at_nominal_speed_T_m=drag,
               duration_s=duration, tracking_pass=passed, settled_error_m=settled_error,
               settled_speed_m_s=settled_speed, final_normal_displacement_m=float(position[-1]),
               worst_normal_error_m=float(error.max()),
               corridor_margin_m=HALF_WIDTH-max(row["radial_peak_m"], row["vertical_peak_m"]))
    return row, trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", action="store_true")
    args = parser.parse_args()
    global MODEL, INPUT
    archival = json.loads((ROOT / "runs/weight_shape_fine_compound_speed_scaled_drag_momentum.json").read_text())
    INPUT = next(row for row in archival["trajectories"] if row["load"] == "same_area")
    MODEL = FieldMap(*archival["field_grid"])
    treatments = ("no_drag", "drag_feedforward") if args.comparison else ("drag_feedback",)
    cases = product(treatments, (.05, .10, .20), (1, -1), (0, 90, 180, 270), (576, 1152))
    with ProcessPoolExecutor(max_workers=6, mp_context=get_context("fork")) as pool:
        records = list(pool.map(simulate, cases))
    rows = [row for row, _ in records]
    for treatment, duration, steps in product(treatments, (.05, .10, .20), (576, 1152)):
        subset = [row for row in rows if (row["treatment"], row["duration_s"], row["steps_per_lap"])
                  == (treatment, duration, steps)]
        assert len(subset) == 8
        print(treatment, duration, steps, sum(row["tracking_pass"] for row in subset), "/8",
              "worst clearance mm", 1000 * min(row["corridor_margin_m"] for row in subset), flush=True)
    payload = dict(input_case=INPUT, start_s=START, displacement_m=DISTANCE,
                   max_settled_error_m=.0005, max_settled_speed_m_s=.02, trajectories=rows)
    stem = "reachable_approach_comparison" if args.comparison else "reachable_approach"
    (ROOT / "runs" / f"{stem}.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    winners = {
        f"{row['treatment']}_{row['duration_s']:g}_{row['direction']}_{row['phase_deg']:g}": trace
        for row, trace in records if row["tracking_pass"] and row["steps_per_lap"] == 1152
    }
    np.savez_compressed(ROOT / "runs" / f"{stem}_tracks.npz", **winners)


if __name__ == "__main__":
    main()

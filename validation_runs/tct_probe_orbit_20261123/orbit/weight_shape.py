"""Test lower mass and an illustrative shape-related drag reduction."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import itertools
import json
from multiprocessing import get_context

import numpy as np

from coupled_recovery import FAST_HIGH, KICK, NOMINAL, SLOW_LOW
from fields import FieldMap, HALF_WIDTH, RADIUS, ROOT
from orbit import TOROIDAL_WEIGHT, trajectory
from run import shifted_height


LOADS = {"bare": (0., 0.), "loaded": (.05, .0002), "lower_drag": (.05, .000192)}
SPEED_SCALED_LOADS = {"same_area": (.05, .0002), "smaller_area": (.05, .0002)}
ERRORS = {"fast_high": (FAST_HIGH, None), "slow_low": (SLOW_LOW, None), "kick": (NOMINAL, KICK)}
COMPOUND_ERRORS = {"fast_high_kick": (FAST_HIGH, KICK), "slow_low_kick": (SLOW_LOW, KICK)}
CONTROLLERS = {
    "original": TOROIDAL_WEIGHT,
    "height_priority": np.array([1., .35, 4.]),
    "momentum": np.array([.04, .30, 4.]),
}
MODEL = None


def orbit_height(kappa):
    trim = shifted_height(MODEL, kappa)
    cap = MODEL.height + HALF_WIDTH - .001
    return cap if trim is None else min(trim, cap)


def simulate(spec):
    controller, bare_kappa, load, error, direction, phase, steps = spec
    added_mass, drag = (LOADS | SPEED_SCALED_LOADS)[load]
    launch, kick = (ERRORS | COMPOUND_ERRORS)[error]
    kappa = bare_kappa / (1 + added_mass)
    target_height = orbit_height(kappa)
    if load in SPEED_SCALED_LOADS:
        reference_kappa = 2500 / (1 + added_mass)
        reference_gradient = MODEL.ambient(RADIUS, orbit_height(reference_kappa))[1][0]
        gradient = MODEL.ambient(RADIUS, target_height)[1][0]
        drag *= kappa * gradient / (reference_kappa * reference_gradient)
        if load == "smaller_area":
            drag *= (2500 / bare_kappa) ** (2 / 3)
    row, _ = trajectory(
        MODEL, "guided_1.6kA_I", kappa, True, phase, launch, 100,
        balanced_height=target_height, steps_per_lap=steps, direction=direction,
        drag_per_moment=drag, kick_at_lap_one_m_s=kick, guide_weights=CONTROLLERS[controller],
        hold_angular_momentum=controller == "momentum",
    )
    row.update(bare_kappa_Am2_kg=bare_kappa, load=load, error=error, added_mass_fraction=added_mass,
               drag_at_nominal_speed_T_m=drag, kick_m_s=kick, controller=controller,
               corridor_margin_m=HALF_WIDTH - max(row["radial_peak_m"], row["vertical_peak_m"]))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compound", action="store_true", help="apply a kick after a perturbed launch")
    parser.add_argument("--speed-scaled-drag", action="store_true", help="scale loaded drag with nominal speed")
    parser.add_argument("--fine", action="store_true")
    parser.add_argument("--controller", choices=CONTROLLERS, action="append")
    parser.add_argument("ratios", metavar="KAPPA", type=int, nargs="+")
    args = parser.parse_args()
    if min(args.ratios) <= 0:
        parser.error("moment-to-mass ratios must be positive")
    field_sizes = (216, 19, 64) if args.fine else (144, 15, 48)
    phases = (0, 90, 180, 270) if args.fine else (0, 90)
    steps = 576 if args.fine else 288
    global MODEL
    MODEL = FieldMap(*field_sizes)
    controllers = args.controller or ["original"]
    errors = COMPOUND_ERRORS if args.compound else ERRORS
    loads = SPEED_SCALED_LOADS if args.speed_scaled_drag else LOADS
    cases = itertools.product(controllers, args.ratios, loads, errors, (1, -1), phases, (steps,))
    rows = []
    with ProcessPoolExecutor(max_workers=6, mp_context=get_context("fork")) as pool:
        for (policy, ratio), group in itertools.groupby(
            pool.map(simulate, cases), key=lambda row: (row["controller"], row["bare_kappa_Am2_kg"])
        ):
            for (load, error), trials in itertools.groupby(group, key=lambda row: (row["load"], row["error"])):
                trials = list(trials)
                rows.extend(trials)
                count = sum(row["outcome"] == "completed" for row in trials)
                margin_mm = 1000 * min(row["corridor_margin_m"] for row in trials)
                print(policy, ratio, load, error,
                      f"{count}/{len(trials)} passed, worst margin {margin_mm:+.3f} mm", flush=True)
    tag = "fine" if args.fine else "screen"
    if args.compound:
        tag += "_compound"
    if args.speed_scaled_drag:
        tag += "_speed_scaled_drag"
    result = dict(field_grid=field_sizes, original_height_m=MODEL.height, trajectories=rows)
    if controllers != ["original"]:
        tag += "_" + "_".join(controllers)
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs" / f"weight_shape_{tag}.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()

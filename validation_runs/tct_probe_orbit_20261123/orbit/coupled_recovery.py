"""Screen bidirectional launches with simultaneous load and trajectory errors."""

import argparse
from collections import Counter
import json

from fields import FieldMap, HALF_WIDTH, ROOT
from orbit import trajectory
from run import shifted_height


PHASES = (0, 90, 180, 270)
NOMINAL = (0., 0., 1.)
FAST_HIGH = (.005, .001, 1.0025)
SLOW_LOW = (.005, -.001, .9975)
KICK = (.10, 0., .10)
CASES = {
    # Added mass divided by bare mass, drag at nominal speed, launch, optional kick.
    "bare_nominal": (0., 0., NOMINAL, None),
    "bare_fast_high": (0., 0., FAST_HIGH, None),
    "bare_slow_low": (0., 0., SLOW_LOW, None),
    "bare_drag": (0., .0002, NOMINAL, None),
    "bare_kick": (0., 0., NOMINAL, KICK),
    "shell_5pct": (.05, 0., NOMINAL, None),
    "shell_10pct": (.10, 0., NOMINAL, None),
    "shell_5pct_drag_01": (.05, .0001, NOMINAL, None),
    "shell_5pct_drag_02": (.05, .0002, NOMINAL, None),
    "shell_10pct_drag_01": (.10, .0001, NOMINAL, None),
    "shell_10pct_drag_02": (.10, .0002, NOMINAL, None),
    "shell_5pct_drag_01_fast_high": (.05, .0001, FAST_HIGH, None),
    "shell_5pct_drag_01_slow_low": (.05, .0001, SLOW_LOW, None),
    "shell_5pct_drag_01_kick": (.05, .0001, NOMINAL, KICK),
}


def run_screen(model, cases, steps, bare_kappa):
    rows = []
    for name in cases:
        mass, drag, launch, kick = CASES[name]
        kappa = bare_kappa / (1 + mass)
        trim = shifted_height(model, kappa)
        height_cap = model.height + HALF_WIDTH - .001
        target_height = height_cap if trim is None else min(trim, height_cap)
        for direction in (1, -1):
            outcomes = Counter()
            for phase in PHASES:
                row, _ = trajectory(
                    model, "guided_1.6kA_I", kappa, True, phase, launch, 100,
                    steps_per_lap=steps, balanced_height=target_height,
                    drag_per_moment=drag, direction=direction, kick_at_lap_one_m_s=kick,
                )
                row.update(case=name, added_mass_fraction=mass, drag_at_nominal_speed_T_m=drag,
                           kick_m_s=kick, ambient_trim_height_m=trim,
                           corridor_margin_m=HALF_WIDTH - max(row["radial_peak_m"], row["vertical_peak_m"]))
                outcomes[row["outcome"]] += 1
                rows.append(row)
            print(name, direction, dict(outcomes), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, choices=(288, 576), default=288)
    parser.add_argument("--fine-field", action="store_true")
    parser.add_argument("--bare-kappa", type=float, choices=(2500., 3000.), default=2500.)
    parser.add_argument("cases", nargs="*", metavar="CASE")
    args = parser.parse_args()
    for case in args.cases:
        if case not in CASES:
            parser.error(f"unknown case {case!r}")
    field_sizes = (216, 19, 64) if args.fine_field else (144, 15, 48)
    model = FieldMap(*field_sizes)
    rows = run_screen(model, args.cases or CASES, args.steps, args.bare_kappa)
    suffix = "_fine_field" if args.fine_field else ""
    if args.bare_kappa != 2500:
        suffix += f"_kappa{args.bare_kappa:g}"
    result = dict(field_grid=field_sizes, bare_kappa_Am2_kg=args.bare_kappa, original_height_m=model.height,
                  corridor_halfwidth_m=HALF_WIDTH, trajectories=rows)
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs" / f"coupled_recovery_{args.steps}{suffix}.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()

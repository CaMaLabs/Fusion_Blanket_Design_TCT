"""Record the evolving magnetic field and heat-exhaust distribution together."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import os
from pathlib import Path

import numpy as np

from island_release import END, HEAT_FLOOR, exhaust_profile, simulate
from source.sweep_mhd import LENGTH

CASES = ("unforced", "centered_solid", "wide_centered_solid", "centered_field")
SNAPSHOT_INTERVAL = .2
SNAPSHOT_TIMES = (np.arange(round(END/SNAPSHOT_INTERVAL)) + .5) * SNAPSHOT_INTERVAL


def snapshot_path(cache, case, level):
    return cache / f"release_target_{case}_{level}.npz"


def record(cache, case, level):
    path = snapshot_path(cache, case, level)
    if path.is_file():
        return
    magnetic, exhaust, saved_times = [], [], []

    def observe(grid, state, model, solid, field, time):
        if not np.any(np.isclose(time, SNAPSHOT_TIMES, atol=1e-10, rtol=0.)):
            return
        source, _, _, _ = model(grid, time, solid, field)
        total = state[1] if source is None else state[1] + source
        magnetic.append(grid.physical(total))
        exhaust.append(exhaust_profile(grid) * np.maximum(state[2] - HEAT_FLOOR, 0.))
        saved_times.append(time)

    run = simulate(case, level, observer=observe)
    np.testing.assert_allclose(saved_times, SNAPSHOT_TIMES, atol=1e-10, rtol=0.)
    time = np.array([row["time"] for row in run["rows"]])
    escaped = np.array([row["cumulative"]["exhaust"] for row in run["rows"]])
    power = np.array([row["exhaust_power"] for row in run["rows"]])
    check = np.searchsorted(time, np.asarray(saved_times))
    shape = np.asarray(run["mesh"])
    cell_volume = np.prod(LENGTH) / np.prod(shape)
    np.testing.assert_allclose(np.asarray(exhaust).sum(axis=(1,2,3))*cell_volume,
                               power[check], rtol=1e-12, atol=1e-13)
    staged = path.with_name(f".{path.stem}-{os.getpid()}.npz")
    try:
        np.savez(staged, time=time, cumulative=escaped, exhaust_power=power, magnetic=magnetic,
                 exhaust=exhaust, snapshot_time=saved_times)
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
    print("Recorded", case, level, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--levels", nargs="+", type=int, choices=(0, 1), default=[0, 1])
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        pending = [pool.submit(record, args.cache, case, level)
                   for case, level in product(args.cases, args.levels)]
        for job in as_completed(pending):
            job.result()


if __name__ == "__main__":
    main()

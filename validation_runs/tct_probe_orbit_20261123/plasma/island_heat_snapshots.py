"""Save the post-clearance plasma field for the absorbing-endplate replay."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import os
from pathlib import Path

import numpy as np

from island_crossing import AFTER, CADENCE, CASES, CROSSING
from island_energy import simulate

RELEASE_TIMES = (0., CROSSING, CROSSING + AFTER/2, CROSSING + AFTER)


def snapshot_path(cache, name, level):
    return cache / f"{name}_{level}.npz"


def save_fields(cache, name, level):
    path = snapshot_path(cache, name, level)
    if path.exists():
        return
    times, fields = [], []

    def inspect(grid, state, time, _mode):
        if np.any(np.isclose(time, RELEASE_TIMES, rtol=0, atol=1e-10)):
            times.append(time)
            fields.append(grid.physical(state[1]))

    run = simulate(name, level, inspect=inspect, cadence=CADENCE)
    np.testing.assert_allclose(times, RELEASE_TIMES, rtol=0, atol=1e-10)
    staged = path.with_name(f".{path.stem}-{os.getpid()}.npz")
    try:
        np.savez(staged, time=times, field=fields, dt_s=run["dt_s"])
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
    print("Saved magnetic snapshots", name, level, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--levels", nargs="+", type=int, choices=(0, 1, 2), default=[0])
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        tasks = [pool.submit(save_fields, args.cache, name, level)
                 for name, level in product(args.cases, args.levels)]
        for task in as_completed(tasks):
            task.result()


if __name__ == "__main__":
    main()

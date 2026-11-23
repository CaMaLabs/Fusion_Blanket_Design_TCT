"""Run the DIII-D point-dipole dynamics screen and generate its summary plot."""

import argparse
from collections import Counter
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import brentq

from fields import FieldMap, HALF_WIDTH, RADIUS, ROOT, TWO_PI
from orbit import G, I_LIMIT, OPTIMISTIC_LIMIT, ring_test, trajectory


RUNS = ROOT / "runs"
MODES = ("ambient", "fixed_plane_5kA_IC", "drive_1.6kA_I", "guided_1.6kA_I", "guided_5kA_IC")
LAUNCHES = {
    "nominal": (0., 0., 1.),
    "1mm_up": (0., .001, 1.),
    "1mm_down": (0., -.001, 1.),
    "5mm_up": (0., .005, 1.),
    "5mm_down": (0., -.005, 1.),
    "5mm_out": (.005, 0., 1.),
    "5mm_in": (-.005, 0., 1.),
    "1pct_fast": (0., 0., 1.01),
    "1pct_slow": (0., 0., .99),
    "2pct_fast": (0., 0., 1.02),
    "2pct_slow": (0., 0., .98),
    "rest": (0., 0., 0.),
}


def reference(field_map):
    z = field_map.height
    h = 0.00025
    local_gradient = lambda r, z: field_map.ambient(r, z)[1][[0, 2]]
    gr, gz = local_gradient(RADIUS, z)
    hessian = np.column_stack(((local_gradient(RADIUS + h, z) - local_gradient(RADIUS - h, z)) / (2 * h),
                               (local_gradient(RADIUS, z + h) - local_gradient(RADIUS, z - h)) / (2 * h)))
    eigenvalues = np.linalg.eigvalsh(hessian + np.diag([3 * gr / RADIUS, 0]))
    grid = np.linspace(0, TWO_PI, 144, endpoint=False)
    sensitivity = np.array([field_map.linear_response(field_map.local(np.array([RADIUS, phi, z])))[1]
                            for phi in grid])
    result = dict(radius_m=RADIUS, height_m=z, flux=float(field_map.flux(RADIUS, z)),
                  corridor_halfwidth_m=HALF_WIDTH, ambient_gradient_T_m=[gr, 0, gz],
                  normalized_circular_speed=field_map.balance_speed,
                  transverse_eigenvalues_per_kappa=eigenvalues.tolist(),
                  unstable_efolds_per_circular_lap=float(np.sqrt(eigenvalues[-1]) * TWO_PI * RADIUS
                                                         / field_map.balance_speed),
                  equilibrium=field_map.metadata, vertical_authority_linear_T_m={})
    for label, limits in (("I_1.6kA", I_LIMIT), ("IC_5kA", OPTIMISTIC_LIMIT)):
        up = np.abs(sensitivity[:, 2]) @ limits
        result["vertical_authority_linear_T_m"][label] = [float(up.min()), float(up.max())]
    return result


def shifted_height(field_map, kappa):
    z = field_map.height
    if field_map.ambient(RADIUS, z + HALF_WIDTH)[1][2] < G / kappa:
        return None
    return brentq(lambda height: field_map.ambient(RADIUS, height)[1][2] - G / kappa, z, z + HALF_WIDTH)


def replay(field_map, quick=False):
    cases, trace_set = [], {}

    def add(suite, mode, kappa, gravity, phi, name, hz=100, steps=288, shifted=None, trace=None):
        record, history = trajectory(field_map, mode, kappa, gravity, phi, LAUNCHES[name], hz,
                                     steps_per_lap=steps, traces=trace is not None, balanced_height=shifted)
        record.update(suite=suite, launch_id=name)
        cases.append(record)
        if trace is not None:
            trace_set[trace] = history

    groups = ((10000, False), (100, True), (1000, True), (3000, True), (10000, True))
    if quick:
        groups = ((10000, False), (10000, True))
    for kappa, gravity in groups:
        for mode in MODES:
            for phase_i, name in enumerate(LAUNCHES if not quick else ("nominal", "1mm_up", "5mm_up", "rest")):
                trace = mode if (kappa, gravity, name) == (10000, True, "1mm_up") else None
                add("main", mode, kappa, gravity, (phase_i * 90) % 360, name, trace=trace)
        counts = Counter(c["mode"] for c in cases if c["kappa_Am2_kg"] == kappa and c["gravity"] == gravity
                         and c["outcome"] == "completed")
        print(f"Main kappa={kappa}, gravity={gravity}: {dict(counts)}", flush=True)
    if quick:
        return cases, trace_set

    for kappa in (100, 1000, 3000, 10000):
        shift = shifted_height(field_map, kappa)
        if shift is None:
            continue
        for mode in ("ambient", "guided_1.6kA_I"):
            for phase_i, name in enumerate(("nominal", "1mm_up", "1mm_down", "5mm_out", "1pct_fast")):
                add("gravity_balanced", mode, kappa, True, phase_i * 90 % 360, name, shifted=shift)

    for phi in (0, 90, 180, 270):
        for name in ("nominal", "1mm_up", "1mm_down", "5mm_up", "5mm_down", "1pct_fast", "1pct_slow"):
            for hz in (30, 100, 300):
                add("phase_and_response", "guided_1.6kA_I", 10000, True, phi, name, hz=hz)

    for mode in MODES:
        for name, phi in (("nominal", 0), ("1mm_up", 90), ("5mm_up", 270), ("1pct_fast", 270)):
            coarse, _ = trajectory(field_map, mode, 10000, True, phi, LAUNCHES[name], 100, steps_per_lap=288)
            add("half_step", mode, 10000, True, phi, name, steps=576)
            fine = cases[-1]
            assert (fine["outcome"] == "completed") == (coarse["outcome"] == "completed"), (coarse, fine)
            assert abs(fine["laps"] - coarse["laps"]) < 0.008, (coarse, fine)
    return cases, trace_set


def plot(data, traces):
    fig, ax = plt.subplots(2, 1, figsize=(9, 7), layout="constrained")
    fig.suptitle("Phase-synchronized coils in the DIII-D orbit model", fontsize=16, weight="bold")
    rows = [r for r in data["ring"]["results"] if r["config"] == "independent_I_1.6kA"]
    for hz in (30, 100, 300, None):
        values = sorted((r for r in rows if r["cutoff_hz"] == hz), key=lambda r: r["laps_hz"])
        ax[0].plot([r["laps_hz"] for r in values], [1000 * r["forward_work_per_moment_T"] for r in values],
                   marker="o", label="Instantaneous" if hz is None else f"{hz} Hz response")
    ax[0].set(xscale="log", xlabel="Prescribed laps per second", ylabel="Work per moment (mT)")
    ax[0].axhline(0, color="black", linestyle=":", label="Fixed currents")
    ax[0].legend(ncol=2, frameon=False)
    labels = dict(zip(MODES, ("Ambient", "Fixed plane, I+C", "Switched torque only, I",
                              "Switched guidance, I", "Switched guidance, I+C")))
    for mode, history in traces.items():
        p = (history[:, 2] - history[0, 2]) / TWO_PI
        z = (history[:, 3] - data["reference"]["height_m"]) * 1000
        ax[1].plot(p, z, label=labels[mode])
    ax[1].set(xlabel="Free-flight laps", ylabel="Vertical offset (mm)")
    ax[1].axhline(HALF_WIDTH * 1000, color="gray", linestyle=":")
    ax[1].axhline(-HALF_WIDTH * 1000, color="gray", linestyle=":")
    ax[1].legend(ncol=2, frameon=False)
    for a in ax:
        a.grid(alpha=.22)
    fig.savefig(RUNS / "orbit_screen.png", dpi=175)
    plt.close(fig)


def main(quick=False):
    RUNS.mkdir(exist_ok=True)
    field_map = FieldMap()
    built = reference(field_map)
    error = field_map.check()
    print(f"Outboard reference {built['height_m']:.5f} m, transverse eigenvalues "
          f"{built['transverse_eigenvalues_per_kappa']}, map error {error}", flush=True)
    ring = ring_test(field_map)
    one_hz = next(r for r in ring["results"] if r["config"] == "independent_I_1.6kA"
                  and r["laps_hz"] == 1 and r["cutoff_hz"] == 100)
    print(f"Constrained ring at 1 Hz: {one_hz['forward_work_per_moment_T']:.6g} J per A m^2", flush=True)
    cases, traces = replay(field_map, quick)
    data = dict(reference=built, map_max_error_T_m=error, ring=ring, trajectories=cases)
    tag = "quick_" if quick else ""
    (RUNS / f"{tag}results.json").write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    np.savez_compressed(RUNS / f"{tag}trajectories.npz", **traces)
    if not quick:
        plot(data, traces)
    print(f"Finished {len(cases)} trajectories", flush=True)


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--quick", action="store_true")
    main(args.parse_args().quick)

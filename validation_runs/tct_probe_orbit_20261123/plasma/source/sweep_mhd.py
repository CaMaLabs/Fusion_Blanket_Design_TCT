#!/usr/bin/env python3
"""Four-way localized forcing test in a periodic resistive incompressible MHD box."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import scipy.fft as fft
from scipy.ndimage import map_coordinates, spline_filter
from scipy.optimize import root

LENGTH = np.array([2 * np.pi, np.pi, np.pi])
ETA = 0.0015
NU = 0.002
END = 2.0
AMPLITUDE = 0.18
SOURCE_WIDTH = 0.19
CORE_RADIUS = 0.23
MASK_HALF_WIDTH = 0.28
PENALTY_TIME = 0.012
PATHS = {"xpoint": (0., 0.), "island": (np.pi, 0.),
         "offsheet": (0., np.pi / 4)}
ASPECTS = {"sphere": 1., "elongated": 2.}
CASES = {"baseline": (False, False), "core": (True, False),
         "field": (False, True), "combined": (True, True)}


class Grid:
    def __init__(self, shape, target, body):
        self.shape = tuple(shape)
        x = [(np.arange(n) / n - 0.5) * length for n, length in zip(shape, LENGTH)]
        self.x, self.y, self.z = np.meshgrid(*x, indexing="ij", sparse=True)
        modes = [fft.fftfreq(n) * n for n in shape]
        modes[-1] = fft.rfftfreq(shape[-1]) * shape[-1]
        self.k = np.meshgrid(*(2 * np.pi * m / length for m, length in zip(modes, LENGTH)),
                             indexing="ij", sparse=True)
        mx, my, mz = np.meshgrid(*modes, indexing="ij", sparse=True)
        self.keep = ((np.abs(mx) < shape[0] / 3) & (np.abs(my) < shape[1] / 3)
                     & (mz < shape[2] / 3))
        self.k2 = sum(k**2 for k in self.k)
        self.kxy2 = self.k[0]**2 + self.k[1]**2
        self.i_k2 = np.divide(1., self.k2, out=np.zeros_like(self.k2), where=self.k2 != 0)
        self.i_kxy2 = np.divide(1., self.kxy2, out=np.zeros_like(self.kxy2),
                                where=self.kxy2 != 0)
        self.volume = float(np.prod(LENGTH))
        self.iy = shape[1] // 2
        self.iz = shape[2] // 2
        self.target = PATHS[target]
        aspect = ASPECTS[body]
        self.axes = CORE_RADIUS * np.array(
            [aspect**(-1/3), aspect**(2/3), aspect**(-1/3)])
        i = np.arange(256) + 0.5
        z = 1 - 2 * i / 256
        phi = np.pi * (3 - np.sqrt(5)) * i
        rad = np.sqrt(1 - z*z)
        self.surface = np.array([rad*np.cos(phi), rad*np.sin(phi), z])

    def transform(self, a):
        return fft.rfftn(a, axes=(-3, -2, -1), workers=2) * self.keep

    def physical(self, a):
        return fft.irfftn(a, s=self.shape, axes=(-3, -2, -1), workers=2)

    def curl(self, f):
        x, y, z = self.k
        return 1j * np.array([y * f[2] - z * f[1], z * f[0] - x * f[2],
                              x * f[1] - y * f[0]])

    def project(self, f):
        longitudinal = sum(i * j for i, j in zip(self.k, f)) * self.i_k2
        return f - np.array([i * longitudinal for i in self.k])


def cross(a, b):
    return np.array([a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
                     a[0] * b[1] - a[1] * b[0]])


def initial_state(grid):
    # Periodic double Harris-like sheet. Seed a finite magnetic island at y=0.
    background = np.zeros((3, *grid.shape))
    background[0] = np.tanh(np.sin(2 * grid.y) / 0.62)
    background[2] = 0.65
    potential = np.zeros_like(background)
    shape = np.exp((np.cos(2 * grid.y) - 1) / 0.47)
    potential[2] = 0.060 * np.cos(grid.x) * shape
    return np.zeros_like(grid.transform(background)), (
        grid.transform(background) + grid.curl(grid.transform(potential))
    )


def probe(grid, t, core, field):
    q = np.clip(t / END, 0., 1.)
    phase = q**3 * (10 - 15 * q + 6 * q*q)
    x_center, y_midpoint = grid.target
    y_center = y_midpoint + 0.40 - 0.80 * phase
    speed = -0.80 / END * 30 * q*q * (1 - q)**2
    coordinates = [grid.x - x_center, grid.y - y_center, grid.z - 0.17]
    x, y, z = ((r + length / 2) % length - length / 2
               for r, length in zip(coordinates, LENGTH))
    radius2 = x*x + y*y + z*z
    mask = None
    if core:
        radius = np.sqrt(sum((r / a)**2 for r, a in zip((x, y, z), grid.axes)))
        weight = np.clip((1 + MASK_HALF_WIDTH - radius) / (2 * MASK_HALF_WIDTH), 0, 1)
        mask = weight**2 * (3 - 2 * weight)
    source = None
    if field:
        # Algebraically divergence-free source, evaluated as a discrete curl.
        strength = 0.5 * AMPLITUDE * np.sin(np.pi * q)**2
        envelope = strength * np.exp(-radius2 / (2 * SOURCE_WIDTH**2))
        potential = np.array([-y * envelope, x * envelope, np.zeros_like(envelope)])
        source = grid.curl(grid.transform(potential))
    return source, mask, np.array([x_center, y_center, 0.17]), speed


def rhs(grid, state, t, core, field, penalty_time, probe_model=probe):
    velocity_hat, plasma_hat = state
    source, mask, _, speed = probe_model(grid, t, core, field)
    velocity = grid.physical(velocity_hat)
    total = grid.physical(plasma_hat if source is None else plasma_hat + source)
    current = grid.physical(grid.curl(plasma_hat))
    vorticity = grid.physical(grid.curl(velocity_hat))
    force = cross(velocity, vorticity) + cross(current, total)
    if mask is not None:
        relative = -velocity
        if np.ndim(speed) == 0:
            relative[1] += speed
        else:
            relative += np.asarray(speed)[:, None, None, None]
        force += mask / penalty_time * relative
    return np.array([
        grid.project(grid.transform(force)) - NU * grid.k2 * velocity_hat,
        grid.curl(grid.transform(cross(velocity, total))) - ETA * grid.k2 * plasma_hat,
    ])


def wrapped(x, length):
    return (x + length / 2) % length - length / 2


def field_line_map(grid, total, guesses, *, axial_steps=64):
    # A return map on one axial period of the frozen 3D total magnetic field.
    # Track the seeded one-turn periodic field lines and classify their stability.
    if total[2].min() <= 0:
        return {"status": "guide_field_changes_sign"}, guesses
    coefficients = [spline_filter(component, mode="grid-wrap") for component in total]
    shape = np.asarray(grid.shape)[:, None]
    length = LENGTH[:, None]

    def field_slope(xy, z):
        positions = np.vstack([xy, np.broadcast_to(z, xy.shape[1])])
        index = ((positions / length + 0.5) % 1.) * shape
        bx, by, bz = (map_coordinates(c, index, mode="grid-wrap", prefilter=False)
                      for c in coefficients)
        if np.any(bz <= 0):
            raise ArithmeticError("Guide field changed sign in interpolation")
        return np.vstack([bx / bz, by / bz])

    def return_displacement(seeds):
        xy = seeds.copy()
        dz = LENGTH[2] / axial_steps
        for i in range(axial_steps):
            z = 0.17 + i * dz
            k1 = field_slope(xy, z)
            k2 = field_slope(xy + dz/2*k1, z + dz/2)
            k3 = field_slope(xy + dz/2*k2, z + dz/2)
            k4 = field_slope(xy + dz*k3, z + dz)
            xy += dz/6*(k1 + 2*k2 + 2*k3 + k4)
        return wrapped(xy - seeds, LENGTH[:2, None])

    points = {}
    locations = guesses.copy()
    eps = 0.0002
    perturbations = eps * np.array([[1, -1, 0, 0], [0, 0, 1, -1]])

    def displacement_gradient(xy):
        changes = return_displacement(xy[:, None] + perturbations)
        return np.column_stack(
            ((changes[:, 0] - changes[:, 1]), (changes[:, 2] - changes[:, 3]))) / (2 * eps)

    for label, guess in guesses.items():
        # Solve for a displacement from the previous point. A small but nonzero
        # absolute coordinate near the X-point can give HYBR a tiny trust region.
        finder = root(lambda dx: return_displacement((guess + dx)[:, None])[:, 0],
                      np.zeros(2), jac=lambda dx: displacement_gradient(guess + dx),
                      options={"maxfev": 50, "factor": 0.3})
        candidate = guess + finder.x
        displacement = wrapped(finder.x, LENGTH[:2])
        error = float(np.linalg.norm(finder.fun))
        if error > 1e-5 or np.linalg.norm(displacement) > 0.6:
            points[label] = {"status": "continuation_failed", "return_error": error,
                             "candidate_distance": float(np.linalg.norm(displacement))}
            continue
        jacobian = np.eye(2) + displacement_gradient(candidate)
        determinant = float(np.linalg.det(jacobian))
        trace = float(np.trace(jacobian))
        discriminant = trace**2 - 4 * determinant
        regime = "elliptic" if discriminant < 0 else "hyperbolic"
        if abs(determinant - 1) > 0.03:
            regime = "stability_unresolved"
        locations[label] = candidate
        points[label] = {
            "status": "tracked", "classification": regime,
            "xy": wrapped(candidate, LENGTH[:2]).tolist(),
            "return_error": error, "trace": trace, "determinant": determinant,
        }
    return points, locations


def observe(grid, state, t, core, field):
    velocity_hat, plasma_hat = state
    source, mask, center, speed = probe(grid, t, core, field)
    current_hat = grid.curl(plasma_hat)
    velocity, plasma, current = map(grid.physical, (velocity_hat, plasma_hat, current_hat))
    total = plasma if source is None else plasma + grid.physical(source)
    # Jz = -laplacian_xy(Az) for the in-plane solenoidal projection on each z plane.
    sheet_flux = grid.physical(current_hat[2] * grid.i_kxy2)
    sheet_band = abs(grid.y[0, :, 0]) < 0.30
    flux_contrast = np.ptp(sheet_flux[:, grid.iy, grid.iz])
    jRMS = np.sqrt(np.mean(current[2, :, sheet_band, :]**2))
    mag = np.sqrt(np.sum(total**2, axis=0))
    e_parallel = ETA * np.abs(np.sum(current * total, axis=0)) / np.maximum(mag, 1e-12)
    fluid = 1 if mask is None else 1 - mask
    fluid_fraction = float(np.mean(np.broadcast_to(fluid, grid.shape)))
    joule = float(ETA * grid.volume * np.mean(fluid * np.sum(current**2, axis=0)))
    divergence = max(float(np.max(np.abs(grid.physical(1j * sum(k*f for k, f in zip(grid.k, hat))))))
                     for hat in (velocity_hat, plasma_hat))
    result = dict(t=t, projected_midplane_flux_contrast=float(flux_contrast),
                  sheet_current_rms=float(jRMS), parallel_e_p99=float(np.quantile(e_parallel, .99)),
                  volume_joule_power=joule, fluid_fraction=fluid_fraction,
                  max_divergence=divergence)
    if mask is not None:
        axes = grid.axes[:, None]
        index = ((center[:, None] + axes * grid.surface) / LENGTH[:, None] + .5)
        index = (index % 1.) * np.asarray(grid.shape)[:, None]
        surface_velocity = np.array([map_coordinates(value, index, order=3, mode="grid-wrap")
                                     for value in velocity])
        surface_velocity[1] -= speed
        normals = grid.surface / axes
        normal_weights = np.linalg.norm(normals, axis=0)
        normal_velocity = np.sum(surface_velocity * normals, axis=0) / normal_weights
        result["surface_normal_slip_rms"] = float(np.sqrt(
            np.average(normal_velocity**2, weights=normal_weights)))
        result["core_speed"] = speed
        result["masked_volume"] = (1 - fluid_fraction) * grid.volume
    return result, total


def run(name, shape, dt, penalty_time, target, body, output):
    core, field = CASES[name]
    grid = Grid(shape, target, body)
    steps = round(END / dt)
    dt = END / steps
    state = np.array(initial_state(grid))
    records = []
    guesses = {"seed_x": np.array([0., 0.]), "seed_o": np.array([np.pi, 0.])}
    trace_steps = {round(fraction * steps / 10) for fraction in range(11)}
    for i in range(steps + 1):
        t = i * dt
        if i % max(1, steps // 20) == 0 or i in trace_steps:
            record, total = observe(grid, state, t, core, field)
            if i in trace_steps:
                record["field_line_return_map"], guesses = field_line_map(grid, total, guesses)
            records.append(record)
        if i < steps:
            slope = rhs(grid, state, t, core, field, penalty_time)
            state += dt * rhs(grid, state + dt/2 * slope, t + dt/2, core, field, penalty_time)
    if not np.isfinite(state).all() or max(row["max_divergence"] for row in records) > 1e-9:
        raise ArithmeticError("nonfinite state or failure to preserve a divergence-free solution")
    result = {
        "case": name, "shape": list(shape), "dt": dt, "steps": steps,
        "penalty_time": penalty_time, "target": target, "body": body,
        "return_map_method": "centered_continuation",
        "semiaxes": grid.axes.tolist(), "solid_volume": float(4*np.pi/3*np.prod(grid.axes)),
        "model": "periodic local resistive incompressible MHD with prescribed induction forcing",
        "records": records,
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"{name} {shape} dt={dt:g} complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=CASES)
    parser.add_argument("--shape", nargs=3, type=int, required=True)
    parser.add_argument("--dt", type=float, required=True)
    parser.add_argument("--penalty-time", type=float, default=PENALTY_TIME)
    parser.add_argument("--target", choices=PATHS, default="xpoint")
    parser.add_argument("--body", choices=ASPECTS, default="sphere")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.dt <= 0 or args.penalty_time <= 0 or any(n < 8 or n % 2 for n in args.shape):
        parser.error("use positive time scales and an even grid of at least 8 points per axis")
    run(args.case, tuple(args.shape), args.dt, args.penalty_time, args.target, args.body, args.out)

#!/usr/bin/env python3
"""Dedalus toy reduced-MHD current-sheet benchmark with optional TCT-style forcing.

This is a deliberately small 2D periodic reduced/resistive-MHD problem. It is
intended to test whether current-sheet diagnostics are useful in a reconnection
proxy problem. It is not a reactor model, tokamak model, or TCT validation.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    import dedalus.public as d3
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without Dedalus installed
    d3 = None
    DEDALUS_IMPORT_ERROR = exc
else:
    DEDALUS_IMPORT_ERROR = None


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkConfig:
    # Grid and domain. A double-Harris sheet is used so the domain can remain
    # periodic in both coordinates.
    nx: int = 192
    nz: int = 192
    lx: float = 12.8
    lz: float = 12.8
    dealias: float = 1.5

    # Reduced-MHD transport parameters.
    eta: float = 2.5e-3
    nu: float = 2.5e-3

    # Initial double-Harris current sheet.
    delta0: float = 0.30
    perturbation_amplitude: float = 2.0e-3
    perturbation_kx: int = 1

    # Time integration.
    timestep: float = 2.0e-3
    stop_time: float = 3.0
    diagnostic_cadence: int = 10
    snapshot_cadence: int = 100
    max_steps: int = 200000

    # Transparent TCT-style proxy. The control is a localized extra resistive
    # smoothing term, activated only after the measured aspect ratio crosses a
    # threshold. Set enabled=False or strength=0 to disable.
    control_enabled: bool = False
    control_aspect_threshold: float = 18.0
    control_strength: float = 8.0e-3
    control_width: float = 0.70

    # Island proxy thresholds.
    onset_island_count_threshold: int = 3
    island_o_point_prominence: float = 2.0e-4
    component_threshold_fraction: float = 0.30
    component_min_cells: int = 3

    # Optional transparent onset driver. This is off by default. When enabled,
    # the same small multimode flux source is applied to baseline and perturbed
    # cases after drive_start_time, so the benchmark can exercise island-onset
    # diagnostics without claiming spontaneous plasmoid formation.
    drive_enabled: bool = False
    drive_start_time: float = 0.5
    drive_end_time: float = 0.7
    drive_strength: float = 0.0
    drive_kx: int = 4
    drive_width: float = 0.45

    # Optional biased wall-current proxy. This is a prescribed reduced-MHD flux
    # source near the two current-sheet/wall-proxy layers. It is not a liquid
    # lithium model; it only tests polarity and trigger sensitivity.
    bias_enabled: bool = False
    bias_mode: str = "standing"
    bias_strength: float = 0.0
    bias_polarity: float = 1.0
    bias_kx: int = 1
    bias_width: float = 0.55
    bias_aspect_threshold: float = 80.0
    bias_rib_count: int = 8
    bias_rib_duty: float = 0.35
    bias_phase: float = 0.0


def _require_dedalus() -> None:
    if d3 is None:
        raise SystemExit(
            "Dedalus is not installed in this Python environment. Install Dedalus "
            "and rerun this benchmark. Original import error: "
            f"{DEDALUS_IMPORT_ERROR}"
        )


def _double_harris_psi(z: np.ndarray, cfg: BenchmarkConfig) -> np.ndarray:
    """Return periodic double-Harris flux psi(z).

    The in-plane magnetic field is B = zhat x grad(psi), so Bx = -dpsi/dz.
    The selected psi produces two oppositely signed Harris current sheets at
    z = +/- Lz/4 while remaining approximately periodic at the box edges.
    """
    zp = z + cfg.lz / 4.0
    zm = z - cfg.lz / 4.0
    return -cfg.delta0 * np.log(np.cosh(zp / cfg.delta0)) + cfg.delta0 * np.log(np.cosh(zm / cfg.delta0)) + z


def _build_problem(cfg: BenchmarkConfig) -> dict[str, Any]:
    _require_dedalus()
    coords = d3.CartesianCoordinates("x", "z")
    dist = d3.Distributor(coords, dtype=np.float64)
    xbasis = d3.RealFourier(coords["x"], size=cfg.nx, bounds=(-cfg.lx / 2.0, cfg.lx / 2.0), dealias=cfg.dealias)
    zbasis = d3.RealFourier(coords["z"], size=cfg.nz, bounds=(-cfg.lz / 2.0, cfg.lz / 2.0), dealias=cfg.dealias)
    bases = (xbasis, zbasis)

    psi = dist.Field(name="psi", bases=bases)
    omega = dist.Field(name="omega", bases=bases)
    phi = dist.Field(name="phi", bases=bases)
    tau_phi = dist.Field(name="tau_phi")
    control = dist.Field(name="control", bases=bases)
    drive = dist.Field(name="drive", bases=bases)
    bias = dist.Field(name="bias", bases=bases)

    x, z = dist.local_grids(xbasis, zbasis)
    psi["g"] = _double_harris_psi(z, cfg)
    psi["g"] += cfg.perturbation_amplitude * np.cos(2 * np.pi * cfg.perturbation_kx * x / cfg.lx) * np.cos(4 * np.pi * z / cfg.lz)
    omega["g"] = 0.0
    phi["g"] = 0.0
    control["g"] = 0.0
    drive["g"] = 0.0
    bias["g"] = 0.0

    eta = cfg.eta
    nu = cfg.nu
    dx = lambda a: d3.Differentiate(a, coords["x"])
    dz = lambda a: d3.Differentiate(a, coords["z"])
    lap = lambda a: d3.Laplacian(a)
    bracket = lambda a, b: dx(a) * dz(b) - dz(a) * dx(b)
    j_expr = -lap(psi)

    problem = d3.IVP([psi, omega, phi, tau_phi], namespace=locals())
    problem.add_equation("dt(psi) - eta*lap(psi) = -bracket(phi, psi) + control + drive + bias")
    problem.add_equation("dt(omega) - nu*lap(omega) = -bracket(phi, omega) + bracket(psi, j_expr)")
    problem.add_equation("lap(phi) + tau_phi + omega = 0")
    problem.add_equation("integ(phi) = 0")

    solver = problem.build_solver(d3.RK222)
    solver.stop_sim_time = cfg.stop_time
    solver.stop_iteration = cfg.max_steps

    return {
        "coords": coords,
        "dist": dist,
        "bases": bases,
        "xbasis": xbasis,
        "zbasis": zbasis,
        "x": x,
        "z": z,
        "psi": psi,
        "omega": omega,
        "phi": phi,
        "control": control,
        "drive": drive,
        "bias": bias,
        "j_expr": j_expr,
        "solver": solver,
    }


def _periodic_gradient(values: np.ndarray, spacing: float, axis: int) -> np.ndarray:
    return (np.roll(values, -1, axis=axis) - np.roll(values, 1, axis=axis)) / (2.0 * spacing)


def _periodic_laplacian(values: np.ndarray, dx: float, dz: float) -> np.ndarray:
    return (
        (np.roll(values, -1, axis=0) - 2.0 * values + np.roll(values, 1, axis=0)) / dx**2
        + (np.roll(values, -1, axis=1) - 2.0 * values + np.roll(values, 1, axis=1)) / dz**2
    )


def compute_diagnostics(psi_grid: np.ndarray, time: float, cfg: BenchmarkConfig) -> dict[str, float]:
    """Compute sheet and reconnection diagnostics from psi on the grid.

    The current density proxy is J = -Delp2(psi). The legacy delta/aspect
    metric is a half-maximum current-profile diagnostic: find the two strongest
    peaks in <|J|>_x, estimate each sheet's z-width above half maximum, and
    average those half-widths. Sheet length L is the x-extent where |J| at the
    active sheet exceeds half of its local peak. These metrics can be insensitive
    on coarse grids, so an RMS current-profile width is also reported.
    """
    dx = cfg.lx / cfg.nx
    dz = cfg.lz / cfg.nz
    current = -_periodic_laplacian(psi_grid, dx, dz)
    abs_j = np.abs(current)
    j_profile = np.mean(abs_j, axis=0)
    peak_indices = np.argsort(j_profile)[-2:]

    deltas = []
    weighted_deltas = []
    lengths = []
    for iz in peak_indices:
        peak = float(j_profile[iz])
        half = 0.5 * peak
        left = iz
        right = iz
        while j_profile[left % cfg.nz] >= half and (iz - left) < cfg.nz // 2:
            left -= 1
        while j_profile[right % cfg.nz] >= half and (right - iz) < cfg.nz // 2:
            right += 1
        full_width = max(1, right - left - 1) * dz
        deltas.append(0.5 * full_width)

        # A smoother companion diagnostic: RMS width of <|J|>_x around the sheet
        # peak. The +/- nz/4 window avoids mixing the two sheets in the periodic
        # double-Harris box. This is still a profile proxy, not a separatrix fit.
        offsets = np.arange(cfg.nz) - int(iz)
        offsets = (offsets + cfg.nz // 2) % cfg.nz - cfg.nz // 2
        window = np.abs(offsets) <= cfg.nz // 4
        weights = np.where(window, j_profile, 0.0)
        weight_sum = float(np.sum(weights))
        if weight_sum > 0.0:
            distances = offsets * dz
            weighted_deltas.append(float(np.sqrt(np.sum(weights * distances * distances) / weight_sum)))

        sheet_row = abs_j[:, iz]
        active = sheet_row >= half
        lengths.append(float(np.count_nonzero(active) * dx))

    delta = float(np.mean(deltas))
    weighted_delta = float(np.mean(weighted_deltas)) if weighted_deltas else float("nan")
    length = float(np.max(lengths))
    aspect = float(length / delta) if delta > 0 else float("inf")
    weighted_aspect = float(length / weighted_delta) if weighted_delta > 0 else float("inf")

    bx = -_periodic_gradient(psi_grid, dz, axis=1)
    bz = _periodic_gradient(psi_grid, dx, axis=0)
    magnetic_energy = float(0.5 * np.mean(bx * bx + bz * bz))

    center_x = cfg.nx // 2
    center_z = int(peak_indices[np.argmax(j_profile[peak_indices])])
    reconnection_rate_proxy = float(cfg.eta * abs_j[center_x, center_z])

    island_count = _count_island_proxy(psi_grid, cfg)
    component_count = _count_component_proxy(psi_grid, cfg)
    return {
        "time": float(time),
        "current_profile_delta_halfmax": delta,
        "current_profile_sheet_length_halfmax": length,
        "current_profile_aspect_ratio_halfmax": aspect,
        "current_weighted_delta_rms": weighted_delta,
        "current_weighted_aspect_ratio": weighted_aspect,
        # Backward-compatible aliases used by older artifact scripts.
        "delta": delta,
        "sheet_length": length,
        "aspect_ratio": aspect,
        "max_abs_J": float(np.max(abs_j)),
        "J_p99": float(np.percentile(abs_j, 99.0)),
        "reconnection_rate_proxy": reconnection_rate_proxy,
        "magnetic_energy": magnetic_energy,
        "island_count_proxy": int(island_count),
        "component_count_proxy": int(component_count),
    }


def _count_island_proxy(psi_grid: np.ndarray, cfg: BenchmarkConfig) -> int:
    """Count robust local extrema of perturbed psi as an island/plasmoid proxy.

    The Harris equilibrium contributes a large x-averaged flux variation. We
    subtract the x-average before looking for extrema so the proxy is sensitive
    to island-like perturbation flux rather than to the background sheet.
    """
    # Field analyzed: perturbation flux psi - <psi>_x, not the raw equilibrium
    # flux. Candidate O-point proxies are local maxima and local minima on the
    # periodic grid. A candidate must exceed every one of its eight neighboring
    # cells by `island_o_point_prominence` for maxima, or be lower by that same
    # prominence for minima. This is a deliberately cheap morphology diagnostic:
    # it does not trace separatrices, distinguish all O-points from X-points, or
    # merge duplicate extrema belonging to one physical island. It can fail by
    # counting grid noise, missing weak/broad islands, double-counting periodic
    # structures, or changing with the prominence threshold.
    psi_perturb = psi_grid - np.mean(psi_grid, axis=0, keepdims=True)
    prominence = cfg.island_o_point_prominence
    extrema = 0
    greater_than_neighbors = np.ones_like(psi_perturb, dtype=bool)
    less_than_neighbors = np.ones_like(psi_perturb, dtype=bool)
    for ax in (-1, 0, 1):
        for az in (-1, 0, 1):
            if ax == 0 and az == 0:
                continue
            neighbor = np.roll(np.roll(psi_perturb, ax, axis=0), az, axis=1)
            greater_than_neighbors &= psi_perturb > neighbor + prominence
            less_than_neighbors &= psi_perturb < neighbor - prominence
    extrema += int(np.count_nonzero(greater_than_neighbors))
    extrema += int(np.count_nonzero(less_than_neighbors))
    return extrema


def _count_component_proxy(psi_grid: np.ndarray, cfg: BenchmarkConfig) -> int:
    """Count connected perturbation-flux structures as a second morphology proxy.

    This diagnostic subtracts the x-averaged equilibrium flux, thresholds
    positive and negative perturbation lobes, and counts periodic 4-connected
    components with at least `component_min_cells`. The threshold is the larger
    of `component_threshold_fraction * max(abs(psi_perturb))` and five times the
    local-extrema prominence. It is independent of the extrema detector but is
    still not a magnetic-topology count; broad, merged, or threshold-sensitive
    structures can be over- or under-counted.
    """
    psi_perturb = psi_grid - np.mean(psi_grid, axis=0, keepdims=True)
    amplitude = float(np.max(np.abs(psi_perturb)))
    if amplitude <= 0.0:
        return 0
    threshold = max(cfg.component_threshold_fraction * amplitude, 5.0 * cfg.island_o_point_prominence)
    return _count_periodic_components(psi_perturb > threshold, cfg.component_min_cells) + _count_periodic_components(
        psi_perturb < -threshold, cfg.component_min_cells
    )


def _count_periodic_components(mask: np.ndarray, min_cells: int) -> int:
    """Count periodic 4-connected components in a boolean mask."""
    visited = np.zeros_like(mask, dtype=bool)
    nx, nz = mask.shape
    components = 0
    for start_x, start_z in zip(*np.nonzero(mask)):
        if visited[start_x, start_z]:
            continue
        stack = [(int(start_x), int(start_z))]
        visited[start_x, start_z] = True
        size = 0
        while stack:
            x, z = stack.pop()
            size += 1
            for nx_i, nz_i in (((x + 1) % nx, z), ((x - 1) % nx, z), (x, (z + 1) % nz), (x, (z - 1) % nz)):
                if mask[nx_i, nz_i] and not visited[nx_i, nz_i]:
                    visited[nx_i, nz_i] = True
                    stack.append((nx_i, nz_i))
        if size >= min_cells:
            components += 1
    return components


def _update_control(state: dict[str, Any], metrics: dict[str, float], cfg: BenchmarkConfig) -> bool:
    """Activate transparent smoothing forcing after aspect-ratio threshold crossing."""
    control = state["control"]
    control.change_scales(1)
    control.require_grid_space()
    if not cfg.control_enabled or cfg.control_strength <= 0.0:
        control["g"] = 0.0
        return False
    if metrics["aspect_ratio"] < cfg.control_aspect_threshold:
        control["g"] = 0.0
        return False

    psi_grid = _psi_grid(state)
    z = state["z"]
    current = -_periodic_laplacian(psi_grid, cfg.lx / cfg.nx, cfg.lz / cfg.nz)
    iz = int(np.argmax(np.mean(np.abs(current), axis=0)))
    z0 = float(z[0, iz])
    mask = np.exp(-((z - z0) / cfg.control_width) ** 2)
    # This term is intentionally simple: additional localized resistive
    # smoothing, proportional to Delp2(psi), near the active sheet.
    control["g"] = cfg.control_strength * _periodic_laplacian(psi_grid, cfg.lx / cfg.nx, cfg.lz / cfg.nz) * mask
    return True


def _update_drive(state: dict[str, Any], sim_time: float, cfg: BenchmarkConfig) -> bool:
    """Apply the optional transparent island-onset drive after start time."""
    drive = state["drive"]
    drive.change_scales(1)
    drive.require_grid_space()
    if (
        not cfg.drive_enabled
        or cfg.drive_strength <= 0.0
        or sim_time < cfg.drive_start_time
        or sim_time > cfg.drive_end_time
    ):
        drive["g"] = 0.0
        return False

    x = state["x"]
    z = state["z"]
    sheet_mask = np.exp(-((z - cfg.lz / 4.0) / cfg.drive_width) ** 2) + np.exp(-((z + cfg.lz / 4.0) / cfg.drive_width) ** 2)
    phase = 2.0 * np.pi * cfg.drive_kx * x / cfg.lx
    drive["g"] = cfg.drive_strength * np.cos(phase) * sheet_mask
    return True


def _update_bias(state: dict[str, Any], metrics: dict[str, float], cfg: BenchmarkConfig) -> bool:
    """Apply a prescribed edge-current bias source.

    These modes are deliberately simple reduced-MHD flux-source proxies:

    - `standing` / `triggered`: smooth liquid-wall-style standing bias.
    - `rib_matrix`: segmented toroidal rib-like source with localized x bands.
    - `mesh`: crossed rib/mesh-like source with additional z modulation.
    - `phase_locked_rib`: rib matrix shifted by `bias_phase` to mimic selecting
      an actuator sector from a mode-phase estimate.

    None of these modes model electrodes, sheaths, contact resistance, material
    response, or real liquid-metal MHD.
    """
    bias = state["bias"]
    bias.change_scales(1)
    bias.require_grid_space()
    if not cfg.bias_enabled or cfg.bias_strength == 0.0:
        bias["g"] = 0.0
        return False
    triggered_modes = {"triggered"}
    if cfg.bias_mode in triggered_modes and metrics["aspect_ratio"] < cfg.bias_aspect_threshold:
        bias["g"] = 0.0
        return False
    if cfg.bias_mode not in {"standing", "triggered", "rib_matrix", "mesh", "phase_locked_rib"}:
        raise ValueError(f"Unsupported bias mode: {cfg.bias_mode}")

    x = state["x"]
    z = state["z"]
    upper_mask = np.exp(-((z - cfg.lz / 4.0) / cfg.bias_width) ** 2)
    lower_mask = np.exp(-((z + cfg.lz / 4.0) / cfg.bias_width) ** 2)
    sheet_shape = upper_mask - lower_mask
    phase = 2.0 * np.pi * cfg.bias_kx * x / cfg.lx + cfg.bias_phase

    if cfg.bias_mode in {"standing", "triggered"}:
        # Smooth standing source used by the earlier liquid-wall proxy.
        wall_current_shape = sheet_shape * np.cos(phase)
    elif cfg.bias_mode == "rib_matrix":
        rib_shape = _rib_pattern(x, cfg)
        wall_current_shape = sheet_shape * rib_shape
    elif cfg.bias_mode == "mesh":
        rib_shape = _rib_pattern(x, cfg)
        z_mesh = np.cos(2.0 * np.pi * cfg.bias_kx * z / cfg.lz)
        wall_current_shape = sheet_shape * rib_shape * z_mesh
    else:
        # Phase-locked ribs use the same segmented geometry, shifted in x by
        # bias_phase. This mimics selecting a sector relative to measured mode
        # phase, without implementing a real feedback controller here.
        rib_shape = _rib_pattern(x, cfg)
        wall_current_shape = sheet_shape * rib_shape

    bias["g"] = cfg.bias_polarity * cfg.bias_strength * wall_current_shape
    return True


def _rib_pattern(x: np.ndarray, cfg: BenchmarkConfig) -> np.ndarray:
    """Return a smooth signed rib/mesh pattern in x.

    The square-wave-like rib mask is represented by a tanh-smoothed cosine so
    the Dedalus run receives a bounded, differentiable-ish source. `bias_rib_duty`
    controls how much of each rib period is energized.
    """
    rib_count = max(1, int(cfg.bias_rib_count))
    duty = min(max(float(cfg.bias_rib_duty), 0.05), 0.95)
    phase = 2.0 * np.pi * rib_count * x / cfg.lx + cfg.bias_phase
    threshold = np.cos(np.pi * duty)
    return np.tanh(8.0 * (np.cos(phase) - threshold))


def _psi_grid(state: dict[str, Any]) -> np.ndarray:
    """Return psi in physical grid layout at scale 1."""
    psi = state["psi"]
    psi.change_scales(1)
    psi.require_grid_space()
    return np.array(psi["g"], copy=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_case(case_name: str, cfg: BenchmarkConfig, run_dir: Path) -> dict[str, Any]:
    state = _build_problem(cfg)
    solver = state["solver"]
    case_dir = run_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    diagnostics: list[dict[str, Any]] = []
    snapshots: list[np.ndarray] = []
    snapshot_times: list[float] = []
    control_active_once = False
    drive_active_once = False
    bias_active_once = False
    onset_time = None
    component_onset_time = None
    initial_island_count = None
    initial_component_count = None

    while solver.proceed:
        if solver.iteration % cfg.diagnostic_cadence == 0:
            psi_grid = _psi_grid(state)
            metrics = compute_diagnostics(psi_grid, solver.sim_time, cfg)
            if initial_island_count is None:
                initial_island_count = int(metrics["island_count_proxy"])
            if initial_component_count is None:
                initial_component_count = int(metrics["component_count_proxy"])
            control_active = _update_control(state, metrics, cfg)
            control_active_once = control_active_once or control_active
            drive_active = _update_drive(state, solver.sim_time, cfg)
            drive_active_once = drive_active_once or drive_active
            bias_active = _update_bias(state, metrics, cfg)
            bias_active_once = bias_active_once or bias_active
            metrics["control_active"] = bool(control_active)
            metrics["drive_active"] = bool(drive_active)
            metrics["bias_active"] = bool(bias_active)
            diagnostics.append(metrics)
            onset_count = max(cfg.onset_island_count_threshold, int(initial_island_count) + 1)
            if onset_time is None and metrics["time"] > 0.0 and metrics["island_count_proxy"] >= onset_count:
                onset_time = float(metrics["time"])
            component_onset_count = max(cfg.onset_island_count_threshold, int(initial_component_count) + 1)
            if (
                component_onset_time is None
                and metrics["time"] > 0.0
                and metrics["component_count_proxy"] >= component_onset_count
            ):
                component_onset_time = float(metrics["time"])
        if solver.iteration % cfg.snapshot_cadence == 0:
            snapshots.append(_psi_grid(state))
            snapshot_times.append(float(solver.sim_time))
        solver.step(cfg.timestep)

    if not diagnostics:
        psi_grid = _psi_grid(state)
        diagnostics.append(compute_diagnostics(psi_grid, solver.sim_time, cfg))

    _write_csv(case_dir / "diagnostics.csv", diagnostics)
    np.savez_compressed(
        case_dir / "snapshots.npz",
        times=np.asarray(snapshot_times, dtype=float),
        psi=np.asarray(snapshots, dtype=float),
        config=json.dumps(asdict(cfg), sort_keys=True),
    )
    max_aspect = max(row["aspect_ratio"] for row in diagnostics)
    min_delta = min(row["delta"] for row in diagnostics)
    max_weighted_aspect = max(row["current_weighted_aspect_ratio"] for row in diagnostics)
    min_weighted_delta = min(row["current_weighted_delta_rms"] for row in diagnostics)
    max_abs_j = max(row["max_abs_J"] for row in diagnostics)
    max_j_p99 = max(row["J_p99"] for row in diagnostics)
    final_energy = diagnostics[-1]["magnetic_energy"]
    initial_energy = diagnostics[0]["magnetic_energy"]
    summary = {
        "case": case_name,
        "control_enabled": cfg.control_enabled,
        "control_active_once": control_active_once,
        "drive_enabled": cfg.drive_enabled,
        "drive_active_once": drive_active_once,
        "bias_enabled": cfg.bias_enabled,
        "bias_active_once": bias_active_once,
        "bias_mode": cfg.bias_mode,
        "bias_strength": cfg.bias_strength,
        "bias_polarity": cfg.bias_polarity,
        "bias_kx": cfg.bias_kx,
        "bias_width": cfg.bias_width,
        "bias_rib_count": cfg.bias_rib_count,
        "bias_rib_duty": cfg.bias_rib_duty,
        "bias_phase": cfg.bias_phase,
        "initial_island_count_proxy": int(initial_island_count) if initial_island_count is not None else None,
        "time_to_secondary_island_proxy": onset_time,
        "initial_component_count_proxy": int(initial_component_count) if initial_component_count is not None else None,
        "time_to_secondary_component_proxy": component_onset_time,
        "max_aspect_ratio": max_aspect,
        "min_delta": min_delta,
        "max_current_weighted_aspect_ratio": max_weighted_aspect,
        "min_current_weighted_delta_rms": min_weighted_delta,
        "max_abs_J": max_abs_j,
        "max_J_p99": max_j_p99,
        "initial_magnetic_energy": initial_energy,
        "final_magnetic_energy": final_energy,
        "magnetic_energy_decay_fraction": 1.0 - final_energy / initial_energy if initial_energy else None,
        "final_island_count_proxy": diagnostics[-1]["island_count_proxy"],
        "final_component_count_proxy": diagnostics[-1]["component_count_proxy"],
        "diagnostic_rows": len(diagnostics),
    }
    (case_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def build_config(args: argparse.Namespace, control_enabled: bool) -> BenchmarkConfig:
    return BenchmarkConfig(
        nx=args.nx,
        nz=args.nz,
        lx=args.lx,
        lz=args.lz,
        eta=args.eta,
        nu=args.nu,
        delta0=args.delta0,
        perturbation_amplitude=args.perturbation_amplitude,
        perturbation_kx=args.perturbation_kx,
        timestep=args.timestep,
        stop_time=args.stop_time,
        diagnostic_cadence=args.diagnostic_cadence,
        snapshot_cadence=args.snapshot_cadence,
        control_enabled=control_enabled,
        control_aspect_threshold=args.control_aspect_threshold,
        control_strength=args.control_strength,
        control_width=args.control_width,
        onset_island_count_threshold=args.onset_island_count_threshold,
        island_o_point_prominence=args.island_o_point_prominence,
        component_threshold_fraction=args.component_threshold_fraction,
        component_min_cells=args.component_min_cells,
        drive_enabled=args.drive_enabled,
        drive_start_time=args.drive_start_time,
        drive_end_time=args.drive_end_time,
        drive_strength=args.drive_strength,
        drive_kx=args.drive_kx,
        drive_width=args.drive_width,
        bias_enabled=args.bias_enabled,
        bias_mode=args.bias_mode,
        bias_strength=args.bias_strength,
        bias_polarity=args.bias_polarity,
        bias_kx=args.bias_kx,
        bias_width=args.bias_width,
        bias_aspect_threshold=args.bias_aspect_threshold,
        bias_rib_count=args.bias_rib_count,
        bias_rib_duty=args.bias_rib_duty,
        bias_phase=args.bias_phase,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("validation_runs/dedalus_current_sheet_default"))
    parser.add_argument("--nx", type=int, default=BenchmarkConfig.nx)
    parser.add_argument("--nz", type=int, default=BenchmarkConfig.nz)
    parser.add_argument("--lx", type=float, default=BenchmarkConfig.lx)
    parser.add_argument("--lz", type=float, default=BenchmarkConfig.lz)
    parser.add_argument("--eta", type=float, default=BenchmarkConfig.eta)
    parser.add_argument("--nu", type=float, default=BenchmarkConfig.nu)
    parser.add_argument("--delta0", type=float, default=BenchmarkConfig.delta0)
    parser.add_argument("--perturbation-amplitude", type=float, default=BenchmarkConfig.perturbation_amplitude)
    parser.add_argument("--perturbation-kx", type=int, default=BenchmarkConfig.perturbation_kx)
    parser.add_argument("--timestep", type=float, default=BenchmarkConfig.timestep)
    parser.add_argument("--stop-time", type=float, default=BenchmarkConfig.stop_time)
    parser.add_argument("--diagnostic-cadence", type=int, default=BenchmarkConfig.diagnostic_cadence)
    parser.add_argument("--snapshot-cadence", type=int, default=BenchmarkConfig.snapshot_cadence)
    parser.add_argument("--control-aspect-threshold", type=float, default=BenchmarkConfig.control_aspect_threshold)
    parser.add_argument("--control-strength", type=float, default=BenchmarkConfig.control_strength)
    parser.add_argument("--control-width", type=float, default=BenchmarkConfig.control_width)
    parser.add_argument("--onset-island-count-threshold", type=int, default=BenchmarkConfig.onset_island_count_threshold)
    parser.add_argument("--island-o-point-prominence", type=float, default=BenchmarkConfig.island_o_point_prominence)
    parser.add_argument("--component-threshold-fraction", type=float, default=BenchmarkConfig.component_threshold_fraction)
    parser.add_argument("--component-min-cells", type=int, default=BenchmarkConfig.component_min_cells)
    parser.add_argument("--drive-enabled", action="store_true")
    parser.add_argument("--drive-start-time", type=float, default=BenchmarkConfig.drive_start_time)
    parser.add_argument("--drive-end-time", type=float, default=BenchmarkConfig.drive_end_time)
    parser.add_argument("--drive-strength", type=float, default=BenchmarkConfig.drive_strength)
    parser.add_argument("--drive-kx", type=int, default=BenchmarkConfig.drive_kx)
    parser.add_argument("--drive-width", type=float, default=BenchmarkConfig.drive_width)
    parser.add_argument("--bias-enabled", action="store_true")
    parser.add_argument(
        "--bias-mode",
        choices=("standing", "triggered", "rib_matrix", "mesh", "phase_locked_rib"),
        default=BenchmarkConfig.bias_mode,
    )
    parser.add_argument("--bias-strength", type=float, default=BenchmarkConfig.bias_strength)
    parser.add_argument("--bias-polarity", type=float, default=BenchmarkConfig.bias_polarity)
    parser.add_argument("--bias-kx", type=int, default=BenchmarkConfig.bias_kx)
    parser.add_argument("--bias-width", type=float, default=BenchmarkConfig.bias_width)
    parser.add_argument("--bias-aspect-threshold", type=float, default=BenchmarkConfig.bias_aspect_threshold)
    parser.add_argument("--bias-rib-count", type=int, default=BenchmarkConfig.bias_rib_count)
    parser.add_argument("--bias-rib-duty", type=float, default=BenchmarkConfig.bias_rib_duty)
    parser.add_argument("--bias-phase", type=float, default=BenchmarkConfig.bias_phase)
    parser.add_argument("--case", choices=("both", "baseline", "perturbed"), default="both")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args.run_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    if args.case in {"both", "baseline"}:
        summaries.append(run_case("baseline", build_config(args, control_enabled=False), args.run_dir))
    if args.case in {"both", "perturbed"}:
        summaries.append(run_case("tct_style_perturbed", build_config(args, control_enabled=True), args.run_dir))
    output = {
        "artifact_type": "dedalus_reduced_mhd_toy_benchmark",
        "not_reactor_claim": True,
        "not_tokamak_validation": True,
        "cases": summaries,
    }
    (args.run_dir / "benchmark_summary.json").write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

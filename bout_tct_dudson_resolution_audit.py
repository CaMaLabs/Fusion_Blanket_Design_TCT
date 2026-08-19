#!/usr/bin/env python3
"""Dudson-aligned fixed-physics BOUT++ current-sheet resolution audit.

This reuses the repository's existing tct_current_sheet BOUT++ model but fixes a
convergence weakness in the historical coarse/base sweep: the current-sheet
width is held constant while the grid is refined.

This is a fixed-grid convergence / resolution falsification study.
It is NOT adaptive mesh refinement and NOT M3D-C1 validation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import netCDF4
import numpy as np

import bout_tct_current_sheet_sweep as legacy


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "bout_tct_dudson_resolution_default"

DEFAULT_GRIDS = (64, 96, 128, 192, 256)
CONTROLS = (0.0, 0.8)

# Freeze the same physical/numerical problem across every grid.
SHEET_WIDTH = 0.055
DOMAIN_X_METRIC = 11.52
DOMAIN_Z_METRIC = 11.52


def parse_grids(text: str) -> list[int]:
    values = sorted({int(v.strip()) for v in text.split(",") if v.strip()})
    if len(values) < 2:
        raise ValueError("Need at least two grid resolutions")
    if any(v < 16 for v in values):
        raise ValueError("Grid resolutions below 16 are not supported")
    return values


def git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        return None


def grid_spec(nx: int) -> dict[str, Any]:
    nz = nx
    return {
        "name": f"n{nx}",
        "nx": nx,
        "nz": nz,
        "dx": DOMAIN_X_METRIC / nx,
        "dz": DOMAIN_Z_METRIC / nz,
        "sheet_width": SHEET_WIDTH,
    }


def write_input(
    case_dir: Path,
    grid: dict[str, Any],
    params: dict[str, float],
    nout: int,
) -> None:
    legacy._write_inp(case_dir, grid, params, nout)
    inp = case_dir / "BOUT.inp"
    text = inp.read_text(encoding="utf-8")
    marker = "[mesh]\n"
    if marker not in text:
        raise RuntimeError(f"[mesh] section missing from {inp}")
    text = text.replace(marker, "[mesh]\nsymmetricGlobalX = true\n", 1)
    inp.write_text(text, encoding="utf-8")


def strip_x_guards(values: np.ndarray) -> np.ndarray:
    if values.ndim >= 2 and values.shape[1] > 8:
        return values[:, 2:-2, ...]
    return values


def contiguous_fwhm_cells(profile: np.ndarray) -> float:
    profile = np.asarray(profile, dtype=float)
    if profile.size == 0 or not np.isfinite(profile).any():
        return float("nan")

    peak = int(np.nanargmax(profile))
    vmax = float(profile[peak])
    if vmax <= 0.0 or not math.isfinite(vmax):
        return float("nan")

    threshold = 0.5 * vmax
    left = peak
    while left > 0 and profile[left - 1] >= threshold:
        left -= 1

    right = peak
    while right + 1 < profile.size and profile[right + 1] >= threshold:
        right += 1

    return float(right - left + 1)


def sheet_width_at_time(abs_j: np.ndarray, t_index: int) -> tuple[float, int, int]:
    frame = np.asarray(abs_j[t_index], dtype=float)

    if frame.ndim == 1:
        return contiguous_fwhm_cells(frame), 0, 0

    location = np.unravel_index(int(np.nanargmax(frame)), frame.shape)

    if frame.ndim == 2:
        zidx = int(location[1])
        return contiguous_fwhm_cells(frame[:, zidx]), 0, zidx

    yidx = int(location[1])
    zidx = int(location[2])
    return contiguous_fwhm_cells(frame[:, yidx, zidx]), yidx, zidx


def analyze(case_dir: Path, grid: dict[str, Any]) -> dict[str, float]:
    output = case_dir / "BOUT.dmp.0.nc"
    if not output.exists():
        raise FileNotFoundError(output)

    with netCDF4.Dataset(output) as ds:
        J = np.asarray(ds.variables["J"][:], dtype=float)
        psi = np.asarray(ds.variables["psi"][:], dtype=float)
        omega = np.asarray(ds.variables["omega"][:], dtype=float)
        time = np.asarray(ds.variables["t_array"][:], dtype=float)

    J = strip_x_guards(J)
    psi = strip_x_guards(psi)
    omega = strip_x_guards(omega)

    abs_j = np.abs(J)
    axes = tuple(range(1, abs_j.ndim))
    max_j = np.max(abs_j, axis=axes)
    p99_j = np.percentile(abs_j.reshape(abs_j.shape[0], -1), 99, axis=1)

    t_peak = int(np.argmax(max_j))
    initial_fwhm_cells, _, _ = sheet_width_at_time(abs_j, 0)
    peak_fwhm_cells, peak_y, peak_z = sheet_width_at_time(abs_j, t_peak)
    final_fwhm_cells, _, _ = sheet_width_at_time(abs_j, len(time) - 1)

    nx_interior = int(abs_j.shape[1])
    initial_fwhm_norm = initial_fwhm_cells / nx_interior
    peak_fwhm_norm = peak_fwhm_cells / nx_interior
    final_fwhm_norm = final_fwhm_cells / nx_interior

    # Reduced topology-sensitive proxy.
    # This is intentionally NOT called a formal reconnection rate.
    xmid = nx_interior // 2

    if psi.ndim == 4:
        psi_center = psi[:, xmid, 0, :]
    elif psi.ndim == 3:
        psi_center = psi[:, xmid, :]
    else:
        psi_center = psi[:, xmid:xmid + 1]

    psi_span = np.max(psi_center, axis=-1) - np.min(psi_center, axis=-1)

    if len(time) > 1:
        psi_span_rate = np.gradient(psi_span, time)
        max_abs_psi_span_rate = float(np.max(np.abs(psi_span_rate)))
    else:
        max_abs_psi_span_rate = float("nan")

    magnetic_energy = 0.5 * np.mean(
        psi * psi, axis=tuple(range(1, psi.ndim))
    )

    max_omega = np.max(
        np.abs(omega), axis=tuple(range(1, omega.ndim))
    )

    return {
        "time_start": float(time[0]),
        "time_end": float(time[-1]),
        "max_abs_J": float(np.max(max_j)),
        "post_initial_max_abs_J": (
            float(np.max(max_j[1:])) if len(max_j) > 1 else float(max_j[0])
        ),
        "time_integrated_max_abs_J": float(np.trapezoid(max_j, time)),
        "max_abs_J_p99": float(np.max(p99_j)),
        "max_abs_omega": float(np.max(max_omega)),
        "initial_sheet_fwhm_cells": initial_fwhm_cells,
        "peak_sheet_fwhm_cells": peak_fwhm_cells,
        "final_sheet_fwhm_cells": final_fwhm_cells,
        "initial_sheet_fwhm_normalized_x": initial_fwhm_norm,
        "peak_sheet_fwhm_normalized_x": peak_fwhm_norm,
        "final_sheet_fwhm_normalized_x": final_fwhm_norm,
        "peak_sheet_fwhm_metric_proxy": peak_fwhm_cells * float(grid["dx"]),
        "peak_J_time": float(time[t_peak]),
        "peak_J_y_index": float(peak_y),
        "peak_J_z_index": float(peak_z),
        "initial_psi_center_span": float(psi_span[0]),
        "final_psi_center_span": float(psi_span[-1]),
        "max_abs_psi_center_span_rate_proxy": max_abs_psi_span_rate,
        "initial_magnetic_energy_proxy": float(magnetic_energy[0]),
        "final_magnetic_energy_proxy": float(magnetic_energy[-1]),
    }


def rel_diff(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-300)


def reduction(control: float, tct: float) -> float:
    return 1.0 - tct / control if control else float("nan")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []

    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
    )

    ap.add_argument(
        "--grids",
        default=",".join(str(x) for x in DEFAULT_GRIDS),
        help="comma-separated nx values; nz follows nx",
    )

    ap.add_argument(
        "--nout",
        type=int,
        default=20,
    )

    ap.add_argument(
        "--bout-build",
        type=Path,
        default=Path(legacy.DEFAULT_BOUT_BUILD),
        help="BOUT++ CMake package/build path",
    )

    ap.add_argument(
        "--skip-build",
        action="store_true",
    )

    ap.add_argument(
        "--executable",
        type=Path,
        default=None,
        help="Use an already-built tct_current_sheet executable",
    )

    ap.add_argument(
        "--mpirun",
        type=Path,
        default=Path("/usr/bin/mpirun.openmpi"),
        help="MPI launcher used for BOUT++ cases",
    )

    ap.add_argument(
        "--min-sheet-cells",
        type=float,
        default=8.0,
        help=(
            "configurable operational adequacy heuristic; "
            "not a literature-derived threshold"
        ),
    )

    ap.add_argument(
        "--effect-convergence-tol",
        type=float,
        default=0.10,
        help=(
            "maximum relative change between the two finest grids "
            "for the main controlled-vs-uncontrolled effect metrics"
        ),
    )

    ap.add_argument(
        "--keep-existing",
        action="store_true",
    )

    args = ap.parse_args()

    grids = [grid_spec(nx) for nx in parse_grids(args.grids)]
    run_dir = args.run_dir.resolve()

    if run_dir.exists() and not args.keep_existing:
        shutil.rmtree(run_dir)

    run_dir.mkdir(parents=True, exist_ok=True)

    _design, plasma, reactor = legacy._evaluate_base()

    if args.executable is not None:
        exe = args.executable.resolve()
        if not exe.exists():
            raise FileNotFoundError(f"Executable not found: {exe}")

    else:
        exe = legacy.BUILD_DIR / "tct_current_sheet"

        if not args.skip_build:
            exe = legacy._build_model(args.bout_build)

        elif not exe.exists():
            raise FileNotFoundError(
                f"--skip-build requested but executable does not exist: {exe}"
            )

    rows: list[dict[str, Any]] = []

    for grid in grids:
        for control in CONTROLS:

            params = legacy._params(
                plasma,
                reactor,
                grid,
                control,
            )

            # Freeze identical current-sheet and actuator geometry
            # on every mesh.
            params["sheet_width"] = SHEET_WIDTH
            params["actuator_width"] = 1.7 * SHEET_WIDTH

            case_name = (
                f"{grid['name']}_fixedphysics_"
                f"tct{int(round(control * 100)):03d}"
            )

            case_dir = run_dir / case_name

            write_input(
                case_dir,
                grid,
                params,
                args.nout,
            )

            result = subprocess.run(
                [
                    str(args.mpirun),
                    "-n",
                    "1",
                    str(exe),
                    "-d",
                    str(case_dir),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            (case_dir / "bout_stdout.log").write_text(
                result.stdout,
                encoding="utf-8",
            )

            (case_dir / "bout_stderr.log").write_text(
                result.stderr,
                encoding="utf-8",
            )

            if result.returncode != 0:
                print(result.stdout[-4000:])
                print(result.stderr[-4000:])
                raise RuntimeError(
                    f"BOUT++ failed for {case_name}: "
                    f"return code {result.returncode}"
                )

            diag = analyze(
                case_dir,
                grid,
            )

            row = {
                "case": case_name,
                "grid": grid["name"],
                "nx": grid["nx"],
                "nz": grid["nz"],
                "dx": grid["dx"],
                "dz": grid["dz"],
                "control": control,
                "sheet_width_input_normalized_x": SHEET_WIDTH,
                "actuator_width_input_normalized_x": 1.7 * SHEET_WIDTH,
                **params,
                **diag,
            }

            rows.append(row)

            (case_dir / "summary.json").write_text(
                json.dumps(
                    row,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            print(
                f"[ok] nx={grid['nx']} "
                f"control={control:.1f} "
                f"peakJ={diag['post_initial_max_abs_J']:.6g} "
                f"peak-sheet={diag['peak_sheet_fwhm_cells']:.1f} cells",
                flush=True,
            )

    by_nx: dict[int, dict[float, dict[str, Any]]] = {}

    for row in rows:
        by_nx.setdefault(
            int(row["nx"]),
            {},
        )[float(row["control"])] = row

    effects: list[dict[str, Any]] = []

    for nx in sorted(by_nx):

        pair = by_nx[nx]
        base = pair[0.0]
        tct = pair[0.8]

        effects.append(
            {
                "nx": nx,
                "nz": int(base["nz"]),

                "uncontrolled_peak_sheet_fwhm_cells":
                    float(base["peak_sheet_fwhm_cells"]),

                "controlled_peak_sheet_fwhm_cells":
                    float(tct["peak_sheet_fwhm_cells"]),

                "min_peak_sheet_fwhm_cells":
                    min(
                        float(base["peak_sheet_fwhm_cells"]),
                        float(tct["peak_sheet_fwhm_cells"]),
                    ),

                "peak_J_reduction_fraction":
                    reduction(
                        float(base["post_initial_max_abs_J"]),
                        float(tct["post_initial_max_abs_J"]),
                    ),

                "integrated_J_reduction_fraction":
                    reduction(
                        float(base["time_integrated_max_abs_J"]),
                        float(tct["time_integrated_max_abs_J"]),
                    ),

                "psi_span_rate_proxy_change_fraction":
                    (
                        float(
                            tct["max_abs_psi_center_span_rate_proxy"]
                        )
                        /
                        max(
                            float(
                                base[
                                    "max_abs_psi_center_span_rate_proxy"
                                ]
                            ),
                            1e-300,
                        )
                        - 1.0
                    ),

                "magnetic_energy_final_change_fraction":
                    (
                        float(
                            tct["final_magnetic_energy_proxy"]
                        )
                        /
                        max(
                            float(
                                base["final_magnetic_energy_proxy"]
                            ),
                            1e-300,
                        )
                        - 1.0
                    ),
            }
        )

    fine_a, fine_b = effects[-2], effects[-1]

    convergence = {
        "finest_pair": [
            fine_a["nx"],
            fine_b["nx"],
        ],

        "peak_J_effect_relative_difference":
            rel_diff(
                float(
                    fine_a[
                        "peak_J_reduction_fraction"
                    ]
                ),
                float(
                    fine_b[
                        "peak_J_reduction_fraction"
                    ]
                ),
            ),

        "integrated_J_effect_relative_difference":
            rel_diff(
                float(
                    fine_a[
                        "integrated_J_reduction_fraction"
                    ]
                ),
                float(
                    fine_b[
                        "integrated_J_reduction_fraction"
                    ]
                ),
            ),

        "psi_span_rate_effect_relative_difference":
            rel_diff(
                float(
                    fine_a[
                        "psi_span_rate_proxy_change_fraction"
                    ]
                ),
                float(
                    fine_b[
                        "psi_span_rate_proxy_change_fraction"
                    ]
                ),
            ),
    }

    finest_sheet_resolved = (
        float(
            fine_b[
                "min_peak_sheet_fwhm_cells"
            ]
        )
        >= args.min_sheet_cells
    )

    effect_converged = (
        convergence[
            "peak_J_effect_relative_difference"
        ]
        <= args.effect_convergence_tol
        and
        convergence[
            "integrated_J_effect_relative_difference"
        ]
        <= args.effect_convergence_tol
    )

    status = (
        "FIXED_GRID_EFFECT_CONVERGED_AT_CONFIGURED_GATE"
        if finest_sheet_resolved and effect_converged
        else
        "FIXED_GRID_EFFECT_NOT_YET_CONVERGED"
    )

    summary = {
        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "git_commit":
            git_head(),

        "status":
            status,

        "claim_boundary":
            (
                "Global fixed-grid BOUT++ resolution falsification only. "
                "This is not adaptive mesh refinement, "
                "not a formal reconnection-rate measurement, "
                "and not M3D-C1/topology-changing validation."
            ),

        "frozen_physics": {
            "sheet_width_normalized_x":
                SHEET_WIDTH,

            "controls":
                list(CONTROLS),

            "eta":
                float(rows[0]["eta"]),

            "nu":
                float(rows[0]["nu"]),

            "psi_amp":
                float(rows[0]["psi_amp"]),

            "island_seed":
                float(rows[0]["island_seed"]),

            "omega_seed":
                float(rows[0]["omega_seed"]),
        },

        "resolution_gate": {
            "min_sheet_cells_heuristic":
                args.min_sheet_cells,

            "effect_convergence_tolerance":
                args.effect_convergence_tol,

            "finest_sheet_resolved":
                finest_sheet_resolved,

            "effect_converged":
                effect_converged,
        },

        "effects_by_grid":
            effects,

        "finest_pair_convergence":
            convergence,

        "m3dc1_handoff_observables": [
            "current-sheet width/thickness versus time",
            "peak and integrated current density",
            "magnetic topology / island evolution",
            "reconnection rate from a topology-aware flux diagnostic",
            "magnetic-energy release",
            "controlled-versus-uncontrolled event timing",
        ],
    }

    write_csv(
        run_dir / "dudson_resolution_results.csv",
        rows,
    )

    write_csv(
        run_dir / "dudson_resolution_effects.csv",
        effects,
    )

    (
        run_dir
        / "dudson_resolution_summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (
        run_dir
        / "M3DC1_HANDOFF.json"
    ).write_text(
        json.dumps(
            {
                "source":
                    "bout_tct_dudson_resolution_audit",

                "git_commit":
                    summary["git_commit"],

                "status":
                    status,

                "finest_grid":
                    fine_b,

                "observables":
                    summary[
                        "m3dc1_handoff_observables"
                    ],

                "claim_boundary":
                    summary[
                        "claim_boundary"
                    ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = f"""# Dudson-aligned BOUT++ current-sheet resolution audit

Status: `{status}`

This study freezes the current-sheet initial condition and TCT actuator width
while refining the global BOUT++ mesh.

It tests whether the reported TCT effect survives better resolution of the
current sheet.

It is **not adaptive mesh refinement** and does not replace M3D-C1
topology-changing validation.

Finest pair: `{fine_a['nx']} -> {fine_b['nx']}`

- Finest minimum measured peak-sheet FWHM:
  `{fine_b['min_peak_sheet_fwhm_cells']:.3f}` cells

- Configured adequacy heuristic:
  `{args.min_sheet_cells:.3f}` cells

- Peak-J effect relative change:
  `{convergence['peak_J_effect_relative_difference']:.6g}`

- Integrated-J effect relative change:
  `{convergence['integrated_J_effect_relative_difference']:.6g}`

- Configured effect-convergence tolerance:
  `{args.effect_convergence_tol:.6g}`

## Interpretation boundary

The `psi` centre-span derivative is a topology-sensitive reduced proxy,
not a formal reconnection rate.

A favorable result supports promotion to M3D-C1 using topology/island
evolution and a code-native reconnection diagnostic.

A failure means the present BOUTresolution-sensitive
and should not be promoted as physical.
"""

    (
        run_dir
        / "DUDSON_RESOLUTION_AUDIT_REPORT.md"
    ).write_text(
        report,
        encoding="utf-8",
    )

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        0
        if status
        == "FIXED_GRID_EFFECT_CONVERGED_AT_CONFIGURED_GATE"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())

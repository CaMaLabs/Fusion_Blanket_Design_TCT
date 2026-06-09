#!/usr/bin/env python3
"""Apply predictive TCT control on a reduced DIII-D EFIT R-Z flux grid."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from closed_loop_tct_validation import _add_reductions, _write_csv


REPO = Path(__file__).resolve().parent
DEFAULT_GEQDSK = REPO / "validation_inputs" / "geqdsk_efit_baseline" / "diii_d_158103_03796" / "geqdsk"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "efit_predictive_tct_validation_default"
FLOAT_RE = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][+-]?\d+)?")
GRIDS = (
    {"name": "coarse", "stride": 2, "dt": 0.02},
    {"name": "native", "stride": 1, "dt": 0.01},
)
STRATEGIES = {
    "uncontrolled": {"control": 0.0, "feedback": False, "feedback_mode": 0, "threshold": 0.15, "delay": 0.0, "noise": 0.0},
    "fixed_moderate": {"control": 0.8, "feedback": False, "feedback_mode": 0, "threshold": 0.15, "delay": 0.0, "noise": 0.0},
    "magnitude_threshold": {"control": 0.8, "feedback": True, "feedback_mode": 0, "threshold": 0.15, "delay": 0.0, "noise": 0.0},
    "predictive_growth": {"control": 0.8, "feedback": True, "feedback_mode": 1, "threshold": 0.03, "delay": 0.0, "noise": 0.0},
    "predictive_noisy_delayed": {"control": 0.8, "feedback": True, "feedback_mode": 1, "threshold": 0.03, "delay": 0.5, "noise": 0.10},
    "fixed_strong": {"control": 1.2, "feedback": False, "feedback_mode": 0, "threshold": 0.15, "delay": 0.0, "noise": 0.0},
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_geqdsk(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    dimensions = [int(item) for item in re.findall(r"[+-]?\d+", lines[0])]
    nw, nh = dimensions[-2:]
    values = [float(item.replace("D", "E").replace("d", "e")) for item in FLOAT_RE.findall("\n".join(lines[1:]))]
    scalars = values[:20]
    start = 20 + 4 * nw
    psi = np.asarray(values[start : start + nw * nh], dtype=float).reshape((nh, nw))
    r = np.linspace(scalars[3], scalars[3] + scalars[0], nw)
    z = np.linspace(scalars[4] - 0.5 * scalars[1], scalars[4] + 0.5 * scalars[1], nh)
    return {
        "header": lines[0].strip(),
        "nw": nw,
        "nh": nh,
        "psi": psi,
        "r": r,
        "z": z,
        "simag": scalars[7],
        "sibry": scalars[8],
        "rmaxis": scalars[5],
        "zmaxis": scalars[6],
        "bcentr_t": scalars[9],
        "current_a": scalars[10],
    }


def _laplacian(field: np.ndarray, dr: float, dz: float) -> np.ndarray:
    result = np.zeros_like(field)
    result[1:-1, 1:-1] = (
        (field[1:-1, 2:] - 2.0 * field[1:-1, 1:-1] + field[1:-1, :-2]) / (dr * dr)
        + (field[2:, 1:-1] - 2.0 * field[1:-1, 1:-1] + field[:-2, 1:-1]) / (dz * dz)
    )
    return result


def _geometry(equilibrium: dict[str, Any], stride: int) -> dict[str, Any]:
    psi = equilibrium["psi"][::stride, ::stride]
    r = equilibrium["r"][::stride]
    z = equilibrium["z"][::stride]
    rr, zz = np.meshgrid(r, z)
    psin = (psi - equilibrium["simag"]) / (equilibrium["sibry"] - equilibrium["simag"])
    edge_mask = np.exp(-((psin - 0.9) / 0.09) ** 2) * ((psin >= 0.0) & (psin <= 1.1))
    poloidal_angle = np.arctan2(zz - equilibrium["zmaxis"], rr - equilibrium["rmaxis"])
    source = edge_mask * np.sin(3.0 * poloidal_angle)
    source /= float(np.max(np.abs(source)))
    return {
        "psi": psi,
        "psin": psin,
        "r": r,
        "z": z,
        "dr": float(r[1] - r[0]),
        "dz": float(z[1] - z[0]),
        "edge_mask": edge_mask,
        "source": source,
    }


def _run_case(grid: dict[str, Any], strategy_name: str, strategy: dict[str, Any], geometry: dict[str, Any]) -> dict[str, Any]:
    dt = float(grid["dt"])
    t_end = 12.0
    steps = int(round(t_end / dt))
    controller_every = max(1, int(round(0.1 / dt)))
    perturbation = np.zeros_like(geometry["psi"])
    trigger_time = -1.0
    filtered = 0.0
    previous_filtered = 0.0
    signal = 0.0
    gate = 0.0
    times: list[float] = []
    max_current: list[float] = []
    energies: list[float] = []
    gates: list[float] = []

    for step in range(steps + 1):
        time = step * dt
        current = np.abs(_laplacian(perturbation, geometry["dr"], geometry["dz"]))
        observable = float(np.max(current))
        if step % controller_every == 0:
            measured = observable * (1.0 + float(strategy["noise"]) * np.sin(1.61803398875 * time))
            previous_filtered = filtered
            filtered = 0.5 * measured + 0.5 * filtered
            growth = (filtered - previous_filtered) / (controller_every * dt)
            signal = growth if int(strategy["feedback_mode"]) == 1 else filtered
            if bool(strategy["feedback"]) and trigger_time < 0.0 and time >= 2.0 and signal >= float(strategy["threshold"]):
                trigger_time = time
        if bool(strategy["feedback"]):
            gate = 1.0 if trigger_time >= 0.0 and time >= trigger_time + float(strategy["delay"]) else 0.0
        else:
            gate = 1.0 if float(strategy["control"]) > 0.0 else 0.0
        if step % controller_every == 0:
            times.append(time)
            max_current.append(observable)
            energies.append(float(np.mean(perturbation * perturbation)))
            gates.append(gate)
        if step == steps:
            break
        drive_ramp = float(np.clip((time - 2.0) / 2.0, 0.0, 1.0))
        diffusion = 2.0e-4 * _laplacian(perturbation, geometry["dr"], geometry["dz"])
        source = 1.2e-4 * drive_ramp * geometry["source"]
        actuator = gate * float(strategy["control"]) * 0.3 * geometry["edge_mask"] * perturbation
        perturbation += dt * (diffusion + source - actuator)
        perturbation[[0, -1], :] = 0.0
        perturbation[:, [0, -1]] = 0.0

    peak_index = int(np.argmax(max_current))
    return {
        "model": "DIII-D EFIT R-Z reduced flux",
        "grid": grid["name"],
        "nr": int(geometry["psi"].shape[1]),
        "nz": int(geometry["psi"].shape[0]),
        "strategy": strategy_name,
        **strategy,
        "feedback_trigger_time": trigger_time,
        "uncontrolled_peak_time": times[peak_index],
        "peak_perturbation_current": float(np.max(max_current)),
        "time_integrated_perturbation_current": float(np.trapz(max_current, times)),
        "peak_perturbation_energy": float(np.max(energies)),
        "time_integrated_perturbation_energy": float(np.trapz(energies, times)),
        "control_duty_fraction": float(np.mean(np.asarray(gates) > 0.5)),
        "control_effort": float(np.trapz(gates, times)),
    }


def _checks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for grid in sorted({str(row["grid"]) for row in rows}):
        group = {str(row["strategy"]): row for row in rows if row["grid"] == grid}
        uncontrolled = group["uncontrolled"]
        moderate = group["fixed_moderate"]
        magnitude = group["magnitude_threshold"]
        predictive = group["predictive_growth"]
        noisy = group["predictive_noisy_delayed"]
        strong = group["fixed_strong"]
        output.append(
            {
                "grid": grid,
                "predictive_trigger_time": predictive["feedback_trigger_time"],
                "magnitude_trigger_time": magnitude["feedback_trigger_time"],
                "uncontrolled_peak_time": uncontrolled["uncontrolled_peak_time"],
                "predictive_triggers_before_magnitude": float(predictive["feedback_trigger_time"]) < float(magnitude["feedback_trigger_time"]),
                "predictive_triggers_before_peak": float(predictive["feedback_trigger_time"]) < float(uncontrolled["uncontrolled_peak_time"]),
                "predictive_reduces_peak": float(predictive["peak_perturbation_current"]) < float(uncontrolled["peak_perturbation_current"]),
                "predictive_reduces_integrated": float(predictive["time_integrated_perturbation_current"]) < float(uncontrolled["time_integrated_perturbation_current"]),
                "predictive_within_20pct_fixed_moderate": float(predictive["time_integrated_perturbation_current"]) <= 1.2 * float(moderate["time_integrated_perturbation_current"]),
                "predictive_effort_below_fixed_strong": float(predictive["control_effort"]) < float(strong["control_effort"]),
                "noisy_delayed_reduces_peak": float(noisy["peak_perturbation_current"]) < float(uncontrolled["peak_perturbation_current"]),
                "noisy_delayed_reduces_integrated": float(noisy["time_integrated_perturbation_current"]) < float(uncontrolled["time_integrated_perturbation_current"]),
            }
        )
    return output


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# DIII-D EFIT-Grid Predictive TCT Validation",
        "",
        f"- Status: `{summary['status']}`",
        f"- GEQDSK: `{summary['equilibrium']['header']}`",
        f"- GEQDSK SHA-256: `{summary['equilibrium']['sha256']}`",
        "",
        "This campaign evolves a reduced perturbation-flux equation directly on the real DIII-D EFIT R-Z grid. The EFIT normalized-flux separatrix geometry defines both the edge perturbation and actuator localization. The delayed perturbation drive is synthetic.",
        "",
        "| Grid | Predictive time | Magnitude time | Peak time | Earlier than magnitude | Before peak | Peak reduced | Integrated reduced | Noisy/delayed peak reduced | Noisy/delayed integrated reduced |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["checks"]:
        lines.append(
            f"| {row['grid']} | {row['predictive_trigger_time']:.3f} | {row['magnitude_trigger_time']:.3f} | "
            f"{row['uncontrolled_peak_time']:.3f} | {row['predictive_triggers_before_magnitude']} | "
            f"{row['predictive_triggers_before_peak']} | {row['predictive_reduces_peak']} | "
            f"{row['predictive_reduces_integrated']} | {row['noisy_delayed_reduces_peak']} | "
            f"{row['noisy_delayed_reduces_integrated']} |"
        )
    lines.extend(["", "## Interpretation", "", summary["interpretation"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geqdsk", type=Path, default=DEFAULT_GEQDSK)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    equilibrium = _read_geqdsk(args.geqdsk)
    rows: list[dict[str, Any]] = []
    geometry_summary = []
    for grid in GRIDS:
        geometry = _geometry(equilibrium, int(grid["stride"]))
        geometry_summary.append(
            {
                "grid": grid["name"],
                "nr": int(geometry["psi"].shape[1]),
                "nz": int(geometry["psi"].shape[0]),
                "dr_m": geometry["dr"],
                "dz_m": geometry["dz"],
                "active_edge_mask_fraction": float(np.mean(geometry["edge_mask"] > 0.1)),
            }
        )
        for name, strategy in STRATEGIES.items():
            rows.append(_run_case(grid, name, strategy, geometry))
    _add_reductions(rows, ("peak_perturbation_current", "time_integrated_perturbation_current"))
    checks = _checks(rows)
    non_boolean = {"grid", "predictive_trigger_time", "magnitude_trigger_time", "uncontrolled_peak_time"}
    supported = all(all(value for key, value in row.items() if key not in non_boolean) for row in checks)
    status = "DIIID_EFIT_GRID_PREDICTIVE_REDUCED_SUPPORTED" if supported else "DIIID_EFIT_GRID_PREDICTIVE_REDUCED_MIXED"
    interpretation = (
        "PASS: one predictive controller configuration triggers before magnitude feedback and the uncontrolled peak on native and coarse DIII-D EFIT grids, reduces peak and integrated perturbation current, remains beneficial with noise and delay, and approaches fixed-moderate performance with lower effort than fixed strong control. This is an EFIT-backed reduced R-Z model, not a field-aligned BOUT++ or nonlinear M3D-C1 machine-geometry validation; the perturbation drive is synthetic and raw diagnostic timing is unavailable."
        if supported
        else "MIXED: at least one EFIT-grid predictive criterion failed. Inspect the per-grid checks."
    )
    summary = {
        "status": status,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "equilibrium": {
            "machine": "DIII-D",
            "shot_time": "158103 @ 3796 ms",
            "path": str(args.geqdsk),
            "sha256": _sha256(args.geqdsk),
            "header": equilibrium["header"],
            "native_grid": [equilibrium["nw"], equilibrium["nh"]],
            "bcentr_t": equilibrium["bcentr_t"],
            "current_a": equilibrium["current_a"],
        },
        "geometry": geometry_summary,
        "controller": {
            "observable": "max_abs_laplacian_perturbation_flux",
            "magnitude_threshold": 0.15,
            "growth_threshold": 0.03,
            "controller_interval": 0.1,
            "filter": "ema_0.5",
            "noisy_delayed_case": {"noise_fraction": 0.10, "delay": 0.5},
        },
        "checks": checks,
        "interpretation": interpretation,
    }
    _write_csv(run_dir / "efit_predictive_results.csv", rows)
    (run_dir / "efit_predictive_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(run_dir / "efit_predictive_report.md", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

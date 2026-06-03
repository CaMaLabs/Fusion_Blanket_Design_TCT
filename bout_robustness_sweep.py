#!/usr/bin/env python3
"""Run BOUT++ robustness and falsification checks for the conduction proxy."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bout_controlled_sweep import _case_name, _sweep_params
from bout_validation_bridge import (
    DEFAULT_BOUT_BUILD,
    DEFAULT_BOUT_TOP,
    REPO,
    _evaluate_design,
    _mapped_bout_parameters,
    _run_bout,
    _summarize_output,
    _write_bout_inp,
)


CONTROLS = (0.0, 0.5, 1.0)
DOMAIN_LENGTH = 20.0


def _mapping_params(base_params: dict[str, float], control: float, mapping: str) -> dict[str, float]:
    if mapping == "diffusivity":
        params = _sweep_params(base_params, control, 1.0)
    elif mapping == "amplitude":
        params = _sweep_params(base_params, 0.0, 1.0)
        params["t_scale"] *= 1.0 - 0.4 * control
        params["tct_control_strength"] = control
    elif mapping == "width":
        params = _sweep_params(base_params, 0.0, 1.0)
        params["gaussian_width"] = min(0.6, params["gaussian_width"] * (1.0 + control))
        params["tct_control_strength"] = control
    else:
        raise ValueError(f"Unknown mapping: {mapping}")

    params["control_mapping"] = mapping
    return params


def _case_specs(base_params: dict[str, float]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []

    for ny in (50, 100, 200):
        for control in CONTROLS:
            specs.append(
                {
                    "group": "resolution",
                    "case": f"resolution_ny{ny}_{_case_name(control, 1.0)}",
                    "params": _mapping_params(base_params, control, "diffusivity"),
                    "ny": ny,
                    "dy": DOMAIN_LENGTH / ny,
                    "boundary": "dirichlet_o4(0.0)",
                }
            )

    for boundary_name, boundary in (
        ("dirichlet_o2", "dirichlet_o2(0.0)"),
        ("dirichlet_o4", "dirichlet_o4(0.0)"),
        ("neumann", "neumann"),
    ):
        for control in CONTROLS:
            specs.append(
                {
                    "group": "boundary",
                    "case": f"boundary_{boundary_name}_{_case_name(control, 1.0)}",
                    "params": _mapping_params(base_params, control, "diffusivity"),
                    "ny": 100,
                    "dy": 0.2,
                    "boundary": boundary,
                }
            )

    for mapping in ("diffusivity", "amplitude", "width"):
        for control in CONTROLS:
            specs.append(
                {
                    "group": "mapping",
                    "case": f"mapping_{mapping}_{_case_name(control, 1.0)}",
                    "params": _mapping_params(base_params, control, mapping),
                    "ny": 100,
                    "dy": 0.2,
                    "boundary": "dirichlet_o4(0.0)",
                }
            )

    return specs


def _row(spec: dict[str, Any], case_dir: Path, bout_summary: dict[str, float]) -> dict[str, Any]:
    params = spec["params"]
    return {
        "group": spec["group"],
        "case": spec["case"],
        "case_dir": str(case_dir),
        "control_mapping": params["control_mapping"],
        "tct_control_strength": params["tct_control_strength"],
        "ny": spec["ny"],
        "dy": spec["dy"],
        "boundary": spec["boundary"],
        "chi": params["chi"],
        "t_scale": params["t_scale"],
        "gaussian_width": params["gaussian_width"],
        "initial_peak_abs_T": bout_summary["initial_peak_abs_T"],
        "final_peak_abs_T": bout_summary["final_peak_abs_T"],
        "peak_decay_ratio": bout_summary["peak_decay_ratio"],
        "mean_peak_abs_T": bout_summary["mean_peak_abs_T"],
    }


def _trend(items: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(items, key=lambda row: float(row["tct_control_strength"]))
    final_peaks = [float(row["final_peak_abs_T"]) for row in ordered]
    decay_ratios = [float(row["peak_decay_ratio"]) for row in ordered]
    return {
        "cases": [row["case"] for row in ordered],
        "final_peak_monotonic_decrease": all(a >= b for a, b in zip(final_peaks, final_peaks[1:])),
        "decay_ratio_monotonic_decrease": all(a >= b for a, b in zip(decay_ratios, decay_ratios[1:])),
        "final_peak_at_control_0": final_peaks[0],
        "final_peak_at_control_1": final_peaks[-1],
        "final_peak_reduction_fraction": 1.0 - final_peaks[-1] / final_peaks[0] if final_peaks[0] else float("nan"),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    trend_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["group"] == "resolution":
            key = f"resolution_ny{row['ny']}"
        elif row["group"] == "boundary":
            key = f"boundary_{row['boundary']}"
        else:
            key = f"mapping_{row['control_mapping']}"
        trend_groups.setdefault(key, []).append(row)

    trend_summary = {key: _trend(group) for key, group in sorted(trend_groups.items())}
    resolution_supported = all(
        value["final_peak_monotonic_decrease"] for key, value in trend_summary.items() if key.startswith("resolution_")
    )
    boundary_supported = all(
        value["final_peak_monotonic_decrease"] for key, value in trend_summary.items() if key.startswith("boundary_")
    )
    mapping_supported = {
        key: value["final_peak_monotonic_decrease"]
        for key, value in trend_summary.items()
        if key.startswith("mapping_")
    }
    return {
        "trend_summary": trend_summary,
        "resolution_supported": resolution_supported,
        "boundary_supported": boundary_supported,
        "mapping_supported": mapping_supported,
        "interpretation": (
            "PASS: the diffusivity-control trend survives the tested mesh and boundary variants; "
            "alternative mappings are reported separately as falsification checks."
            if resolution_supported and boundary_supported
            else "CHECK: the diffusivity-control trend failed at least one mesh or boundary variant."
        ),
    }


def _write_outputs(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with (run_dir / "robustness_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "robustness_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bout-top", type=Path, default=Path(DEFAULT_BOUT_TOP))
    parser.add_argument("--bout-build", type=Path, default=Path(DEFAULT_BOUT_BUILD))
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--nout", type=int, default=20)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    _design, _plasma, _reactor = _evaluate_design()
    base_params = _mapped_bout_parameters(_design, _plasma, _reactor)

    if args.run_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = REPO / "validation_runs" / f"bout_robustness_sweep_{stamp}"
    else:
        run_dir = args.run_dir

    if run_dir.exists() and not args.keep_existing:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for spec in _case_specs(base_params):
        case_dir = run_dir / spec["case"]
        _write_bout_inp(
            case_dir,
            spec["params"],
            args.nout,
            ny=spec["ny"],
            dy=spec["dy"],
            boundary=spec["boundary"],
        )
        _run_bout(case_dir, args.bout_build)
        bout_summary = _summarize_output(case_dir)
        case_summary = {"case_spec": spec, "bout_summary": bout_summary}
        (case_dir / "summary.json").write_text(json.dumps(case_summary, indent=2, sort_keys=True), encoding="utf-8")
        rows.append(_row(spec, case_dir, bout_summary))

    summary = {
        "run_dir": str(run_dir),
        "bout_top": str(args.bout_top),
        "bout_build": str(args.bout_build),
        "controls": list(CONTROLS),
        "checks": _summarize(rows),
    }
    _write_outputs(run_dir, rows, summary)
    print(json.dumps({"run_dir": str(run_dir), **summary["checks"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

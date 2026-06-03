#!/usr/bin/env python3
"""Run a controlled BOUT++ conduction sweep around the default fusion design."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bout_validation_bridge import (
    DEFAULT_BOUT_BUILD,
    DEFAULT_BOUT_TOP,
    REPO,
    _evaluate_design,
    _mapped_bout_parameters,
    _run_bout,
    _safe_float,
    _summarize_output,
    _write_bout_inp,
)


DEFAULT_CONTROL_VALUES = (0.0, 0.25, 0.5, 0.75, 1.0)
DEFAULT_WALL_LOAD_SCALES = (0.5, 1.0, 2.0)


def _split_float_list(text: str) -> list[float]:
    return [float(part.strip()) for part in text.split(",") if part.strip()]


def _case_name(control: float, wall_scale: float) -> str:
    control_part = f"tct{int(round(control * 100)):03d}"
    wall_part = f"wall{int(round(wall_scale * 100)):03d}"
    return f"{control_part}_{wall_part}"


def _sweep_params(base_params: dict[str, float], control: float, wall_scale: float) -> dict[str, float]:
    params = dict(base_params)
    lithium_mod = max(params["lithium_wall_modifier"], 0.25)
    wall_load = params["wall_load_mw_m2"] * wall_scale
    raw_wall_load = params["raw_wall_load_mw_m2"] * wall_scale

    params.update(
        {
            "chi": float(max(0.05, min(8.0, 0.75 + 2.25 * control + 0.25 * max(lithium_mod - 1.0, 0.0)))),
            "t_scale": float(max(0.05, min(5.0, wall_load / 2.0))),
            "gaussian_width": float(max(0.08, min(0.6, 0.2 / lithium_mod))),
            "wall_load_mw_m2": float(wall_load),
            "raw_wall_load_mw_m2": float(raw_wall_load),
            "wall_load_scale": float(wall_scale),
            "tct_control_strength": float(control),
        }
    )
    return params


def _row_from_case(case_dir: Path, params: dict[str, float], bout_summary: dict[str, float]) -> dict[str, Any]:
    return {
        "case": case_dir.name,
        "case_dir": str(case_dir),
        "tct_control_strength": params["tct_control_strength"],
        "wall_load_scale": params["wall_load_scale"],
        "wall_load_mw_m2": params["wall_load_mw_m2"],
        "chi": params["chi"],
        "t_scale": params["t_scale"],
        "gaussian_width": params["gaussian_width"],
        "initial_peak_abs_T": bout_summary["initial_peak_abs_T"],
        "final_peak_abs_T": bout_summary["final_peak_abs_T"],
        "peak_decay_ratio": bout_summary["peak_decay_ratio"],
        "mean_peak_abs_T": bout_summary["mean_peak_abs_T"],
        "time_end": bout_summary["time_end"],
    }


def _trend_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_wall: dict[float, list[dict[str, Any]]] = {}
    for row in rows:
        by_wall.setdefault(float(row["wall_load_scale"]), []).append(row)

    control_trends = []
    for wall_scale, group in sorted(by_wall.items()):
        ordered = sorted(group, key=lambda row: float(row["tct_control_strength"]))
        final_peaks = [float(row["final_peak_abs_T"]) for row in ordered]
        decay_ratios = [float(row["peak_decay_ratio"]) for row in ordered]
        control_trends.append(
            {
                "wall_load_scale": wall_scale,
                "final_peak_monotonic_decrease": all(a >= b for a, b in zip(final_peaks, final_peaks[1:])),
                "decay_ratio_monotonic_decrease": all(a >= b for a, b in zip(decay_ratios, decay_ratios[1:])),
                "final_peak_at_control_0": final_peaks[0],
                "final_peak_at_control_1": final_peaks[-1],
                "final_peak_reduction_fraction": (
                    1.0 - final_peaks[-1] / final_peaks[0] if final_peaks[0] else float("nan")
                ),
            }
        )

    return {
        "control_trends": control_trends,
        "all_control_trends_supported": all(item["final_peak_monotonic_decrease"] for item in control_trends),
        "interpretation": (
            "PASS: final heat perturbation decreases monotonically as the controlled "
            "effective diffusivity increases at each wall-load scale."
            if all(item["final_peak_monotonic_decrease"] for item in control_trends)
            else "CHECK: at least one wall-load scale did not show monotonic final-peak reduction."
        ),
    }


def _write_outputs(sweep_dir: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    summary_path = sweep_dir / "sweep_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    csv_path = sweep_dir / "sweep_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bout-top", type=Path, default=Path(DEFAULT_BOUT_TOP))
    parser.add_argument("--bout-build", type=Path, default=Path(DEFAULT_BOUT_BUILD))
    parser.add_argument("--sweep-dir", type=Path, default=None)
    parser.add_argument("--controls", default=",".join(str(value) for value in DEFAULT_CONTROL_VALUES))
    parser.add_argument("--wall-load-scales", default=",".join(str(value) for value in DEFAULT_WALL_LOAD_SCALES))
    parser.add_argument("--nout", type=int, default=20)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    controls = _split_float_list(args.controls)
    wall_load_scales = _split_float_list(args.wall_load_scales)
    design, plasma, reactor = _evaluate_design()
    base_params = _mapped_bout_parameters(design, plasma, reactor)

    if args.sweep_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sweep_dir = REPO / "validation_runs" / f"bout_controlled_sweep_{stamp}"
    else:
        sweep_dir = args.sweep_dir

    if sweep_dir.exists() and not args.keep_existing:
        shutil.rmtree(sweep_dir)
    sweep_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for wall_scale in wall_load_scales:
        for control in controls:
            case_dir = sweep_dir / _case_name(control, wall_scale)
            params = _sweep_params(base_params, control, wall_scale)
            _write_bout_inp(case_dir, params, args.nout)
            _run_bout(case_dir, args.bout_build)
            bout_summary = _summarize_output(case_dir)
            row = _row_from_case(case_dir, params, bout_summary)
            rows.append(row)
            case_summary = {"mapped_parameters": params, "bout_summary": bout_summary}
            (case_dir / "summary.json").write_text(json.dumps(case_summary, indent=2, sort_keys=True), encoding="utf-8")
            cases.append({"case": case_dir.name, **case_summary})

    summary = {
        "sweep_dir": str(sweep_dir),
        "bout_top": str(args.bout_top),
        "bout_build": str(args.bout_build),
        "controls": controls,
        "wall_load_scales": wall_load_scales,
        "base_plasma_summary": {
            "pfus_mw": _safe_float(plasma.get("pfus_mw"), 0.0),
            "pbrem_mw": _safe_float(plasma.get("pbrem_mw"), 0.0),
            "ptr_mw": _safe_float(plasma.get("ptr_mw"), 0.0),
            "wn_mw_m2": _safe_float(plasma.get("wn_mw_m2"), 0.0),
            "betaN": _safe_float(plasma.get("betaN"), 0.0),
            "qstar": _safe_float(plasma.get("qstar"), 0.0),
        },
        "base_reactor_summary": {
            "score": _safe_float(reactor.get("score"), 0.0),
            "net_electric": _safe_float(reactor.get("net_electric"), 0.0),
            "wall_load": _safe_float(reactor.get("wall_load"), 0.0),
            "raw_wall_load": _safe_float(reactor.get("raw_wall_load"), 0.0),
            "tct_control_strength": _safe_float(reactor.get("tct_control_strength"), 0.0),
            "event_loss_frac": _safe_float(reactor.get("event_loss_frac"), 0.0),
        },
        "trend_summary": _trend_summary(rows),
        "cases": cases,
    }
    _write_outputs(sweep_dir, summary, rows)
    print(json.dumps({"sweep_dir": str(sweep_dir), **summary["trend_summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

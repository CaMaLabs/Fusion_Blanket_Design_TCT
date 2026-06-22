#!/usr/bin/env python3
"""Expanded measured-RMP FAIR-MAST causal analog screen."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import zarr
from scipy.signal import find_peaks


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_rmp_expanded_causal_analog_default"
LEVEL1_ROOT = "https://s3.echo.stfc.ac.uk/mast/level1/shots"
LEVEL2_ROOT = "https://s3.echo.stfc.ac.uk/mast/level2/shots"
METADATA_ROOT = "https://mastapp.site/json/level2/shots"

SHOTS = (30275, 30276, 30277, 30285, 30311, 30418, 30419, 30421, 30423)
WINDOW_S = (0.30, 0.48)
ACTUATOR_THRESHOLD_V_RMS = 0.10
D_ALPHA_CHANNEL = 1
D_ALPHA_PROMINENCE_V = 0.30
MINIMUM_EVENT_SEPARATION_S = 0.003


def fetch_metadata(shot: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"{METADATA_ROOT}/{shot}", timeout=20) as response:
            return json.load(response)
    except Exception as exc:
        return {
            "rmp_coil": None,
            "scenario": None,
            "shot_postshot_comment": f"metadata fetch failed: {type(exc).__name__}: {exc}",
        }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def interpolate_mean(time: np.ndarray, values: np.ndarray) -> float | None:
    mask = (time >= WINDOW_S[0]) & (time < WINDOW_S[1]) & np.isfinite(values)
    return float(np.mean(values[mask])) if np.any(mask) else None


def analyze_shot(shot: int) -> dict[str, Any]:
    level1 = zarr.open_group(f"{LEVEL1_ROOT}/{shot}.zarr", mode="r")
    actuator_time = np.asarray(level1["xma"]["time"], dtype=float)
    actuator = np.asarray(level1["xma"]["rog_elm_l01"], dtype=float)
    actuator_mask = (
        (actuator_time >= WINDOW_S[0])
        & (actuator_time < WINDOW_S[1])
        & np.isfinite(actuator)
    )
    actuator_rms = float(np.sqrt(np.mean(actuator[actuator_mask] ** 2)))
    actuator_active = actuator_rms >= ACTUATOR_THRESHOLD_V_RMS

    level2 = zarr.open_group(f"{LEVEL2_ROOT}/{shot}.zarr", mode="r")
    visible = level2["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[D_ALPHA_CHANNEL]
    dalpha_dt = float(np.nanmedian(np.diff(dalpha_time)))
    event_indices, _ = find_peaks(
        np.nan_to_num(dalpha),
        prominence=D_ALPHA_PROMINENCE_V,
        distance=max(1, int(MINIMUM_EVENT_SEPARATION_S / dalpha_dt)),
    )
    event_indices = event_indices[
        (dalpha_time[event_indices] >= WINDOW_S[0])
        & (dalpha_time[event_indices] < WINDOW_S[1])
    ]
    peaks = dalpha[event_indices]

    summary = level2["summary"]
    summary_time = np.asarray(summary["time"], dtype=float)
    metadata = fetch_metadata(shot)
    return {
        "shot": shot,
        "actuator_active_measured": actuator_active,
        "rog_elm_l01_rms_v": actuator_rms,
        "catalog_rmp_coil": metadata.get("rmp_coil"),
        "scenario": metadata.get("scenario"),
        "operator_log": metadata.get("shot_postshot_comment"),
        "event_count": len(event_indices),
        "event_rate_hz": len(event_indices) / (WINDOW_S[1] - WINDOW_S[0]),
        "median_dalpha_peak_v": float(np.median(peaks)) if len(peaks) else None,
        "p90_dalpha_peak_v": float(np.percentile(peaks, 90)) if len(peaks) else None,
        "mean_plasma_current_a": interpolate_mean(summary_time, np.asarray(summary["ip"], dtype=float)),
        "mean_line_average_ne_m3": interpolate_mean(
            summary_time, np.asarray(summary["line_average_n_e"], dtype=float)
        ),
        "mean_nbi_power_w": interpolate_mean(summary_time, np.asarray(summary["power_nbi"], dtype=float)),
    }


def exact_directional_p(rows: list[dict[str, Any]], field: str, lower_with_actuator: bool) -> float | None:
    rows = [row for row in rows if row[field] is not None]
    treated_count = sum(row["actuator_active_measured"] for row in rows)
    if treated_count == 0 or treated_count == len(rows):
        return None
    values = np.asarray([row[field] for row in rows], dtype=float)
    observed_mask = np.asarray([row["actuator_active_measured"] for row in rows], dtype=bool)
    observed = float(np.mean(values[observed_mask]) - np.mean(values[~observed_mask]))
    differences = []
    for treated_indices in itertools.combinations(range(len(rows)), treated_count):
        mask = np.zeros(len(rows), dtype=bool)
        mask[list(treated_indices)] = True
        differences.append(float(np.mean(values[mask]) - np.mean(values[~mask])))
    if lower_with_actuator:
        return sum(value <= observed + 1e-12 for value in differences) / len(differences)
    return sum(value >= observed - 1e-12 for value in differences) / len(differences)


def mean_optional(values: list[float | None]) -> float | None:
    finite = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.mean(finite)) if finite else None


def group_metrics(rows: list[dict[str, Any]], active: bool) -> dict[str, Any]:
    group = [row for row in rows if row["actuator_active_measured"] is active]
    return {
        "shot_count": len(group),
        "shots": [row["shot"] for row in group],
        "mean_event_rate_hz": mean_optional([row["event_rate_hz"] for row in group]),
        "mean_median_dalpha_peak_v": mean_optional([row["median_dalpha_peak_v"] for row in group]),
        "mean_p90_dalpha_peak_v": mean_optional([row["p90_dalpha_peak_v"] for row in group]),
        "mean_rog_elm_l01_rms_v": mean_optional([row["rog_elm_l01_rms_v"] for row in group]),
        "mean_plasma_current_a": mean_optional([row["mean_plasma_current_a"] for row in group]),
        "mean_line_average_ne_m3": mean_optional([row["mean_line_average_ne_m3"] for row in group]),
        "mean_nbi_power_w": mean_optional([row["mean_nbi_power_w"] for row in group]),
    }


def relative_change(active: float | None, inactive: float | None) -> float | None:
    if active is None or inactive in (None, 0.0):
        return None
    return active / inactive - 1.0


def format_optional(value: Any, precision: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != 0.0 and (abs(value) >= 1.0e5 or abs(value) < 1.0e-3):
            return f"{value:.{precision}e}"
        return f"{value:.{precision}f}"
    return str(value)


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    active = summary["groups"]["actuator_active"]
    inactive = summary["groups"]["actuator_inactive"]
    effects = summary["effects"]
    lines = [
        "# FAIR-MAST Expanded Measured-RMP Causal-Analog Screen",
        "",
        f"- Status: `{summary['status']}`",
        "- Data: public real MAST Level-1 actuator and Level-2 diagnostic signals",
        f"- Candidate shots: `{list(SHOTS)}`",
        f"- Usable shots: `{[row['shot'] for row in summary['shots']]}`",
        f"- Skipped shots: `{[row['shot'] for row in summary['skipped_shots']]}`",
        f"- Common comparison window: `{WINDOW_S[0] * 1000:.0f}-{WINDOW_S[1] * 1000:.0f} ms`",
        "- Actuator exposure: measured `xma/rog_elm_l01` RMS, not catalog flags",
        "",
        "## Shot-Level Results",
        "",
        "| Shot | Active | Catalog RMP | Actuator RMS | Event rate | Median D-alpha peak |",
        "| ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for row in summary["shots"]:
        lines.append(
            f"| `{row['shot']}` | {row['actuator_active_measured']} | {row['catalog_rmp_coil']} | "
            f"{row['rog_elm_l01_rms_v']:.4f} V RMS | {row['event_rate_hz']:.2f} Hz | "
            f"{format_optional(row['median_dalpha_peak_v'])} V |"
        )
    lines += [
        "",
        "## Group Contrast",
        "",
        f"- Active shots: `{active['shots']}`",
        f"- Inactive shots: `{inactive['shots']}`",
        f"- Event-rate relative change: `{format_optional(effects['event_rate_relative_change'], 3)}`",
        f"- Median D-alpha peak relative change: `{format_optional(effects['median_peak_relative_change'], 3)}`",
        f"- Directional exact permutation p, higher event rate: `{format_optional(effects['event_rate_directional_permutation_p'], 4)}`",
        f"- Directional exact permutation p, lower median peak: `{format_optional(effects['median_peak_directional_permutation_p'], 4)}`",
        "",
        "## Covariate Warning",
        "",
        "| Group | Mean plasma current | Mean line density | Mean NBI power |",
        "| --- | ---: | ---: | ---: |",
        f"| Actuator active | {format_optional(active['mean_plasma_current_a'], 4)} A | "
        f"{format_optional(active['mean_line_average_ne_m3'], 4)} m^-3 | {format_optional(active['mean_nbi_power_w'], 4)} W |",
        f"| Actuator inactive | {format_optional(inactive['mean_plasma_current_a'], 4)} A | "
        f"{format_optional(inactive['mean_line_average_ne_m3'], 4)} m^-3 | {format_optional(inactive['mean_nbi_power_w'], 4)} W |",
        "",
        "## Claim Boundary",
        "",
        "This is still a causal analog rather than causal TCT validation. The exposure",
        "is measured before the outcomes, but shots are non-randomized, plasma-state",
        "covariates are not balanced, MAST RMP coils are not a TCT actuator, and the",
        "D-alpha event labels are automatic. A convincing next step remains a",
        "precommitted matched-shot or randomized actuator experiment with an actual",
        "TCT-like actuator command and independent diagnostics.",
        "",
    ]
    (run_dir / "fair_mast_rmp_expanded_causal_analog_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    rows = []
    skipped = []
    for shot in SHOTS:
        try:
            rows.append(analyze_shot(shot))
        except Exception as exc:  # Keep the run reproducible even if one public archive object is unavailable.
            skipped.append({"shot": shot, "error": type(exc).__name__, "message": str(exc)})

    active = group_metrics(rows, True)
    inactive = group_metrics(rows, False)
    effects = {
        "event_rate_relative_change": relative_change(active["mean_event_rate_hz"], inactive["mean_event_rate_hz"]),
        "median_peak_relative_change": relative_change(
            active["mean_median_dalpha_peak_v"], inactive["mean_median_dalpha_peak_v"]
        ),
        "event_rate_directional_permutation_p": exact_directional_p(rows, "event_rate_hz", False),
        "median_peak_directional_permutation_p": exact_directional_p(rows, "median_dalpha_peak_v", True),
    }
    status = (
        "MAST_RMP_EXPANDED_CAUSAL_ANALOG_COMPLETED"
        if active["shot_count"] and inactive["shot_count"]
        else "MAST_RMP_EXPANDED_CAUSAL_ANALOG_INSUFFICIENT_GROUPS"
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "window_s": list(WINDOW_S),
        "candidate_shots": list(SHOTS),
        "shots": rows,
        "skipped_shots": skipped,
        "groups": {"actuator_active": active, "actuator_inactive": inactive},
        "effects": effects,
        "claim_boundary": "Expanded measured-RMP causal analog only; not causal TCT validation.",
    }
    write_csv(args.run_dir / "fair_mast_rmp_expanded_causal_analog_shots.csv", rows)
    write_csv(args.run_dir / "fair_mast_rmp_expanded_causal_analog_skipped.csv", skipped, ["shot", "error", "message"])
    (args.run_dir / "fair_mast_rmp_expanded_causal_analog_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps({"status": status, "usable_shots": len(rows), "skipped_shots": len(skipped), **effects}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Held-out FAIR-MAST precursor test with fixed channels and trained threshold."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import zarr
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_prospective_precursor_default"
ARCHIVE_ROOT = "https://s3.echo.stfc.ac.uk/mast/level2/shots"
METADATA_ROOT = "https://mastapp.site/json/level2/shots"

CASES = (
    {"shot": 30311, "split": "train", "window_s": (0.20, 0.60)},
    {"shot": 30423, "split": "train", "window_s": (0.18, 0.60)},
    {"shot": 30276, "split": "test", "window_s": (0.30, 0.48)},
    {"shot": 30277, "split": "test", "window_s": (0.30, 0.48)},
    {"shot": 30418, "split": "test", "window_s": (0.30, 0.48)},
    {"shot": 30419, "split": "test", "window_s": (0.30, 0.48)},
    {"shot": 30421, "split": "test", "window_s": (0.30, 0.48)},
)
THRESHOLD_SIGMA_GRID = (4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0)
D_ALPHA_CHANNEL = 1
MIRNOV_CHANNEL = 2
D_ALPHA_PROMINENCE_V = 0.30
MINIMUM_EVENT_SEPARATION_S = 0.004
BASELINE_WINDOW_S = 0.040
PRECURSOR_WINDOW_S = (0.0005, 0.015)
EVENT_SIGNATURE_EXCLUSION_S = 0.002
LATENCIES_MS = (3.0, 5.0, 8.0, 12.0)


def robust_sigma(values: np.ndarray) -> float:
    median = np.nanmedian(values)
    return float(1.4826 * np.nanmedian(np.abs(values - median)))


def fetch_metadata(shot: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"{METADATA_ROOT}/{shot}", timeout=20) as response:
            return json.load(response)
    except Exception as exc:
        return {"shot_postshot_comment": f"metadata fetch failed: {type(exc).__name__}: {exc}"}


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def detect_events(dalpha_time: np.ndarray, dalpha: np.ndarray, window_s: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    dalpha_dt = float(np.nanmedian(np.diff(dalpha_time)))
    peaks, _ = find_peaks(
        np.nan_to_num(dalpha),
        prominence=D_ALPHA_PROMINENCE_V,
        distance=max(1, int(MINIMUM_EVENT_SEPARATION_S / dalpha_dt)),
    )
    in_window = (dalpha_time[peaks] >= window_s[0]) & (dalpha_time[peaks] <= window_s[1])
    return peaks[in_window], dalpha_time[peaks[in_window]]


def mirnov_envelope(mirnov_time: np.ndarray, mirnov: np.ndarray) -> np.ndarray:
    finite = np.isfinite(mirnov)
    mirnov = np.interp(mirnov_time, mirnov_time[finite], mirnov[finite])
    dt = float(np.nanmedian(np.diff(mirnov_time)))
    trend_points = max(3, int(0.002 / dt))
    rms_points = max(3, int(0.0005 / dt))
    high_pass = mirnov - uniform_filter1d(mirnov, trend_points, mode="nearest")
    return np.sqrt(uniform_filter1d(high_pass * high_pass, rms_points, mode="nearest"))


def crossing_times(
    mirnov_time: np.ndarray,
    envelope: np.ndarray,
    window_s: tuple[float, float],
    threshold_sigma: float,
) -> tuple[np.ndarray, float, float, float]:
    baseline = (
        (mirnov_time >= window_s[0])
        & (mirnov_time <= min(window_s[1], window_s[0] + BASELINE_WINDOW_S))
        & np.isfinite(envelope)
    )
    median = float(np.nanmedian(envelope[baseline]))
    sigma = robust_sigma(envelope[baseline])
    threshold = median + threshold_sigma * sigma
    dt = float(np.nanmedian(np.diff(mirnov_time)))
    persistence_points = max(1, int(0.0001 / dt))
    above = envelope > threshold
    persistent = uniform_filter1d(above.astype(float), persistence_points, mode="nearest") >= 0.8
    indices = np.flatnonzero(persistent & ~np.r_[False, persistent[:-1]])
    times = mirnov_time[indices]
    times = times[(times >= window_s[0]) & (times <= window_s[1])]
    return times, median, sigma, threshold


def score_case(event_times: np.ndarray, crossings: np.ndarray) -> dict[str, Any]:
    available = set(range(len(crossings)))
    leads: list[float] = []
    detected = 0
    matched: set[int] = set()
    for event_time in event_times:
        candidates = [
            index
            for index in available
            if event_time - PRECURSOR_WINDOW_S[1] <= crossings[index] <= event_time - PRECURSOR_WINDOW_S[0]
        ]
        if candidates:
            index = candidates[-1]
            available.remove(index)
            matched.add(index)
            detected += 1
            leads.append(float((event_time - crossings[index]) * 1000.0))
    false_triggers = 0
    for index, crossing_time in enumerate(crossings):
        in_signature = bool(np.any(np.abs(event_times - crossing_time) <= EVENT_SIGNATURE_EXCLUSION_S))
        false_triggers += index not in matched and not in_signature
    event_count = len(event_times)
    precision = detected / (detected + false_triggers) if detected + false_triggers else 0.0
    recall = detected / event_count if event_count else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "event_count": event_count,
        "detected_event_count": detected,
        "missed_event_count": event_count - detected,
        "false_trigger_count": false_triggers,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "lead_ms_values": leads,
    }


def load_case(case: dict[str, Any]) -> dict[str, Any]:
    shot = int(case["shot"])
    window_s = tuple(case["window_s"])
    group = zarr.open_group(f"{ARCHIVE_ROOT}/{shot}.zarr", mode="r")
    visible = group["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[D_ALPHA_CHANNEL]
    event_indices, event_times = detect_events(dalpha_time, dalpha, window_s)

    magnetics = group["magnetics"]
    mirnov_time = np.asarray(magnetics["time_mirnov"], dtype=float)
    mirnov = np.asarray(magnetics["b_field_pol_probe_cc_field"], dtype=float)[MIRNOV_CHANNEL]
    envelope = mirnov_envelope(mirnov_time, mirnov)
    metadata = fetch_metadata(shot)
    return {
        "shot": shot,
        "split": case["split"],
        "window_s": list(window_s),
        "operator_log": metadata.get("shot_postshot_comment"),
        "event_times": event_times,
        "event_indices": event_indices,
        "dalpha_peaks": dalpha[event_indices],
        "mirnov_time": mirnov_time,
        "envelope": envelope,
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    event_count = sum(row["event_count"] for row in scores)
    detected = sum(row["detected_event_count"] for row in scores)
    false = sum(row["false_trigger_count"] for row in scores)
    leads = [value for row in scores for value in row["lead_ms_values"]]
    precision = detected / (detected + false) if detected + false else 0.0
    recall = detected / event_count if event_count else 0.0
    return {
        "event_count": event_count,
        "detected_event_count": detected,
        "missed_event_count": event_count - detected,
        "false_trigger_count": false,
        "precision": precision,
        "recall": recall,
        "f1": 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "lead_ms": {
            "minimum": float(np.min(leads)) if leads else None,
            "median": float(np.median(leads)) if leads else None,
            "maximum": float(np.max(leads)) if leads else None,
        },
        "latency_feasible_event_count": {
            f"{latency:g}_ms": sum(value >= latency for value in leads)
            for latency in LATENCIES_MS
        },
    }


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    test = summary["test_aggregate"]
    lines = [
        "# FAIR-MAST Held-Out Precursor Test",
        "",
        f"- Status: `{summary['status']}`",
        "- Data: public real MAST Level-2 diagnostic archive",
        "- Training shots: threshold multiplier selected only on the train split",
        "- Test shots: fixed D-alpha channel, fixed Mirnov channel, fixed D-alpha threshold, trained Mirnov threshold multiplier",
        "- Baseline normalization: first 40 ms of each analysis window; event labels are not used for trigger thresholding",
        "",
        "## Trained Trigger",
        "",
        f"- D-alpha channel index: `{D_ALPHA_CHANNEL}`",
        f"- Mirnov channel index: `{MIRNOV_CHANNEL}`",
        f"- D-alpha event prominence: `{D_ALPHA_PROMINENCE_V:.3f} V`",
        f"- Selected Mirnov threshold multiplier: `{summary['selected_threshold_sigma']:.1f} sigma`",
        "",
        "## Held-Out Result",
        "",
        f"- Test events: `{test['event_count']}`",
        f"- Detected events: `{test['detected_event_count']}`",
        f"- Missed events: `{test['missed_event_count']}`",
        f"- False triggers: `{test['false_trigger_count']}`",
        f"- Precision: `{test['precision']:.3f}`",
        f"- Recall: `{test['recall']:.3f}`",
        f"- F1: `{test['f1']:.3f}`",
        f"- Median detected-event lead: `{test['lead_ms']['median']:.3f} ms`"
        if test["lead_ms"]["median"] is not None
        else "- Median detected-event lead: `n/a`",
        "",
        "| Split | Shot | Events | Detected | False triggers | Precision | Recall | Median lead |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["shot_scores"]:
        median = row["lead_ms"]["median"]
        lines.append(
            f"| {row['split']} | `{row['shot']}` | {row['event_count']} | {row['detected_event_count']} | "
            f"{row['false_trigger_count']} | {row['precision']:.3f} | {row['recall']:.3f} | "
            f"{median:.3f} ms |" if median is not None else
            f"| {row['split']} | `{row['shot']}` | {row['event_count']} | {row['detected_event_count']} | "
            f"{row['false_trigger_count']} | {row['precision']:.3f} | {row['recall']:.3f} | n/a |"
        )
    lines += [
        "",
        "## Claim Boundary",
        "",
        "This improves over the earlier retrospective precursor screen because the",
        "threshold multiplier is selected on training shots and evaluated on held-out",
        "shots. It is still not a deployed real-time controller: event labels are",
        "automatic D-alpha peaks, channel choices are engineering choices rather than",
        "machine-calibrated diagnostics, and the first-window baseline would need a",
        "validated online equivalent.",
        "",
    ]
    (run_dir / "fair_mast_prospective_precursor_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    loaded = [load_case(case) for case in CASES]
    train_cases = [case for case in loaded if case["split"] == "train"]
    grid_rows = []
    for sigma in THRESHOLD_SIGMA_GRID:
        scores = []
        for case in train_cases:
            crossings, _, _, _ = crossing_times(case["mirnov_time"], case["envelope"], tuple(case["window_s"]), sigma)
            scores.append(score_case(case["event_times"], crossings))
        row = {"threshold_sigma": sigma, **aggregate(scores)}
        grid_rows.append(row)
    selected = sorted(grid_rows, key=lambda row: (row["f1"], row["precision"], row["threshold_sigma"]))[-1]["threshold_sigma"]

    shot_scores = []
    event_rows = []
    for case in loaded:
        crossings, baseline_median, baseline_sigma, threshold = crossing_times(
            case["mirnov_time"], case["envelope"], tuple(case["window_s"]), selected
        )
        score = score_case(case["event_times"], crossings)
        leads = score.pop("lead_ms_values")
        lead_summary = {
            "minimum": float(np.min(leads)) if leads else None,
            "median": float(np.median(leads)) if leads else None,
            "maximum": float(np.max(leads)) if leads else None,
        }
        shot_scores.append(
            {
                "shot": case["shot"],
                "split": case["split"],
                "window_s": case["window_s"],
                "operator_log": case["operator_log"],
                "baseline_median": baseline_median,
                "baseline_sigma": baseline_sigma,
                "trigger_threshold": threshold,
                "lead_ms": lead_summary,
                **score,
            }
        )
        for i, (event_time, peak) in enumerate(zip(case["event_times"], case["dalpha_peaks"], strict=True), start=1):
            candidates = [time for time in crossings if event_time - PRECURSOR_WINDOW_S[1] <= time <= event_time - PRECURSOR_WINDOW_S[0]]
            trigger_time = float(candidates[-1]) if candidates else None
            event_rows.append(
                {
                    "shot": case["shot"],
                    "split": case["split"],
                    "event_number": i,
                    "event_time_s": float(event_time),
                    "dalpha_peak_v": float(peak),
                    "trigger_detected": trigger_time is not None,
                    "trigger_time_s": trigger_time,
                    "lead_ms": float((event_time - trigger_time) * 1000.0) if trigger_time is not None else None,
                }
            )

    test_scores = [dict(row, lead_ms_values=[]) for row in shot_scores if row["split"] == "test"]
    for row in test_scores:
        row.pop("lead_ms_values", None)
    test_aggregate = aggregate([
        {
            "event_count": row["event_count"],
            "detected_event_count": row["detected_event_count"],
            "false_trigger_count": row["false_trigger_count"],
            "lead_ms_values": [event["lead_ms"] for event in event_rows if event["shot"] == row["shot"] and event["lead_ms"] is not None],
        }
        for row in shot_scores
        if row["split"] == "test"
    ])
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_HELD_OUT_PRECURSOR_TEST_COMPLETED",
        "data_source": "FAIR-MAST public Level-2 experimental archive",
        "selected_threshold_sigma": selected,
        "threshold_grid": grid_rows,
        "shot_scores": shot_scores,
        "test_aggregate": test_aggregate,
        "claim_boundary": "Held-out precursor timing test only; not causal TCT actuator validation.",
    }
    write_csv(args.run_dir / "fair_mast_prospective_precursor_threshold_grid.csv", grid_rows)
    write_csv(args.run_dir / "fair_mast_prospective_precursor_shots.csv", shot_scores)
    write_csv(args.run_dir / "fair_mast_prospective_precursor_events.csv", event_rows)
    (args.run_dir / "fair_mast_prospective_precursor_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps({"status": summary["status"], "selected_threshold_sigma": selected, **test_aggregate}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

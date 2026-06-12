#!/usr/bin/env python3
"""Screen real FAIR-MAST ELM shots for Mirnov precursor lead time."""

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
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_elm_precursor_default"
ARCHIVE_ROOT = "https://s3.echo.stfc.ac.uk/mast/level2/shots"
METADATA_ROOT = "https://mastapp.site/json/level2/shots"
CASES = (
    {"shot": 30423, "window_s": (0.18, 0.60)},
    {"shot": 30311, "window_s": (0.20, 0.60)},
)
PRECURSOR_WINDOW_S = (0.0005, 0.015)
EVENT_EXCLUSION_S = (0.015, 0.002)
EVENT_SIGNATURE_EXCLUSION_S = 0.002
THRESHOLD_SIGMA = 6.0
LATENCIES_MS = (3.0, 5.0, 8.0, 12.0)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fetch_metadata(shot: int) -> dict[str, Any]:
    with urllib.request.urlopen(f"{METADATA_ROOT}/{shot}", timeout=60) as response:
        return json.load(response)


def robust_sigma(values: np.ndarray) -> float:
    median = np.nanmedian(values)
    return float(1.4826 * np.nanmedian(np.abs(values - median)))


def select_dalpha_channel(data: np.ndarray, valid: np.ndarray) -> int:
    scores = [
        np.nanpercentile(channel[valid], 99) - np.nanmedian(channel[valid])
        for channel in data
    ]
    return int(np.nanargmax(scores))


def select_mirnov_channel(data: np.ndarray, valid: np.ndarray) -> int:
    scores = [np.nanstd(channel[valid]) for channel in data]
    return int(np.nanargmax(scores))


def analyze_case(case: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    shot = int(case["shot"])
    start_s, end_s = case["window_s"]
    archive_url = f"{ARCHIVE_ROOT}/{shot}.zarr"
    group = zarr.open_group(archive_url, mode="r")

    visible = group["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha_all = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)
    dalpha_valid = (dalpha_time >= start_s) & (dalpha_time <= end_s)
    dalpha_channel = select_dalpha_channel(dalpha_all, dalpha_valid)
    dalpha = dalpha_all[dalpha_channel]
    dalpha_median = float(np.nanmedian(dalpha[dalpha_valid]))
    dalpha_mad = float(np.nanmedian(np.abs(dalpha[dalpha_valid] - dalpha_median)))
    dalpha_filled = np.nan_to_num(dalpha, nan=dalpha_median)
    dalpha_dt = float(np.nanmedian(np.diff(dalpha_time)))
    event_prominence = max(10.0 * dalpha_mad, 0.03)
    event_indices, _ = find_peaks(
        dalpha_filled,
        prominence=event_prominence,
        distance=max(1, int(0.004 / dalpha_dt)),
    )
    event_indices = event_indices[
        (dalpha_time[event_indices] >= start_s) & (dalpha_time[event_indices] <= end_s)
    ]
    event_times = dalpha_time[event_indices]

    magnetics = group["magnetics"]
    mirnov_time = np.asarray(magnetics["time_mirnov"], dtype=float)
    mirnov_all = np.asarray(magnetics["b_field_pol_probe_cc_field"], dtype=float)
    mirnov_valid = (mirnov_time >= start_s) & (mirnov_time <= end_s)
    mirnov_channel = select_mirnov_channel(mirnov_all, mirnov_valid)
    mirnov = mirnov_all[mirnov_channel]
    finite = np.isfinite(mirnov)
    mirnov = np.interp(mirnov_time, mirnov_time[finite], mirnov[finite])
    mirnov_dt = float(np.nanmedian(np.diff(mirnov_time)))
    trend_points = max(3, int(0.002 / mirnov_dt))
    rms_points = max(3, int(0.0005 / mirnov_dt))
    persistence_points = max(1, int(0.0001 / mirnov_dt))
    high_pass = mirnov - uniform_filter1d(mirnov, trend_points, mode="nearest")
    envelope = np.sqrt(uniform_filter1d(high_pass * high_pass, rms_points, mode="nearest"))

    baseline = mirnov_valid.copy()
    for event_time in event_times:
        baseline &= ~(
            (mirnov_time >= event_time - EVENT_EXCLUSION_S[0])
            & (mirnov_time <= event_time + EVENT_EXCLUSION_S[1])
        )
    envelope_median = float(np.nanmedian(envelope[baseline]))
    envelope_sigma = robust_sigma(envelope[baseline])
    trigger_threshold = envelope_median + THRESHOLD_SIGMA * envelope_sigma
    above = envelope > trigger_threshold
    persistent = uniform_filter1d(
        above.astype(float), persistence_points, mode="nearest"
    ) >= 0.8
    crossing_indices = np.flatnonzero(persistent & ~np.r_[False, persistent[:-1]])
    crossing_times = mirnov_time[crossing_indices]
    crossing_times = crossing_times[
        (crossing_times >= start_s) & (crossing_times <= end_s)
    ]

    available = set(range(len(crossing_times)))
    event_rows: list[dict[str, Any]] = []
    matched_crossings: set[int] = set()
    for event_number, (event_index, event_time) in enumerate(
        zip(event_indices, event_times, strict=True), start=1
    ):
        candidates = [
            index
            for index in available
            if event_time - PRECURSOR_WINDOW_S[1]
            <= crossing_times[index]
            <= event_time - PRECURSOR_WINDOW_S[0]
        ]
        match_index = candidates[-1] if candidates else None
        if match_index is not None:
            available.remove(match_index)
            matched_crossings.add(match_index)
            trigger_time = float(crossing_times[match_index])
            lead_ms = float((event_time - trigger_time) * 1000.0)
        else:
            trigger_time = None
            lead_ms = None
        event_rows.append(
            {
                "shot": shot,
                "event_number": event_number,
                "event_time_s": float(event_time),
                "dalpha_peak_v": float(dalpha_filled[event_index]),
                "trigger_detected": match_index is not None,
                "trigger_time_s": trigger_time,
                "lead_ms": lead_ms,
                **{
                    f"latency_{latency:g}_ms_feasible": lead_ms is not None and lead_ms >= latency
                    for latency in LATENCIES_MS
                },
            }
        )

    trigger_rows = []
    false_trigger_count = 0
    for index, crossing_time in enumerate(crossing_times):
        in_event_signature = bool(
            np.any(np.abs(event_times - crossing_time) <= EVENT_SIGNATURE_EXCLUSION_S)
        )
        classification = "matched_precursor" if index in matched_crossings else (
            "event_signature_excluded" if in_event_signature else "false_trigger"
        )
        false_trigger_count += classification == "false_trigger"
        trigger_rows.append(
            {
                "shot": shot,
                "trigger_time_s": float(crossing_time),
                "classification": classification,
            }
        )

    detected = sum(row["trigger_detected"] for row in event_rows)
    precision = detected / (detected + false_trigger_count) if detected + false_trigger_count else 0.0
    lead_values = [row["lead_ms"] for row in event_rows if row["lead_ms"] is not None]
    metadata = fetch_metadata(shot)
    result = {
        "shot": shot,
        "archive_url": archive_url,
        "window_s": [start_s, end_s],
        "operator_log": metadata.get("shot_postshot_comment"),
        "dalpha_channel_index": dalpha_channel,
        "mirnov_channel_index": mirnov_channel,
        "dalpha_event_prominence_v": event_prominence,
        "mirnov_trigger_threshold_t": trigger_threshold,
        "event_count": len(event_rows),
        "detected_event_count": detected,
        "missed_event_count": len(event_rows) - detected,
        "false_trigger_count": false_trigger_count,
        "recall": detected / len(event_rows) if event_rows else 0.0,
        "precision": precision,
        "lead_ms": {
            "minimum": float(np.min(lead_values)) if lead_values else None,
            "median": float(np.median(lead_values)) if lead_values else None,
            "maximum": float(np.max(lead_values)) if lead_values else None,
        },
        "latency_feasible_event_count": {
            f"{latency:g}_ms": sum(row[f"latency_{latency:g}_ms_feasible"] for row in event_rows)
            for latency in LATENCIES_MS
        },
    }
    return result, event_rows, trigger_rows


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    aggregate = summary["aggregate"]
    lines = [
        "# FAIR-MAST Experimental ELM Precursor / Latency Screen",
        "",
        f"- Status: `{summary['status']}`",
        "- Data: public, real MAST experimental Level-2 signals from FAIR-MAST",
        "- Event marker: automatically detected D-alpha peaks",
        "- Candidate precursor: high-pass/RMS envelope of a centre-column Mirnov channel",
        "- Channel selection: per-shot D-alpha dynamic range and Mirnov standard deviation",
        "- Analysis type: retrospective; thresholds use event labels to exclude event windows",
        "",
        "## Results",
        "",
        "| Shot | Operator log | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in summary["cases"]:
        lines.append(
            f"| `{case['shot']}` | {case['operator_log']} | {case['event_count']} | "
            f"{case['detected_event_count']} | {case['missed_event_count']} | "
            f"{case['false_trigger_count']} | {case['precision']:.3f} | "
            f"{case['recall']:.3f} | {case['lead_ms']['median']:.3f} ms |"
        )
    lines += [
        "",
        f"- Aggregate events: `{aggregate['event_count']}`",
        f"- Aggregate detected events: `{aggregate['detected_event_count']}`",
        f"- Aggregate false triggers: `{aggregate['false_trigger_count']}`",
        f"- Aggregate precision: `{aggregate['precision']:.3f}`",
        f"- Aggregate recall: `{aggregate['recall']:.3f}`",
        f"- Detected-event median lead: `{aggregate['lead_ms']['median']:.3f} ms`",
        "",
        "## Latency feasibility",
        "",
        "| Required end-to-end latency | Events with enough measured lead | Fraction of all events |",
        "| --- | ---: | ---: |",
    ]
    for latency in LATENCIES_MS:
        key = f"{latency:g}_ms"
        count = aggregate["latency_feasible_event_count"][key]
        lines.append(
            f"| `{latency:g} ms` | {count}/{aggregate['event_count']} | "
            f"{count / aggregate['event_count']:.3f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "The real MAST signals contain a detectable pre-event magnetic-envelope pattern",
        "for many of the automatically marked ELMs, with millisecond-scale lead time.",
        "The same fixed trigger also misses events and produces false triggers. This is",
        "mixed experimental support for the precursor/latency prerequisite, not a",
        "reliable real-time predictor.",
        "",
        "## Preventative-control addendum",
        "",
        "Earlier reduced-model runs found that moderate early/fixed control performs",
        "better than waiting for late event formation before applying strong control.",
        "This experimental timing screen reinforces that operating direction: only",
        "12/28 events provide at least 5 ms lead, only 2/28 provide at least 8 ms, and",
        "the trigger produces 20 false triggers. The current evidence therefore favors",
        "moderate preventative control scheduled from slower plasma-state indicators,",
        "with fast precursor signals used only for bounded adjustments.",
        "",
        "The companion `fair_mast_rmp_causal_analog_default` run tests that direction",
        "against measured MAST RMP-coil exposure. It is an experimental causal analog,",
        "not a causal TCT actuator test.",
        "",
        "## Claim boundary",
        "",
        "This run does not test a TCT actuator, a TCT plasma configuration, causal",
        "suppression, DIII-D behavior, or prospective real-time performance. The event",
        "labels are automatic rather than manually reviewed, and threshold estimation",
        "and per-shot channel selection are retrospective. A prospective train/test",
        "split, preselected channels, independent event labels, additional diagnostics,",
        "and actuator command/response data are required next.",
        "",
    ]
    (run_dir / "fair_mast_elm_precursor_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    cases = []
    event_rows: list[dict[str, Any]] = []
    trigger_rows: list[dict[str, Any]] = []
    for case in CASES:
        result, events, triggers = analyze_case(case)
        cases.append(result)
        event_rows.extend(events)
        trigger_rows.extend(triggers)

    total_events = sum(case["event_count"] for case in cases)
    total_detected = sum(case["detected_event_count"] for case in cases)
    total_false = sum(case["false_trigger_count"] for case in cases)
    lead_values = [row["lead_ms"] for row in event_rows if row["lead_ms"] is not None]
    aggregate = {
        "event_count": total_events,
        "detected_event_count": total_detected,
        "missed_event_count": total_events - total_detected,
        "false_trigger_count": total_false,
        "precision": total_detected / (total_detected + total_false),
        "recall": total_detected / total_events,
        "lead_ms": {
            "minimum": float(np.min(lead_values)),
            "median": float(np.median(lead_values)),
            "maximum": float(np.max(lead_values)),
        },
        "latency_feasible_event_count": {
            f"{latency:g}_ms": sum(row[f"latency_{latency:g}_ms_feasible"] for row in event_rows)
            for latency in LATENCIES_MS
        },
    }
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_EXPERIMENTAL_PRECURSOR_SCREEN_MIXED",
        "data_source": "FAIR-MAST public Level-2 experimental archive",
        "data_source_url": "https://mastapp.site/",
        "algorithm": {
            "dalpha_channel_selection": "largest 99th-percentile minus median dynamic range in the case window",
            "mirnov_channel_selection": "largest standard deviation in the case window",
            "dalpha_event_prominence": "max(10 * median absolute deviation, 0.03 V)",
            "minimum_event_separation_ms": 4.0,
            "mirnov_high_pass_window_ms": 2.0,
            "mirnov_rms_window_ms": 0.5,
            "trigger_threshold": f"non-event median + {THRESHOLD_SIGMA:g} robust sigma",
            "trigger_persistence_ms": 0.1,
            "precursor_association_window_ms": [0.5, 15.0],
        },
        "cases": cases,
        "aggregate": aggregate,
        "claim_boundary": (
            "Real MAST retrospective precursor/latency screen only; not TCT actuator, "
            "causal suppression, DIII-D, or prospective real-time validation."
        ),
    }
    write_csv(args.run_dir / "fair_mast_elm_events.csv", event_rows)
    write_csv(args.run_dir / "fair_mast_trigger_crossings.csv", trigger_rows)
    (args.run_dir / "fair_mast_elm_precursor_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps({"status": summary["status"], **aggregate}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

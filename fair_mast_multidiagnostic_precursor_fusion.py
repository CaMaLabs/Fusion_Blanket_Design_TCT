#!/usr/bin/env python3
"""Train/test a FAIR-MAST multi-diagnostic precursor fusion trigger."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import zarr
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_multidiagnostic_precursor_fusion_default"
DEFAULT_REVIEW_DIR = REPO / "validation_runs" / "fair_mast_machine_reviewed_labels_default"
ARCHIVE_ROOT = "https://s3.echo.stfc.ac.uk/mast/level2/shots"

CASES = (
    {"shot": 30311, "split": "train", "window_s": (0.20, 0.60)},
    {"shot": 30423, "split": "train", "window_s": (0.18, 0.60)},
    {"shot": 30276, "split": "test", "window_s": (0.30, 0.48)},
    {"shot": 30277, "split": "test", "window_s": (0.30, 0.48)},
    {"shot": 30418, "split": "test", "window_s": (0.30, 0.48)},
    {"shot": 30419, "split": "test", "window_s": (0.30, 0.48)},
    {"shot": 30421, "split": "test", "window_s": (0.30, 0.48)},
)
D_ALPHA_CHANNEL = 1
D_ALPHA_PROMINENCE_V = 0.30
MINIMUM_EVENT_SEPARATION_S = 0.004
BASELINE_WINDOW_S = 0.040
PRECURSOR_WINDOW_S = (0.0005, 0.015)
EVENT_SIGNATURE_EXCLUSION_S = 0.002
MERGE_SEPARATION_S = 0.00035
LATENCIES_MS = (3.0, 5.0, 8.0, 12.0)
THRESHOLD_SIGMA_GRID = (4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0)


FEATURE_SPECS = (
    {"name": "pol_cc_ch2", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_cc_field", "channels": (2,), "kind": "rms"},
    {"name": "pol_cc_all", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_cc_field", "channels": (0, 1, 2, 3, 4), "kind": "rms"},
    {"name": "tor_cc_all", "group": "magnetics", "time": "time_mirnov", "field": "b_field_tor_probe_cc_field", "channels": (0, 1, 2), "kind": "rms"},
    {"name": "sxr_lower_all", "group": "soft_x_rays", "time": "time", "field": "horizontal_cam_lower", "channels": tuple(range(18)), "kind": "rms"},
    {"name": "sxr_upper_all", "group": "soft_x_rays", "time": "time", "field": "horizontal_cam_upper", "channels": tuple(range(18)), "kind": "rms"},
    {"name": "sxr_tangential_all", "group": "soft_x_rays", "time": "time", "field": "tangential_cam", "channels": tuple(range(18)), "kind": "rms"},
    {"name": "dalpha_slope", "group": "spectrometer_visible", "time": "time", "field": "filter_spectrometer_dalpha_voltage", "channels": (D_ALPHA_CHANNEL,), "kind": "positive_slope"},
)


def robust_sigma(values: np.ndarray) -> float:
    median = np.nanmedian(values)
    return float(1.4826 * np.nanmedian(np.abs(values - median)))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str | None) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def detect_events(dalpha_time: np.ndarray, dalpha: np.ndarray, window_s: tuple[float, float]) -> np.ndarray:
    dalpha_dt = float(np.nanmedian(np.diff(dalpha_time)))
    peaks, _ = find_peaks(
        np.nan_to_num(dalpha),
        prominence=D_ALPHA_PROMINENCE_V,
        distance=max(1, int(MINIMUM_EVENT_SEPARATION_S / dalpha_dt)),
    )
    in_window = (dalpha_time[peaks] >= window_s[0]) & (dalpha_time[peaks] <= window_s[1])
    return dalpha_time[peaks[in_window]]


def rms_envelope(time: np.ndarray, values: np.ndarray) -> np.ndarray:
    finite = np.isfinite(values)
    if np.count_nonzero(finite) < 2:
        return np.zeros_like(time, dtype=float)
    values = np.interp(time, time[finite], values[finite])
    dt = float(np.nanmedian(np.diff(time)))
    trend_points = max(3, int(0.002 / dt))
    rms_points = max(3, int(0.0005 / dt))
    high_pass = values - uniform_filter1d(values, trend_points, mode="nearest")
    power = np.nan_to_num(high_pass * high_pass, nan=0.0, posinf=0.0, neginf=0.0)
    return np.sqrt(np.maximum(uniform_filter1d(power, rms_points, mode="nearest"), 0.0))


def positive_slope_signal(time: np.ndarray, values: np.ndarray) -> np.ndarray:
    finite = np.isfinite(values)
    values = np.interp(time, time[finite], values[finite])
    dt = float(np.nanmedian(np.diff(time)))
    smooth_points = max(3, int(0.0004 / dt))
    smooth = uniform_filter1d(values, smooth_points, mode="nearest")
    slope = np.gradient(smooth, time)
    return np.maximum(slope, 0.0)


def crossing_times_for_signal(
    time: np.ndarray,
    signal: np.ndarray,
    window_s: tuple[float, float],
    sigma: float,
) -> tuple[np.ndarray, float]:
    baseline = (
        (time >= window_s[0])
        & (time <= min(window_s[1], window_s[0] + BASELINE_WINDOW_S))
        & np.isfinite(signal)
    )
    median = float(np.nanmedian(signal[baseline]))
    rsigma = robust_sigma(signal[baseline])
    threshold = median + sigma * rsigma
    dt = float(np.nanmedian(np.diff(time)))
    persistence_points = max(1, int(0.0001 / dt))
    above = signal > threshold
    persistent = uniform_filter1d(above.astype(float), persistence_points, mode="nearest") >= 0.8
    indices = np.flatnonzero(persistent & ~np.r_[False, persistent[:-1]])
    crossing_times = time[indices]
    crossing_times = crossing_times[(crossing_times >= window_s[0]) & (crossing_times <= window_s[1])]
    return crossing_times, threshold


def merge_crossings(crossings: list[tuple[float, str]]) -> list[dict[str, Any]]:
    if not crossings:
        return []
    crossings = sorted(crossings)
    merged: list[dict[str, Any]] = []
    current_time, source = crossings[0]
    current_sources = {source}
    for time, source in crossings[1:]:
        if time - current_time <= MERGE_SEPARATION_S:
            current_time = min(current_time, time)
            current_sources.add(source)
        else:
            merged.append({"time": current_time, "sources": "+".join(sorted(current_sources))})
            current_time = time
            current_sources = {source}
    merged.append({"time": current_time, "sources": "+".join(sorted(current_sources))})
    return merged


def score_alignment(event_times: np.ndarray, crossings: list[dict[str, Any]]) -> dict[str, Any]:
    crossing_times = np.asarray([row["time"] for row in crossings], dtype=float)
    available = set(range(len(crossing_times)))
    leads: list[float] = []
    matched: set[int] = set()
    matched_sources: list[str] = []
    for event_time in event_times:
        candidates = [
            index
            for index in available
            if event_time - PRECURSOR_WINDOW_S[1] <= crossing_times[index] <= event_time - PRECURSOR_WINDOW_S[0]
        ]
        if candidates:
            index = candidates[-1]
            available.remove(index)
            matched.add(index)
            leads.append(float((event_time - crossing_times[index]) * 1000.0))
            matched_sources.append(crossings[index]["sources"])
    false_count = 0
    for index, crossing_time in enumerate(crossing_times):
        in_signature = bool(np.any(np.abs(event_times - crossing_time) <= EVENT_SIGNATURE_EXCLUSION_S))
        false_count += index not in matched and not in_signature
    precision = len(leads) / (len(leads) + false_count) if len(leads) + false_count else 0.0
    recall = len(leads) / len(event_times) if len(event_times) else 0.0
    return {
        "event_count": len(event_times),
        "detected_event_count": len(leads),
        "missed_event_count": len(event_times) - len(leads),
        "false_trigger_count": false_count,
        "precision": precision,
        "recall": recall,
        "f1": 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "lead_ms_values": leads,
        "matched_sources": matched_sources,
    }


def load_review_labels(review_dir: Path) -> dict[int, np.ndarray]:
    rows = read_csv(review_dir / "fair_mast_machine_reviewed_label_manifest.csv")
    by_shot: dict[int, list[float]] = {}
    for row in rows:
        if row["review_label"] == "true_elm":
            by_shot.setdefault(int(row["shot"]), []).append(float(row["event_time_s"]))
    return {shot: np.asarray(sorted(times), dtype=float) for shot, times in by_shot.items()}


def load_case(case: dict[str, Any]) -> dict[str, Any]:
    shot = int(case["shot"])
    window_s = tuple(case["window_s"])
    group = zarr.open_group(f"{ARCHIVE_ROOT}/{shot}.zarr", mode="r")
    visible = group["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[D_ALPHA_CHANNEL]
    automatic_events = detect_events(dalpha_time, dalpha, window_s)

    features: dict[str, dict[str, Any]] = {}
    for spec in FEATURE_SPECS:
        node = group[spec["group"]]
        time = np.asarray(node[spec["time"]], dtype=float)
        data = np.asarray(node[spec["field"]], dtype=float)
        if data.ndim == 1:
            channel_values = [data]
        else:
            channel_values = [data[channel] for channel in spec["channels"] if channel < data.shape[0]]
        feature_signal = None
        for channel in channel_values:
            if spec["kind"] == "rms":
                signal = rms_envelope(time, channel)
            elif spec["kind"] == "positive_slope":
                signal = positive_slope_signal(time, channel)
            else:
                raise ValueError(spec["kind"])
            feature_signal = signal if feature_signal is None else np.maximum(feature_signal, signal)
        features[spec["name"]] = {"time": time, "signal": feature_signal}

    return {
        "shot": shot,
        "split": case["split"],
        "window_s": window_s,
        "automatic_event_times": automatic_events,
        "features": features,
    }


def crossings_for_config(case: dict[str, Any], config: dict[str, float]) -> list[dict[str, Any]]:
    crossings: list[tuple[float, str]] = []
    for feature_name, sigma in config.items():
        feature = case["features"][feature_name]
        times, _ = crossing_times_for_signal(feature["time"], feature["signal"], case["window_s"], sigma)
        crossings.extend((float(time), feature_name) for time in times)
    return merge_crossings(crossings)


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    event_count = sum(row["event_count"] for row in scores)
    detected = sum(row["detected_event_count"] for row in scores)
    false = sum(row["false_trigger_count"] for row in scores)
    leads = [lead for row in scores for lead in row["lead_ms_values"]]
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
            f"{latency:g}_ms": sum(lead >= latency for lead in leads)
            for latency in LATENCIES_MS
        },
    }


def config_score(aggregate_score: dict[str, Any]) -> float:
    # Favor recall, but make false triggers expensive enough to reject noisy fusions.
    return (
        2.0 * aggregate_score["recall"]
        + 0.6 * aggregate_score["precision"]
        - 0.015 * aggregate_score["false_trigger_count"]
    )


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    test = summary["test_aggregate_reviewed_labels"]
    baseline = summary["baseline_single_channel_reviewed_labels"]
    recall_gain = test["detected_event_count"] - baseline["detected_event_count"]
    false_gain = test["false_trigger_count"] - baseline["false_trigger_count"]
    if recall_gain > 0 and false_gain <= 0 and test["lead_ms"]["median"] >= baseline["lead_ms"]["median"] - 1.0:
        interpretation = [
            "The selected fusion trigger improves accepted-event recognition without",
            "increasing false triggers or materially collapsing the median lead time.",
            "That makes it a better trigger candidate than the fixed single-channel",
            "baseline, subject to the same causal and actuator caveats.",
        ]
    elif recall_gain > 0:
        interpretation = [
            "The selected fusion trigger improves raw accepted-event recognition,",
            "but the gain is paid for with more false triggers and/or shorter lead",
            "time. This is useful as evidence that the added diagnostic contains",
            "precursor information, but it is not yet a cleaner operational trigger.",
        ]
    else:
        interpretation = [
            "The selected fusion trigger does not improve accepted-event recognition",
            "over the fixed single-channel baseline. The added diagnostics should be",
            "treated as negative or inconclusive for this threshold-fusion design.",
        ]
    latency_delta = {
        key: test["latency_feasible_event_count"][key] - baseline["latency_feasible_event_count"][key]
        for key in baseline["latency_feasible_event_count"]
    }
    if any(value != 0 for value in latency_delta.values()):
        latency_lines = [
            "The latency-reachable counts change relative to baseline, so the raw",
            "recognition gain must be interpreted together with the actuator budget.",
            f"Delta by budget: `{latency_delta}`.",
        ]
    else:
        latency_lines = [
            "The latency-reachable counts are unchanged at the tested 3, 5, 8, and 12 ms",
            "budgets. The result therefore does not solve the actuator timing caveat.",
        ]
    lines = [
        "# FAIR-MAST Multi-Diagnostic Precursor Fusion",
        "",
        f"- Status: `{summary['status']}`",
        "- Goal: improve precursor recall beyond the single fixed Mirnov channel while keeping false triggers bounded",
        "- Train split: automatic D-alpha labels on shots `30311`, `30423`",
        "- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`",
        "- Candidate fast diagnostics: centre-column poloidal/toroidal Mirnov, soft-X-ray camera envelopes, D-alpha positive slope",
        "",
        "## Selected Fusion",
        "",
        f"- Selected config: `{summary['selected_config']}`",
        f"- Train score: `{summary['selected_train_score']:.3f}`",
        "",
        "## Held-Out Accepted-Label Result",
        "",
        "| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Single-channel baseline | {baseline['event_count']} | {baseline['detected_event_count']} | {baseline['missed_event_count']} | {baseline['false_trigger_count']} | {baseline['precision']:.3f} | {baseline['recall']:.3f} | {baseline['lead_ms']['median']:.3f} ms |",
        f"| Multi-diagnostic fusion | {test['event_count']} | {test['detected_event_count']} | {test['missed_event_count']} | {test['false_trigger_count']} | {test['precision']:.3f} | {test['recall']:.3f} | {test['lead_ms']['median']:.3f} ms |",
        "",
        "## Latency-Reachable Accepted Events",
        "",
        "| Required latency | Single-channel baseline | Multi-diagnostic fusion |",
        "| --- | ---: | ---: |",
    ]
    for latency in LATENCIES_MS:
        key = f"{latency:g}_ms"
        lines.append(
            f"| `{key}` | {baseline['latency_feasible_event_count'][key]} | "
            f"{test['latency_feasible_event_count'][key]} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This run tests whether adding fast diagnostics improves the actual",
        "control-relevant metric: accepted true events with enough lead after",
        "false-trigger constraints. The selected fusion trigger is compared directly",
        "with the fixed single-channel Mirnov baseline on accepted held-out events.",
        "A gain should be treated as useful only if it does not merely add false",
        "triggers or collapse lead time.",
        "",
        *interpretation,
        "",
        *latency_lines,
        "The result remains compatible with fast bounded boost layered on standing",
        "bias, but it does not make late or slow response chains viable.",
        "",
        "## Claim Boundary",
        "",
        "This is still a public MAST diagnostic-trigger screen. It does not provide",
        "expert-reviewed labels, a measured TCT actuator, or causal suppression.",
        "",
    ]
    (run_dir / "fair_mast_multidiagnostic_precursor_fusion_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--review-dir", type=Path, default=REPO / "validation_runs" / "fair_mast_machine_reviewed_labels_default")
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    reviewed_events = load_review_labels(args.review_dir)
    cases = [load_case(case) for case in CASES]
    train_cases = [case for case in cases if case["split"] == "train"]
    test_cases = [case for case in cases if case["split"] == "test"]

    configs = []
    for sigma in THRESHOLD_SIGMA_GRID:
        configs.append({"pol_cc_ch2": sigma})
    extra_features = (
        "pol_cc_all",
        "tor_cc_all",
        "sxr_lower_all",
        "sxr_upper_all",
        "sxr_tangential_all",
        "dalpha_slope",
    )
    for pol_sigma in THRESHOLD_SIGMA_GRID:
        configs.append({"pol_cc_all": pol_sigma})
        configs.append({"pol_cc_ch2": pol_sigma, "pol_cc_all": pol_sigma})
        for feature_name in extra_features:
            for feature_sigma in THRESHOLD_SIGMA_GRID:
                configs.append({"pol_cc_all": pol_sigma, feature_name: feature_sigma})
                configs.append({"pol_cc_ch2": pol_sigma, feature_name: feature_sigma})
    for feature_name in extra_features:
        for sigma in THRESHOLD_SIGMA_GRID:
            configs.append({feature_name: sigma})

    grid_rows = []
    best_config = None
    best_score = -1e9
    for config in configs:
        train_scores = []
        for case in train_cases:
            crossings = crossings_for_config(case, config)
            train_scores.append(score_alignment(case["automatic_event_times"], crossings))
        agg = aggregate(train_scores)
        score = config_score(agg)
        grid_rows.append({"config": json.dumps(config, sort_keys=True), "train_score": score, **agg})
        if score > best_score:
            best_score = score
            best_config = config

    test_rows = []
    test_scores = []
    baseline_scores = []
    baseline_config = {"pol_cc_ch2": 6.0}
    for case in test_cases:
        events = reviewed_events[int(case["shot"])]
        fusion_crossings = crossings_for_config(case, best_config)
        baseline_crossings = crossings_for_config(case, baseline_config)
        fusion_score = score_alignment(events, fusion_crossings)
        baseline_score = score_alignment(events, baseline_crossings)
        test_scores.append(fusion_score)
        baseline_scores.append(baseline_score)
        test_rows.append(
            {
                "shot": case["shot"],
                "event_count": fusion_score["event_count"],
                "fusion_detected": fusion_score["detected_event_count"],
                "fusion_false_triggers": fusion_score["false_trigger_count"],
                "fusion_recall": fusion_score["recall"],
                "fusion_precision": fusion_score["precision"],
                "fusion_median_lead_ms": float(np.median(fusion_score["lead_ms_values"])) if fusion_score["lead_ms_values"] else None,
                "baseline_detected": baseline_score["detected_event_count"],
                "baseline_false_triggers": baseline_score["false_trigger_count"],
                "baseline_recall": baseline_score["recall"],
                "baseline_precision": baseline_score["precision"],
                "baseline_median_lead_ms": float(np.median(baseline_score["lead_ms_values"])) if baseline_score["lead_ms_values"] else None,
            }
        )

    test_agg = aggregate(test_scores)
    baseline_agg = aggregate(baseline_scores)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_MULTIDIAGNOSTIC_PRECURSOR_FUSION_COMPLETED",
        "selected_config": best_config,
        "selected_train_score": best_score,
        "baseline_config": baseline_config,
        "test_aggregate_reviewed_labels": test_agg,
        "baseline_single_channel_reviewed_labels": baseline_agg,
        "shot_rows": test_rows,
        "claim_boundary": "Multi-diagnostic trigger screen only; not causal TCT validation.",
    }
    write_csv(args.run_dir / "fair_mast_multidiagnostic_precursor_fusion_grid.csv", grid_rows)
    write_csv(args.run_dir / "fair_mast_multidiagnostic_precursor_fusion_shots.csv", test_rows)
    (args.run_dir / "fair_mast_multidiagnostic_precursor_fusion_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

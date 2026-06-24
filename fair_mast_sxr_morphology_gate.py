#!/usr/bin/env python3
"""Train/test a causal morphology gate for FAIR-MAST SXR precursor candidates."""

from __future__ import annotations

import argparse
import csv
import json
import signal
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import zarr

import fair_mast_multidiagnostic_precursor_fusion as fusion


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_sxr_morphology_gate_default"
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}
TOROIDAL_CONFIG = {"pol_cc_ch2": 6.0, "tor_cc_all": 6.0}
SXR_FEATURES = ("sxr_upper_all", "sxr_tangential_all")
SXR_SIGMAS = (4.0, 8.0)
MAG_FEATURES = ("pol_cc_ch2", "tor_cc_all")
MAG_SIGMAS = (2.0, 3.0, 4.0)
MAG_WINDOWS_MS = (1.0, 2.0, 4.0)
DEADTIMES_MS = (0.35, 3.0)
MINIMAL_FEATURE_SPECS = (
    {"name": "pol_cc_ch2", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_cc_field", "channels": (2,)},
    {"name": "tor_cc_all", "group": "magnetics", "time": "time_mirnov", "field": "b_field_tor_probe_cc_field", "channels": (0, 1, 2)},
    {"name": "sxr_upper_all", "group": "soft_x_rays", "time": "time", "field": "horizontal_cam_upper", "channels": tuple(range(18))},
    {"name": "sxr_tangential_all", "group": "soft_x_rays", "time": "time", "field": "tangential_cam", "channels": tuple(range(18))},
)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_minimal_case(case_def: dict[str, Any]) -> dict[str, Any]:
    shot = int(case_def["shot"])
    window_s = tuple(case_def["window_s"])
    group = zarr.open_group(f"{fusion.ARCHIVE_ROOT}/{shot}.zarr", mode="r")
    visible = group["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[fusion.D_ALPHA_CHANNEL]
    automatic_events = fusion.detect_events(dalpha_time, dalpha, window_s)

    features: dict[str, dict[str, Any]] = {}
    for spec in MINIMAL_FEATURE_SPECS:
        node = group[spec["group"]]
        time = np.asarray(node[spec["time"]], dtype=float)
        data = np.asarray(node[spec["field"]], dtype=float)
        if data.ndim == 1:
            channel_values = [data]
        else:
            channel_values = [data[channel] for channel in spec["channels"] if channel < data.shape[0]]
        feature_signal = None
        for channel in channel_values:
            signal = fusion.rms_envelope(time, channel)
            feature_signal = signal if feature_signal is None else np.maximum(feature_signal, signal)
        features[spec["name"]] = {"time": time, "signal": feature_signal}

    return {
        "shot": shot,
        "split": case_def["split"],
        "window_s": window_s,
        "automatic_event_times": automatic_events,
        "features": features,
    }


class ShotLoadTimeout(TimeoutError):
    pass


def _timeout_handler(_signum: int, _frame: Any) -> None:
    raise ShotLoadTimeout("FAIR-MAST shot load timed out")


def load_case_with_retries(case_def: dict[str, Any], attempts: int = 4, timeout_s: int = 120) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout_s)
            try:
                return load_minimal_case(case_def)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        except Exception as exc:  # Public object-store reads occasionally truncate.
            last_error = exc
            print(
                f"load failed for shot {case_def['shot']} attempt {attempt}/{attempts}: {type(exc).__name__}",
                flush=True,
            )
            if attempt < attempts:
                time.sleep(2.0 * attempt)
    assert last_error is not None
    raise last_error


def feature_threshold(case: dict[str, Any], feature_name: str, sigma: float) -> float:
    cache = case.setdefault("_threshold_cache", {})
    key = (feature_name, sigma)
    if key in cache:
        return cache[key]
    feature = case["features"][feature_name]
    _, threshold = fusion.crossing_times_for_signal(
        feature["time"],
        feature["signal"],
        case["window_s"],
        sigma,
    )
    cache[key] = threshold
    return threshold


def feature_crossings(case: dict[str, Any], feature_name: str, sigma: float) -> np.ndarray:
    cache = case.setdefault("_crossing_cache", {})
    key = (feature_name, sigma)
    if key in cache:
        return cache[key]
    feature = case["features"][feature_name]
    crossings, threshold = fusion.crossing_times_for_signal(
        feature["time"],
        feature["signal"],
        case["window_s"],
        sigma,
    )
    case.setdefault("_threshold_cache", {})[key] = threshold
    cache[key] = crossings
    return crossings


def is_level_high(case: dict[str, Any], feature_name: str, sigma: float, time_s: float) -> bool:
    feature = case["features"][feature_name]
    threshold = feature_threshold(case, feature_name, sigma)
    value = float(np.interp(time_s, feature["time"], feature["signal"]))
    return value >= threshold


def has_recent_crossing(
    case: dict[str, Any],
    feature_name: str,
    sigma: float,
    time_s: float,
    window_s: float,
) -> bool:
    crossings = feature_crossings(case, feature_name, sigma)
    if len(crossings) == 0:
        return False
    return bool(np.any((crossings >= time_s - window_s) & (crossings <= time_s)))


def magnetic_gate_passes(case: dict[str, Any], config: dict[str, Any], time_s: float) -> bool:
    mode = config["mag_mode"]
    if mode == "none":
        return True
    predicates = []
    for feature_name in config["mag_features"]:
        level_high = is_level_high(case, feature_name, config["mag_sigma"], time_s)
        recent_crossing = has_recent_crossing(
            case,
            feature_name,
            config["mag_sigma"],
            time_s,
            config["mag_window_ms"] / 1000.0,
        )
        predicates.append(level_high or recent_crossing)
    if mode == "any":
        return any(predicates)
    if mode == "all":
        return all(predicates)
    raise ValueError(mode)


def gated_crossings(case: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    baseline_crossings = fusion.crossings_for_config(case, BASELINE_CONFIG)
    sxr_feature = case["features"][config["sxr_feature"]]
    sxr_times = feature_crossings(case, config["sxr_feature"], config["sxr_sigma"])
    crossings = [(row["time"], row["sources"]) for row in baseline_crossings]
    for time_s in sxr_times:
        if magnetic_gate_passes(case, config, float(time_s)):
            crossings.append((float(time_s), f"{config['sxr_feature']}_gated"))
    old_merge = fusion.MERGE_SEPARATION_S
    try:
        fusion.MERGE_SEPARATION_S = config["deadtime_ms"] / 1000.0
        return fusion.merge_crossings(crossings)
    finally:
        fusion.MERGE_SEPARATION_S = old_merge


def score_cases(
    cases: list[dict[str, Any]],
    events_by_shot: dict[int, np.ndarray],
    config: dict[str, Any],
) -> dict[str, Any]:
    return fusion.aggregate(
        [
            fusion.score_alignment(
                events_by_shot[int(case["shot"])],
                gated_crossings(case, config),
            )
            for case in cases
        ]
    )


def score_plain_config(
    cases: list[dict[str, Any]],
    events_by_shot: dict[int, np.ndarray],
    config: dict[str, float],
    deadtime_ms: float = 0.35,
) -> dict[str, Any]:
    old_merge = fusion.MERGE_SEPARATION_S
    try:
        fusion.MERGE_SEPARATION_S = deadtime_ms / 1000.0
        return fusion.aggregate(
            [
                fusion.score_alignment(
                    events_by_shot[int(case["shot"])],
                    fusion.crossings_for_config(case, config),
                )
                for case in cases
            ]
        )
    finally:
        fusion.MERGE_SEPARATION_S = old_merge


def compact_score(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "events": score["event_count"],
        "detected": score["detected_event_count"],
        "missed": score["missed_event_count"],
        "false_triggers": score["false_trigger_count"],
        "precision": score["precision"],
        "recall": score["recall"],
        "f1": score["f1"],
        "median_lead_ms": score["lead_ms"]["median"],
        "latency_reachable_3_ms": score["latency_feasible_event_count"]["3_ms"],
        "latency_reachable_5_ms": score["latency_feasible_event_count"]["5_ms"],
        "latency_reachable_8_ms": score["latency_feasible_event_count"]["8_ms"],
        "latency_reachable_12_ms": score["latency_feasible_event_count"]["12_ms"],
    }


def selection_score(score: dict[str, Any]) -> float:
    # Reject false-trigger-heavy SXR signatures while still valuing recall.
    return (
        2.0 * score["recall"]
        + 0.8 * score["precision"]
        - 0.025 * score["false_trigger_count"]
        + 0.004 * score["latency_feasible_event_count"]["5_ms"]
    )


def config_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sxr_feature in SXR_FEATURES:
        for sxr_sigma in SXR_SIGMAS:
            for deadtime_ms in DEADTIMES_MS:
                rows.append(
                    {
                        "sxr_feature": sxr_feature,
                        "sxr_sigma": sxr_sigma,
                        "deadtime_ms": deadtime_ms,
                        "mag_mode": "none",
                        "mag_features": (),
                        "mag_sigma": 0.0,
                        "mag_window_ms": 0.0,
                    }
                )
                for mag_mode, mag_features in (
                    ("any", ("pol_cc_ch2",)),
                    ("any", ("tor_cc_all",)),
                    ("any", MAG_FEATURES),
                ):
                    for mag_sigma in MAG_SIGMAS:
                        for mag_window_ms in MAG_WINDOWS_MS:
                            rows.append(
                                {
                                    "sxr_feature": sxr_feature,
                                    "sxr_sigma": sxr_sigma,
                                    "deadtime_ms": deadtime_ms,
                                    "mag_mode": mag_mode,
                                    "mag_features": mag_features,
                                    "mag_sigma": mag_sigma,
                                    "mag_window_ms": mag_window_ms,
                                }
                            )
    return rows


def row_for_score(split: str, config: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    return {
        "split": split,
        "config": json.dumps(
            {key: (list(value) if isinstance(value, tuple) else value) for key, value in config.items()},
            sort_keys=True,
        ),
        **compact_score(score),
        "selection_score": selection_score(score),
    }


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    baseline = summary["baseline_single_channel_reviewed_labels"]
    toroidal = summary["mirnov_toroidal_reviewed_labels"]
    selected = summary["selected_gate_reviewed_labels"]
    raw = summary["raw_sxr_reference_reviewed_labels"]
    lines = [
        "# FAIR-MAST SXR Morphology Gate",
        "",
        "- Status: `MAST_SXR_MORPHOLOGY_GATE_COMPLETED`",
        "- Goal: keep SXR recognition gains while rejecting SXR-only false-trigger bursts",
        "- Train split: automatic D-alpha labels on shots `30311`, `30423`",
        "- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`",
        "- Gate family: SXR threshold crossings plus causal magnetic level/recent-crossing requirements",
        "",
        "## Selected Gate",
        "",
        f"- Selected config: `{summary['selected_config']}`",
        f"- Train selection score: `{summary['selected_train_score']:.3f}`",
        "",
        "## Held-Out Accepted-Label Result",
        "",
        "| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Single-channel baseline | {baseline['event_count']} | {baseline['detected_event_count']} | {baseline['missed_event_count']} | {baseline['false_trigger_count']} | {baseline['precision']:.3f} | {baseline['recall']:.3f} | {baseline['lead_ms']['median']:.3f} ms |",
        f"| Mirnov+toroidal reference | {toroidal['event_count']} | {toroidal['detected_event_count']} | {toroidal['missed_event_count']} | {toroidal['false_trigger_count']} | {toroidal['precision']:.3f} | {toroidal['recall']:.3f} | {toroidal['lead_ms']['median']:.3f} ms |",
        f"| Raw SXR reference | {raw['event_count']} | {raw['detected_event_count']} | {raw['missed_event_count']} | {raw['false_trigger_count']} | {raw['precision']:.3f} | {raw['recall']:.3f} | {raw['lead_ms']['median']:.3f} ms |",
        f"| Selected morphology gate | {selected['event_count']} | {selected['detected_event_count']} | {selected['missed_event_count']} | {selected['false_trigger_count']} | {selected['precision']:.3f} | {selected['recall']:.3f} | {selected['lead_ms']['median']:.3f} ms |",
        "",
        "## Latency-Reachable Accepted Events",
        "",
        "| Required latency | Baseline | Mirnov+toroidal | Raw SXR | Morphology gate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for latency in fusion.LATENCIES_MS:
        key = f"{latency:g}_ms"
        lines.append(
            f"| `{key}` | {baseline['latency_feasible_event_count'][key]} | "
            f"{toroidal['latency_feasible_event_count'][key]} | "
            f"{raw['latency_feasible_event_count'][key]} | "
            f"{selected['latency_feasible_event_count'][key]} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This is a causal gate in the limited sense that it uses only current or",
        "prior diagnostic state at the candidate trigger time. It does not use the",
        "future D-alpha event label except during offline train/test scoring.",
        "",
        "If the selected gate does not beat the Mirnov+toroidal reference on held-out",
        "reviewed labels, then the fixed-threshold SXR morphology path should be",
        "treated as useful diagnostic evidence but not an improved operational",
        "trigger. A stronger model would need additional features, more shots, or",
        "expert-reviewed labels.",
        "",
        "## Claim Boundary",
        "",
        "This is an offline public-data gate screen. It is not causal TCT validation,",
        "a measured actuator response, or a deployable controller.",
        "",
    ]
    (run_dir / "fair_mast_sxr_morphology_gate_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    reviewed = fusion.load_review_labels(fusion.DEFAULT_REVIEW_DIR)
    cases = []
    for case_def in fusion.CASES:
        print(f"loading shot {case_def['shot']} ({case_def['split']})", flush=True)
        cases.append(load_case_with_retries(case_def))
    print("loaded cases; starting grid search", flush=True)
    train_cases = [case for case in cases if case["split"] == "train"]
    test_cases = [case for case in cases if case["split"] == "test"]
    train_events = {int(case["shot"]): case["automatic_event_times"] for case in train_cases}

    rows: list[dict[str, Any]] = []
    best_config: dict[str, Any] | None = None
    best_train_score = -1e9
    best_train_agg: dict[str, Any] | None = None
    for config in config_rows():
        train_agg = score_cases(train_cases, train_events, config)
        score = selection_score(train_agg)
        rows.append(row_for_score("train", config, train_agg))
        if score > best_train_score:
            best_train_score = score
            best_config = config
            best_train_agg = train_agg

    assert best_config is not None
    print("grid search complete; evaluating held-out reviewed labels", flush=True)
    test_agg = score_cases(test_cases, reviewed, best_config)
    rows.append(row_for_score("test_selected", best_config, test_agg))

    baseline_agg = score_plain_config(test_cases, reviewed, BASELINE_CONFIG)
    toroidal_agg = score_plain_config(test_cases, reviewed, TOROIDAL_CONFIG)
    raw_sxr_config = {
        "sxr_feature": "sxr_upper_all",
        "sxr_sigma": 4.0,
        "deadtime_ms": 0.35,
        "mag_mode": "none",
        "mag_features": (),
        "mag_sigma": 0.0,
        "mag_window_ms": 0.0,
    }
    raw_sxr_agg = score_cases(test_cases, reviewed, raw_sxr_config)

    serial_config = {
        key: (list(value) if isinstance(value, tuple) else value)
        for key, value in best_config.items()
    }
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_SXR_MORPHOLOGY_GATE_COMPLETED",
        "selected_config": serial_config,
        "selected_train_score": best_train_score,
        "selected_train_labels": best_train_agg,
        "selected_gate_reviewed_labels": test_agg,
        "baseline_single_channel_reviewed_labels": baseline_agg,
        "mirnov_toroidal_reviewed_labels": toroidal_agg,
        "raw_sxr_reference_reviewed_labels": raw_sxr_agg,
        "claim_boundary": "Offline public-data SXR morphology gate only; not causal TCT validation.",
    }

    write_csv(args.run_dir / "fair_mast_sxr_morphology_gate_grid.csv", rows)
    (args.run_dir / "fair_mast_sxr_morphology_gate_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

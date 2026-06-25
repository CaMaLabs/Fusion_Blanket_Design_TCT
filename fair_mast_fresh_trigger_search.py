#!/usr/bin/env python3
"""Search for better FAIR-MAST triggers on unused fresh public shots."""

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
import fair_mast_omv_fresh_split as fresh
import fair_mast_other_trigger_screen as other


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_fresh_trigger_search_default"
TRAIN_SHOT_COUNT = 10
TEST_SHOT_COUNT = 10
SIGMA_GRID = (4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0)
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}


FEATURE_SPECS = (
    {"name": "pol_cc_ch2", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_cc_field", "channels": (2,), "kind": "rms"},
    {"name": "pol_cc_all", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_cc_field", "channels": (0, 1, 2, 3, 4), "kind": "rms"},
    {"name": "tor_cc_all", "group": "magnetics", "time": "time_mirnov", "field": "b_field_tor_probe_cc_field", "channels": (0, 1, 2), "kind": "rms"},
    {"name": "pol_omv_rms", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_omv_voltage", "channels": (0, 1, 2), "kind": "rms"},
    {"name": "tor_omaha_rms", "group": "magnetics", "time": "time_omaha", "field": "b_field_tor_probe_omaha_voltage", "channels": (0, 1, 2, 3), "kind": "rms"},
    {"name": "saddle_tor_rms", "group": "magnetics", "time": "time_saddle", "field": "b_field_tor_probe_saddle_voltage", "channels": tuple(range(12)), "kind": "rms"},
    {"name": "dalpha_ch0_abs_slope", "group": "spectrometer_visible", "time": "time", "field": "filter_spectrometer_dalpha_voltage", "channels": (0,), "kind": "abs_slope"},
    {"name": "density_gradient_abs_slope", "group": "spectrometer_visible", "time": "time", "field": "density_gradient", "channels": None, "kind": "abs_slope"},
    {"name": "summary_radiated_abs_slope", "group": "summary", "time": "time", "field": "power_radiated", "channels": None, "kind": "abs_slope"},
)


class ShotLoadTimeout(TimeoutError):
    pass


def _timeout_handler(_signum: int, _frame: Any) -> None:
    raise ShotLoadTimeout("FAIR-MAST shot load timed out")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def available(group: zarr.Group, spec: dict[str, Any]) -> bool:
    try:
        node = group[spec["group"]]
        _ = node[spec["time"]].shape
        _ = node[spec["field"]].shape
    except Exception:
        return False
    return True


def load_case(shot: int, window_s: tuple[float, float]) -> dict[str, Any]:
    group = zarr.open_group(f"{fusion.ARCHIVE_ROOT}/{shot}.zarr", mode="r")
    visible = group["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[fusion.D_ALPHA_CHANNEL]
    automatic_events = fusion.detect_events(dalpha_time, dalpha, window_s)

    accepted = []
    review_rows = []
    for event_number, event_time in enumerate(automatic_events, start=1):
        context = fresh.local_peak_context(dalpha_time, dalpha, float(event_time))
        label, notes = fresh.review_label(float(event_time), automatic_events, context, window_s)
        if label == "true_elm":
            accepted.append(float(event_time))
        review_rows.append(
            {
                "shot": shot,
                "event_number": event_number,
                "event_time_s": float(event_time),
                **context,
                "review_label": label,
                "review_notes": notes,
            }
        )

    features: dict[str, dict[str, Any]] = {}
    missing = []
    for spec in FEATURE_SPECS:
        if not available(group, spec):
            missing.append(spec["name"])
            continue
        node = group[spec["group"]]
        time_axis = np.asarray(node[spec["time"]], dtype=float)
        data = np.asarray(node[spec["field"]], dtype=float)
        signal = other.feature_signal(time_axis, data, spec)
        time_axis, signal = other.maybe_decimate(time_axis, signal)
        features[spec["name"]] = {"time": time_axis, "signal": signal}

    return {
        "shot": shot,
        "split": "fresh_search",
        "window_s": window_s,
        "automatic_event_times": automatic_events,
        "accepted_event_times": np.asarray(accepted, dtype=float),
        "review_rows": review_rows,
        "features": features,
        "missing_features": missing,
    }


def load_case_with_retries(shot: int, window_s: tuple[float, float], attempts: int = 3, timeout_s: int = 180) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout_s)
            try:
                return load_case(shot, window_s)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        except Exception as exc:
            last_error = exc
            print(f"load failed for shot {shot} attempt {attempt}/{attempts}: {type(exc).__name__}", flush=True)
            if attempt < attempts:
                time.sleep(2.0 * attempt)
    assert last_error is not None
    raise last_error


def candidate_configs(feature_names: set[str]) -> list[dict[str, float]]:
    configs: list[dict[str, float]] = []
    for sigma in SIGMA_GRID:
        if "pol_cc_ch2" in feature_names:
            configs.append({"pol_cc_ch2": sigma})
    for feature_name in sorted(feature_names):
        if feature_name == "pol_cc_ch2":
            continue
        for sigma in SIGMA_GRID:
            configs.append({feature_name: sigma})
            if "pol_cc_ch2" in feature_names:
                for base_sigma in (6.0, 8.0, 10.0):
                    configs.append({"pol_cc_ch2": base_sigma, feature_name: sigma})
    deduped = []
    seen = set()
    for config in configs:
        key = json.dumps(config, sort_keys=True)
        if key not in seen:
            seen.add(key)
            deduped.append(config)
    return deduped


def score_config(cases: list[dict[str, Any]], config: dict[str, float]) -> dict[str, Any]:
    scores = []
    for case in cases:
        if not set(config).issubset(case["features"]):
            continue
        scores.append(fusion.score_alignment(case["accepted_event_times"], fusion.crossings_for_config(case, config)))
    return fusion.aggregate(scores)


def selection_score(score: dict[str, Any]) -> float:
    return 2.0 * score["recall"] + 1.0 * score["precision"] - 0.035 * score["false_trigger_count"]


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


def per_shot_rows(cases: list[dict[str, Any]], configs: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        for name, config in configs.items():
            score = score_config([case], config)
            rows.append(
                {
                    "shot": int(case["shot"]),
                    "config_name": name,
                    "config": json.dumps(config, sort_keys=True),
                    **compact_score(score),
                    "selection_score": selection_score(score),
                }
            )
    return rows


def write_report(run_dir: Path, summary: dict[str, Any], rows: list[dict[str, Any]], per_shot: list[dict[str, Any]]) -> None:
    baseline = summary["test_baseline"]
    selected = summary["test_selected"]
    top_train = sorted([row for row in rows if row["split"] == "train"], key=lambda row: -row["selection_score"])[:10]
    top_test = sorted([row for row in rows if row["split"] == "test_all"], key=lambda row: -row["selection_score"])[:10]
    lines = [
        "# FAIR-MAST Fresh Trigger Search",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: search unused FAIR-MAST shots for a cleaner trigger than fixed Mirnov6",
        f"- Train shots: `{summary['train_shots']}`",
        f"- Test shots: `{summary['test_shots']}`",
        f"- Candidate count: `{summary['config_count']}`",
        f"- Selected config: `{summary['selected_config']}`",
        "",
        "## Held-Out Fresh Test Result",
        "",
        "| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Baseline Mirnov6 | {baseline['event_count']} | {baseline['detected_event_count']} | {baseline['missed_event_count']} | {baseline['false_trigger_count']} | {baseline['precision']:.3f} | {baseline['recall']:.3f} | {baseline['lead_ms']['median']:.3f} ms | {summary['test_baseline_score']:.3f} |",
        f"| Train-selected trigger | {selected['event_count']} | {selected['detected_event_count']} | {selected['missed_event_count']} | {selected['false_trigger_count']} | {selected['precision']:.3f} | {selected['recall']:.3f} | {selected['lead_ms']['median']:.3f} ms | {summary['test_selected_score']:.3f} |",
        "",
        "## Top Train Rows",
        "",
        "| Config | Detected | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top_train:
        lines.append(
            f"| `{row['config']}` | {row['detected']}/{row['events']} | {row['false_triggers']} | "
            f"{row['precision']:.3f} | {row['recall']:.3f} | {row['median_lead_ms']} | {row['selection_score']:.3f} |"
        )
    lines += [
        "",
        "## Top Exploratory Test Rows",
        "",
        "These rows rank test labels directly and are for lead generation only.",
        "",
        "| Config | Detected | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top_test:
        lines.append(
            f"| `{row['config']}` | {row['detected']}/{row['events']} | {row['false_triggers']} | "
            f"{row['precision']:.3f} | {row['recall']:.3f} | {row['median_lead_ms']} | {row['selection_score']:.3f} |"
        )
    lines += [
        "",
        "## Per-Shot Selected Vs Baseline",
        "",
        "| Shot | Baseline detected | Selected detected | Baseline false | Selected false |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    by_key = {(row["shot"], row["config_name"]): row for row in per_shot}
    for shot in summary["test_shots"]:
        base = by_key[(shot, "baseline")]
        selected_row = by_key[(shot, "selected")]
        lines.append(
            f"| {shot} | {base['detected']}/{base['events']} | {selected_row['detected']}/{selected_row['events']} | "
            f"{base['false_triggers']} | {selected_row['false_triggers']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        f"Search verdict: `{summary['search_verdict']}`.",
        "",
        "This is a fresh unused-shot train/test search with machine morphology",
        "labels. It can identify candidate trigger directions, but it is not",
        "expert-reviewed or causal TCT validation.",
        "",
    ]
    (run_dir / "fair_mast_fresh_trigger_search_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--candidate-skip-count", type=int, default=0)
    parser.add_argument("--train-shot-count", type=int, default=TRAIN_SHOT_COUNT)
    parser.add_argument("--test-shot-count", type=int, default=TEST_SHOT_COUNT)
    args = parser.parse_args()

    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    candidates = fresh.discover_candidates(fresh.MIN_AUTOMATIC_EVENTS)
    needed = args.train_shot_count + args.test_shot_count
    if len(candidates) < needed:
        raise RuntimeError(f"found only {len(candidates)} fresh candidates; need {needed}")
    selected_candidates = []
    skipped_candidates = []
    cases = []
    for row in candidates[args.candidate_skip_count :]:
        if len(cases) >= needed:
            break
        shot = int(row["shot"])
        print(f"loading shot {shot}", flush=True)
        try:
            cases.append(load_case_with_retries(shot, fresh.FRESH_WINDOW_S))
            selected_candidates.append(row)
        except Exception as exc:
            skipped = dict(row)
            skipped["skip_reason"] = type(exc).__name__
            skipped_candidates.append(skipped)
            print(f"skipping shot {shot}: {type(exc).__name__}", flush=True)
    if len(cases) < needed:
        raise RuntimeError(f"loaded only {len(cases)} usable fresh shots; need {needed}")

    train_cases = cases[: args.train_shot_count]
    test_cases = cases[args.train_shot_count : needed]
    train_shots = [int(case["shot"]) for case in train_cases]
    test_shots = [int(case["shot"]) for case in test_cases]
    feature_names = set.intersection(*(set(case["features"]) for case in cases))
    configs = candidate_configs(feature_names)

    rows = []
    best_config = None
    best_score = -1e9
    for config in configs:
        score = score_config(train_cases, config)
        row_score = selection_score(score)
        rows.append({"split": "train", "config": json.dumps(config, sort_keys=True), **compact_score(score), "selection_score": row_score})
        if row_score > best_score:
            best_config = config
            best_score = row_score
    assert best_config is not None

    baseline_test = score_config(test_cases, BASELINE_CONFIG)
    selected_test = score_config(test_cases, best_config)
    rows.append({"split": "test_selected", "config": json.dumps(best_config, sort_keys=True), **compact_score(selected_test), "selection_score": selection_score(selected_test)})
    rows.append({"split": "test_baseline", "config": json.dumps(BASELINE_CONFIG, sort_keys=True), **compact_score(baseline_test), "selection_score": selection_score(baseline_test)})

    best_test_config = None
    best_test_score = -1e9
    best_test_result = None
    for config in configs:
        score = score_config(test_cases, config)
        row_score = selection_score(score)
        rows.append({"split": "test_all", "config": json.dumps(config, sort_keys=True), **compact_score(score), "selection_score": row_score})
        if row_score > best_test_score:
            best_test_config = config
            best_test_score = row_score
            best_test_result = score
    assert best_test_config is not None and best_test_result is not None

    per_shot = per_shot_rows(test_cases, {"baseline": BASELINE_CONFIG, "selected": best_config})
    selected_delta_detected = selected_test["detected_event_count"] - baseline_test["detected_event_count"]
    selected_delta_false = selected_test["false_trigger_count"] - baseline_test["false_trigger_count"]
    selected_delta_score = selection_score(selected_test) - selection_score(baseline_test)
    if selected_delta_score > 0 and selected_delta_detected >= 0:
        verdict = "train_selected_trigger_improves_fresh_test_score"
    elif selected_delta_detected > 0:
        verdict = "train_selected_trigger_recovers_events_with_noise_cost"
    else:
        verdict = "no_train_selected_improvement_on_fresh_test"

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_FRESH_TRIGGER_SEARCH_COMPLETED",
        "candidate_count": len(candidates),
        "candidate_skip_count": args.candidate_skip_count,
        "skipped_candidate_count": len(skipped_candidates),
        "config_count": len(configs),
        "window_s": list(fresh.FRESH_WINDOW_S),
        "excluded_prior_shots": sorted(fresh.EXCLUDED_PRIOR_SHOTS),
        "train_shots": train_shots,
        "test_shots": test_shots,
        "feature_names": sorted(feature_names),
        "selected_config": best_config,
        "selected_train_score": best_score,
        "test_baseline": baseline_test,
        "test_selected": selected_test,
        "test_baseline_score": selection_score(baseline_test),
        "test_selected_score": selection_score(selected_test),
        "test_selected_detected_delta_vs_baseline": selected_delta_detected,
        "test_selected_false_trigger_delta_vs_baseline": selected_delta_false,
        "test_selected_score_delta_vs_baseline": selected_delta_score,
        "best_exploratory_test_config": best_test_config,
        "best_exploratory_test": best_test_result,
        "best_exploratory_test_score": best_test_score,
        "search_verdict": verdict,
        "claim_boundary": "Fresh unused-shot trigger search only; not expert-reviewed or causal validation.",
    }

    write_csv(args.run_dir / "fair_mast_fresh_trigger_search_candidates.csv", candidates)
    write_csv(args.run_dir / "fair_mast_fresh_trigger_search_skipped_candidates.csv", skipped_candidates)
    write_csv(args.run_dir / "fair_mast_fresh_trigger_search_grid.csv", rows)
    write_csv(args.run_dir / "fair_mast_fresh_trigger_search_per_shot.csv", per_shot)
    (args.run_dir / "fair_mast_fresh_trigger_search_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary, rows, per_shot)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

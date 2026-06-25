#!/usr/bin/env python3
"""Train/test a causal morphology classifier trigger on fresh FAIR-MAST shots."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import fair_mast_fresh_trigger_search as search
import fair_mast_omv_fresh_split as fresh
import fair_mast_other_trigger_screen as other
import fair_mast_multidiagnostic_precursor_fusion as fusion


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_morphology_classifier_trigger_default"
TRAIN_SHOT_COUNT = 7
TEST_SHOT_COUNT = 6
CANDIDATE_SKIP_COUNT = 20
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}
REFERENCE_CONFIG = {"pol_cc_all": 5.0}
SOURCE_CONFIGS = (
    ("pol_cc_ch2", 4.0),
    ("pol_cc_ch2", 6.0),
    ("pol_cc_ch2", 8.0),
    ("pol_cc_all", 4.0),
    ("pol_cc_all", 5.0),
    ("pol_cc_all", 6.0),
    ("tor_cc_all", 6.0),
    ("tor_cc_all", 8.0),
    ("pol_omv_rms", 4.0),
    ("pol_omv_rms", 6.0),
    ("dalpha_ch0_abs_slope", 4.0),
)
FEATURE_NAMES = ("pol_cc_ch2", "pol_cc_all", "tor_cc_all", "pol_omv_rms", "dalpha_ch0_abs_slope")
THRESHOLD_QUANTILES = tuple(np.linspace(0.50, 0.98, 25))
RIDGE_ALPHA = 1.0


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_cases(skip_count: int, train_count: int, test_count: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = fresh.discover_candidates(fresh.MIN_AUTOMATIC_EVENTS)
    needed = train_count + test_count
    loaded = []
    skipped = []
    for row in candidates[skip_count:]:
        if len(loaded) >= needed:
            break
        shot = int(row["shot"])
        print(f"loading shot {shot}", flush=True)
        try:
            loaded.append(search.load_case_with_retries(shot, fresh.FRESH_WINDOW_S))
        except Exception as exc:
            skipped_row = dict(row)
            skipped_row["skip_reason"] = type(exc).__name__
            skipped.append(skipped_row)
            print(f"skipping shot {shot}: {type(exc).__name__}", flush=True)
    if len(loaded) < needed:
        raise RuntimeError(f"loaded only {len(loaded)} usable shots; need {needed}")
    return loaded, candidates, skipped


def feature_baseline_stats(case: dict[str, Any], feature_name: str) -> tuple[float, float]:
    cache = case.setdefault("_morph_stats", {})
    if feature_name in cache:
        return cache[feature_name]
    feature = case["features"][feature_name]
    start, end = case["window_s"]
    baseline = (feature["time"] >= start) & (feature["time"] <= min(end, start + fusion.BASELINE_WINDOW_S))
    values = feature["signal"][baseline]
    median = float(np.nanmedian(values))
    sigma = max(float(fusion.robust_sigma(values)), 1e-12)
    cache[feature_name] = (median, sigma)
    return median, sigma


def normalized_value(case: dict[str, Any], feature_name: str, time_s: float) -> float:
    feature = case["features"][feature_name]
    median, sigma = feature_baseline_stats(case, feature_name)
    value = float(np.interp(time_s, feature["time"], feature["signal"]))
    return (value - median) / sigma


def normalized_slope(case: dict[str, Any], feature_name: str, time_s: float, lag_s: float) -> float:
    feature = case["features"][feature_name]
    _, sigma = feature_baseline_stats(case, feature_name)
    current = float(np.interp(time_s, feature["time"], feature["signal"]))
    previous = float(np.interp(max(case["window_s"][0], time_s - lag_s), feature["time"], feature["signal"]))
    return (current - previous) / sigma


def source_crossings(case: dict[str, Any], feature_name: str, sigma: float) -> np.ndarray:
    cache = case.setdefault("_morph_crossings", {})
    key = (feature_name, sigma)
    if key in cache:
        return cache[key]
    if feature_name not in case["features"]:
        crossings = np.asarray([], dtype=float)
    else:
        feature = case["features"][feature_name]
        crossings, _ = fusion.crossing_times_for_signal(feature["time"], feature["signal"], case["window_s"], sigma)
    cache[key] = crossings
    return crossings


def recent_crossing_count(case: dict[str, Any], feature_name: str, time_s: float, window_s: float = 0.002) -> int:
    total = 0
    for source_name, sigma in SOURCE_CONFIGS:
        if source_name != feature_name:
            continue
        crossings = source_crossings(case, source_name, sigma)
        total += int(np.count_nonzero((crossings >= time_s - window_s) & (crossings <= time_s)))
    return total


def candidate_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for source_name, sigma in SOURCE_CONFIGS:
        if source_name not in case["features"]:
            continue
        for time_s in source_crossings(case, source_name, sigma):
            key = round(float(time_s), 6)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"shot": int(case["shot"]), "time": float(time_s), "source": source_name, "sigma": sigma})
    return sorted(rows, key=lambda row: row["time"])


def candidate_features(case: dict[str, Any], row: dict[str, Any]) -> list[float]:
    time_s = float(row["time"])
    values: list[float] = [1.0, float(row["sigma"])]
    for source_name, _ in SOURCE_CONFIGS[:0]:
        values.append(0.0)
    for source_name, _sigma in SOURCE_CONFIGS:
        values.append(1.0 if row["source"] == source_name else 0.0)
    for feature_name in FEATURE_NAMES:
        if feature_name not in case["features"]:
            values.extend([0.0, 0.0, 0.0, 0.0])
            continue
        values.append(normalized_value(case, feature_name, time_s))
        values.append(normalized_slope(case, feature_name, time_s, 0.0005))
        values.append(normalized_slope(case, feature_name, time_s, 0.0015))
        values.append(float(recent_crossing_count(case, feature_name, time_s)))
    return values


def candidate_label(case: dict[str, Any], time_s: float) -> int:
    events = case["accepted_event_times"]
    return int(np.any((events - fusion.PRECURSOR_WINDOW_S[1] <= time_s) & (time_s <= events - fusion.PRECURSOR_WINDOW_S[0])))


def build_matrix(cases: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    rows = []
    x_rows = []
    y_rows = []
    for case in cases:
        for row in candidate_rows(case):
            row = dict(row)
            row["label"] = candidate_label(case, row["time"])
            rows.append(row)
            x_rows.append(candidate_features(case, row))
            y_rows.append(row["label"])
    return np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=float), rows


def fit_linear_classifier(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    means = np.nanmean(x, axis=0)
    stds = np.nanstd(x, axis=0)
    stds[stds < 1e-9] = 1.0
    z = (np.nan_to_num(x, nan=0.0) - means) / stds
    xtx = z.T @ z
    xty = z.T @ y
    weights = np.linalg.solve(xtx + RIDGE_ALPHA * np.eye(xtx.shape[0]), xty)
    scores = z @ weights
    return {"means": means, "stds": stds, "weights": weights, "train_scores": scores}


def score_candidates(model: dict[str, Any], x: np.ndarray) -> np.ndarray:
    z = (np.nan_to_num(x, nan=0.0) - model["means"]) / model["stds"]
    return z @ model["weights"]


def classifier_crossings(cases: list[dict[str, Any]], model: dict[str, Any], threshold: float) -> dict[int, list[dict[str, Any]]]:
    by_shot: dict[int, list[dict[str, Any]]] = {}
    for case in cases:
        x, _y, rows = build_matrix([case])
        scores = score_candidates(model, x) if len(rows) else np.asarray([], dtype=float)
        crossings = []
        for row, score in zip(rows, scores):
            if float(score) >= threshold:
                crossings.append((float(row["time"]), f"classifier:{row['source']}"))
        by_shot[int(case["shot"])] = fusion.merge_crossings(crossings)
    return by_shot


def score_classifier(cases: list[dict[str, Any]], model: dict[str, Any], threshold: float) -> dict[str, Any]:
    crossing_map = classifier_crossings(cases, model, threshold)
    return fusion.aggregate(
        [
            fusion.score_alignment(case["accepted_event_times"], crossing_map[int(case["shot"])])
            for case in cases
        ]
    )


def selection_score(score: dict[str, Any]) -> float:
    return 2.0 * score["recall"] + 1.0 * score["precision"] - 0.04 * score["false_trigger_count"]


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


def per_shot_rows(cases: list[dict[str, Any]], model: dict[str, Any], threshold: float) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        baseline = search.score_config([case], BASELINE_CONFIG)
        reference = search.score_config([case], REFERENCE_CONFIG)
        classifier = score_classifier([case], model, threshold)
        for name, score in {"baseline": baseline, "reference_pol_cc_all5": reference, "classifier": classifier}.items():
            rows.append({"shot": int(case["shot"]), "config_name": name, **compact_score(score), "selection_score": selection_score(score)})
    return rows


def write_report(run_dir: Path, summary: dict[str, Any], threshold_rows: list[dict[str, Any]], per_shot: list[dict[str, Any]]) -> None:
    baseline = summary["test_baseline"]
    reference = summary["test_reference_pol_cc_all5"]
    classifier = summary["test_classifier"]
    top = sorted(threshold_rows, key=lambda row: -row["selection_score"])[:10]
    lines = [
        "# FAIR-MAST Morphology Classifier Trigger",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: train a causal pre-trigger morphology classifier on fresh unused shots",
        f"- Train shots: `{summary['train_shots']}`",
        f"- Test shots: `{summary['test_shots']}`",
        f"- Selected classifier threshold: `{summary['selected_threshold']:.6f}`",
        f"- Candidate rows: train `{summary['train_candidate_count']}`, test `{summary['test_candidate_count']}`",
        "",
        "## Held-Out Fresh Test Result",
        "",
        "| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Baseline Mirnov6 | {baseline['event_count']} | {baseline['detected_event_count']} | {baseline['missed_event_count']} | {baseline['false_trigger_count']} | {baseline['precision']:.3f} | {baseline['recall']:.3f} | {baseline['lead_ms']['median']:.3f} ms | {summary['test_baseline_score']:.3f} |",
        f"| Reference pol_cc_all5 | {reference['event_count']} | {reference['detected_event_count']} | {reference['missed_event_count']} | {reference['false_trigger_count']} | {reference['precision']:.3f} | {reference['recall']:.3f} | {reference['lead_ms']['median']:.3f} ms | {summary['test_reference_score']:.3f} |",
        f"| Morphology classifier | {classifier['event_count']} | {classifier['detected_event_count']} | {classifier['missed_event_count']} | {classifier['false_trigger_count']} | {classifier['precision']:.3f} | {classifier['recall']:.3f} | {classifier['lead_ms']['median']:.3f} ms | {summary['test_classifier_score']:.3f} |",
        "",
        "## Top Train Thresholds",
        "",
        "| Threshold | Detected | False triggers | Precision | Recall | Score |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top:
        lines.append(
            f"| {row['threshold']:.6f} | {row['detected']}/{row['events']} | {row['false_triggers']} | "
            f"{row['precision']:.3f} | {row['recall']:.3f} | {row['selection_score']:.3f} |"
        )
    lines += [
        "",
        "## Per-Shot Test Result",
        "",
        "| Shot | Baseline detected/false | Reference detected/false | Classifier detected/false |",
        "| ---: | ---: | ---: | ---: |",
    ]
    by_key = {(row["shot"], row["config_name"]): row for row in per_shot}
    for shot in summary["test_shots"]:
        base = by_key[(shot, "baseline")]
        ref = by_key[(shot, "reference_pol_cc_all5")]
        clf = by_key[(shot, "classifier")]
        lines.append(
            f"| {shot} | {base['detected']}/{base['events']} / {base['false_triggers']} | "
            f"{ref['detected']}/{ref['events']} / {ref['false_triggers']} | "
            f"{clf['detected']}/{clf['events']} / {clf['false_triggers']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        f"Classifier verdict: `{summary['classifier_verdict']}`.",
        "",
        "Features are computed at or before the candidate trigger time. The event",
        "labels are used only offline for training and evaluation.",
        "",
    ]
    (run_dir / "fair_mast_morphology_classifier_trigger_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--candidate-skip-count", type=int, default=CANDIDATE_SKIP_COUNT)
    parser.add_argument("--train-shot-count", type=int, default=TRAIN_SHOT_COUNT)
    parser.add_argument("--test-shot-count", type=int, default=TEST_SHOT_COUNT)
    args = parser.parse_args()

    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    cases, candidates, skipped = load_cases(args.candidate_skip_count, args.train_shot_count, args.test_shot_count)
    train_cases = cases[: args.train_shot_count]
    test_cases = cases[args.train_shot_count :]

    x_train, y_train, train_rows = build_matrix(train_cases)
    x_test, y_test, test_rows = build_matrix(test_cases)
    model = fit_linear_classifier(x_train, y_train)
    train_scores = model["train_scores"]
    candidate_thresholds = sorted(set(float(np.quantile(train_scores, q)) for q in THRESHOLD_QUANTILES))
    threshold_rows = []
    best_threshold = None
    best_score = -1e9
    best_train_score = None
    for threshold in candidate_thresholds:
        score = score_classifier(train_cases, model, threshold)
        row_score = selection_score(score)
        row = {"threshold": threshold, **compact_score(score), "selection_score": row_score}
        threshold_rows.append(row)
        if row_score > best_score:
            best_score = row_score
            best_threshold = threshold
            best_train_score = score
    assert best_threshold is not None
    assert best_train_score is not None

    baseline_test = search.score_config(test_cases, BASELINE_CONFIG)
    reference_test = search.score_config(test_cases, REFERENCE_CONFIG)
    classifier_test = score_classifier(test_cases, model, best_threshold)
    per_shot = per_shot_rows(test_cases, model, best_threshold)
    score_delta = selection_score(classifier_test) - selection_score(baseline_test)
    false_delta = classifier_test["false_trigger_count"] - baseline_test["false_trigger_count"]
    detected_delta = classifier_test["detected_event_count"] - baseline_test["detected_event_count"]
    if score_delta > 0.1 and false_delta <= 0:
        verdict = "classifier_cleanly_improves_baseline"
    elif detected_delta > 0 and score_delta > 0:
        verdict = "classifier_recall_gain_with_tradeoff"
    elif detected_delta > 0:
        verdict = "classifier_recall_gain_with_unfavorable_noise"
    else:
        verdict = "classifier_does_not_improve_baseline"

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_MORPHOLOGY_CLASSIFIER_TRIGGER_COMPLETED",
        "candidate_skip_count": args.candidate_skip_count,
        "train_shots": [int(case["shot"]) for case in train_cases],
        "test_shots": [int(case["shot"]) for case in test_cases],
        "skipped_candidate_count": len(skipped),
        "source_configs": [{"feature": name, "sigma": sigma} for name, sigma in SOURCE_CONFIGS],
        "feature_names": list(FEATURE_NAMES),
        "train_candidate_count": len(train_rows),
        "test_candidate_count": len(test_rows),
        "train_positive_candidate_count": int(np.sum(y_train)),
        "test_positive_candidate_count": int(np.sum(y_test)),
        "selected_threshold": best_threshold,
        "selected_train_score": best_score,
        "selected_train_result": best_train_score,
        "test_baseline": baseline_test,
        "test_reference_pol_cc_all5": reference_test,
        "test_classifier": classifier_test,
        "test_baseline_score": selection_score(baseline_test),
        "test_reference_score": selection_score(reference_test),
        "test_classifier_score": selection_score(classifier_test),
        "test_classifier_detected_delta_vs_baseline": detected_delta,
        "test_classifier_false_trigger_delta_vs_baseline": false_delta,
        "test_classifier_score_delta_vs_baseline": score_delta,
        "classifier_verdict": verdict,
        "claim_boundary": "Fresh unused-shot morphology classifier only; not expert-reviewed or causal validation.",
    }

    write_csv(args.run_dir / "fair_mast_morphology_classifier_thresholds.csv", threshold_rows)
    write_csv(args.run_dir / "fair_mast_morphology_classifier_per_shot.csv", per_shot)
    write_csv(args.run_dir / "fair_mast_morphology_classifier_skipped_candidates.csv", skipped)
    (args.run_dir / "fair_mast_morphology_classifier_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary, threshold_rows, per_shot)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

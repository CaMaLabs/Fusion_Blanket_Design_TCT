#!/usr/bin/env python3
"""Follow up the exploratory FAIR-MAST lower-threshold OMV trigger lead."""

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
import fair_mast_other_trigger_screen as other


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_omv_followup_default"
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}
TRAIN_SELECTED_OMV_CONFIG = {"pol_cc_ch2": 6.0, "pol_omv_rms": 10.0}
EXPLORATORY_OMV_CONFIG = {"pol_cc_ch2": 6.0, "pol_omv_rms": 6.0}
OMV_SIGMAS = (4.0, 5.0, 6.0, 8.0, 10.0)


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


def load_case(case_def: dict[str, Any]) -> dict[str, Any]:
    shot = int(case_def["shot"])
    window_s = tuple(case_def["window_s"])
    group = zarr.open_group(f"{fusion.ARCHIVE_ROOT}/{shot}.zarr", mode="r")
    visible = group["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[fusion.D_ALPHA_CHANNEL]
    automatic_events = fusion.detect_events(dalpha_time, dalpha, window_s)

    specs = (
        {"name": "pol_cc_ch2", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_cc_field", "channels": (2,), "kind": "rms"},
        {"name": "pol_omv_rms", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_omv_voltage", "channels": (0, 1, 2), "kind": "rms"},
    )
    features: dict[str, dict[str, Any]] = {}
    for spec in specs:
        node = group[spec["group"]]
        time_axis = np.asarray(node[spec["time"]], dtype=float)
        data = np.asarray(node[spec["field"]], dtype=float)
        signal = other.feature_signal(time_axis, data, spec)
        time_axis, signal = other.maybe_decimate(time_axis, signal)
        features[spec["name"]] = {"time": time_axis, "signal": signal}

    return {
        "shot": shot,
        "split": case_def["split"],
        "window_s": window_s,
        "automatic_event_times": automatic_events,
        "features": features,
    }


def load_case_with_retries(case_def: dict[str, Any], attempts: int = 3, timeout_s: int = 180) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout_s)
            try:
                return load_case(case_def)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        except Exception as exc:
            last_error = exc
            print(f"load failed for shot {case_def['shot']} attempt {attempt}/{attempts}: {type(exc).__name__}", flush=True)
            if attempt < attempts:
                time.sleep(2.0 * attempt)
    assert last_error is not None
    raise last_error


def score_config(cases: list[dict[str, Any]], events_by_shot: dict[int, np.ndarray], config: dict[str, float]) -> dict[str, Any]:
    return fusion.aggregate(
        [
            fusion.score_alignment(events_by_shot[int(case["shot"])], fusion.crossings_for_config(case, config))
            for case in cases
        ]
    )


def selection_score(score: dict[str, Any]) -> float:
    return other.selection_score(score)


def match_details(event_times: np.ndarray, crossings: list[dict[str, Any]]) -> dict[str, Any]:
    crossing_times = np.asarray([row["time"] for row in crossings], dtype=float)
    available = set(range(len(crossing_times)))
    matched_events: list[float] = []
    matched_trigger_times: list[float] = []
    matched_sources: list[str] = []
    leads_ms: list[float] = []
    matched_trigger_indices: set[int] = set()
    for event_time in event_times:
        candidates = [
            index
            for index in available
            if event_time - fusion.PRECURSOR_WINDOW_S[1] <= crossing_times[index] <= event_time - fusion.PRECURSOR_WINDOW_S[0]
        ]
        if candidates:
            index = candidates[-1]
            available.remove(index)
            matched_trigger_indices.add(index)
            matched_events.append(float(event_time))
            matched_trigger_times.append(float(crossing_times[index]))
            matched_sources.append(crossings[index]["sources"])
            leads_ms.append(float((event_time - crossing_times[index]) * 1000.0))
    false_triggers: list[float] = []
    for index, crossing_time in enumerate(crossing_times):
        in_signature = bool(np.any(np.abs(event_times - crossing_time) <= fusion.EVENT_SIGNATURE_EXCLUSION_S))
        if index not in matched_trigger_indices and not in_signature:
            false_triggers.append(float(crossing_time))
    return {
        "matched_events": matched_events,
        "matched_trigger_times": matched_trigger_times,
        "matched_sources": matched_sources,
        "leads_ms": leads_ms,
        "false_triggers": false_triggers,
    }


def per_shot_rows(cases: list[dict[str, Any]], reviewed: dict[int, np.ndarray]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    configs = {
        "baseline_mirnov6": BASELINE_CONFIG,
        "omv6_exploratory": EXPLORATORY_OMV_CONFIG,
        "omv10_train_selected": TRAIN_SELECTED_OMV_CONFIG,
    }
    for case in cases:
        shot = int(case["shot"])
        event_times = reviewed[shot]
        for name, config in configs.items():
            score = fusion.score_alignment(event_times, fusion.crossings_for_config(case, config))
            rows.append(
                {
                    "shot": shot,
                    "config_name": name,
                    "config": json.dumps(config, sort_keys=True),
                    "events": score["event_count"],
                    "detected": score["detected_event_count"],
                    "missed": score["missed_event_count"],
                    "false_triggers": score["false_trigger_count"],
                    "precision": score["precision"],
                    "recall": score["recall"],
                    "median_lead_ms": float(np.median(score["lead_ms_values"])) if score["lead_ms_values"] else None,
                    "score": selection_score(fusion.aggregate([score])),
                }
            )
    return rows


def transition_rows(cases: list[dict[str, Any]], reviewed: dict[int, np.ndarray]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        shot = int(case["shot"])
        events = reviewed[shot]
        baseline = match_details(events, fusion.crossings_for_config(case, BASELINE_CONFIG))
        omv6 = match_details(events, fusion.crossings_for_config(case, EXPLORATORY_OMV_CONFIG))
        baseline_events = {round(value, 9) for value in baseline["matched_events"]}
        omv_events = {round(value, 9) for value in omv6["matched_events"]}
        for event_time in sorted(omv_events - baseline_events):
            index = [round(value, 9) for value in omv6["matched_events"]].index(event_time)
            rows.append(
                {
                    "shot": shot,
                    "event_time_s": event_time,
                    "transition": "newly_detected_by_omv6",
                    "omv_trigger_time_s": omv6["matched_trigger_times"][index],
                    "omv_lead_ms": omv6["leads_ms"][index],
                    "omv_sources": omv6["matched_sources"][index],
                }
            )
        for event_time in sorted(baseline_events - omv_events):
            index = [round(value, 9) for value in baseline["matched_events"]].index(event_time)
            rows.append(
                {
                    "shot": shot,
                    "event_time_s": event_time,
                    "transition": "lost_by_omv6_merge_or_rematch",
                    "omv_trigger_time_s": "",
                    "omv_lead_ms": baseline["leads_ms"][index],
                    "omv_sources": baseline["matched_sources"][index],
                }
            )
    return rows


def jackknife_rows(cases: list[dict[str, Any]], reviewed: dict[int, np.ndarray]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for omitted in sorted(int(case["shot"]) for case in cases):
        kept = [case for case in cases if int(case["shot"]) != omitted]
        baseline = score_config(kept, reviewed, BASELINE_CONFIG)
        omv6 = score_config(kept, reviewed, EXPLORATORY_OMV_CONFIG)
        rows.append(
            {
                "omitted_shot": omitted,
                "baseline_detected": baseline["detected_event_count"],
                "baseline_false_triggers": baseline["false_trigger_count"],
                "baseline_precision": baseline["precision"],
                "baseline_recall": baseline["recall"],
                "baseline_score": selection_score(baseline),
                "omv6_detected": omv6["detected_event_count"],
                "omv6_false_triggers": omv6["false_trigger_count"],
                "omv6_precision": omv6["precision"],
                "omv6_recall": omv6["recall"],
                "omv6_score": selection_score(omv6),
                "detected_delta": omv6["detected_event_count"] - baseline["detected_event_count"],
                "false_trigger_delta": omv6["false_trigger_count"] - baseline["false_trigger_count"],
                "score_delta": selection_score(omv6) - selection_score(baseline),
            }
        )
    return rows


def omv_sigma_rows(cases: list[dict[str, Any]], reviewed: dict[int, np.ndarray]) -> list[dict[str, Any]]:
    rows = []
    baseline = score_config(cases, reviewed, BASELINE_CONFIG)
    rows.append({"name": "baseline_mirnov6", "config": json.dumps(BASELINE_CONFIG, sort_keys=True), **other.compact_score(baseline), "score": selection_score(baseline)})
    for sigma in OMV_SIGMAS:
        config = {"pol_cc_ch2": 6.0, "pol_omv_rms": sigma}
        score = score_config(cases, reviewed, config)
        rows.append({"name": f"omv{sigma:g}", "config": json.dumps(config, sort_keys=True), **other.compact_score(score), "score": selection_score(score)})
    return rows


def write_report(
    run_dir: Path,
    summary: dict[str, Any],
    sigma_rows: list[dict[str, Any]],
    shot_rows: list[dict[str, Any]],
    jackknife: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
) -> None:
    baseline = summary["baseline"]
    omv6 = summary["omv6_exploratory"]
    omv10 = summary["omv10_train_selected"]
    lines = [
        "# FAIR-MAST OMV Lower-Threshold Follow-Up",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: test whether the exploratory lower-threshold OMV gain is broad or shot-specific",
        "- Baseline: fixed centre-column Mirnov channel at `6.0 sigma`",
        "- Follow-up candidate: fixed Mirnov plus OMV RMS at `6.0 sigma`",
        "- Train-selected reference: fixed Mirnov plus OMV RMS at `10.0 sigma`",
        "",
        "## Aggregate Held-Out Result",
        "",
        "| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Baseline Mirnov `6.0` | {baseline['event_count']} | {baseline['detected_event_count']} | {baseline['missed_event_count']} | {baseline['false_trigger_count']} | {baseline['precision']:.3f} | {baseline['recall']:.3f} | {baseline['lead_ms']['median']:.3f} ms | {summary['baseline_score']:.3f} |",
        f"| OMV `6.0` exploratory | {omv6['event_count']} | {omv6['detected_event_count']} | {omv6['missed_event_count']} | {omv6['false_trigger_count']} | {omv6['precision']:.3f} | {omv6['recall']:.3f} | {omv6['lead_ms']['median']:.3f} ms | {summary['omv6_score']:.3f} |",
        f"| OMV `10.0` train-selected | {omv10['event_count']} | {omv10['detected_event_count']} | {omv10['missed_event_count']} | {omv10['false_trigger_count']} | {omv10['precision']:.3f} | {omv10['recall']:.3f} | {omv10['lead_ms']['median']:.3f} ms | {summary['omv10_score']:.3f} |",
        "",
        "## OMV Threshold Scan",
        "",
        "| Name | Detected | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sigma_rows:
        lines.append(
            f"| `{row['name']}` | {row['detected']}/{row['events']} | {row['false_triggers']} | "
            f"{row['precision']:.3f} | {row['recall']:.3f} | {row['median_lead_ms']:.3f} ms | {row['score']:.3f} |"
        )
    lines += [
        "",
        "## Leave-One-Shot-Out Robustness",
        "",
        "| Omitted shot | Detected delta | False-trigger delta | Score delta |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in jackknife:
        lines.append(
            f"| {row['omitted_shot']} | {row['detected_delta']:+d} | "
            f"{row['false_trigger_delta']:+d} | {row['score_delta']:+.3f} |"
        )
    lines += [
        "",
        "## Per-Shot Delta",
        "",
        "| Shot | Baseline detected | OMV6 detected | Detected delta | Baseline false | OMV6 false | False delta |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    by_shot_config = {(row["shot"], row["config_name"]): row for row in shot_rows}
    for shot in sorted({row["shot"] for row in shot_rows}):
        base = by_shot_config[(shot, "baseline_mirnov6")]
        omv = by_shot_config[(shot, "omv6_exploratory")]
        lines.append(
            f"| {shot} | {base['detected']}/{base['events']} | {omv['detected']}/{omv['events']} | "
            f"{omv['detected'] - base['detected']:+d} | {base['false_triggers']} | {omv['false_triggers']} | "
            f"{omv['false_triggers'] - base['false_triggers']:+d} |"
        )
    lines += [
        "",
        "## Event Transitions",
        "",
        f"- Newly detected by OMV6: `{summary['newly_detected_by_omv6_count']}`",
        f"- Lost/rematched relative to baseline: `{summary['lost_by_omv6_count']}`",
        "",
    ]
    if transitions:
        lines += [
            "| Shot | Event time | Transition | OMV lead | Sources |",
            "| ---: | ---: | --- | ---: | --- |",
        ]
        for row in transitions:
            lead = row["omv_lead_ms"]
            lead_text = f"{lead:.3f} ms" if isinstance(lead, float) else "n/a"
            lines.append(
                f"| {row['shot']} | {row['event_time_s']:.9f} | `{row['transition']}` | "
                f"{lead_text} | `{row['omv_sources']}` |"
            )
    lines += [
        "",
        "## Interpretation",
        "",
        "The lower-threshold OMV result remains exploratory because it was found by",
        "ranking held-out labels. This follow-up checks robustness and attribution,",
        "not independent validation.",
        "",
        f"Robustness verdict: `{summary['robustness_verdict']}`.",
        "",
        "## Claim Boundary",
        "",
        "This can justify a fresh pre-registered OMV validation split or a stricter",
        "magnetic morphology classifier. It does not prove causal suppression or a",
        "deployable trigger.",
        "",
    ]
    (run_dir / "fair_mast_omv_followup_report.md").write_text("\n".join(lines), encoding="utf-8")


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
    test_cases = [case for case in cases if case["split"] == "test"]

    baseline = score_config(test_cases, reviewed, BASELINE_CONFIG)
    omv6 = score_config(test_cases, reviewed, EXPLORATORY_OMV_CONFIG)
    omv10 = score_config(test_cases, reviewed, TRAIN_SELECTED_OMV_CONFIG)
    sigma_rows = omv_sigma_rows(test_cases, reviewed)
    shot_rows = per_shot_rows(test_cases, reviewed)
    jackknife = jackknife_rows(test_cases, reviewed)
    transitions = transition_rows(test_cases, reviewed)

    positive_jackknife = sum(row["detected_delta"] > 0 and row["score_delta"] > 0 for row in jackknife)
    if omv6["detected_event_count"] <= baseline["detected_event_count"]:
        verdict = "no_aggregate_gain"
    elif positive_jackknife == len(jackknife):
        verdict = "broad_exploratory_gain"
    elif positive_jackknife >= len(jackknife) - 1:
        verdict = "mostly_stable_exploratory_gain"
    else:
        verdict = "shot_sensitive_exploratory_gain"

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_OMV_FOLLOWUP_COMPLETED",
        "baseline_config": BASELINE_CONFIG,
        "omv6_exploratory_config": EXPLORATORY_OMV_CONFIG,
        "omv10_train_selected_config": TRAIN_SELECTED_OMV_CONFIG,
        "baseline": baseline,
        "omv6_exploratory": omv6,
        "omv10_train_selected": omv10,
        "baseline_score": selection_score(baseline),
        "omv6_score": selection_score(omv6),
        "omv10_score": selection_score(omv10),
        "detected_delta_omv6_vs_baseline": omv6["detected_event_count"] - baseline["detected_event_count"],
        "false_trigger_delta_omv6_vs_baseline": omv6["false_trigger_count"] - baseline["false_trigger_count"],
        "positive_jackknife_folds": positive_jackknife,
        "jackknife_fold_count": len(jackknife),
        "newly_detected_by_omv6_count": sum(row["transition"] == "newly_detected_by_omv6" for row in transitions),
        "lost_by_omv6_count": sum(row["transition"] == "lost_by_omv6_merge_or_rematch" for row in transitions),
        "robustness_verdict": verdict,
        "claim_boundary": "Exploratory OMV follow-up only; not independent validation or causal TCT validation.",
    }

    write_csv(args.run_dir / "fair_mast_omv_followup_sigma_scan.csv", sigma_rows)
    write_csv(args.run_dir / "fair_mast_omv_followup_per_shot.csv", shot_rows)
    write_csv(args.run_dir / "fair_mast_omv_followup_jackknife.csv", jackknife)
    write_csv(args.run_dir / "fair_mast_omv_followup_event_transitions.csv", transitions)
    (args.run_dir / "fair_mast_omv_followup_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary, sigma_rows, shot_rows, jackknife, transitions)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Pre-registered fresh split test for the FAIR-MAST OMV6 trigger candidate."""

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
import fair_mast_omv_followup as omv_followup
import fair_mast_other_trigger_screen as other


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_omv_fresh_split_default"
EXCLUDED_PRIOR_SHOTS = {30276, 30277, 30311, 30418, 30419, 30421, 30423}
DISCOVERY_RANGES = (range(30260, 30320), range(30400, 30445))
FRESH_WINDOW_S = (0.30, 0.48)
MIN_AUTOMATIC_EVENTS = 5
FRESH_SHOT_COUNT = 5
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}
OMV6_CONFIG = {"pol_cc_ch2": 6.0, "pol_omv_rms": 6.0}
OMV10_CONFIG = {"pol_cc_ch2": 6.0, "pol_omv_rms": 10.0}


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


def has_required_arrays(group: zarr.Group) -> bool:
    try:
        visible = group["spectrometer_visible"]
        magnetics = group["magnetics"]
        _ = visible["time"].shape
        _ = visible["filter_spectrometer_dalpha_voltage"].shape
        _ = magnetics["time_mirnov"].shape
        _ = magnetics["b_field_pol_probe_cc_field"].shape
        _ = magnetics["b_field_pol_probe_omv_voltage"].shape
    except Exception:
        return False
    return True


def local_peak_context(time_axis: np.ndarray, values: np.ndarray, event_time: float) -> dict[str, float]:
    local = (time_axis >= event_time - 0.002) & (time_axis <= event_time + 0.002)
    pre = (time_axis >= event_time - 0.010) & (time_axis <= event_time - 0.002)
    peak = float(np.nanmax(values[local])) if np.any(local) else float("nan")
    pre_median = float(np.nanmedian(values[pre])) if np.any(pre) else float("nan")
    return {
        "local_peak_v": peak,
        "pre_event_median_v": pre_median,
        "local_peak_minus_pre_median_v": peak - pre_median,
    }


def review_label(event_time: float, event_times: np.ndarray, context: dict[str, float], window_s: tuple[float, float]) -> tuple[str, str]:
    index = int(np.where(np.isclose(event_times, event_time))[0][0])
    previous_time = float(event_times[index - 1]) if index > 0 else None
    next_time = float(event_times[index + 1]) if index + 1 < len(event_times) else None
    contrast = context["local_peak_minus_pre_median_v"]
    peak = context["local_peak_v"]
    near_window_edge = event_time <= window_s[0] + 0.003 or event_time >= window_s[1] - 0.002
    close_neighbor = (
        (previous_time is not None and event_time - previous_time < 0.006)
        or (next_time is not None and next_time - event_time < 0.006)
    )
    if near_window_edge:
        return "ambiguous", "Machine first pass: event is close to the fresh-split analysis-window boundary."
    if peak < 0.75 or contrast < 0.35:
        return "ambiguous", "Machine first pass: D-alpha peak/contrast is below conservative morphology threshold."
    if close_neighbor and contrast < 0.70:
        return "ambiguous", "Machine first pass: close neighboring peak with only moderate contrast; possible split label."
    return "true_elm", "Machine first pass: D-alpha morphology accepted; trigger timing not used for this fresh-split label."


def load_case(shot: int, window_s: tuple[float, float]) -> dict[str, Any]:
    group = zarr.open_group(f"{fusion.ARCHIVE_ROOT}/{shot}.zarr", mode="r")
    if not has_required_arrays(group):
        raise KeyError(f"shot {shot} missing required arrays")

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

    review_rows = []
    accepted = []
    for event_number, event_time in enumerate(automatic_events, start=1):
        context = local_peak_context(dalpha_time, dalpha, float(event_time))
        label, notes = review_label(float(event_time), automatic_events, context, window_s)
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

    return {
        "shot": shot,
        "split": "fresh_test",
        "window_s": window_s,
        "automatic_event_times": automatic_events,
        "accepted_event_times": np.asarray(accepted, dtype=float),
        "review_rows": review_rows,
        "features": features,
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


def discover_candidates(min_events: int) -> list[dict[str, Any]]:
    candidates = []
    for shot_range in DISCOVERY_RANGES:
        for shot in shot_range:
            if shot in EXCLUDED_PRIOR_SHOTS:
                continue
            try:
                group = zarr.open_group(f"{fusion.ARCHIVE_ROOT}/{shot}.zarr", mode="r")
                if not has_required_arrays(group):
                    continue
                visible = group["spectrometer_visible"]
                dalpha_time = np.asarray(visible["time"], dtype=float)
                dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[fusion.D_ALPHA_CHANNEL]
                events = fusion.detect_events(dalpha_time, dalpha, FRESH_WINDOW_S)
                if len(events) >= min_events:
                    candidates.append(
                        {
                            "shot": shot,
                            "window_s": list(FRESH_WINDOW_S),
                            "automatic_event_count": int(len(events)),
                            "eligible": True,
                        }
                    )
            except Exception:
                continue
    return candidates


def score_config(cases: list[dict[str, Any]], config: dict[str, float]) -> dict[str, Any]:
    return fusion.aggregate(
        [
            fusion.score_alignment(case["accepted_event_times"], fusion.crossings_for_config(case, config))
            for case in cases
        ]
    )


def per_shot_rows(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    configs = {
        "baseline_mirnov6": BASELINE_CONFIG,
        "omv6_fixed_candidate": OMV6_CONFIG,
        "omv10_prior_train_selected": OMV10_CONFIG,
    }
    for case in cases:
        for name, config in configs.items():
            score = fusion.score_alignment(case["accepted_event_times"], fusion.crossings_for_config(case, config))
            aggregate = fusion.aggregate([score])
            rows.append(
                {
                    "shot": int(case["shot"]),
                    "config_name": name,
                    "config": json.dumps(config, sort_keys=True),
                    "accepted_events": score["event_count"],
                    "detected": score["detected_event_count"],
                    "missed": score["missed_event_count"],
                    "false_triggers": score["false_trigger_count"],
                    "precision": score["precision"],
                    "recall": score["recall"],
                    "median_lead_ms": float(np.median(score["lead_ms_values"])) if score["lead_ms_values"] else None,
                    "score": other.selection_score(aggregate),
                }
            )
    return rows


def transition_rows(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        events = case["accepted_event_times"]
        baseline = omv_followup.match_details(events, fusion.crossings_for_config(case, BASELINE_CONFIG))
        omv6 = omv_followup.match_details(events, fusion.crossings_for_config(case, OMV6_CONFIG))
        baseline_events = {round(value, 9) for value in baseline["matched_events"]}
        omv_events = {round(value, 9) for value in omv6["matched_events"]}
        rounded_omv = [round(value, 9) for value in omv6["matched_events"]]
        rounded_baseline = [round(value, 9) for value in baseline["matched_events"]]
        for event_time in sorted(omv_events - baseline_events):
            index = rounded_omv.index(event_time)
            rows.append(
                {
                    "shot": int(case["shot"]),
                    "event_time_s": event_time,
                    "transition": "newly_detected_by_omv6",
                    "trigger_time_s": omv6["matched_trigger_times"][index],
                    "lead_ms": omv6["leads_ms"][index],
                    "sources": omv6["matched_sources"][index],
                }
            )
        for event_time in sorted(baseline_events - omv_events):
            index = rounded_baseline.index(event_time)
            rows.append(
                {
                    "shot": int(case["shot"]),
                    "event_time_s": event_time,
                    "transition": "lost_by_omv6_merge_or_rematch",
                    "trigger_time_s": baseline["matched_trigger_times"][index],
                    "lead_ms": baseline["leads_ms"][index],
                    "sources": baseline["matched_sources"][index],
                }
            )
    return rows


def write_report(
    run_dir: Path,
    summary: dict[str, Any],
    per_shot: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
) -> None:
    baseline = summary["baseline"]
    omv6 = summary["omv6_fixed_candidate"]
    omv10 = summary["omv10_prior_train_selected"]
    lines = [
        "# FAIR-MAST OMV Fresh Split",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: fixed-threshold fresh split test of the exploratory OMV6 candidate",
        f"- Excluded prior shots: `{summary['excluded_prior_shots']}`",
        f"- Discovery rule: first `{summary['fresh_shot_count']}` unused shots in configured ranges with required arrays and at least `{summary['min_automatic_events']}` automatic D-alpha events in `{summary['window_s']}`",
        f"- Selected fresh shots: `{summary['fresh_shots']}`",
        "- Event labels: machine D-alpha morphology triage only; trigger timing is not used for fresh labels",
        "- Candidate was fixed before this run: Mirnov `6.0 sigma` plus OMV `6.0 sigma`",
        "",
        "## Aggregate Fresh-Split Result",
        "",
        "| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Baseline Mirnov `6.0` | {baseline['event_count']} | {baseline['detected_event_count']} | {baseline['missed_event_count']} | {baseline['false_trigger_count']} | {baseline['precision']:.3f} | {baseline['recall']:.3f} | {baseline['lead_ms']['median']:.3f} ms | {summary['baseline_score']:.3f} |",
        f"| OMV `6.0` fixed candidate | {omv6['event_count']} | {omv6['detected_event_count']} | {omv6['missed_event_count']} | {omv6['false_trigger_count']} | {omv6['precision']:.3f} | {omv6['recall']:.3f} | {omv6['lead_ms']['median']:.3f} ms | {summary['omv6_score']:.3f} |",
        f"| OMV `10.0` prior train-selected | {omv10['event_count']} | {omv10['detected_event_count']} | {omv10['missed_event_count']} | {omv10['false_trigger_count']} | {omv10['precision']:.3f} | {omv10['recall']:.3f} | {omv10['lead_ms']['median']:.3f} ms | {summary['omv10_score']:.3f} |",
        "",
        "## Per-Shot Delta",
        "",
        "| Shot | Baseline detected | OMV6 detected | Detected delta | Baseline false | OMV6 false | False delta |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    by_shot_config = {(row["shot"], row["config_name"]): row for row in per_shot}
    for shot in summary["fresh_shots"]:
        base = by_shot_config[(shot, "baseline_mirnov6")]
        omv = by_shot_config[(shot, "omv6_fixed_candidate")]
        lines.append(
            f"| {shot} | {base['detected']}/{base['accepted_events']} | {omv['detected']}/{omv['accepted_events']} | "
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
            "| Shot | Event time | Transition | Lead | Sources |",
            "| ---: | ---: | --- | ---: | --- |",
        ]
        for row in transitions:
            lines.append(
                f"| {row['shot']} | {row['event_time_s']:.9f} | `{row['transition']}` | "
                f"{row['lead_ms']:.3f} ms | `{row['sources']}` |"
            )
    lines += [
        "",
        "## Interpretation",
        "",
        f"Fresh-split verdict: `{summary['fresh_split_verdict']}`.",
        "",
        "Because the OMV6 candidate was fixed before scoring these unused shots,",
        "this is stronger than the prior held-out exploratory ranking. The event",
        "labels remain machine-generated morphology labels, so this is still not",
        "expert-reviewed experimental validation.",
        "",
        "## Claim Boundary",
        "",
        "This tests trigger generalization on unused public shots. It does not prove",
        "causal TCT suppression, actuator sufficiency, or sustained fusion.",
        "",
    ]
    (run_dir / "fair_mast_omv_fresh_split_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--fresh-shot-count", type=int, default=FRESH_SHOT_COUNT)
    parser.add_argument("--min-automatic-events", type=int, default=MIN_AUTOMATIC_EVENTS)
    args = parser.parse_args()

    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    candidates = discover_candidates(args.min_automatic_events)
    if len(candidates) < args.fresh_shot_count:
        raise RuntimeError(f"found only {len(candidates)} eligible fresh shots")
    selected = candidates[: args.fresh_shot_count]
    fresh_shots = [int(row["shot"]) for row in selected]

    cases = []
    for shot in fresh_shots:
        print(f"loading fresh shot {shot}", flush=True)
        cases.append(load_case_with_retries(shot, FRESH_WINDOW_S))

    review_rows = [row for case in cases for row in case["review_rows"]]
    baseline = score_config(cases, BASELINE_CONFIG)
    omv6 = score_config(cases, OMV6_CONFIG)
    omv10 = score_config(cases, OMV10_CONFIG)
    per_shot = per_shot_rows(cases)
    transitions = transition_rows(cases)
    detected_delta = omv6["detected_event_count"] - baseline["detected_event_count"]
    false_delta = omv6["false_trigger_count"] - baseline["false_trigger_count"]
    score_delta = other.selection_score(omv6) - other.selection_score(baseline)
    if detected_delta > 0 and score_delta > 0 and false_delta <= max(2, detected_delta):
        verdict = "fresh_split_supports_omv6_candidate"
    elif detected_delta > 0:
        verdict = "fresh_split_mixed_gain_with_noise_cost"
    else:
        verdict = "fresh_split_does_not_support_omv6_candidate"

    label_counts: dict[str, int] = {}
    for row in review_rows:
        label_counts[row["review_label"]] = label_counts.get(row["review_label"], 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_OMV_FRESH_SPLIT_COMPLETED",
        "excluded_prior_shots": sorted(EXCLUDED_PRIOR_SHOTS),
        "discovery_ranges": [[min(r), max(r)] for r in DISCOVERY_RANGES],
        "window_s": list(FRESH_WINDOW_S),
        "min_automatic_events": args.min_automatic_events,
        "fresh_shot_count": args.fresh_shot_count,
        "fresh_shots": fresh_shots,
        "candidate_count": len(candidates),
        "selected_candidates": selected,
        "event_label_rule": "D-alpha morphology triage only; trigger timing not used.",
        "label_counts": label_counts,
        "baseline_config": BASELINE_CONFIG,
        "omv6_fixed_candidate_config": OMV6_CONFIG,
        "omv10_prior_train_selected_config": OMV10_CONFIG,
        "baseline": baseline,
        "omv6_fixed_candidate": omv6,
        "omv10_prior_train_selected": omv10,
        "baseline_score": other.selection_score(baseline),
        "omv6_score": other.selection_score(omv6),
        "omv10_score": other.selection_score(omv10),
        "detected_delta_omv6_vs_baseline": detected_delta,
        "false_trigger_delta_omv6_vs_baseline": false_delta,
        "score_delta_omv6_vs_baseline": score_delta,
        "newly_detected_by_omv6_count": sum(row["transition"] == "newly_detected_by_omv6" for row in transitions),
        "lost_by_omv6_count": sum(row["transition"] == "lost_by_omv6_merge_or_rematch" for row in transitions),
        "fresh_split_verdict": verdict,
        "claim_boundary": "Fresh public-shot trigger generalization only; labels are machine morphology triage, not expert labels.",
    }

    write_csv(args.run_dir / "fair_mast_omv_fresh_split_candidates.csv", candidates)
    write_csv(args.run_dir / "fair_mast_omv_fresh_split_labels.csv", review_rows)
    write_csv(args.run_dir / "fair_mast_omv_fresh_split_per_shot.csv", per_shot)
    write_csv(args.run_dir / "fair_mast_omv_fresh_split_event_transitions.csv", transitions)
    (args.run_dir / "fair_mast_omv_fresh_split_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary, per_shot, transitions)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

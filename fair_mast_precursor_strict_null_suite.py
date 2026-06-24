#!/usr/bin/env python3
"""Stricter null suite for FAIR-MAST held-out precursor timing."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parent
DEFAULT_REVIEW_DIR = REPO / "validation_runs" / "fair_mast_machine_reviewed_labels_default"
DEFAULT_SOURCE_DIR = REPO / "validation_runs" / "fair_mast_prospective_precursor_default"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_precursor_strict_null_suite_default"
PRECURSOR_WINDOW_S = (0.0005, 0.015)
LATENCIES_MS = (3.0, 5.0, 8.0, 12.0)
DEFAULT_TRIALS = 50_000
DEFAULT_SEED = 20260624


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: str | None) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def circular_shift(times: np.ndarray, window_s: tuple[float, float], offset: float) -> np.ndarray:
    start, end = window_s
    span = end - start
    return np.sort(((times - start + offset) % span) + start)


def local_event_jitter(
    event_times: np.ndarray, window_s: tuple[float, float], rng: np.random.Generator
) -> np.ndarray:
    """Sample each event within its midpoint-bounded local interval.

    This preserves event count, event order, and the local support implied by
    neighboring accepted labels, while breaking exact trigger/event alignment.
    """
    if len(event_times) == 0:
        return event_times
    starts = np.empty_like(event_times)
    ends = np.empty_like(event_times)
    starts[0] = window_s[0]
    ends[-1] = window_s[1]
    if len(event_times) > 1:
        midpoints = (event_times[:-1] + event_times[1:]) / 2.0
        ends[:-1] = midpoints
        starts[1:] = midpoints
    else:
        ends[0] = window_s[1]
    return np.sort(rng.uniform(starts, ends))


def score_alignment(event_times: np.ndarray, trigger_times: np.ndarray) -> dict[str, Any]:
    available = set(range(len(trigger_times)))
    leads: list[float] = []
    for event_time in event_times:
        candidates = [
            index
            for index in available
            if event_time - PRECURSOR_WINDOW_S[1]
            <= trigger_times[index]
            <= event_time - PRECURSOR_WINDOW_S[0]
        ]
        if candidates:
            index = candidates[-1]
            available.remove(index)
            leads.append(float((event_time - trigger_times[index]) * 1000.0))
    return {
        "detected_count": len(leads),
        "lead_ms_values": leads,
        "latency_feasible_count": {
            f"{latency:g}_ms": sum(lead >= latency for lead in leads)
            for latency in LATENCIES_MS
        },
    }


def load_inputs(review_dir: Path, source_dir: Path) -> tuple[dict[int, tuple[float, float]], dict[int, np.ndarray], dict[int, np.ndarray]]:
    reviewed = read_csv(review_dir / "fair_mast_machine_reviewed_label_manifest.csv")
    with (source_dir / "fair_mast_prospective_precursor_summary.json").open(encoding="utf-8") as handle:
        source_summary = json.load(handle)
    shot_windows = {
        int(row["shot"]): tuple(float(value) for value in row["window_s"])
        for row in source_summary["shot_scores"]
        if row["split"] == "test"
    }
    events_by_shot: dict[int, list[float]] = {shot: [] for shot in shot_windows}
    triggers_by_shot: dict[int, set[float]] = {shot: set() for shot in shot_windows}
    for row in reviewed:
        shot = int(row["shot"])
        if row["review_label"] == "true_elm":
            events_by_shot[shot].append(float(row["event_time_s"]))
        trigger_time = as_float(row["trigger_time_s"])
        if trigger_time is not None:
            triggers_by_shot[shot].add(trigger_time)
    event_arrays = {shot: np.asarray(sorted(times), dtype=float) for shot, times in events_by_shot.items()}
    trigger_arrays = {shot: np.asarray(sorted(times), dtype=float) for shot, times in triggers_by_shot.items()}
    return shot_windows, event_arrays, trigger_arrays


def observed_for_shots(
    shots: list[int], event_arrays: dict[int, np.ndarray], trigger_arrays: dict[int, np.ndarray]
) -> dict[str, Any]:
    scores = {shot: score_alignment(event_arrays[shot], trigger_arrays[shot]) for shot in shots}
    leads = [lead for score in scores.values() for lead in score["lead_ms_values"]]
    event_count = sum(len(event_arrays[shot]) for shot in shots)
    detected = sum(score["detected_count"] for score in scores.values())
    return {
        "event_count": event_count,
        "trigger_count": sum(len(trigger_arrays[shot]) for shot in shots),
        "detected_count": detected,
        "recall": detected / event_count if event_count else 0.0,
        "lead_ms": {
            "minimum": float(np.min(leads)) if leads else None,
            "median": float(np.median(leads)) if leads else None,
            "maximum": float(np.max(leads)) if leads else None,
        },
        "latency_feasible_count": {
            f"{latency:g}_ms": sum(lead >= latency for lead in leads)
            for latency in LATENCIES_MS
        },
    }


def summarize_null(values: np.ndarray, observed: int, trials: int) -> dict[str, Any]:
    return {
        "observed": observed,
        "null_mean": float(np.mean(values)),
        "null_p50": float(np.percentile(values, 50)),
        "null_p95": float(np.percentile(values, 95)),
        "null_p99": float(np.percentile(values, 99)),
        "null_max": int(np.max(values)),
        "p_value_ge_observed": (int(np.sum(values >= observed)) + 1) / (trials + 1),
    }


def run_null(
    kind: str,
    shots: list[int],
    shot_windows: dict[int, tuple[float, float]],
    event_arrays: dict[int, np.ndarray],
    trigger_arrays: dict[int, np.ndarray],
    observed: dict[str, Any],
    trials: int,
    rng: np.random.Generator,
) -> tuple[dict[str, Any], np.ndarray, dict[str, np.ndarray]]:
    detected = np.zeros(trials, dtype=int)
    latency = {f"{latency:g}_ms": np.zeros(trials, dtype=int) for latency in LATENCIES_MS}
    for trial in range(trials):
        total = 0
        lat_total = {key: 0 for key in latency}
        for shot in shots:
            events = event_arrays[shot]
            triggers = trigger_arrays[shot]
            if kind == "trigger_train_block_shift":
                if len(triggers):
                    shifted_triggers = circular_shift(
                        triggers,
                        shot_windows[shot],
                        float(rng.uniform(0.0, shot_windows[shot][1] - shot_windows[shot][0])),
                    )
                else:
                    shifted_triggers = triggers
                shifted_events = events
            elif kind == "local_event_jitter":
                shifted_events = local_event_jitter(events, shot_windows[shot], rng)
                shifted_triggers = triggers
            else:
                raise ValueError(f"unknown null kind: {kind}")
            score = score_alignment(shifted_events, shifted_triggers)
            total += score["detected_count"]
            for key, value in score["latency_feasible_count"].items():
                lat_total[key] += value
        detected[trial] = total
        for key, value in lat_total.items():
            latency[key][trial] = value

    summary = {
        "detected_count": summarize_null(detected, observed["detected_count"], trials),
        "latency_feasible_count": {
            key: summarize_null(values, observed["latency_feasible_count"][key], trials)
            for key, values in latency.items()
        },
    }
    return summary, detected, latency


def flatten_rows(
    scope: str,
    excluded_shot: int | None,
    null_kind: str,
    observed: dict[str, Any],
    null_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        {
            "scope": scope,
            "excluded_shot": excluded_shot,
            "null_kind": null_kind,
            "metric": "detected_count",
            **null_summary["detected_count"],
        }
    ]
    for key, stats in null_summary["latency_feasible_count"].items():
        rows.append(
            {
                "scope": scope,
                "excluded_shot": excluded_shot,
                "null_kind": null_kind,
                "metric": f"latency_{key}_feasible_count",
                **stats,
            }
        )
    return rows


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    full = summary["full_shot_results"]
    lines = [
        "# FAIR-MAST Strict Null Suite",
        "",
        f"- Status: `{summary['status']}`",
        "- Scope: accepted `true_elm` rows from the FAIR-MAST machine-aided label review",
        f"- Monte Carlo trials per null: `{summary['trial_count']}`",
        f"- Random seed: `{summary['seed']}`",
        "",
        "## Null Models",
        "",
        "- `trigger_train_block_shift`: shift the whole trigger train by one random circular offset inside each shot window. This preserves trigger burstiness and inter-trigger spacing.",
        "- `local_event_jitter`: keep trigger times fixed and resample each accepted event inside its midpoint-bounded local interval. This preserves event count, order, and local density support.",
        "- Leave-one-shot-out repeats both nulls after removing each held-out shot.",
        "",
        "## Full Held-Out Set",
        "",
        "| Null | Observed detected | Null mean | Null p95 | Null max | Directional p |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for null_kind, result in full.items():
        stats = result["null_summary"]["detected_count"]
        lines.append(
            f"| `{null_kind}` | {stats['observed']} | {stats['null_mean']:.3f} | "
            f"{stats['null_p95']:.3f} | {stats['null_max']} | {stats['p_value_ge_observed']:.6f} |"
        )
    lines += [
        "",
        "## Leave-One-Shot-Out Sensitivity",
        "",
        "| Excluded shot | Null | Observed detected | Null mean | Null p95 | Null max | Directional p |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summary["leave_one_shot_out"]:
        for null_kind, result in item["results"].items():
            stats = result["null_summary"]["detected_count"]
            lines.append(
                f"| `{item['excluded_shot']}` | `{null_kind}` | {stats['observed']} | "
                f"{stats['null_mean']:.3f} | {stats['null_p95']:.3f} | "
                f"{stats['null_max']} | {stats['p_value_ge_observed']:.6f} |"
            )
    lines += [
        "",
        "## Interpretation",
        "",
        "The trigger-train block shift is the stricter version of the original time-shift null because it preserves the observed trigger burst structure within each shot. The local event-jitter null attacks the complementary concern that dense event labels might catch fixed triggers by chance. Leave-one-shot-out rows test whether the result is dominated by a single held-out shot.",
        "",
        "## Claim Boundary",
        "",
        "These nulls strengthen timing-specificity evidence for the precursor screen. They still do not prove causal actuator mitigation, expert-reviewed ELM labels, or deployed controller readiness.",
        "",
    ]
    (run_dir / "fair_mast_precursor_strict_null_suite_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    shot_windows, event_arrays, trigger_arrays = load_inputs(args.review_dir, args.source_dir)
    all_shots = sorted(shot_windows)
    rng = np.random.default_rng(args.seed)

    rows: list[dict[str, Any]] = []
    full_observed = observed_for_shots(all_shots, event_arrays, trigger_arrays)
    full_results: dict[str, Any] = {}
    for null_kind in ("trigger_train_block_shift", "local_event_jitter"):
        null_summary, _, _ = run_null(
            null_kind, all_shots, shot_windows, event_arrays, trigger_arrays, full_observed, args.trials, rng
        )
        full_results[null_kind] = {"observed": full_observed, "null_summary": null_summary}
        rows.extend(flatten_rows("full", None, null_kind, full_observed, null_summary))

    loo = []
    for excluded in all_shots:
        shots = [shot for shot in all_shots if shot != excluded]
        observed = observed_for_shots(shots, event_arrays, trigger_arrays)
        item = {"excluded_shot": excluded, "observed": observed, "results": {}}
        for null_kind in ("trigger_train_block_shift", "local_event_jitter"):
            null_summary, _, _ = run_null(
                null_kind, shots, shot_windows, event_arrays, trigger_arrays, observed, args.trials, rng
            )
            item["results"][null_kind] = {"observed": observed, "null_summary": null_summary}
            rows.extend(flatten_rows("leave_one_shot_out", excluded, null_kind, observed, null_summary))
        loo.append(item)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_PRECURSOR_STRICT_NULL_SUITE_COMPLETED",
        "trial_count": args.trials,
        "seed": args.seed,
        "source_review_run": str(args.review_dir.relative_to(REPO)),
        "held_out_shots": all_shots,
        "full_shot_results": full_results,
        "leave_one_shot_out": loo,
        "claim_boundary": "Stricter timing-specificity null suite only; not causal TCT actuator validation.",
    }
    fields = [
        "scope",
        "excluded_shot",
        "null_kind",
        "metric",
        "observed",
        "null_mean",
        "null_p50",
        "null_p95",
        "null_p99",
        "null_max",
        "p_value_ge_observed",
    ]
    write_csv(args.run_dir / "fair_mast_precursor_strict_null_suite_metrics.csv", rows, fields)
    (args.run_dir / "fair_mast_precursor_strict_null_suite_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

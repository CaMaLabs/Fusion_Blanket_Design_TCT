#!/usr/bin/env python3
"""Time-shift null test for FAIR-MAST held-out precursor alignment."""

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
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_precursor_time_shift_null_default"
PRECURSOR_WINDOW_S = (0.0005, 0.015)
LATENCIES_MS = (3.0, 5.0, 8.0, 12.0)
DEFAULT_TRIALS = 50_000
DEFAULT_SEED = 20260623


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


def percentile_rank(null_values: np.ndarray, observed: int) -> float:
    return float(np.mean(null_values <= observed))


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    observed = summary["observed"]
    null = summary["null_distribution"]
    lines = [
        "# FAIR-MAST Precursor Time-Shift Null Test",
        "",
        f"- Status: `{summary['status']}`",
        "- Scope: held-out FAIR-MAST accepted `true_elm` rows from the machine-aided review",
        "- Null model: circularly shift observed trigger times independently within each shot window",
        "- Preserved by null: shot windows, event times, trigger count per shot, trigger density per shot",
        "- Broken by null: physical trigger/event temporal alignment",
        f"- Monte Carlo trials: `{summary['trial_count']}`",
        f"- Random seed: `{summary['seed']}`",
        "",
        "## Observed Alignment",
        "",
        f"- Accepted true ELM events: `{observed['event_count']}`",
        f"- Unique observed trigger times used: `{observed['trigger_count']}`",
        f"- Observed detected true ELMs: `{observed['detected_count']}`",
        f"- Observed recall: `{observed['recall']:.3f}`",
        f"- Observed median lead: `{observed['lead_ms']['median']:.3f} ms`",
        "",
        "## Null Result",
        "",
        f"- Null mean detected count: `{null['detected_count_mean']:.3f}`",
        f"- Null 95th percentile detected count: `{null['detected_count_p95']:.3f}`",
        f"- Null max detected count: `{null['detected_count_max']}`",
        f"- Directional Monte Carlo p, null detected >= observed: `{summary['p_value_detected_ge_observed']:.6f}`",
        f"- Observed percentile in null distribution: `{summary['observed_percentile_rank']:.6f}`",
        "",
        "| Required latency | Observed detected true ELMs with enough lead | Null mean | Directional p |",
        "| --- | ---: | ---: | ---: |",
    ]
    for latency in LATENCIES_MS:
        key = f"{latency:g}_ms"
        lines.append(
            f"| `{key}` | {observed['latency_feasible_count'][key]} | "
            f"{null['latency_feasible_count_mean'][key]:.3f} | "
            f"{summary['p_value_latency_ge_observed'][key]:.6f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "The observed trigger/event alignment is tested against chance timing while",
        "holding fixed the number of triggers in each shot. A low directional p-value",
        "means the measured precursor timing is unlikely to be explained only by random",
        "placement of the same trigger counts inside the same shot windows.",
        "",
        "## Claim Boundary",
        "",
        "This null test supports temporal specificity of the measured precursor trigger.",
        "It does not prove causal actuator mitigation, replace expert event labels, or",
        "establish that a deployed controller can respond within the measured lead time.",
        "",
    ]
    (run_dir / "fair_mast_precursor_time_shift_null_report.md").write_text("\n".join(lines), encoding="utf-8")


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

    reviewed = read_csv(args.review_dir / "fair_mast_machine_reviewed_label_manifest.csv")
    with (args.source_dir / "fair_mast_prospective_precursor_summary.json").open(encoding="utf-8") as handle:
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
    trigger_arrays = {
        shot: np.asarray(sorted(times), dtype=float) for shot, times in triggers_by_shot.items()
    }

    observed_scores = {
        shot: score_alignment(event_arrays[shot], trigger_arrays[shot])
        for shot in shot_windows
    }
    observed_leads = [
        lead
        for score in observed_scores.values()
        for lead in score["lead_ms_values"]
    ]
    observed = {
        "event_count": sum(len(values) for values in event_arrays.values()),
        "trigger_count": sum(len(values) for values in trigger_arrays.values()),
        "detected_count": sum(score["detected_count"] for score in observed_scores.values()),
        "recall": sum(score["detected_count"] for score in observed_scores.values())
        / sum(len(values) for values in event_arrays.values()),
        "lead_ms": {
            "minimum": float(np.min(observed_leads)) if observed_leads else None,
            "median": float(np.median(observed_leads)) if observed_leads else None,
            "maximum": float(np.max(observed_leads)) if observed_leads else None,
        },
        "latency_feasible_count": {
            f"{latency:g}_ms": sum(lead >= latency for lead in observed_leads)
            for latency in LATENCIES_MS
        },
    }

    rng = np.random.default_rng(args.seed)
    null_detected = np.zeros(args.trials, dtype=int)
    null_latency = {f"{latency:g}_ms": np.zeros(args.trials, dtype=int) for latency in LATENCIES_MS}
    shot_rows: list[dict[str, Any]] = []
    for shot, score in observed_scores.items():
        shot_rows.append(
            {
                "shot": shot,
                "event_count": len(event_arrays[shot]),
                "trigger_count": len(trigger_arrays[shot]),
                "observed_detected_count": score["detected_count"],
                "observed_median_lead_ms": float(np.median(score["lead_ms_values"]))
                if score["lead_ms_values"]
                else None,
            }
        )

    for trial in range(args.trials):
        total = 0
        lat_total = {f"{latency:g}_ms": 0 for latency in LATENCIES_MS}
        for shot, window in shot_windows.items():
            triggers = trigger_arrays[shot]
            if len(triggers):
                shifted = circular_shift(triggers, window, float(rng.uniform(0.0, window[1] - window[0])))
            else:
                shifted = triggers
            score = score_alignment(event_arrays[shot], shifted)
            total += score["detected_count"]
            for key, value in score["latency_feasible_count"].items():
                lat_total[key] += value
        null_detected[trial] = total
        for key, value in lat_total.items():
            null_latency[key][trial] = value

    null_rows = [
        {
            "metric": "detected_count",
            "observed": observed["detected_count"],
            "null_mean": float(np.mean(null_detected)),
            "null_p50": float(np.percentile(null_detected, 50)),
            "null_p95": float(np.percentile(null_detected, 95)),
            "null_max": int(np.max(null_detected)),
            "p_value_ge_observed": (int(np.sum(null_detected >= observed["detected_count"])) + 1)
            / (args.trials + 1),
        }
    ]
    for latency in LATENCIES_MS:
        key = f"{latency:g}_ms"
        values = null_latency[key]
        obs = observed["latency_feasible_count"][key]
        null_rows.append(
            {
                "metric": f"latency_{key}_feasible_count",
                "observed": obs,
                "null_mean": float(np.mean(values)),
                "null_p50": float(np.percentile(values, 50)),
                "null_p95": float(np.percentile(values, 95)),
                "null_max": int(np.max(values)),
                "p_value_ge_observed": (int(np.sum(values >= obs)) + 1) / (args.trials + 1),
            }
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_PRECURSOR_TIME_SHIFT_NULL_COMPLETED",
        "trial_count": args.trials,
        "seed": args.seed,
        "source_review_run": str(args.review_dir.relative_to(REPO)),
        "observed": observed,
        "null_distribution": {
            "detected_count_mean": float(np.mean(null_detected)),
            "detected_count_p50": float(np.percentile(null_detected, 50)),
            "detected_count_p95": float(np.percentile(null_detected, 95)),
            "detected_count_max": int(np.max(null_detected)),
            "latency_feasible_count_mean": {
                key: float(np.mean(values)) for key, values in null_latency.items()
            },
        },
        "p_value_detected_ge_observed": null_rows[0]["p_value_ge_observed"],
        "observed_percentile_rank": percentile_rank(null_detected, observed["detected_count"]),
        "p_value_latency_ge_observed": {
            row["metric"].replace("latency_", "").replace("_feasible_count", ""): row["p_value_ge_observed"]
            for row in null_rows[1:]
        },
        "claim_boundary": "Time-shift temporal-specificity test only; not causal TCT actuator validation.",
    }
    write_csv(args.run_dir / "fair_mast_precursor_time_shift_null_metrics.csv", null_rows, list(null_rows[0]))
    write_csv(args.run_dir / "fair_mast_precursor_time_shift_null_shots.csv", shot_rows, list(shot_rows[0]))
    (args.run_dir / "fair_mast_precursor_time_shift_null_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

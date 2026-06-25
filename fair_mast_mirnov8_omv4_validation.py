#!/usr/bin/env python3
"""Validate the exploratory FAIR-MAST Mirnov8+OMV4 trigger on later unused shots."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fair_mast_fresh_trigger_search as search
import fair_mast_omv_fresh_split as fresh
import fair_mast_other_trigger_screen as other


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_mirnov8_omv4_validation_default"
DISCOVERY_SKIP_COUNT = 20
VALIDATION_SHOT_COUNT = 10
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}
CANDIDATE_CONFIG = {"pol_cc_ch2": 8.0, "pol_omv_rms": 4.0}


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_validation_cases(skip_count: int, validation_count: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = fresh.discover_candidates(fresh.MIN_AUTOMATIC_EVENTS)
    loaded = []
    skipped = []
    for row in candidates[skip_count:]:
        if len(loaded) >= validation_count:
            break
        shot = int(row["shot"])
        print(f"loading validation shot {shot}", flush=True)
        try:
            loaded.append(search.load_case_with_retries(shot, fresh.FRESH_WINDOW_S))
        except Exception as exc:
            skipped_row = dict(row)
            skipped_row["skip_reason"] = type(exc).__name__
            skipped.append(skipped_row)
            print(f"skipping shot {shot}: {type(exc).__name__}", flush=True)
    if len(loaded) < validation_count:
        raise RuntimeError(f"loaded only {len(loaded)} validation shots; need {validation_count}")
    return candidates, loaded, skipped


def per_shot_rows(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        for name, config in {"baseline": BASELINE_CONFIG, "mirnov8_omv4": CANDIDATE_CONFIG}.items():
            score = search.score_config([case], config)
            rows.append(
                {
                    "shot": int(case["shot"]),
                    "config_name": name,
                    "config": json.dumps(config, sort_keys=True),
                    **search.compact_score(score),
                    "selection_score": search.selection_score(score),
                }
            )
    return rows


def write_report(run_dir: Path, summary: dict[str, Any], per_shot: list[dict[str, Any]]) -> None:
    baseline = summary["baseline"]
    candidate = summary["candidate"]
    lines = [
        "# FAIR-MAST Mirnov8+OMV4 Validation",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: validate the exploratory `pol_cc_ch2=8 + pol_omv_rms=4` trigger on later unused shots",
        f"- Discovery skip count: `{summary['discovery_skip_count']}`",
        f"- Validation shots: `{summary['validation_shots']}`",
        "- Candidate fixed before this validation run: `{'pol_cc_ch2': 8.0, 'pol_omv_rms': 4.0}`",
        "",
        "## Aggregate Validation Result",
        "",
        "| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Baseline Mirnov6 | {baseline['event_count']} | {baseline['detected_event_count']} | {baseline['missed_event_count']} | {baseline['false_trigger_count']} | {baseline['precision']:.3f} | {baseline['recall']:.3f} | {baseline['lead_ms']['median']:.3f} ms | {summary['baseline_score']:.3f} |",
        f"| Mirnov8+OMV4 | {candidate['event_count']} | {candidate['detected_event_count']} | {candidate['missed_event_count']} | {candidate['false_trigger_count']} | {candidate['precision']:.3f} | {candidate['recall']:.3f} | {candidate['lead_ms']['median']:.3f} ms | {summary['candidate_score']:.3f} |",
        "",
        "## Per-Shot Delta",
        "",
        "| Shot | Baseline detected | Candidate detected | Detected delta | Baseline false | Candidate false | False delta |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    by_key = {(row["shot"], row["config_name"]): row for row in per_shot}
    for shot in summary["validation_shots"]:
        base = by_key[(shot, "baseline")]
        candidate_row = by_key[(shot, "mirnov8_omv4")]
        lines.append(
            f"| {shot} | {base['detected']}/{base['events']} | {candidate_row['detected']}/{candidate_row['events']} | "
            f"{candidate_row['detected'] - base['detected']:+d} | {base['false_triggers']} | "
            f"{candidate_row['false_triggers']} | {candidate_row['false_triggers'] - base['false_triggers']:+d} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        f"Validation verdict: `{summary['validation_verdict']}`.",
        "",
        "This validates a candidate discovered on the previous fresh test block,",
        "using the next unused public-shot block. Labels remain machine morphology",
        "triage, not expert adjudication.",
        "",
    ]
    (run_dir / "fair_mast_mirnov8_omv4_validation_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--skip-count", type=int, default=DISCOVERY_SKIP_COUNT)
    parser.add_argument("--validation-shot-count", type=int, default=VALIDATION_SHOT_COUNT)
    args = parser.parse_args()

    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    candidates, cases, skipped = load_validation_cases(args.skip_count, args.validation_shot_count)
    baseline = search.score_config(cases, BASELINE_CONFIG)
    candidate = search.score_config(cases, CANDIDATE_CONFIG)
    per_shot = per_shot_rows(cases)
    detected_delta = candidate["detected_event_count"] - baseline["detected_event_count"]
    false_delta = candidate["false_trigger_count"] - baseline["false_trigger_count"]
    score_delta = search.selection_score(candidate) - search.selection_score(baseline)
    if score_delta > 0 and detected_delta >= 0:
        verdict = "validated_candidate_improves_score"
    elif detected_delta > 0:
        verdict = "mixed_candidate_gain_with_noise_cost"
    else:
        verdict = "candidate_does_not_generalize"

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_MIRNOV8_OMV4_VALIDATION_COMPLETED",
        "discovery_skip_count": args.skip_count,
        "validation_shot_count": args.validation_shot_count,
        "validation_shots": [int(case["shot"]) for case in cases],
        "skipped_candidate_count": len(skipped),
        "baseline_config": BASELINE_CONFIG,
        "candidate_config": CANDIDATE_CONFIG,
        "baseline": baseline,
        "candidate": candidate,
        "baseline_score": search.selection_score(baseline),
        "candidate_score": search.selection_score(candidate),
        "detected_delta_vs_baseline": detected_delta,
        "false_trigger_delta_vs_baseline": false_delta,
        "score_delta_vs_baseline": score_delta,
        "validation_verdict": verdict,
        "claim_boundary": "Fresh unused-shot fixed-candidate validation only; not expert-reviewed or causal validation.",
    }

    write_csv(args.run_dir / "fair_mast_mirnov8_omv4_validation_candidates.csv", candidates)
    write_csv(args.run_dir / "fair_mast_mirnov8_omv4_validation_skipped.csv", skipped)
    write_csv(args.run_dir / "fair_mast_mirnov8_omv4_validation_per_shot.csv", per_shot)
    (args.run_dir / "fair_mast_mirnov8_omv4_validation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary, per_shot)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

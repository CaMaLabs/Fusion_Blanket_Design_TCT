#!/usr/bin/env python3
"""Expand the TCT precursor bank on genuinely unused FAIR-MAST shots.

The trigger is deliberately frozen: centre-column poloidal Mirnov channel 2,
6 robust sigma, using the established causal pre-event association window.
This rung tests generalization, not another threshold search.

Fresh event labels are machine morphology triage from D-alpha only. Trigger
information is never used to accept/reject an event. A per-shot circular
trigger-train shift null preserves trigger count and intra-shot trigger pattern.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import zarr

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fair_mast_multidiagnostic_precursor_fusion as fusion
import fair_mast_omv_fresh_split as fresh
import fair_mast_other_trigger_screen as other

OUT = ROOT / "validation_runs" / "tct_precursor_bank_fair_mast_expansion"
OUT.mkdir(parents=True, exist_ok=True)

WINDOW_S = (0.30, 0.48)
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}
MIN_AUTOMATIC_EVENTS = int(os.environ.get("TCT_PRECURSOR_BANK_MIN_EVENTS", "5"))
TARGET_SHOTS = int(os.environ.get("TCT_PRECURSOR_BANK_SHOTS", "8"))
NULL_TRIALS = int(os.environ.get("TCT_PRECURSOR_BANK_NULL_TRIALS", "5000"))
RNG_SEED = int(os.environ.get("TCT_PRECURSOR_BANK_SEED", "20260929"))
FAST_BUDGET_MS = 2.75
NOMINAL_BUDGET_MS = 5.25

# Deliberately outside the ranges used by the earlier train/held-out/fresh work.
DISCOVERY_RANGES = (
    range(30180, 30260),
    range(30445, 30540),
)


class ShotTimeout(TimeoutError):
    pass


def _alarm(_signum: int, _frame: Any) -> None:
    raise ShotTimeout("FAIR-MAST shot operation timed out")


def with_alarm(seconds: int, fn, *args, **kwargs):
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(seconds)
    try:
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def collect_prior_shots() -> set[int]:
    """Collect shots already represented in FAIR-MAST CSV artifacts.

    This is intentionally conservative: if a shot appeared in a prior CSV audit,
    it is excluded from this fresh bank even if it was only a secondary candidate.
    """
    used = {30276, 30277, 30311, 30418, 30419, 30421, 30423}
    runs = ROOT / "validation_runs"
    for path in runs.glob("fair_mast*/*.csv"):
        try:
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or "shot" not in reader.fieldnames:
                    continue
                for row in reader:
                    text = str(row.get("shot", "")).strip()
                    if re.fullmatch(r"\d+", text):
                        used.add(int(text))
        except Exception:
            continue
    return used


def basic_arrays_present(group: zarr.Group) -> bool:
    try:
        visible = group["spectrometer_visible"]
        magnetics = group["magnetics"]
        _ = visible["time"].shape
        _ = visible["filter_spectrometer_dalpha_voltage"].shape
        _ = magnetics["time_mirnov"].shape
        field = magnetics["b_field_pol_probe_cc_field"]
        if field.shape[0] <= 2:
            return False
    except Exception:
        return False
    return True


def open_group(shot: int) -> zarr.Group:
    return zarr.open_group(f"{fusion.ARCHIVE_ROOT}/{shot}.zarr", mode="r")


def automatic_events_for_group(group: zarr.Group) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    visible = group["spectrometer_visible"]
    t = np.asarray(visible["time"], dtype=float)
    d = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[fusion.D_ALPHA_CHANNEL]
    e = fusion.detect_events(t, d, WINDOW_S)
    return t, d, e


def discover_fresh_shots(prior: set[int]) -> tuple[list[int], list[dict[str, Any]]]:
    selected: list[int] = []
    audit: list[dict[str, Any]] = []
    for shot_range in DISCOVERY_RANGES:
        for shot in shot_range:
            if len(selected) >= TARGET_SHOTS:
                return selected, audit
            if shot in prior:
                continue
            row: dict[str, Any] = {"shot": shot, "prior": False, "eligible": False}
            try:
                group = with_alarm(45, open_group, shot)
                if not basic_arrays_present(group):
                    row["reason"] = "required_dalpha_or_mirnov_missing"
                    audit.append(row)
                    continue
                _, _, events = with_alarm(45, automatic_events_for_group, group)
                row["automatic_event_count"] = int(len(events))
                if len(events) < MIN_AUTOMATIC_EVENTS:
                    row["reason"] = "too_few_automatic_dalpha_events"
                    audit.append(row)
                    continue
                row["eligible"] = True
                row["reason"] = "selected"
                selected.append(shot)
                audit.append(row)
            except Exception as exc:
                row["reason"] = f"load_error:{type(exc).__name__}"
                audit.append(row)
    return selected, audit


def load_fresh_case(shot: int) -> dict[str, Any]:
    group = with_alarm(120, open_group, shot)
    t_d, dalpha, automatic_events = with_alarm(120, automatic_events_for_group, group)

    accepted: list[float] = []
    labels: list[dict[str, Any]] = []
    for event_number, event_time in enumerate(automatic_events, start=1):
        context = fresh.local_peak_context(t_d, dalpha, float(event_time))
        label, notes = fresh.review_label(float(event_time), automatic_events, context, WINDOW_S)
        if label == "true_elm":
            accepted.append(float(event_time))
        labels.append({
            "shot": shot,
            "event_number": event_number,
            "event_time_s": float(event_time),
            **context,
            "review_label": label,
            "review_notes": notes,
        })

    magnetics = group["magnetics"]
    t_m = np.asarray(magnetics["time_mirnov"], dtype=float)
    data = np.asarray(magnetics["b_field_pol_probe_cc_field"], dtype=float)
    spec = {
        "name": "pol_cc_ch2",
        "group": "magnetics",
        "time": "time_mirnov",
        "field": "b_field_pol_probe_cc_field",
        "channels": (2,),
        "kind": "rms",
    }
    signal_values = other.feature_signal(t_m, data, spec)
    t_m, signal_values = other.maybe_decimate(t_m, signal_values)

    case = {
        "shot": shot,
        "window_s": WINDOW_S,
        "accepted_event_times": np.asarray(accepted, dtype=float),
        "labels": labels,
        "features": {"pol_cc_ch2": {"time": t_m, "signal": signal_values}},
    }
    case["crossings"] = fusion.crossings_for_config(case, BASELINE_CONFIG)
    return case


def match_events(event_times: np.ndarray, crossings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    crossing_times = np.asarray([float(x["time"]) for x in crossings], dtype=float)
    available = set(range(len(crossing_times)))
    matched_indices: set[int] = set()
    rows: list[dict[str, Any]] = []

    for event_number, event_time in enumerate(event_times, start=1):
        candidates = [
            i for i in available
            if event_time - fusion.PRECURSOR_WINDOW_S[1] <= crossing_times[i] <= event_time - fusion.PRECURSOR_WINDOW_S[0]
        ]
        if candidates:
            i = candidates[-1]
            available.remove(i)
            matched_indices.add(i)
            lead_ms = float((event_time - crossing_times[i]) * 1000.0)
            rows.append({
                "event_number": event_number,
                "event_time_s": float(event_time),
                "detected": True,
                "trigger_time_s": float(crossing_times[i]),
                "lead_ms": lead_ms,
                "fast_2p75ms_reachable": lead_ms >= FAST_BUDGET_MS,
                "nominal_5p25ms_reachable": lead_ms >= NOMINAL_BUDGET_MS,
                "sources": crossings[i].get("sources", "pol_cc_ch2"),
            })
        else:
            rows.append({
                "event_number": event_number,
                "event_time_s": float(event_time),
                "detected": False,
                "trigger_time_s": None,
                "lead_ms": None,
                "fast_2p75ms_reachable": False,
                "nominal_5p25ms_reachable": False,
                "sources": None,
            })

    false_count = 0
    for i, crossing_time in enumerate(crossing_times):
        in_signature = bool(np.any(np.abs(event_times - crossing_time) <= fusion.EVENT_SIGNATURE_EXCLUSION_S))
        false_count += i not in matched_indices and not in_signature
    return rows, false_count


def circular_shift_crossings(crossings: list[dict[str, Any]], shift_s: float) -> list[dict[str, Any]]:
    start, end = WINDOW_S
    width = end - start
    shifted = []
    for row in crossings:
        t = start + ((float(row["time"]) - start + shift_s) % width)
        shifted.append({"time": t, "sources": row.get("sources", "pol_cc_ch2")})
    return sorted(shifted, key=lambda x: x["time"])


def circular_shift_null(cases: list[dict[str, Any]], observed_detected: int) -> dict[str, Any]:
    rng = np.random.default_rng(RNG_SEED)
    width = WINDOW_S[1] - WINDOW_S[0]
    counts = np.zeros(NULL_TRIALS, dtype=int)
    for trial in range(NULL_TRIALS):
        detected = 0
        for case in cases:
            shift = float(rng.uniform(0.0, width))
            shifted = circular_shift_crossings(case["crossings"], shift)
            detected += int(fusion.score_alignment(case["accepted_event_times"], shifted)["detected_event_count"])
        counts[trial] = detected
    p = (1 + int(np.count_nonzero(counts >= observed_detected))) / (NULL_TRIALS + 1)
    return {
        "trials": NULL_TRIALS,
        "seed": RNG_SEED,
        "null_model": "independent per-shot circular shift of the frozen trigger train within the fixed analysis window",
        "observed_detected": observed_detected,
        "mean_detected": float(np.mean(counts)),
        "p95_detected": float(np.quantile(counts, 0.95)),
        "max_detected": int(np.max(counts)),
        "directional_p_ge_observed": float(p),
    }


def main() -> int:
    prior = collect_prior_shots()
    selected, discovery = discover_fresh_shots(prior)
    write_csv(OUT / "discovery_audit.csv", discovery)

    cases: list[dict[str, Any]] = []
    load_errors: list[dict[str, Any]] = []
    for shot in selected:
        try:
            cases.append(with_alarm(240, load_fresh_case, shot))
        except Exception as exc:
            load_errors.append({"shot": shot, "error": f"{type(exc).__name__}: {exc}"})

    event_rows: list[dict[str, Any]] = []
    shot_rows: list[dict[str, Any]] = []
    all_leads: list[float] = []
    total_events = total_detected = total_false = 0

    for case in cases:
        matched, false_count = match_events(case["accepted_event_times"], case["crossings"])
        leads = [float(r["lead_ms"]) for r in matched if r["detected"]]
        for row in matched:
            event_rows.append({"shot": case["shot"], **row})
        total_events += len(matched)
        total_detected += len(leads)
        total_false += false_count
        all_leads.extend(leads)
        shot_rows.append({
            "shot": case["shot"],
            "accepted_events": len(matched),
            "detected": len(leads),
            "missed": len(matched) - len(leads),
            "false_triggers": false_count,
            "precision": len(leads) / (len(leads) + false_count) if len(leads) + false_count else 0.0,
            "recall": len(leads) / len(matched) if matched else 0.0,
            "median_lead_ms": float(np.median(leads)) if leads else None,
            "fast_2p75ms_reachable": sum(x >= FAST_BUDGET_MS for x in leads),
            "nominal_5p25ms_reachable": sum(x >= NOMINAL_BUDGET_MS for x in leads),
        })

    write_csv(OUT / "events.csv", event_rows)
    write_csv(OUT / "shots.csv", shot_rows)
    if load_errors:
        write_csv(OUT / "load_errors.csv", load_errors)

    precision = total_detected / (total_detected + total_false) if total_detected + total_false else 0.0
    recall = total_detected / total_events if total_events else 0.0
    fast_count = sum(x >= FAST_BUDGET_MS for x in all_leads)
    nominal_count = sum(x >= NOMINAL_BUDGET_MS for x in all_leads)
    null = circular_shift_null(cases, total_detected) if cases and total_events else None

    if len(cases) < 3 or total_events < 10:
        classification = "TCT_PRECURSOR_BANK_FAIR_MAST_EXPANSION_INSUFFICIENT_FRESH_DATA"
    elif null is not None and null["directional_p_ge_observed"] <= 0.05:
        classification = "TCT_PRECURSOR_BANK_FAIR_MAST_FRESH_PRECURSOR_SIGNAL_OBSERVED"
    else:
        classification = "TCT_PRECURSOR_BANK_FAIR_MAST_FRESH_PRECURSOR_SIGNAL_NOT_ESTABLISHED"

    summary = {
        "schema_version": 1,
        "classification": classification,
        "pipeline_failure": False,
        "machine": "MAST",
        "source": "FAIR-MAST public Level-2 experimental archive",
        "source_root": fusion.ARCHIVE_ROOT,
        "precursor_class": "fast_mhd_elm_candidate",
        "event_marker": "D-alpha morphology triage; trigger timing excluded from labeling",
        "trigger": {
            "name": "frozen_centre_column_poloidal_mirnov",
            "config": BASELINE_CONFIG,
            "association_window_ms": [fusion.PRECURSOR_WINDOW_S[0] * 1000.0, fusion.PRECURSOR_WINDOW_S[1] * 1000.0],
            "retuned_on_this_bank": False,
        },
        "freshness": {
            "prior_shot_count_excluded": len(prior),
            "discovery_ranges": [[r.start, r.stop - 1] for r in DISCOVERY_RANGES],
            "selected_shots": [int(c["shot"]) for c in cases],
            "selected_count": len(cases),
            "load_errors": load_errors,
        },
        "aggregate": {
            "accepted_event_count": total_events,
            "detected_event_count": total_detected,
            "missed_event_count": total_events - total_detected,
            "false_trigger_count": total_false,
            "precision": precision,
            "recall": recall,
            "lead_ms": {
                "minimum": float(np.min(all_leads)) if all_leads else None,
                "median": float(np.median(all_leads)) if all_leads else None,
                "maximum": float(np.max(all_leads)) if all_leads else None,
            },
            "actuator_reachability": {
                "prebiased_fast_2p75_ms": {
                    "reachable_events": fast_count,
                    "accepted_events": total_events,
                    "fraction": fast_count / total_events if total_events else 0.0,
                },
                "prebiased_nominal_5p25_ms": {
                    "reachable_events": nominal_count,
                    "accepted_events": total_events,
                    "fraction": nominal_count / total_events if total_events else 0.0,
                },
            },
        },
        "null_test": null,
        "claim_boundary": (
            "Retrospective public MAST precursor-generalization audit with machine-generated D-alpha morphology labels. "
            "It does not prove expert-reviewed ELM identity, causal TCT suppression, actuator efficacy, reactor-scale control, "
            "or transfer to DIII-D/other machines."
        ),
        "next_step": (
            "If the frozen Mirnov signal remains above the fresh-shot circular-shift null, add these shots to the precursor bank "
            "and test a separately sourced machine. Treat Fusion Equilibrium Challenge DIII-D data as slow equilibrium/state "
            "antecedent data only unless an independent fast-MHD/ELM event marker becomes available."
        ),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report = [
        "# TCT FAIR-MAST Precursor Bank Expansion",
        "",
        f"- Classification: `{classification}`",
        f"- Fresh shots: `{summary['freshness']['selected_shots']}`",
        f"- Accepted D-alpha morphology events: `{total_events}`",
        f"- Frozen Mirnov detections: `{total_detected}`",
        f"- False triggers: `{total_false}`",
        f"- Precision: `{precision:.3f}`",
        f"- Recall: `{recall:.3f}`",
        f"- Median detected lead: `{summary['aggregate']['lead_ms']['median']}` ms",
        f"- 2.75 ms reachable: `{fast_count}/{total_events}`",
        f"- 5.25 ms reachable: `{nominal_count}/{total_events}`",
        "",
        "## Null test",
        "",
        json.dumps(null, indent=2) if null is not None else "No null test: insufficient fresh data.",
        "",
        "## Claim boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Next step",
        "",
        summary["next_step"],
        "",
    ]
    (OUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

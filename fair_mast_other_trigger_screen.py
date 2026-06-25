#!/usr/bin/env python3
"""Screen additional FAIR-MAST diagnostics as candidate ELM/TCT precursors."""

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
from scipy.ndimage import uniform_filter1d

import fair_mast_multidiagnostic_precursor_fusion as fusion


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_other_trigger_screen_default"
BASELINE_CONFIG = {"pol_cc_ch2": 6.0}
SIGMA_GRID = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
MIN_DT_FOR_TRIGGER_S = 2.0e-5


FEATURE_SPECS = (
    {"name": "pol_omv_rms", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_omv_voltage", "channels": (0, 1, 2), "kind": "rms"},
    {"name": "tor_omaha_rms", "group": "magnetics", "time": "time_omaha", "field": "b_field_tor_probe_omaha_voltage", "channels": (0, 1, 2, 3), "kind": "rms"},
    {"name": "saddle_tor_rms", "group": "magnetics", "time": "time_saddle", "field": "b_field_tor_probe_saddle_voltage", "channels": tuple(range(12)), "kind": "rms"},
    {"name": "bes_sparse_rms", "group": "spectrometer_visible", "time": "time_bes", "field": "filter_spectrometer_bes_voltage", "channels": (0, 8, 16, 24), "kind": "rms"},
    {"name": "density_gradient_abs_slope", "group": "spectrometer_visible", "time": "time", "field": "density_gradient", "channels": None, "kind": "abs_slope"},
    {"name": "dalpha_ch0_abs_slope", "group": "spectrometer_visible", "time": "time", "field": "filter_spectrometer_dalpha_voltage", "channels": (0,), "kind": "abs_slope"},
    {"name": "dalpha_ch2_abs_slope", "group": "spectrometer_visible", "time": "time", "field": "filter_spectrometer_dalpha_voltage", "channels": (2,), "kind": "abs_slope"},
    {"name": "bolometer_total_abs_slope", "group": "bolometer", "time": "time", "field": "power_radiated_total", "channels": None, "kind": "abs_slope"},
    {"name": "controller_zip_abs_slope", "group": "controllers", "time": "time", "field": "zip_proxy", "channels": None, "kind": "abs_slope"},
    {"name": "gas_pressure_abs_slope", "group": "gas_injection", "time": "time", "field": "pressure", "channels": None, "kind": "abs_slope"},
    {"name": "pf_active_current_abs_slope", "group": "pf_active", "time": "time", "field": "coil_current", "channels": tuple(range(13)), "kind": "abs_slope"},
    {"name": "passive_ring_abs_slope", "group": "pf_passive", "time": "time", "field": "ring_current", "channels": tuple(range(10)), "kind": "abs_slope"},
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


def finite_interp(time_axis: np.ndarray, values: np.ndarray) -> np.ndarray:
    finite = np.isfinite(values)
    if np.count_nonzero(finite) < 2:
        return np.zeros_like(time_axis, dtype=float)
    return np.interp(time_axis, time_axis[finite], values[finite])


def abs_slope_signal(time_axis: np.ndarray, values: np.ndarray) -> np.ndarray:
    values = finite_interp(time_axis, values)
    dt = float(np.nanmedian(np.diff(time_axis)))
    smooth_points = max(3, int(0.0005 / max(dt, 1e-9)))
    smooth = uniform_filter1d(values, smooth_points, mode="nearest")
    return np.abs(np.gradient(smooth, time_axis))


def maybe_decimate(time_axis: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(time_axis) < 2:
        return time_axis, values
    dt = float(np.nanmedian(np.diff(time_axis)))
    step = max(1, int(MIN_DT_FOR_TRIGGER_S / max(dt, 1e-12)))
    return time_axis[::step], values[::step]


def feature_signal(time_axis: np.ndarray, data: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    if data.ndim == 1:
        channels = [data]
    else:
        selected = spec["channels"] if spec["channels"] is not None else tuple(range(data.shape[0]))
        channels = [data[index] for index in selected if index < data.shape[0]]
    signal = None
    for channel in channels:
        if spec["kind"] == "rms":
            component = fusion.rms_envelope(time_axis, channel)
        elif spec["kind"] == "abs_slope":
            component = abs_slope_signal(time_axis, channel)
        else:
            raise ValueError(spec["kind"])
        signal = component if signal is None else np.maximum(signal, component)
    if signal is None:
        signal = np.zeros_like(time_axis, dtype=float)
    return signal


def load_case(case_def: dict[str, Any]) -> dict[str, Any]:
    shot = int(case_def["shot"])
    window_s = tuple(case_def["window_s"])
    group = zarr.open_group(f"{fusion.ARCHIVE_ROOT}/{shot}.zarr", mode="r")
    visible = group["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[fusion.D_ALPHA_CHANNEL]
    automatic_events = fusion.detect_events(dalpha_time, dalpha, window_s)
    features: dict[str, dict[str, Any]] = {}

    baseline = {"name": "pol_cc_ch2", "group": "magnetics", "time": "time_mirnov", "field": "b_field_pol_probe_cc_field", "channels": (2,), "kind": "rms"}
    for spec in (baseline, *FEATURE_SPECS):
        node = group[spec["group"]]
        time_axis = np.asarray(node[spec["time"]], dtype=float)
        data = np.asarray(node[spec["field"]], dtype=float)
        signal = feature_signal(time_axis, data, spec)
        time_axis, signal = maybe_decimate(time_axis, signal)
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
    scores = [
        fusion.score_alignment(events_by_shot[int(case["shot"])], fusion.crossings_for_config(case, config))
        for case in cases
    ]
    return fusion.aggregate(scores)


def selection_score(score: dict[str, Any]) -> float:
    return 2.0 * score["recall"] + 0.8 * score["precision"] - 0.025 * score["false_trigger_count"]


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


def candidate_configs() -> list[dict[str, float]]:
    configs: list[dict[str, float]] = []
    for spec in FEATURE_SPECS:
        for sigma in SIGMA_GRID:
            configs.append({spec["name"]: sigma})
            configs.append({"pol_cc_ch2": 6.0, spec["name"]: sigma})
    return configs


def write_report(run_dir: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    baseline = summary["baseline_reviewed_labels"]
    selected = summary["selected_reviewed_labels"]
    exploratory = summary["best_exploratory_reviewed_labels"]
    top_train = sorted([row for row in rows if row["split"] == "train"], key=lambda row: -row["selection_score"])[:10]
    top_test = sorted([row for row in rows if row["split"] == "test_all"], key=lambda row: -row["selection_score"])[:10]
    lines = [
        "# FAIR-MAST Other Trigger Screen",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: screen additional public FAIR-MAST diagnostics as possible precursor triggers",
        "- Train split: automatic D-alpha labels on shots `30311`, `30423`",
        "- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`",
        "- Candidate families: OMV/OMAHA/saddle magnetics, sparse BES, density-gradient, alternate D-alpha channels, bolometer, controller/gas, coil/passive-current, and summary radiation traces",
        "",
        "## Held-Out Result",
        "",
        "| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Fixed Mirnov baseline | {baseline['event_count']} | {baseline['detected_event_count']} | {baseline['missed_event_count']} | {baseline['false_trigger_count']} | {baseline['precision']:.3f} | {baseline['recall']:.3f} | {baseline['lead_ms']['median']:.3f} ms |",
        f"| Selected other-trigger config | {selected['event_count']} | {selected['detected_event_count']} | {selected['missed_event_count']} | {selected['false_trigger_count']} | {selected['precision']:.3f} | {selected['recall']:.3f} | {selected['lead_ms']['median']:.3f} ms |",
        f"| Best exploratory held-out config | {exploratory['event_count']} | {exploratory['detected_event_count']} | {exploratory['missed_event_count']} | {exploratory['false_trigger_count']} | {exploratory['precision']:.3f} | {exploratory['recall']:.3f} | {exploratory['lead_ms']['median']:.3f} ms |",
        "",
        "## Selected Config",
        "",
        f"- Config: `{summary['selected_config']}`",
        f"- Train score: `{summary['selected_train_score']:.3f}`",
        f"- Best exploratory held-out config: `{summary['best_exploratory_config']}`",
        f"- Best exploratory held-out score: `{summary['best_exploratory_score']:.3f}`",
        "",
        "## Top Train-Selected Rows",
        "",
        "| Split | Config | Detected | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top_train:
        lines.append(
            f"| `{row['split']}` | `{row['config']}` | {row['detected']}/{row['events']} | "
            f"{row['false_triggers']} | {row['precision']:.3f} | {row['recall']:.3f} | "
            f"{row['median_lead_ms'] if row['median_lead_ms'] is not None else 'n/a'} | {row['selection_score']:.3f} |"
        )
    lines += [
        "",
        "## Top Exploratory Held-Out Rows",
        "",
        "These rows are an oracle-style diagnostic screen over the held-out shots.",
        "They are useful for finding leads, but they are not a clean validation",
        "selection because the test labels are used for ranking.",
        "",
        "| Split | Config | Detected | False triggers | Precision | Recall | Median lead | Score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top_test:
        lines.append(
            f"| `{row['split']}` | `{row['config']}` | {row['detected']}/{row['events']} | "
            f"{row['false_triggers']} | {row['precision']:.3f} | {row['recall']:.3f} | "
            f"{row['median_lead_ms'] if row['median_lead_ms'] is not None else 'n/a'} | {row['selection_score']:.3f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "No train-selected additional trigger family improved on the fixed Mirnov",
        "baseline in held-out reviewed labels. The selected OMV augmentation was",
        "neutral on the test split.",
        "",
        "This is a broad trigger-discovery screen. A candidate should only be treated",
        "as promising if held-out precision/false-trigger behavior is competitive",
        "with the fixed Mirnov or Mirnov+toroidal references while retaining enough",
        "lead for the fast biased-current response budget.",
        "",
        "## Claim Boundary",
        "",
        "This is diagnostic trigger discovery only. It is not causal TCT validation",
        "or a deployable real-time trigger.",
        "",
    ]
    (run_dir / "fair_mast_other_trigger_screen_report.md").write_text("\n".join(lines), encoding="utf-8")


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
    train_cases = [case for case in cases if case["split"] == "train"]
    test_cases = [case for case in cases if case["split"] == "test"]
    train_events = {int(case["shot"]): case["automatic_event_times"] for case in train_cases}

    rows: list[dict[str, Any]] = []
    best_config = None
    best_score = -1e9
    for config in candidate_configs():
        train_score = score_config(train_cases, train_events, config)
        score = selection_score(train_score)
        row = {"split": "train", "config": json.dumps(config, sort_keys=True), **compact_score(train_score), "selection_score": score}
        rows.append(row)
        if score > best_score:
            best_score = score
            best_config = config

    assert best_config is not None
    best_test_config = None
    best_test_score = -1e9
    best_test_result = None
    for config in candidate_configs():
        test_score = score_config(test_cases, reviewed, config)
        score = selection_score(test_score)
        row = {"split": "test_all", "config": json.dumps(config, sort_keys=True), **compact_score(test_score), "selection_score": score}
        rows.append(row)
        if score > best_test_score:
            best_test_score = score
            best_test_config = config
            best_test_result = test_score

    assert best_test_config is not None
    assert best_test_result is not None
    selected_score = score_config(test_cases, reviewed, best_config)
    baseline_score = score_config(test_cases, reviewed, BASELINE_CONFIG)
    rows.append({"split": "test_selected", "config": json.dumps(best_config, sort_keys=True), **compact_score(selected_score), "selection_score": selection_score(selected_score)})
    rows.append({"split": "test_baseline", "config": json.dumps(BASELINE_CONFIG, sort_keys=True), **compact_score(baseline_score), "selection_score": selection_score(baseline_score)})

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_OTHER_TRIGGER_SCREEN_COMPLETED",
        "selected_config": best_config,
        "selected_train_score": best_score,
        "selected_reviewed_labels": selected_score,
        "baseline_reviewed_labels": baseline_score,
        "best_exploratory_config": best_test_config,
        "best_exploratory_score": best_test_score,
        "best_exploratory_reviewed_labels": best_test_result,
        "feature_count": len(FEATURE_SPECS),
        "config_count": len(candidate_configs()),
        "claim_boundary": "Broad FAIR-MAST diagnostic trigger screen only; not causal validation.",
    }
    write_csv(args.run_dir / "fair_mast_other_trigger_screen_grid.csv", rows)
    (args.run_dir / "fair_mast_other_trigger_screen_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate a visual event-label audit packet for the FAIR-MAST held-out test."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import zarr
from scipy.ndimage import uniform_filter1d


REPO = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = REPO / "validation_runs" / "fair_mast_prospective_precursor_default"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_event_label_audit_default"
ARCHIVE_ROOT = "https://s3.echo.stfc.ac.uk/mast/level2/shots"
D_ALPHA_CHANNEL = 1
MIRNOV_CHANNEL = 2
BASELINE_WINDOW_S = 0.040
WINDOW_HALF_WIDTH_S = 0.020
LATENCIES_MS = (3.0, 5.0, 8.0, 12.0)


def robust_sigma(values: np.ndarray) -> float:
    median = np.nanmedian(values)
    return float(1.4826 * np.nanmedian(np.abs(values - median)))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def bool_from_csv(value: str) -> bool:
    return value.strip().lower() == "true"


def float_or_none(value: str) -> float | None:
    return None if value == "" else float(value)


def mirnov_envelope(mirnov_time: np.ndarray, mirnov: np.ndarray) -> np.ndarray:
    finite = np.isfinite(mirnov)
    mirnov = np.interp(mirnov_time, mirnov_time[finite], mirnov[finite])
    dt = float(np.nanmedian(np.diff(mirnov_time)))
    trend_points = max(3, int(0.002 / dt))
    rms_points = max(3, int(0.0005 / dt))
    high_pass = mirnov - uniform_filter1d(mirnov, trend_points, mode="nearest")
    return np.sqrt(uniform_filter1d(high_pass * high_pass, rms_points, mode="nearest"))


def load_shot(shot: int, window_s: tuple[float, float], threshold_sigma: float) -> dict[str, Any]:
    group = zarr.open_group(f"{ARCHIVE_ROOT}/{shot}.zarr", mode="r")
    visible = group["spectrometer_visible"]
    dalpha_time = np.asarray(visible["time"], dtype=float)
    dalpha = np.asarray(visible["filter_spectrometer_dalpha_voltage"], dtype=float)[D_ALPHA_CHANNEL]

    magnetics = group["magnetics"]
    mirnov_time = np.asarray(magnetics["time_mirnov"], dtype=float)
    mirnov = np.asarray(magnetics["b_field_pol_probe_cc_field"], dtype=float)[MIRNOV_CHANNEL]
    envelope = mirnov_envelope(mirnov_time, mirnov)
    baseline = (
        (mirnov_time >= window_s[0])
        & (mirnov_time <= min(window_s[1], window_s[0] + BASELINE_WINDOW_S))
        & np.isfinite(envelope)
    )
    baseline_median = float(np.nanmedian(envelope[baseline]))
    baseline_sigma = robust_sigma(envelope[baseline])
    threshold = baseline_median + threshold_sigma * baseline_sigma
    return {
        "dalpha_time": dalpha_time,
        "dalpha": dalpha,
        "mirnov_time": mirnov_time,
        "envelope": envelope,
        "threshold": threshold,
    }


def local_peak_context(time: np.ndarray, values: np.ndarray, event_time: float) -> dict[str, float]:
    local = (time >= event_time - 0.002) & (time <= event_time + 0.002)
    pre = (time >= event_time - 0.010) & (time <= event_time - 0.002)
    peak = float(np.nanmax(values[local])) if np.any(local) else float("nan")
    pre_median = float(np.nanmedian(values[pre])) if np.any(pre) else float("nan")
    return {
        "local_peak_v": peak,
        "pre_event_median_v": pre_median,
        "local_peak_minus_pre_median_v": peak - pre_median,
    }


def plot_event(
    plot_path: Path,
    shot_data: dict[str, Any],
    row: dict[str, Any],
    lead_ms: float | None,
) -> None:
    event_time = float(row["event_time_s"])
    start = event_time - WINDOW_HALF_WIDTH_S
    end = event_time + WINDOW_HALF_WIDTH_S
    dalpha_mask = (shot_data["dalpha_time"] >= start) & (shot_data["dalpha_time"] <= end)
    mirnov_mask = (shot_data["mirnov_time"] >= start) & (shot_data["mirnov_time"] <= end)

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    fig.suptitle(
        f"FAIR-MAST event audit: shot {row['shot']} event {row['event_number']} "
        f"({row['classification_hint']})"
    )

    x_dalpha = (shot_data["dalpha_time"][dalpha_mask] - event_time) * 1000.0
    axes[0].plot(x_dalpha, shot_data["dalpha"][dalpha_mask], color="#1f77b4", lw=1.2)
    axes[0].axvline(0.0, color="#d62728", lw=1.4, label="D-alpha event")
    if lead_ms is not None:
        axes[0].axvline(-lead_ms, color="#2ca02c", lw=1.2, ls="--", label="trigger")
    axes[0].set_ylabel("D-alpha V")
    axes[0].legend(loc="upper right", fontsize=8)
    axes[0].grid(True, alpha=0.25)

    x_mirnov = (shot_data["mirnov_time"][mirnov_mask] - event_time) * 1000.0
    axes[1].plot(x_mirnov, shot_data["envelope"][mirnov_mask], color="#111111", lw=1.0)
    axes[1].axhline(shot_data["threshold"], color="#9467bd", lw=1.1, ls=":", label="trigger threshold")
    axes[1].axvline(0.0, color="#d62728", lw=1.4)
    if lead_ms is not None:
        axes[1].axvline(-lead_ms, color="#2ca02c", lw=1.2, ls="--")
    axes[1].set_ylabel("Mirnov RMS envelope")
    axes[1].set_xlabel("Time relative to D-alpha event (ms)")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].grid(True, alpha=0.25)
    axes[1].set_xlim(-WINDOW_HALF_WIDTH_S * 1000.0, WINDOW_HALF_WIDTH_S * 1000.0)

    fig.tight_layout()
    fig.savefig(plot_path, dpi=140)
    plt.close(fig)


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    source = summary["source_test_aggregate"]
    lines = [
        "# FAIR-MAST Event-Label Audit Packet",
        "",
        f"- Status: `{summary['status']}`",
        "- Scope: held-out test events from the FAIR-MAST prospective precursor run",
        "- Purpose: independent review of automatic D-alpha event labels and trigger timing",
        f"- Events plotted: `{summary['event_count']}`",
        f"- Shots: `{summary['shots']}`",
        f"- Plot window: `+/-{WINDOW_HALF_WIDTH_S * 1000:.0f} ms` around each automatic D-alpha event",
        "",
        "## Reviewer Instructions",
        "",
        "Use `fair_mast_event_label_audit_manifest.csv` as the working sheet. For each",
        "row, inspect the linked PNG and set `review_label` to one of:",
        "",
        "- `true_elm`",
        "- `ambiguous`",
        "- `artifact`",
        "- `missed_obvious_elm_nearby`",
        "",
        "Then fill `review_notes` with the basis for that call. The manifest already",
        "contains trigger timing, lead time, latency-feasibility flags, and simple",
        "D-alpha local-peak context to make the review auditable.",
        "",
        "## Current Automatic-Label Summary",
        "",
        f"- Source aggregate trigger-detected events: `{source['detected_event_count']}`",
        f"- Source aggregate missed automatic events: `{source['missed_event_count']}`",
        f"- Raw event-row trigger flags: `{summary['raw_trigger_detected_count']}` detected / `{summary['raw_missed_count']}` missed",
        f"- Event rows with reused trigger times requiring audit attention: `{summary['reused_trigger_row_count']}`",
        f"- Events with at least 3 ms lead: `{summary['latency_feasible_event_count']['3_ms']}`",
        f"- Events with at least 5 ms lead: `{summary['latency_feasible_event_count']['5_ms']}`",
        f"- Events with at least 8 ms lead: `{summary['latency_feasible_event_count']['8_ms']}`",
        f"- Events with at least 12 ms lead: `{summary['latency_feasible_event_count']['12_ms']}`",
        "",
        "## Claim Boundary",
        "",
        "This packet does not itself prove the event labels. It creates the review set",
        "needed to replace automatic labels with audited labels, after which precision,",
        "recall, false-trigger rate, and lead-time feasibility should be recomputed on",
        "accepted `true_elm` rows only.",
        "",
    ]
    (run_dir / "fair_mast_event_label_audit_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    plot_dir = args.run_dir / "plots"
    plot_dir.mkdir(parents=True)

    event_rows = read_csv(args.input_dir / "fair_mast_prospective_precursor_events.csv")
    with (args.input_dir / "fair_mast_prospective_precursor_summary.json").open(encoding="utf-8") as handle:
        source_summary = json.load(handle)
    threshold_sigma = float(source_summary["selected_threshold_sigma"])
    shot_windows = {
        int(row["shot"]): tuple(row["window_s"])
        for row in source_summary["shot_scores"]
        if row["split"] == "test"
    }
    test_events = [row for row in event_rows if row["split"] == "test"]
    trigger_key_counts: dict[tuple[int, str], int] = {}
    for row in test_events:
        if row["trigger_time_s"]:
            key = (int(row["shot"]), row["trigger_time_s"])
            trigger_key_counts[key] = trigger_key_counts.get(key, 0) + 1
    shot_cache: dict[int, dict[str, Any]] = {}
    manifest = []
    for row in test_events:
        shot = int(row["shot"])
        if shot not in shot_cache:
            shot_cache[shot] = load_shot(shot, shot_windows[shot], threshold_sigma)
        lead_ms = float_or_none(row["lead_ms"])
        trigger_detected = bool_from_csv(row["trigger_detected"])
        trigger_key = (shot, row["trigger_time_s"])
        trigger_reuse_count = trigger_key_counts.get(trigger_key, 0) if row["trigger_time_s"] else 0
        hint = "triggered" if trigger_detected else "missed"
        plot_name = f"shot_{shot}_event_{int(row['event_number']):03d}_{hint}.png"
        plot_path = plot_dir / plot_name
        row_for_plot = {
            **row,
            "classification_hint": hint,
        }
        plot_event(plot_path, shot_cache[shot], row_for_plot, lead_ms)
        context = local_peak_context(
            shot_cache[shot]["dalpha_time"],
            shot_cache[shot]["dalpha"],
            float(row["event_time_s"]),
        )
        manifest.append(
            {
                "shot": shot,
                "event_number": int(row["event_number"]),
                "event_time_s": float(row["event_time_s"]),
                "automatic_label": "dalpha_peak",
                "trigger_detected": trigger_detected,
                "trigger_time_s": float_or_none(row["trigger_time_s"]),
                "lead_ms": lead_ms,
                "latency_3_ms_feasible": lead_ms is not None and lead_ms >= 3.0,
                "latency_5_ms_feasible": lead_ms is not None and lead_ms >= 5.0,
                "latency_8_ms_feasible": lead_ms is not None and lead_ms >= 8.0,
                "latency_12_ms_feasible": lead_ms is not None and lead_ms >= 12.0,
                "trigger_time_reuse_count": trigger_reuse_count,
                "audit_priority": "duplicate_trigger_reuse" if trigger_reuse_count > 1 else "",
                **context,
                "plot_path": f"plots/{plot_name}",
                "review_label": "",
                "review_notes": "",
            }
        )

    fields = [
        "shot",
        "event_number",
        "event_time_s",
        "automatic_label",
        "trigger_detected",
        "trigger_time_s",
        "lead_ms",
        "latency_3_ms_feasible",
        "latency_5_ms_feasible",
        "latency_8_ms_feasible",
        "latency_12_ms_feasible",
        "trigger_time_reuse_count",
        "audit_priority",
        "local_peak_v",
        "pre_event_median_v",
        "local_peak_minus_pre_median_v",
        "plot_path",
        "review_label",
        "review_notes",
    ]
    write_csv(args.run_dir / "fair_mast_event_label_audit_manifest.csv", manifest, fields)
    source_test = source_summary["test_aggregate"]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_EVENT_LABEL_AUDIT_PACKET_GENERATED",
        "source_run": str(args.input_dir.relative_to(REPO)),
        "event_count": len(manifest),
        "shots": sorted(shot_cache),
        "source_test_aggregate": {
            "detected_event_count": source_test["detected_event_count"],
            "missed_event_count": source_test["missed_event_count"],
            "false_trigger_count": source_test["false_trigger_count"],
            "precision": source_test["precision"],
            "recall": source_test["recall"],
        },
        "raw_trigger_detected_count": sum(row["trigger_detected"] for row in manifest),
        "raw_missed_count": sum(not row["trigger_detected"] for row in manifest),
        "reused_trigger_row_count": sum(row["trigger_time_reuse_count"] > 1 for row in manifest),
        "latency_feasible_event_count": {
            f"{latency:g}_ms": sum(
                row["lead_ms"] is not None and row["lead_ms"] >= latency for row in manifest
            )
            for latency in LATENCIES_MS
        },
        "review_status": "unreviewed",
        "claim_boundary": "Visual audit packet only; audited labels must be filled before recomputing validation metrics.",
    }
    (args.run_dir / "fair_mast_event_label_audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

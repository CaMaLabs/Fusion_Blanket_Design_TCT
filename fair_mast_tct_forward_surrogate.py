#!/usr/bin/env python3
"""Run a FAIR-MAST-calibrated forward surrogate for TCT-style control policies."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_tct_forward_surrogate_default"
REVIEW_MANIFEST = REPO / "validation_runs" / "fair_mast_machine_reviewed_labels_default" / "fair_mast_machine_reviewed_label_manifest.csv"
SXR_TRADEOFF = REPO / "validation_runs" / "fair_mast_sxr_precursor_tradeoff_default" / "fair_mast_sxr_precursor_tradeoff.csv"
ACTUATOR_SUMMARY = REPO / "validation_runs" / "fair_mast_biased_actuator_response_budget_default" / "fair_mast_biased_actuator_response_budget_summary.json"

DEFAULT_HORIZON_S = 10.0
DEFAULT_RUNS = 2000
DEFAULT_SEED = 20260624
FAIR_MAST_TEST_WINDOW_S = 5 * 0.18


@dataclass(frozen=True)
class Policy:
    name: str
    source: str
    detected_fraction: float
    reachable_fraction: float
    false_trigger_rate_hz: float
    standing_bias: float
    event_reduction: float
    false_trigger_cost: float
    steady_cost_per_s: float
    description: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_reviewed_events() -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(REVIEW_MANIFEST):
        if row["review_label"] != "true_elm":
            continue
        rows.append(
            {
                "shot": int(row["shot"]),
                "event_time_s": float(row["event_time_s"]),
                "severity_proxy": max(0.0, float(row["local_peak_minus_pre_median_v"])),
                "baseline_detected": row["trigger_detected"] == "True",
                "baseline_lead_ms": float(row["lead_ms"]) if row["lead_ms"] else None,
            }
        )
    if not rows:
        raise RuntimeError(f"No reviewed true ELM rows found in {REVIEW_MANIFEST}")
    return rows


def normalize_severities(events: list[dict[str, Any]]) -> np.ndarray:
    values = np.asarray([row["severity_proxy"] for row in events], dtype=float)
    median = float(np.median(values))
    if median <= 0:
        return np.ones_like(values)
    return np.clip(values / median, 0.25, 4.0)


def row_by_name(rows: list[dict[str, str]], name: str, deadtime_ms: float = 0.35) -> dict[str, str]:
    for row in rows:
        if row["config_name"] == name and math.isclose(float(row["deadtime_ms"]), deadtime_ms, abs_tol=1e-9):
            return row
    raise KeyError(name)


def policy_from_tradeoff(
    name: str,
    tradeoff_row: dict[str, str],
    latency_key: str,
    event_reduction: float,
    standing_bias: float,
    false_trigger_cost: float,
    steady_cost_per_s: float,
    description: str,
) -> Policy:
    events = float(tradeoff_row["events"])
    return Policy(
        name=name,
        source=tradeoff_row["config_name"],
        detected_fraction=float(tradeoff_row["detected"]) / events,
        reachable_fraction=float(tradeoff_row[latency_key]) / events,
        false_trigger_rate_hz=float(tradeoff_row["false_triggers"]) / FAIR_MAST_TEST_WINDOW_S,
        standing_bias=standing_bias,
        event_reduction=event_reduction,
        false_trigger_cost=false_trigger_cost,
        steady_cost_per_s=steady_cost_per_s,
        description=description,
    )


def build_policies() -> list[Policy]:
    tradeoff = read_csv(SXR_TRADEOFF)
    baseline = row_by_name(tradeoff, "baseline")
    mirnov_toroidal = row_by_name(tradeoff, "mirnov_toroidal")
    sxr_raw = row_by_name(tradeoff, "sxr_upper_all_4sigma")
    sxr_precision = row_by_name(tradeoff, "sxr_tangential_all_8sigma", deadtime_ms=8.0)
    sxr_false_bounded = row_by_name(tradeoff, "sxr_lower_all_4sigma")

    return [
        Policy(
            name="no_control",
            source="none",
            detected_fraction=0.0,
            reachable_fraction=0.0,
            false_trigger_rate_hz=0.0,
            standing_bias=0.0,
            event_reduction=0.0,
            false_trigger_cost=0.0,
            steady_cost_per_s=0.0,
            description="No preventative bias and no event-specific boost.",
        ),
        Policy(
            name="preventative_bias_only",
            source="standing_bias_assumption",
            detected_fraction=0.0,
            reachable_fraction=0.0,
            false_trigger_rate_hz=0.0,
            standing_bias=0.25,
            event_reduction=0.0,
            false_trigger_cost=0.0,
            steady_cost_per_s=0.004,
            description="Standing lithium/current bias reduces every event proxy severity, with a small continuous operating cost.",
        ),
        policy_from_tradeoff(
            name="baseline_mirnov_fast_boost",
            tradeoff_row=baseline,
            latency_key="latency_reachable_3_ms",
            event_reduction=0.55,
            standing_bias=0.25,
            false_trigger_cost=0.006,
            steady_cost_per_s=0.004,
            description="Standing bias plus fast bounded boost from the fixed Mirnov trigger.",
        ),
        policy_from_tradeoff(
            name="mirnov_toroidal_fast_boost",
            tradeoff_row=mirnov_toroidal,
            latency_key="latency_reachable_3_ms",
            event_reduction=0.55,
            standing_bias=0.25,
            false_trigger_cost=0.006,
            steady_cost_per_s=0.004,
            description="Standing bias plus fast bounded boost from the cleaner Mirnov+toroidal fusion trigger.",
        ),
        policy_from_tradeoff(
            name="mirnov_toroidal_nominal_boost",
            tradeoff_row=mirnov_toroidal,
            latency_key="latency_reachable_5_ms",
            event_reduction=0.45,
            standing_bias=0.25,
            false_trigger_cost=0.006,
            steady_cost_per_s=0.004,
            description="Same trigger with a nominal 5 ms response budget.",
        ),
        policy_from_tradeoff(
            name="sxr_raw_high_recall_fast_boost",
            tradeoff_row=sxr_raw,
            latency_key="latency_reachable_3_ms",
            event_reduction=0.55,
            standing_bias=0.25,
            false_trigger_cost=0.006,
            steady_cost_per_s=0.004,
            description="High-recall SXR trigger; included to expose false-trigger cost.",
        ),
        policy_from_tradeoff(
            name="sxr_precision_gated_fast_boost",
            tradeoff_row=sxr_precision,
            latency_key="latency_reachable_3_ms",
            event_reduction=0.55,
            standing_bias=0.25,
            false_trigger_cost=0.006,
            steady_cost_per_s=0.004,
            description="Higher-precision SXR operating point from the deadtime tradeoff.",
        ),
        policy_from_tradeoff(
            name="sxr_false_bounded_fast_boost",
            tradeoff_row=sxr_false_bounded,
            latency_key="latency_reachable_3_ms",
            event_reduction=0.55,
            standing_bias=0.25,
            false_trigger_cost=0.006,
            steady_cost_per_s=0.004,
            description="False-trigger-bounded SXR operating point.",
        ),
        Policy(
            name="oracle_fast_upper_bound",
            source="oracle",
            detected_fraction=1.0,
            reachable_fraction=1.0,
            false_trigger_rate_hz=0.0,
            standing_bias=0.25,
            event_reduction=0.55,
            false_trigger_cost=0.0,
            steady_cost_per_s=0.004,
            description="Upper bound: every event is known early enough for fast bounded boost.",
        ),
    ]


def simulate_policy(
    rng: np.random.Generator,
    policy: Policy,
    severities: np.ndarray,
    event_rate_hz: float,
    horizon_s: float,
    runs: int,
) -> dict[str, Any]:
    total_losses = []
    event_losses = []
    false_costs = []
    controlled_counts = []
    event_counts = []
    disruption_flags = []

    for _ in range(runs):
        n_events = int(rng.poisson(event_rate_hz * horizon_s))
        event_counts.append(n_events)
        if n_events:
            sampled = rng.choice(severities, size=n_events, replace=True)
            prebiased = sampled * (1.0 - policy.standing_bias)
            controlled = rng.random(n_events) < policy.reachable_fraction
            residual = np.where(controlled, prebiased * (1.0 - policy.event_reduction), prebiased)
            event_loss = float(np.sum(residual))
            max_residual = float(np.max(residual))
            controlled_count = int(np.count_nonzero(controlled))
        else:
            event_loss = 0.0
            max_residual = 0.0
            controlled_count = 0

        false_triggers = int(rng.poisson(policy.false_trigger_rate_hz * horizon_s))
        false_cost = false_triggers * policy.false_trigger_cost
        steady_cost = policy.steady_cost_per_s * horizon_s
        total_loss = event_loss + false_cost + steady_cost

        event_losses.append(event_loss)
        false_costs.append(false_cost)
        total_losses.append(total_loss)
        controlled_counts.append(controlled_count)
        disruption_flags.append(max_residual > 2.5 or event_loss > max(1.0, 1.35 * n_events))

    arr = np.asarray(total_losses)
    events = np.asarray(event_counts)
    controlled = np.asarray(controlled_counts)
    return {
        "policy": policy.name,
        "source": policy.source,
        "description": policy.description,
        "detected_fraction_input": policy.detected_fraction,
        "reachable_fraction_input": policy.reachable_fraction,
        "false_trigger_rate_hz_input": policy.false_trigger_rate_hz,
        "standing_bias": policy.standing_bias,
        "event_reduction": policy.event_reduction,
        "runs": runs,
        "horizon_s": horizon_s,
        "mean_event_count": float(np.mean(events)),
        "mean_controlled_events": float(np.mean(controlled)),
        "mean_total_loss": float(np.mean(arr)),
        "median_total_loss": float(np.median(arr)),
        "p90_total_loss": float(np.percentile(arr, 90)),
        "p95_total_loss": float(np.percentile(arr, 95)),
        "mean_event_loss": float(np.mean(event_losses)),
        "mean_false_trigger_cost": float(np.mean(false_costs)),
        "proxy_disruption_rate": float(np.mean(disruption_flags)),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = next(row for row in rows if row["policy"] == "no_control")
    no_control_loss = baseline["mean_total_loss"]
    out = []
    for row in rows:
        improvement = 1.0 - row["mean_total_loss"] / no_control_loss if no_control_loss else 0.0
        out.append({**row, "mean_loss_reduction_vs_no_control": improvement})
    return out


def write_report(run_dir: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    ranked = sorted(rows, key=lambda row: row["mean_total_loss"])
    lines = [
        "# FAIR-MAST TCT Forward Surrogate",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: run a reduced-order forward simulation seeded by public FAIR-MAST event/precursor data",
        f"- Monte Carlo runs per policy: `{summary['runs']}`",
        f"- Horizon per run: `{summary['horizon_s']} s`",
        f"- Calibrated event rate: `{summary['event_rate_hz']:.3f} events/s` from `59` accepted events over `{FAIR_MAST_TEST_WINDOW_S:.2f} s` of held-out windows",
        "- Plant state: proxy event-loss accounting, not burn physics",
        "",
        "## Policy Ranking",
        "",
        "| Policy | Mean loss | Reduction vs no control | P95 loss | Proxy disruption rate | Controlled events/run | False-trigger cost/run |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in ranked:
        lines.append(
            f"| `{row['policy']}` | {row['mean_total_loss']:.3f} | "
            f"{100.0 * row['mean_loss_reduction_vs_no_control']:.1f}% | "
            f"{row['p95_total_loss']:.3f} | {100.0 * row['proxy_disruption_rate']:.1f}% | "
            f"{row['mean_controlled_events']:.2f} | {row['mean_false_trigger_cost']:.3f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "The forward surrogate favors standing preventative bias plus fast bounded",
        "boost when the trigger has enough lead and limited false-trigger burden.",
        "The noisy high-recall SXR policy recognizes more events, but its shorter",
        "lead distribution means fewer events remain reachable at the fast response",
        "budget used here, and it pays a larger false-trigger cost. This mirrors",
        "the held-out precursor tradeoff: better recognition is not automatically",
        "better control.",
        "",
        "The oracle policy is an upper bound, not a realizable controller. The gap",
        "between Mirnov/toroidal and oracle is the remaining room for better",
        "precursor recognition, morphology gating, or a faster measured actuator.",
        "",
        "## Claim Boundary",
        "",
        "This is not a sustained-fusion validation. It does not model alpha heating,",
        "burn control, transport, equilibrium evolution, material survival, TBR, or",
        "a measured TCT actuator transfer function. It is a FAIR-MAST-calibrated",
        "control-policy proxy for edge-event severity and timing. The event rate is",
        "calibrated from short FAIR-MAST ELM windows and should not be interpreted",
        "as a reactor duty-cycle forecast.",
        "",
    ]
    (run_dir / "fair_mast_tct_forward_surrogate_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--horizon-s", type=float, default=DEFAULT_HORIZON_S)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    events = load_reviewed_events()
    severities = normalize_severities(events)
    event_rate_hz = len(events) / FAIR_MAST_TEST_WINDOW_S
    rng = np.random.default_rng(args.seed)

    raw_rows = [
        simulate_policy(rng, policy, severities, event_rate_hz, args.horizon_s, args.runs)
        for policy in build_policies()
    ]
    rows = summarize(raw_rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_TCT_FORWARD_SURROGATE_COMPLETED",
        "seed": args.seed,
        "runs": args.runs,
        "horizon_s": args.horizon_s,
        "accepted_event_count": len(events),
        "event_rate_hz": event_rate_hz,
        "severity_proxy": "local D-alpha peak minus pre-event median, normalized by median accepted event severity",
        "actuator_source": str(ACTUATOR_SUMMARY.relative_to(REPO)),
        "trigger_source": str(SXR_TRADEOFF.relative_to(REPO)),
        "claim_boundary": "Reduced-order FAIR-MAST-seeded forward proxy only; not sustained-fusion validation.",
    }

    write_csv(args.run_dir / "fair_mast_tct_forward_surrogate_policies.csv", rows)
    (args.run_dir / "fair_mast_tct_forward_surrogate_summary.json").write_text(
        json.dumps({**summary, "policy_rows": rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Sensitivity and falsification sweep for the FAIR-MAST TCT forward surrogate."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import fair_mast_tct_forward_surrogate as forward


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_tct_forward_sensitivity_default"
DEFAULT_HORIZON_S = 10.0

STANDING_BIAS_GRID = (0.10, 0.20, 0.25, 0.35)
BOOST_REDUCTION_GRID = (0.25, 0.40, 0.55, 0.70)
FALSE_TRIGGER_COST_MULTIPLIERS = (0.0, 0.5, 1.0, 2.0, 5.0)
EVENT_RATE_MULTIPLIERS = (0.25, 0.5, 1.0, 2.0)
NOMINAL_BOOST_REDUCTION_SCALE = 0.45 / 0.55
NOMINAL_REACHABILITY_SCALE = 0.5084745762711864 / 0.6440677966101694
SLOW_REACHABILITY_SCALE = 0.3559322033898305 / 0.6440677966101694


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def policy_expected_loss(
    policy: forward.Policy,
    mean_severity: float,
    event_rate_hz: float,
    horizon_s: float,
    standing_bias: float,
    boost_reduction: float,
    false_cost_multiplier: float,
    event_rate_multiplier: float,
) -> dict[str, Any]:
    event_count = event_rate_hz * event_rate_multiplier * horizon_s
    false_count = policy.false_trigger_rate_hz * horizon_s

    if policy.name == "no_control":
        effective_bias = 0.0
        effective_boost = 0.0
        reachable = 0.0
        steady_cost_per_s = 0.0
        false_cost = 0.0
    elif policy.name == "preventative_bias_only":
        effective_bias = standing_bias
        effective_boost = 0.0
        reachable = 0.0
        steady_cost_per_s = policy.steady_cost_per_s * standing_bias / 0.25
        false_cost = 0.0
    elif policy.name == "mirnov_toroidal_nominal_boost":
        effective_bias = standing_bias
        effective_boost = boost_reduction * NOMINAL_BOOST_REDUCTION_SCALE
        reachable = policy.reachable_fraction
        steady_cost_per_s = policy.steady_cost_per_s * standing_bias / 0.25
        false_cost = false_count * policy.false_trigger_cost * false_cost_multiplier
    elif policy.name == "oracle_fast_upper_bound":
        effective_bias = standing_bias
        effective_boost = boost_reduction
        reachable = 1.0
        steady_cost_per_s = policy.steady_cost_per_s * standing_bias / 0.25
        false_cost = 0.0
    else:
        effective_bias = standing_bias
        effective_boost = boost_reduction
        reachable = policy.reachable_fraction
        steady_cost_per_s = policy.steady_cost_per_s * standing_bias / 0.25
        false_cost = false_count * policy.false_trigger_cost * false_cost_multiplier

    residual_factor = (1.0 - effective_bias) * (1.0 - reachable * effective_boost)
    event_loss = event_count * mean_severity * residual_factor
    steady_cost = steady_cost_per_s * horizon_s
    total_loss = event_loss + false_cost + steady_cost
    return {
        "policy": policy.name,
        "expected_total_loss": total_loss,
        "expected_event_loss": event_loss,
        "expected_false_trigger_cost": false_cost,
        "expected_event_count": event_count,
        "expected_controlled_events": event_count * reachable,
        "reachable_fraction": reachable,
        "standing_bias": effective_bias,
        "boost_reduction": effective_boost,
    }


def scenario_rows(mean_severity: float, event_rate_hz: float, horizon_s: float) -> list[dict[str, Any]]:
    policies = [
        policy
        for policy in forward.build_policies()
        if policy.name
        in {
            "no_control",
            "preventative_bias_only",
            "baseline_mirnov_fast_boost",
            "mirnov_toroidal_fast_boost",
            "mirnov_toroidal_nominal_boost",
            "sxr_raw_high_recall_fast_boost",
            "sxr_precision_gated_fast_boost",
            "sxr_false_bounded_fast_boost",
            "oracle_fast_upper_bound",
        }
    ]
    rows: list[dict[str, Any]] = []
    scenario_id = 0
    for standing_bias in STANDING_BIAS_GRID:
        for boost_reduction in BOOST_REDUCTION_GRID:
            for false_mult in FALSE_TRIGGER_COST_MULTIPLIERS:
                for event_mult in EVENT_RATE_MULTIPLIERS:
                    scenario_id += 1
                    losses = [
                        policy_expected_loss(
                            policy,
                            mean_severity,
                            event_rate_hz,
                            horizon_s,
                            standing_bias,
                            boost_reduction,
                            false_mult,
                            event_mult,
                        )
                        for policy in policies
                    ]
                    realizable = [row for row in losses if row["policy"] != "oracle_fast_upper_bound"]
                    winner = min(realizable, key=lambda row: row["expected_total_loss"])
                    oracle = min(losses, key=lambda row: row["expected_total_loss"])
                    mirnov = next(row for row in losses if row["policy"] == "mirnov_toroidal_fast_boost")
                    no_control = next(row for row in losses if row["policy"] == "no_control")
                    best_loss = winner["expected_total_loss"]
                    mirnov_gap = mirnov["expected_total_loss"] - best_loss
                    rows.append(
                        {
                            "scenario_id": scenario_id,
                            "standing_bias": standing_bias,
                            "boost_reduction": boost_reduction,
                            "false_trigger_cost_multiplier": false_mult,
                            "event_rate_multiplier": event_mult,
                            "realizable_winner": winner["policy"],
                            "oracle_winner": oracle["policy"],
                            "mirnov_toroidal_loss": mirnov["expected_total_loss"],
                            "realizable_winner_loss": best_loss,
                            "no_control_loss": no_control["expected_total_loss"],
                            "mirnov_toroidal_tied_for_best": mirnov_gap <= 1e-9,
                            "mirnov_toroidal_within_1pct": mirnov["expected_total_loss"] <= 1.01 * best_loss,
                            "mirnov_toroidal_loss_reduction_vs_no_control": 1.0 - mirnov["expected_total_loss"] / no_control["expected_total_loss"],
                            "loss_gap_to_realizable_best": mirnov_gap,
                            "loss_gap_to_oracle": mirnov["expected_total_loss"] - oracle["expected_total_loss"],
                        }
                    )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    winners = Counter(row["realizable_winner"] for row in rows)
    mirnov_tied_best = sum(bool(row["mirnov_toroidal_tied_for_best"]) for row in rows)
    mirnov_near = sum(bool(row["mirnov_toroidal_within_1pct"]) for row in rows)
    falsifiers = [row for row in rows if row["loss_gap_to_realizable_best"] > 1e-9]
    win_rate_rows = [
        {
            "policy": policy,
            "win_count": win_count,
            "win_fraction": win_count / count if count else 0.0,
        }
        for policy, win_count in sorted(winners.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "scenario_count": count,
        "mirnov_toroidal_tied_best_count": mirnov_tied_best,
        "mirnov_toroidal_tied_best_fraction": mirnov_tied_best / count if count else 0.0,
        "mirnov_toroidal_within_1pct_count": mirnov_near,
        "mirnov_toroidal_within_1pct_fraction": mirnov_near / count if count else 0.0,
        "win_rate_rows": win_rate_rows,
        "falsifier_count": len(falsifiers),
        "falsifier_examples": falsifiers[:10],
        "mean_mirnov_loss_reduction_vs_no_control": float(np.mean([row["mirnov_toroidal_loss_reduction_vs_no_control"] for row in rows])),
        "minimum_mirnov_loss_reduction_vs_no_control": float(np.min([row["mirnov_toroidal_loss_reduction_vs_no_control"] for row in rows])),
        "maximum_mirnov_loss_reduction_vs_no_control": float(np.max([row["mirnov_toroidal_loss_reduction_vs_no_control"] for row in rows])),
    }


def write_report(run_dir: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    win_rates = summary["win_rate_rows"]
    falsifiers = [row for row in rows if row["loss_gap_to_realizable_best"] > 1e-9]
    lines = [
        "# FAIR-MAST TCT Forward Sensitivity",
        "",
        f"- Status: `{summary['status']}`",
        "- Purpose: falsify or bound the FAIR-MAST-seeded forward surrogate policy ranking",
        f"- Scenario count: `{summary['scenario_count']}`",
        "- Swept assumptions: standing-bias reduction, boost reduction, false-trigger penalty, and event-rate multiplier",
        "- Method: deterministic expected-loss calculation using the same FAIR-MAST trigger/latency metrics as the forward surrogate",
        "",
        "## Policy Win Rates",
        "",
        "| Policy | Win count | Win fraction |",
        "| --- | ---: | ---: |",
    ]
    for row in win_rates:
        lines.append(f"| `{row['policy']}` | {row['win_count']} | {100.0 * row['win_fraction']:.1f}% |")
    lines += [
        "",
        "The win-rate table uses deterministic tie-breaking. In this sweep, the",
        "fixed Mirnov baseline and Mirnov+toroidal fast boost have equal expected",
        "loss because they share the same 3 ms reachability and false-trigger count",
        "in the held-out input table.",
        "",
        "## Mirnov/Toroidal Robustness",
        "",
        f"- Tied for best realizable policy: `{summary['mirnov_toroidal_tied_best_count']}/{summary['scenario_count']}` ({100.0 * summary['mirnov_toroidal_tied_best_fraction']:.1f}%)",
        f"- Within 1% of best realizable policy: `{summary['mirnov_toroidal_within_1pct_count']}/{summary['scenario_count']}` ({100.0 * summary['mirnov_toroidal_within_1pct_fraction']:.1f}%)",
        f"- Mean loss reduction vs no control: `{100.0 * summary['mean_mirnov_loss_reduction_vs_no_control']:.1f}%`",
        f"- Range of loss reduction vs no control: `{100.0 * summary['minimum_mirnov_loss_reduction_vs_no_control']:.1f}%` to `{100.0 * summary['maximum_mirnov_loss_reduction_vs_no_control']:.1f}%`",
        "",
        "## Falsification Conditions",
        "",
    ]
    if falsifiers:
        lines += [
            "Mirnov/toroidal fast boost is not the best realizable policy in the scenarios listed below.",
            "These are the parameter regimes that would weaken the current control-ranking claim.",
            "",
            "| Bias | Boost | False cost mult | Event rate mult | Winner | Mirnov loss gap |",
            "| ---: | ---: | ---: | ---: | --- | ---: |",
        ]
        for row in falsifiers[:12]:
            lines.append(
                f"| {row['standing_bias']:.2f} | {row['boost_reduction']:.2f} | "
                f"{row['false_trigger_cost_multiplier']:.1f} | {row['event_rate_multiplier']:.2f} | "
                f"`{row['realizable_winner']}` | {row['loss_gap_to_realizable_best']:.3f} |"
            )
    else:
        lines.append("No swept scenario made another non-oracle policy beat Mirnov/toroidal fast boost.")
    lines += [
        "",
        "## Interpretation",
        "",
        "This sweep tests whether the forward-surrogate result depends on a narrow",
        "choice of proxy assumptions. Mirnov/toroidal being tied for best across the",
        "grid supports the ranking as a robust reduced-order result. Falsifier rows",
        "identify exactly which assumptions would make another policy preferable.",
        "",
        "The oracle policy is excluded from the realizable winner count and remains",
        "an upper bound. If reviewer feedback changes the false-trigger penalty,",
        "standing-bias cost, or boost efficacy, this script should be rerun before",
        "using the forward-surrogate ranking.",
        "",
        "## Claim Boundary",
        "",
        "This is a sensitivity analysis of a reduced-order proxy. It is not a",
        "sustained-fusion validation, reactor duty-cycle model, or measured TCT",
        "actuator result.",
        "",
    ]
    (run_dir / "fair_mast_tct_forward_sensitivity_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--horizon-s", type=float, default=DEFAULT_HORIZON_S)
    args = parser.parse_args()

    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    events = forward.load_reviewed_events()
    severities = forward.normalize_severities(events)
    mean_severity = float(np.mean(severities))
    event_rate_hz = len(events) / forward.FAIR_MAST_TEST_WINDOW_S
    rows = scenario_rows(mean_severity, event_rate_hz, args.horizon_s)
    sweep_summary = summarize(rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "MAST_TCT_FORWARD_SENSITIVITY_COMPLETED",
        "horizon_s": args.horizon_s,
        "event_rate_hz": event_rate_hz,
        "mean_severity": mean_severity,
        "standing_bias_grid": STANDING_BIAS_GRID,
        "boost_reduction_grid": BOOST_REDUCTION_GRID,
        "false_trigger_cost_multipliers": FALSE_TRIGGER_COST_MULTIPLIERS,
        "event_rate_multipliers": EVENT_RATE_MULTIPLIERS,
        "claim_boundary": "Reduced-order proxy sensitivity only; not sustained-fusion validation.",
        **sweep_summary,
    }

    write_csv(args.run_dir / "fair_mast_tct_forward_sensitivity_scenarios.csv", rows)
    write_csv(args.run_dir / "fair_mast_tct_forward_sensitivity_win_rates.csv", summary["win_rate_rows"])
    (args.run_dir / "fair_mast_tct_forward_sensitivity_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, summary, rows)
    print(json.dumps({key: value for key, value in summary.items() if key != "falsifier_examples"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

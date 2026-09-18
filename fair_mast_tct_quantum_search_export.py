#!/usr/bin/env python3
"""Export the FAIR-MAST TCT sensitivity surface as a frozen search dataset.

This is a bridge for compiler/search experiments.  It does not replace the
forward surrogate and does not make a quantum-advantage claim.  The exported
objective is computed by the existing deterministic reduced-order sensitivity
model, then a small set of lowest-loss parameter settings is marked for an
unstructured-search/Grover compiler benchmark.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import fair_mast_tct_forward_surrogate as forward
import fair_mast_tct_forward_sensitivity as sensitivity


REPO = Path(__file__).resolve().parent
DEFAULT_OUT = (
    REPO
    / "validation_runs"
    / "fair_mast_tct_quantum_search_export_default"
    / "fair_mast_tct_quantum_search_dataset.json"
)


def grover_metadata(valid_count: int, marked_count: int) -> dict:
    index_qubits = max(1, math.ceil(math.log2(valid_count)))
    padded_count = 1 << index_qubits
    if not (0 < marked_count <= valid_count):
        raise ValueError("marked_count must be in 1..valid_count")
    theta = math.asin(math.sqrt(marked_count / padded_count))
    iterations = max(0, int(round(math.pi / (4.0 * theta) - 0.5)))
    success = math.sin((2 * iterations + 1) * theta) ** 2
    valid_random_expected = (valid_count + 1.0) / (marked_count + 1.0)
    padded_random_expected = (padded_count + 1.0) / (marked_count + 1.0)
    return {
        "index_qubits": index_qubits,
        "padded_search_space": padded_count,
        "optimal_grover_iterations_idealized": iterations,
        "idealized_grover_success_probability": success,
        "classical_random_without_replacement_expected_queries_valid_domain": valid_random_expected,
        "classical_random_without_replacement_expected_queries_padded_domain": padded_random_expected,
        "idealized_valid_random_over_grover_query_ratio": (
            None if iterations == 0 else valid_random_expected / iterations
        ),
        "exhaustive_valid_candidates_over_grover_query_ratio": (
            None if iterations == 0 else valid_count / iterations
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--horizon-s", type=float, default=sensitivity.DEFAULT_HORIZON_S)
    ap.add_argument("--mark-top-k", type=int, default=8)
    ap.add_argument(
        "--objective",
        choices=("mirnov_toroidal_loss", "realizable_winner_loss"),
        default="mirnov_toroidal_loss",
        help="Reduced-order scalar objective to minimize.",
    )
    args = ap.parse_args()
    if args.mark_top_k < 1:
        raise SystemExit("--mark-top-k must be >= 1")

    events = forward.load_reviewed_events()
    severities = forward.normalize_severities(events)
    mean_severity = float(np.mean(severities))
    event_rate_hz = len(events) / forward.FAIR_MAST_TEST_WINDOW_S
    source_rows = sensitivity.scenario_rows(mean_severity, event_rate_hz, args.horizon_s)
    if not source_rows:
        raise RuntimeError("sensitivity model returned no scenarios")

    objective_key = args.objective
    ranked = sorted(
        enumerate(source_rows),
        key=lambda item: (float(item[1][objective_key]), int(item[1]["scenario_id"])),
    )
    kth = min(args.mark_top_k, len(ranked))
    threshold = float(ranked[kth - 1][1][objective_key])

    candidates = []
    marked_indices = []
    for index, row in enumerate(source_rows):
        value = float(row[objective_key])
        # Include ties at the requested top-k boundary so the marking rule is
        # deterministic and independent of row ordering.
        marked = value <= threshold + 1e-12
        if marked:
            marked_indices.append(index)
        candidates.append(
            {
                "index": index,
                "scenario_id": int(row["scenario_id"]),
                "standing_bias": float(row["standing_bias"]),
                "boost_reduction": float(row["boost_reduction"]),
                "false_trigger_cost_multiplier": float(row["false_trigger_cost_multiplier"]),
                "event_rate_multiplier": float(row["event_rate_multiplier"]),
                "realizable_winner": row["realizable_winner"],
                "mirnov_toroidal_loss": float(row["mirnov_toroidal_loss"]),
                "realizable_winner_loss": float(row["realizable_winner_loss"]),
                "no_control_loss": float(row["no_control_loss"]),
                "mirnov_toroidal_loss_reduction_vs_no_control": float(
                    row["mirnov_toroidal_loss_reduction_vs_no_control"]
                ),
                "objective_loss": value,
                "marked": marked,
            }
        )

    meta = grover_metadata(len(candidates), len(marked_indices))
    result = {
        "experiment": "fair_mast_tct_quantum_search_export_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_model": "fair_mast_tct_forward_sensitivity.py",
        "source_forward_model": "fair_mast_tct_forward_surrogate.py",
        "objective": objective_key,
        "objective_direction": "minimize",
        "requested_mark_top_k": args.mark_top_k,
        "mark_threshold_inclusive": threshold,
        "valid_candidate_count": len(candidates),
        "marked_count": len(marked_indices),
        "marked_indices": marked_indices,
        "horizon_s": args.horizon_s,
        "accepted_event_count": len(events),
        "event_rate_hz": event_rate_hz,
        "mean_normalized_event_severity": mean_severity,
        "parameter_grids": {
            "standing_bias": list(sensitivity.STANDING_BIAS_GRID),
            "boost_reduction": list(sensitivity.BOOST_REDUCTION_GRID),
            "false_trigger_cost_multiplier": list(sensitivity.FALSE_TRIGGER_COST_MULTIPLIERS),
            "event_rate_multiplier": list(sensitivity.EVENT_RATE_MULTIPLIERS),
        },
        "search_metadata": meta,
        "candidates": candidates,
        "claim_boundary": (
            "Reduced-order FAIR-MAST-seeded screening surface only. The exported "
            "marking table is classically precomputed; Grover query counts are an "
            "idealized unstructured-search comparison, not an end-to-end quantum "
            "speedup and not a fusion-physics validation."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    best = min(candidates, key=lambda row: (row["objective_loss"], row["scenario_id"]))
    print("===== TCT QUANTUM SEARCH DATASET =====")
    print(
        f"objective={objective_key} valid={len(candidates)} marked={len(marked_indices)} "
        f"index_qubits={meta['index_qubits']} padded={meta['padded_search_space']}"
    )
    print(
        f"idealized_grover_iterations={meta['optimal_grover_iterations_idealized']} "
        f"idealized_success={meta['idealized_grover_success_probability']:.6f}"
    )
    print(
        "best="
        + json.dumps(
            {k: best[k] for k in (
                "index", "scenario_id", "standing_bias", "boost_reduction",
                "false_trigger_cost_multiplier", "event_rate_multiplier",
                "realizable_winner", "objective_loss"
            )},
            sort_keys=True,
        )
    )
    print(f"wrote {args.out}")
    print("NO QPU JOB SUBMITTED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

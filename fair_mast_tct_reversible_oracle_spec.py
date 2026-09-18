#!/usr/bin/env python3
"""Export a fixed-point arithmetic specification for the TCT search oracle.

This bridges the deterministic FAIR-MAST-seeded sensitivity model to a future
reversible quantum arithmetic circuit.  It does not build or run a quantum
circuit.  Instead it:

1. reloads the frozen quantum-search dataset;
2. reconstructs the Mirnov/toroidal expected-loss formula from the same source
   model used to generate that dataset;
3. searches for the smallest decimal fixed-point scale whose integer threshold
   reproduces the marked-state classification exactly; and
4. exports register widths, grid codebooks, formula constants, threshold, and
   verification metadata.

The exported specification is intended to be consumed by RecycledQubitRegisters
for reversible-oracle synthesis.  No QPU job is submitted.
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
DEFAULT_DATASET = (
    REPO
    / "validation_runs"
    / "fair_mast_tct_quantum_search_export_default"
    / "fair_mast_tct_quantum_search_dataset.json"
)
DEFAULT_OUT = (
    REPO
    / "validation_runs"
    / "fair_mast_tct_reversible_oracle_spec_default"
    / "fair_mast_tct_reversible_oracle_spec.json"
)


def ceil_log2(n: int) -> int:
    return max(1, math.ceil(math.log2(max(1, n))))


def mirnov_formula_constants(horizon_s: float) -> dict[str, float]:
    events = forward.load_reviewed_events()
    severities = forward.normalize_severities(events)
    mean_severity = float(np.mean(severities))
    event_rate_hz = len(events) / forward.FAIR_MAST_TEST_WINDOW_S
    policy = next(
        p for p in forward.build_policies()
        if p.name == "mirnov_toroidal_fast_boost"
    )

    # L = A * event_mult * (1-bias) * (1-r*boost)
    #     + B*bias + C*false_mult
    A = event_rate_hz * horizon_s * mean_severity
    r = float(policy.reachable_fraction)
    B = float(policy.steady_cost_per_s) * horizon_s / 0.25
    C = (
        float(policy.false_trigger_rate_hz)
        * horizon_s
        * float(policy.false_trigger_cost)
    )
    return {
        "event_rate_hz": event_rate_hz,
        "mean_severity": mean_severity,
        "horizon_s": horizon_s,
        "A_event_base": A,
        "reachable_fraction": r,
        "B_bias_cost_per_unit_bias": B,
        "C_false_cost_per_unit_multiplier": C,
        "policy_false_trigger_rate_hz": float(policy.false_trigger_rate_hz),
        "policy_false_trigger_cost": float(policy.false_trigger_cost),
        "policy_steady_cost_per_s": float(policy.steady_cost_per_s),
    }


def formula_loss(row: dict, constants: dict[str, float]) -> float:
    bias = float(row["standing_bias"])
    boost = float(row["boost_reduction"])
    false_mult = float(row["false_trigger_cost_multiplier"])
    event_mult = float(row["event_rate_multiplier"])
    return (
        constants["A_event_base"]
        * event_mult
        * (1.0 - bias)
        * (1.0 - constants["reachable_fraction"] * boost)
        + constants["B_bias_cost_per_unit_bias"] * bias
        + constants["C_false_cost_per_unit_multiplier"] * false_mult
    )


def find_integer_encoding(candidates: list[dict], marked: set[int], losses: list[float]) -> dict:
    # Decimal scales are intentionally simple and auditable.  We accept the
    # first scale for which an inclusive integer threshold reproduces the frozen
    # marked set exactly.
    for digits in range(0, 10):
        scale = 10 ** digits
        scores = [int(round(x * scale)) for x in losses]
        marked_scores = [scores[i] for i in sorted(marked)]
        threshold = max(marked_scores)
        classified = {i for i, score in enumerate(scores) if score <= threshold}
        if classified == marked:
            max_score = max(scores)
            return {
                "decimal_digits": digits,
                "scale": scale,
                "threshold_int": threshold,
                "minimum_score_int": min(scores),
                "maximum_score_int": max_score,
                "accumulator_bits_unsigned": ceil_log2(max_score + 1),
                "integer_scores": scores,
                "classification_exact": True,
            }
    raise RuntimeError(
        "No decimal fixed-point scale through 1e9 reproduced the marked set exactly"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    if data.get("objective") != "mirnov_toroidal_loss":
        raise SystemExit(
            "This v1 arithmetic specification supports objective=mirnov_toroidal_loss only"
        )

    candidates = data["candidates"]
    marked = {int(i) for i in data["marked_indices"]}
    constants = mirnov_formula_constants(float(data["horizon_s"]))

    losses = [formula_loss(row, constants) for row in candidates]
    source_losses = [float(row["mirnov_toroidal_loss"]) for row in candidates]
    max_abs_error = max(abs(a - b) for a, b in zip(losses, source_losses))
    if max_abs_error > 1e-9:
        raise RuntimeError(
            f"Reconstructed formula disagrees with source dataset: max_abs_error={max_abs_error}"
        )

    encoding = find_integer_encoding(candidates, marked, losses)

    grids = {
        "standing_bias": list(sensitivity.STANDING_BIAS_GRID),
        "boost_reduction": list(sensitivity.BOOST_REDUCTION_GRID),
        "false_trigger_cost_multiplier": list(sensitivity.FALSE_TRIGGER_COST_MULTIPLIERS),
        "event_rate_multiplier": list(sensitivity.EVENT_RATE_MULTIPLIERS),
    }
    register_bits = {
        name: ceil_log2(len(values))
        for name, values in grids.items()
    }
    register_bits["total_parameter_bits"] = sum(register_bits.values())

    codebooks = {
        name: [
            {"code": i, "value": float(value)}
            for i, value in enumerate(values)
        ]
        for name, values in grids.items()
    }

    result = {
        "experiment": "fair_mast_tct_reversible_oracle_spec_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(args.dataset),
        "source_dataset_experiment": data.get("experiment"),
        "objective": data["objective"],
        "objective_direction": "minimize",
        "valid_candidate_count": len(candidates),
        "marked_count": len(marked),
        "marked_indices": sorted(marked),
        "formula": (
            "L = A*event_mult*(1-bias)*(1-reachable*boost) "
            "+ B*bias + C*false_mult"
        ),
        "formula_constants": constants,
        "parameter_grids": grids,
        "parameter_codebooks": codebooks,
        "parameter_register_bits": register_bits,
        "valid_code_constraints": {
            "standing_bias": "code < 4",
            "boost_reduction": "code < 4",
            "false_trigger_cost_multiplier": "code < 5",
            "event_rate_multiplier": "code < 4",
        },
        "fixed_point": {
            key: value
            for key, value in encoding.items()
            if key != "integer_scores"
        },
        "verification": {
            "max_abs_formula_error_vs_dataset": max_abs_error,
            "integer_threshold_reproduces_marked_set_exactly": True,
            "reconstructed_marked_indices": [
                i
                for i, score in enumerate(encoding["integer_scores"])
                if score <= encoding["threshold_int"]
            ],
        },
        "candidate_integer_scores": [
            {
                "index": int(row["index"]),
                "scenario_id": int(row["scenario_id"]),
                "score_int": int(score),
                "marked": int(row["index"]) in marked,
            }
            for row, score in zip(candidates, encoding["integer_scores"])
        ],
        "claim_boundary": (
            "Arithmetic specification for a reduced-order FAIR-MAST-seeded proxy. "
            "It is not a fusion-physics validation and is not evidence of quantum "
            "speedup. A future reversible circuit must include arithmetic, valid-code "
            "checks, threshold comparison, uncomputation, and hardware overhead."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fp = result["fixed_point"]
    print("===== TCT REVERSIBLE ORACLE SPEC =====")
    print(
        f"valid={len(candidates)} marked={len(marked)} "
        f"parameter_bits={register_bits['total_parameter_bits']} "
        f"accumulator_bits={fp['accumulator_bits_unsigned']}"
    )
    print(
        f"fixed_point_scale={fp['scale']} decimal_digits={fp['decimal_digits']} "
        f"threshold_int={fp['threshold_int']} max_score_int={fp['maximum_score_int']}"
    )
    print(f"formula_max_abs_error={max_abs_error:.3e} classification_exact=True")
    print(f"wrote {args.out}")
    print("NO QPU JOB SUBMITTED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

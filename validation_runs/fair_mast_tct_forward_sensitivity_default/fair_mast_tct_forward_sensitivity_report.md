# FAIR-MAST TCT Forward Sensitivity

- Status: `MAST_TCT_FORWARD_SENSITIVITY_COMPLETED`
- Purpose: falsify or bound the FAIR-MAST-seeded forward surrogate policy ranking
- Scenario count: `320`
- Swept assumptions: standing-bias reduction, boost reduction, false-trigger penalty, and event-rate multiplier
- Method: deterministic expected-loss calculation using the same FAIR-MAST trigger/latency metrics as the forward surrogate

## Policy Win Rates

| Policy | Win count | Win fraction |
| --- | ---: | ---: |
| `baseline_mirnov_fast_boost` | 320 | 100.0% |

The win-rate table uses deterministic tie-breaking. In this sweep, the
fixed Mirnov baseline and Mirnov+toroidal fast boost have equal expected
loss because they share the same 3 ms reachability and false-trigger count
in the held-out input table.

## Mirnov/Toroidal Robustness

- Tied for best realizable policy: `320/320` (100.0%)
- Within 1% of best realizable policy: `320/320` (100.0%)
- Mean loss reduction vs no control: `46.0%`
- Range of loss reduction vs no control: `23.0%` to `64.3%`

## Falsification Conditions

No swept scenario made another non-oracle policy beat Mirnov/toroidal fast boost.

## Interpretation

This sweep tests whether the forward-surrogate result depends on a narrow
choice of proxy assumptions. Mirnov/toroidal being tied for best across the
grid supports the ranking as a robust reduced-order result. Falsifier rows
identify exactly which assumptions would make another policy preferable.

The oracle policy is excluded from the realizable winner count and remains
an upper bound. If reviewer feedback changes the false-trigger penalty,
standing-bias cost, or boost efficacy, this script should be rerun before
using the forward-surrogate ranking.

## Claim Boundary

This is a sensitivity analysis of a reduced-order proxy. It is not a
sustained-fusion validation, reactor duty-cycle model, or measured TCT
actuator result.

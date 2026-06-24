# FAIR-MAST TCT Forward Surrogate

- Status: `MAST_TCT_FORWARD_SURROGATE_COMPLETED`
- Purpose: run a reduced-order forward simulation seeded by public FAIR-MAST event/precursor data
- Monte Carlo runs per policy: `2000`
- Horizon per run: `10.0 s`
- Calibrated event rate: `65.556 events/s` from `59` accepted events over `0.90 s` of held-out windows
- Plant state: proxy event-loss accounting, not burn physics

## Policy Ranking

| Policy | Mean loss | Reduction vs no control | P95 loss | Proxy disruption rate | Controlled events/run | False-trigger cost/run |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle_fast_upper_bound` | 250.005 | 66.2% | 267.116 | 0.0% | 655.61 | 0.000 |
| `mirnov_toroidal_fast_boost` | 358.578 | 51.5% | 385.379 | 0.0% | 421.83 | 0.532 |
| `sxr_false_bounded_fast_boost` | 359.009 | 51.4% | 385.669 | 0.0% | 421.81 | 0.534 |
| `baseline_mirnov_fast_boost` | 359.770 | 51.3% | 385.929 | 0.0% | 422.28 | 0.533 |
| `sxr_precision_gated_fast_boost` | 380.625 | 48.5% | 407.639 | 0.0% | 378.53 | 0.869 |
| `sxr_raw_high_recall_fast_boost` | 393.099 | 46.8% | 423.111 | 0.0% | 355.77 | 3.601 |
| `mirnov_toroidal_nominal_boost` | 429.023 | 42.0% | 461.286 | 0.0% | 333.37 | 0.533 |
| `preventative_bias_only` | 556.006 | 24.8% | 593.524 | 0.0% | 0.00 | 0.000 |
| `no_control` | 739.214 | 0.0% | 790.271 | 0.0% | 0.00 | 0.000 |

## Interpretation

The forward surrogate favors standing preventative bias plus fast bounded
boost when the trigger has enough lead and limited false-trigger burden.
The noisy high-recall SXR policy recognizes more events, but its shorter
lead distribution means fewer events remain reachable at the fast response
budget used here, and it pays a larger false-trigger cost. This mirrors
the held-out precursor tradeoff: better recognition is not automatically
better control.

The oracle policy is an upper bound, not a realizable controller. The gap
between Mirnov/toroidal and oracle is the remaining room for better
precursor recognition, morphology gating, or a faster measured actuator.

## Claim Boundary

This is not a sustained-fusion validation. It does not model alpha heating,
burn control, transport, equilibrium evolution, material survival, TBR, or
a measured TCT actuator transfer function. It is a FAIR-MAST-calibrated
control-policy proxy for edge-event severity and timing. The event rate is
calibrated from short FAIR-MAST ELM windows and should not be interpreted
as a reactor duty-cycle forecast.

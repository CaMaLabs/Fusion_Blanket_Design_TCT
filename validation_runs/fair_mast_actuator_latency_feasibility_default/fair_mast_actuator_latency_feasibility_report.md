# FAIR-MAST Actuator-Latency Feasibility Sweep

- Status: `MAST_ACTUATOR_LATENCY_FEASIBILITY_COMPLETED`
- Input: accepted `true_elm` rows from machine-aided FAIR-MAST label review
- Purpose: test whether measured precursor lead times are compatible with plausible actuator latency assumptions
- This is a timing feasibility gate, not a suppression physics model
- Accepted true ELMs: `59`
- Detected accepted true ELMs: `39`
- False-trigger count carried forward: `1`

## Lead Distribution

- Minimum detected lead: `2.554 ms`
- Median detected lead: `8.376 ms`
- Maximum detected lead: `14.958 ms`

## Recommended Policy By Latency

| Actuator latency | Settle margin | Reachable accepted events | Reachable detected events | Recommended policy | Claim |
| ---: | ---: | ---: | ---: | --- | --- |
| `0.5 ms` | `0.0 ms` | 39/59 (0.661) | 1.000 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `0.5 ms` | `1.0 ms` | 39/59 (0.661) | 1.000 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `0.5 ms` | `2.0 ms` | 39/59 (0.661) | 1.000 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `1.0 ms` | `0.0 ms` | 39/59 (0.661) | 1.000 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `1.0 ms` | `1.0 ms` | 39/59 (0.661) | 1.000 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `1.0 ms` | `2.0 ms` | 38/59 (0.644) | 0.974 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `2.0 ms` | `0.0 ms` | 39/59 (0.661) | 1.000 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `2.0 ms` | `1.0 ms` | 38/59 (0.644) | 0.974 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `2.0 ms` | `2.0 ms` | 34/59 (0.576) | 0.872 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `3.0 ms` | `0.0 ms` | 38/59 (0.644) | 0.974 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `3.0 ms` | `1.0 ms` | 34/59 (0.576) | 0.872 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `3.0 ms` | `2.0 ms` | 30/59 (0.508) | 0.769 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `5.0 ms` | `0.0 ms` | 30/59 (0.508) | 0.769 | `precursor_gated_boost` | plausible bounded boost with preventative bias |
| `5.0 ms` | `1.0 ms` | 28/59 (0.475) | 0.718 | `fixed_preventative_bias_plus_limited_boost` | plausible but constrained; precursor-only not supported |
| `5.0 ms` | `2.0 ms` | 26/59 (0.441) | 0.667 | `fixed_preventative_bias_plus_limited_boost` | plausible but constrained; precursor-only not supported |
| `8.0 ms` | `0.0 ms` | 23/59 (0.390) | 0.590 | `fixed_preventative_bias_plus_limited_boost` | plausible but constrained; precursor-only not supported |
| `8.0 ms` | `1.0 ms` | 16/59 (0.271) | 0.410 | `fixed_preventative_bias` | event-specific response too limited; slow preventative scheduling only |
| `8.0 ms` | `2.0 ms` | 15/59 (0.254) | 0.385 | `fixed_preventative_bias` | event-specific response too limited; slow preventative scheduling only |
| `10.0 ms` | `0.0 ms` | 15/59 (0.254) | 0.385 | `fixed_preventative_bias` | event-specific response too limited; slow preventative scheduling only |
| `10.0 ms` | `1.0 ms` | 12/59 (0.203) | 0.308 | `fixed_preventative_bias` | event-specific response too limited; slow preventative scheduling only |
| `10.0 ms` | `2.0 ms` | 9/59 (0.153) | 0.231 | `fixed_preventative_bias` | event-specific response too limited; slow preventative scheduling only |
| `12.0 ms` | `0.0 ms` | 9/59 (0.153) | 0.231 | `fixed_preventative_bias` | event-specific response too limited; slow preventative scheduling only |
| `12.0 ms` | `1.0 ms` | 5/59 (0.085) | 0.128 | `fixed_preventative_bias` | event-specific response too limited; slow preventative scheduling only |
| `12.0 ms` | `2.0 ms` | 1/59 (0.017) | 0.026 | `fixed_preventative_bias` | event-specific response too limited; slow preventative scheduling only |

## Interpretation

Fast actuator assumptions support a precursor-gated boost layered on a
preventative bias. Around 5 ms latency, the result becomes constrained:
a useful subset of events remains reachable, but precursor-only control is
not justified. At 8-12 ms latency, the measured precursor should be treated
mostly as a slow scheduling or bounded-adjustment signal, not a reliable
late event stopper.

## Claim Boundary

This run does not measure a TCT actuator, actuator transfer function, plasma
response, or suppression efficacy. It only maps validated precursor lead
times onto hypothetical end-to-end latency plus settle-margin budgets.

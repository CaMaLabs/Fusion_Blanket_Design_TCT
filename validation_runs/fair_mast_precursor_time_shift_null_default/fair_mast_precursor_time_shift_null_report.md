# FAIR-MAST Precursor Time-Shift Null Test

- Status: `MAST_PRECURSOR_TIME_SHIFT_NULL_COMPLETED`
- Scope: held-out FAIR-MAST accepted `true_elm` rows from the machine-aided review
- Null model: circularly shift observed trigger times independently within each shot window
- Preserved by null: shot windows, event times, trigger count per shot, trigger density per shot
- Broken by null: physical trigger/event temporal alignment
- Monte Carlo trials: `50000`
- Random seed: `20260623`

## Observed Alignment

- Accepted true ELM events: `59`
- Unique observed trigger times used: `46`
- Observed detected true ELMs: `39`
- Observed recall: `0.661`
- Observed median lead: `8.376 ms`

## Null Result

- Null mean detected count: `27.700`
- Null 95th percentile detected count: `33.000`
- Null max detected count: `38`
- Directional Monte Carlo p, null detected >= observed: `0.000020`
- Observed percentile in null distribution: `1.000000`

| Required latency | Observed detected true ELMs with enough lead | Null mean | Directional p |
| --- | ---: | ---: | ---: |
| `3_ms` | 38 | 19.633 | 0.000020 |
| `5_ms` | 30 | 13.744 | 0.000040 |
| `8_ms` | 23 | 6.823 | 0.000020 |
| `12_ms` | 9 | 1.771 | 0.000040 |

## Interpretation

The observed trigger/event alignment is tested against chance timing while
holding fixed the number of triggers in each shot. A low directional p-value
means the measured precursor timing is unlikely to be explained only by random
placement of the same trigger counts inside the same shot windows.

## Claim Boundary

This null test supports temporal specificity of the measured precursor trigger.
It does not prove causal actuator mitigation, replace expert event labels, or
establish that a deployed controller can respond within the measured lead time.

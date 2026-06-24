# FAIR-MAST Multi-Diagnostic Precursor Fusion

- Status: `MAST_MULTIDIAGNOSTIC_PRECURSOR_FUSION_COMPLETED`
- Goal: improve precursor recall beyond the single fixed Mirnov channel while keeping false triggers bounded
- Train split: automatic D-alpha labels on shots `30311`, `30423`
- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`
- Candidate fast diagnostics: multi-channel centre-column poloidal Mirnov, multi-channel centre-column toroidal Mirnov, D-alpha positive slope

## Selected Fusion

- Selected config: `{'pol_cc_ch2': 6.0, 'tor_cc_all': 6.0}`
- Train score: `2.080`

## Held-Out Accepted-Label Result

| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single-channel baseline | 59 | 39 | 20 | 8 | 0.830 | 0.661 | 8.376 ms |
| Multi-diagnostic fusion | 59 | 40 | 19 | 8 | 0.833 | 0.678 | 8.360 ms |

## Latency-Reachable Accepted Events

| Required latency | Single-channel baseline | Multi-diagnostic fusion |
| --- | ---: | ---: |
| `3_ms` | 38 | 38 |
| `5_ms` | 30 | 30 |
| `8_ms` | 23 | 23 |
| `12_ms` | 9 | 9 |

## Interpretation

This run tests whether adding fast diagnostics improves the actual
control-relevant metric: accepted true events with enough lead after
false-trigger constraints. The selected fusion trigger adds the centre-column
toroidal Mirnov RMS envelope to the fixed poloidal Mirnov channel and recovers
one additional accepted event without increasing false triggers. That is a
small precursor improvement, not a step change.

The latency-reachable counts are unchanged at the tested 3, 5, 8, and 12 ms
budgets. The result therefore does not solve the actuator timing caveat: it is
compatible with fast bounded boost layered on standing bias, but it does not
make late or slow response chains viable.

## Claim Boundary

This is still a public MAST diagnostic-trigger screen. It does not provide
expert-reviewed labels, a measured TCT actuator, or causal suppression.

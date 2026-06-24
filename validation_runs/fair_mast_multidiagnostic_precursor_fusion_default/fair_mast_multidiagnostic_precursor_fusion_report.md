# FAIR-MAST Multi-Diagnostic Precursor Fusion

- Status: `MAST_MULTIDIAGNOSTIC_PRECURSOR_FUSION_COMPLETED`
- Goal: improve precursor recall beyond the single fixed Mirnov channel while keeping false triggers bounded
- Train split: automatic D-alpha labels on shots `30311`, `30423`
- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`
- Candidate fast diagnostics: centre-column poloidal/toroidal Mirnov, soft-X-ray camera envelopes, D-alpha positive slope

## Selected Fusion

- Selected config: `{'pol_cc_ch2': 6.0, 'sxr_tangential_all': 4.0}`
- Train score: `2.183`

## Held-Out Accepted-Label Result

| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single-channel baseline | 59 | 39 | 20 | 8 | 0.830 | 0.661 | 8.376 ms |
| Multi-diagnostic fusion | 59 | 57 | 2 | 89 | 0.390 | 0.966 | 3.810 ms |

## Latency-Reachable Accepted Events

| Required latency | Single-channel baseline | Multi-diagnostic fusion |
| --- | ---: | ---: |
| `3_ms` | 38 | 34 |
| `5_ms` | 30 | 20 |
| `8_ms` | 23 | 11 |
| `12_ms` | 9 | 5 |

## Interpretation

This run tests whether adding fast diagnostics improves the actual
control-relevant metric: accepted true events with enough lead after
false-trigger constraints. The selected fusion trigger is compared directly
with the fixed single-channel Mirnov baseline on accepted held-out events.
A gain should be treated as useful only if it does not merely add false
triggers or collapse lead time.

The selected fusion trigger improves raw accepted-event recognition,
but the gain is paid for with more false triggers and/or shorter lead
time. This is useful as evidence that the added diagnostic contains
precursor information, but it is not yet a cleaner operational trigger.

The latency-reachable counts change relative to baseline, so the raw
recognition gain must be interpreted together with the actuator budget.
Delta by budget: `{'3_ms': -4, '5_ms': -10, '8_ms': -12, '12_ms': -4}`.
The result remains compatible with fast bounded boost layered on standing
bias, but it does not make late or slow response chains viable.

## Claim Boundary

This is still a public MAST diagnostic-trigger screen. It does not provide
expert-reviewed labels, a measured TCT actuator, or causal suppression.

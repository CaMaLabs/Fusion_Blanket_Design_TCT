# FAIR-MAST Strict Null Suite

- Status: `MAST_PRECURSOR_STRICT_NULL_SUITE_COMPLETED`
- Scope: accepted `true_elm` rows from the FAIR-MAST machine-aided label review
- Monte Carlo trials per null: `50000`
- Random seed: `20260624`

## Null Models

- `trigger_train_block_shift`: shift the whole trigger train by one random circular offset inside each shot window. This preserves trigger burstiness and inter-trigger spacing.
- `local_event_jitter`: keep trigger times fixed and resample each accepted event inside its midpoint-bounded local interval. This preserves event count, order, and local density support.
- Leave-one-shot-out repeats both nulls after removing each held-out shot.

## Full Held-Out Set

| Null | Observed detected | Null mean | Null p95 | Null max | Directional p |
| --- | ---: | ---: | ---: | ---: | ---: |
| `trigger_train_block_shift` | 39 | 27.725 | 33.000 | 39 | 0.000060 |
| `local_event_jitter` | 39 | 32.137 | 35.000 | 40 | 0.000300 |

## Leave-One-Shot-Out Sensitivity

| Excluded shot | Null | Observed detected | Null mean | Null p95 | Null max | Directional p |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `30276` | `trigger_train_block_shift` | 39 | 26.982 | 32.000 | 38 | 0.000020 |
| `30276` | `local_event_jitter` | 39 | 31.549 | 35.000 | 38 | 0.000020 |
| `30277` | `trigger_train_block_shift` | 32 | 22.175 | 27.000 | 33 | 0.000300 |
| `30277` | `local_event_jitter` | 32 | 26.769 | 30.000 | 34 | 0.001920 |
| `30418` | `trigger_train_block_shift` | 29 | 21.164 | 25.000 | 30 | 0.000580 |
| `30418` | `local_event_jitter` | 29 | 24.661 | 27.000 | 30 | 0.006420 |
| `30419` | `trigger_train_block_shift` | 31 | 22.624 | 27.000 | 32 | 0.001660 |
| `30419` | `local_event_jitter` | 31 | 26.048 | 29.000 | 32 | 0.001840 |
| `30421` | `trigger_train_block_shift` | 25 | 17.909 | 22.000 | 27 | 0.001640 |
| `30421` | `local_event_jitter` | 25 | 19.531 | 22.000 | 26 | 0.000900 |

## Interpretation

The trigger-train block shift is the stricter version of the original time-shift null because it preserves the observed trigger burst structure within each shot. The local event-jitter null attacks the complementary concern that dense event labels might catch fixed triggers by chance. Leave-one-shot-out rows test whether the result is dominated by a single held-out shot.

## Claim Boundary

These nulls strengthen timing-specificity evidence for the precursor screen. They still do not prove causal actuator mitigation, expert-reviewed ELM labels, or deployed controller readiness.

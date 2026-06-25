# FAIR-MAST OMV Fresh Split

- Status: `MAST_OMV_FRESH_SPLIT_COMPLETED`
- Purpose: fixed-threshold fresh split test of the exploratory OMV6 candidate
- Excluded prior shots: `[30276, 30277, 30311, 30418, 30419, 30421, 30423]`
- Discovery rule: first `5` unused shots in configured ranges with required arrays and at least `5` automatic D-alpha events in `[0.3, 0.48]`
- Selected fresh shots: `[30260, 30261, 30262, 30263, 30265]`
- Event labels: machine D-alpha morphology triage only; trigger timing is not used for fresh labels
- Candidate was fixed before this run: Mirnov `6.0 sigma` plus OMV `6.0 sigma`

## Aggregate Fresh-Split Result

| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline Mirnov `6.0` | 61 | 50 | 11 | 53 | 0.485 | 0.820 | 8.517 ms | 0.703 |
| OMV `6.0` fixed candidate | 61 | 50 | 11 | 59 | 0.459 | 0.820 | 8.047 ms | 0.531 |
| OMV `10.0` prior train-selected | 61 | 49 | 12 | 53 | 0.480 | 0.803 | 8.388 ms | 0.666 |

## Per-Shot Delta

| Shot | Baseline detected | OMV6 detected | Detected delta | Baseline false | OMV6 false | False delta |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30260 | 11/14 | 12/14 | +1 | 1 | 1 | +0 |
| 30261 | 16/18 | 16/18 | +0 | 3 | 4 | +1 |
| 30262 | 7/8 | 7/8 | +0 | 31 | 31 | +0 |
| 30263 | 8/9 | 9/9 | +1 | 17 | 22 | +5 |
| 30265 | 8/12 | 6/12 | -2 | 1 | 1 | +0 |

## Event Transitions

- Newly detected by OMV6: `2`
- Lost/rematched relative to baseline: `2`

| Shot | Event time | Transition | Lead | Sources |
| ---: | ---: | --- | ---: | --- |
| 30260 | 0.371880000 | `newly_detected_by_omv6` | 10.810 ms | `pol_omv_rms` |
| 30263 | 0.311400000 | `newly_detected_by_omv6` | 4.042 ms | `pol_omv_rms` |
| 30265 | 0.437460000 | `lost_by_omv6_merge_or_rematch` | 11.608 ms | `pol_cc_ch2` |
| 30265 | 0.475420000 | `lost_by_omv6_merge_or_rematch` | 13.838 ms | `pol_cc_ch2` |

## Interpretation

Fresh-split verdict: `fresh_split_does_not_support_omv6_candidate`.

Because the OMV6 candidate was fixed before scoring these unused shots,
this is stronger than the prior held-out exploratory ranking. The event
labels remain machine-generated morphology labels, so this is still not
expert-reviewed experimental validation.

## Claim Boundary

This tests trigger generalization on unused public shots. It does not prove
causal TCT suppression, actuator sufficiency, or sustained fusion.

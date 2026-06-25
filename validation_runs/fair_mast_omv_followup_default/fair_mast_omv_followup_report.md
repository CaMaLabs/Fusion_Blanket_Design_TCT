# FAIR-MAST OMV Lower-Threshold Follow-Up

- Status: `MAST_OMV_FOLLOWUP_COMPLETED`
- Purpose: test whether the exploratory lower-threshold OMV gain is broad or shot-specific
- Baseline: fixed centre-column Mirnov channel at `6.0 sigma`
- Follow-up candidate: fixed Mirnov plus OMV RMS at `6.0 sigma`
- Train-selected reference: fixed Mirnov plus OMV RMS at `10.0 sigma`

## Aggregate Held-Out Result

| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline Mirnov `6.0` | 59 | 39 | 20 | 8 | 0.830 | 0.661 | 8.384 ms | 1.786 |
| OMV `6.0` exploratory | 59 | 42 | 17 | 9 | 0.824 | 0.712 | 8.413 ms | 1.858 |
| OMV `10.0` train-selected | 59 | 39 | 20 | 8 | 0.830 | 0.661 | 8.384 ms | 1.786 |

## OMV Threshold Scan

| Name | Detected | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_mirnov6` | 39/59 | 8 | 0.830 | 0.661 | 8.384 ms | 1.786 |
| `omv4` | 43/59 | 13 | 0.768 | 0.729 | 8.314 ms | 1.747 |
| `omv5` | 42/59 | 12 | 0.778 | 0.712 | 8.304 ms | 1.746 |
| `omv6` | 42/59 | 9 | 0.824 | 0.712 | 8.413 ms | 1.858 |
| `omv8` | 39/59 | 8 | 0.830 | 0.661 | 8.384 ms | 1.786 |
| `omv10` | 39/59 | 8 | 0.830 | 0.661 | 8.384 ms | 1.786 |

## Leave-One-Shot-Out Robustness

| Omitted shot | Detected delta | False-trigger delta | Score delta |
| ---: | ---: | ---: | ---: |
| 30276 | +0 | +1 | -0.039 |
| 30277 | +3 | +1 | +0.097 |
| 30418 | +3 | +1 | +0.096 |
| 30419 | +3 | +1 | +0.102 |
| 30421 | +3 | +0 | +0.142 |

## Per-Shot Delta

| Shot | Baseline detected | OMV6 detected | Detected delta | Baseline false | OMV6 false | False delta |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30276 | 0/9 | 3/9 | +3 | 1 | 1 | +0 |
| 30277 | 7/12 | 7/12 | +0 | 1 | 1 | +0 |
| 30418 | 10/11 | 10/11 | +0 | 1 | 1 | +0 |
| 30419 | 8/13 | 8/13 | +0 | 0 | 0 | +0 |
| 30421 | 14/14 | 14/14 | +0 | 5 | 6 | +1 |

## Event Transitions

- Newly detected by OMV6: `3`
- Lost/rematched relative to baseline: `0`

| Shot | Event time | Transition | OMV lead | Sources |
| ---: | ---: | --- | ---: | --- |
| 30276 | 0.316840000 | `newly_detected_by_omv6` | 8.294 ms | `pol_omv_rms` |
| 30276 | 0.333940000 | `newly_detected_by_omv6` | 8.672 ms | `pol_omv_rms` |
| 30276 | 0.360100000 | `newly_detected_by_omv6` | 13.880 ms | `pol_omv_rms` |

## Interpretation

The lower-threshold OMV result remains exploratory because it was found by
ranking held-out labels. This follow-up checks robustness and attribution,
not independent validation.

Robustness verdict: `mostly_stable_exploratory_gain`.

## Claim Boundary

This can justify a fresh pre-registered OMV validation split or a stricter
magnetic morphology classifier. It does not prove causal suppression or a
deployable trigger.

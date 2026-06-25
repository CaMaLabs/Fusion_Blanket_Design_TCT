# FAIR-MAST Fresh Trigger Search

- Status: `MAST_FRESH_TRIGGER_SEARCH_COMPLETED`
- Purpose: search unused FAIR-MAST shots for a cleaner trigger than fixed Mirnov6
- Train shots: `[30299, 30304, 30305, 30306, 30310, 30316, 30400]`
- Test shots: `[30404, 30407, 30412, 30417, 30422, 30424]`
- Candidate count: `231`
- Selected config: `{'pol_cc_all': 5.0}`

## Held-Out Fresh Test Result

| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline Mirnov6 | 59 | 35 | 24 | 30 | 0.538 | 0.593 | 6.368 ms | 0.675 |
| Train-selected trigger | 59 | 43 | 16 | 37 | 0.537 | 0.729 | 5.160 ms | 0.700 |

## Top Train Rows

| Config | Detected | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `{"pol_cc_all": 5.0}` | 24/49 | 5 | 0.828 | 0.490 | 11.480000000000047 | 1.632 |
| `{"tor_cc_all": 8.0}` | 20/49 | 3 | 0.870 | 0.408 | 10.842000000000045 | 1.581 |
| `{"pol_cc_ch2": 6.0}` | 22/49 | 5 | 0.815 | 0.449 | 11.335000000000068 | 1.538 |
| `{"pol_cc_ch2": 8.0, "pol_omv_rms": 12.0}` | 22/49 | 5 | 0.815 | 0.449 | 11.166000000000036 | 1.538 |
| `{"pol_cc_ch2": 8.0, "pol_omv_rms": 14.0}` | 22/49 | 5 | 0.815 | 0.449 | 11.166000000000036 | 1.538 |
| `{"pol_cc_ch2": 6.0, "tor_cc_all": 8.0}` | 22/49 | 5 | 0.815 | 0.449 | 11.344000000000047 | 1.538 |
| `{"pol_cc_ch2": 6.0, "pol_omv_rms": 12.0}` | 23/49 | 6 | 0.793 | 0.469 | 11.191999999999979 | 1.522 |
| `{"pol_cc_ch2": 6.0, "pol_omv_rms": 14.0}` | 23/49 | 6 | 0.793 | 0.469 | 11.191999999999979 | 1.522 |
| `{"pol_cc_ch2": 8.0, "tor_cc_all": 8.0}` | 20/49 | 4 | 0.833 | 0.408 | 10.842000000000045 | 1.510 |
| `{"pol_cc_ch2": 10.0, "tor_cc_all": 8.0}` | 20/49 | 4 | 0.833 | 0.408 | 10.842000000000045 | 1.510 |

## Top Exploratory Test Rows

These rows rank test labels directly and are for lead generation only.

| Config | Detected | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `{"dalpha_ch0_abs_slope": 4.0}` | 25/59 | 4 | 0.862 | 0.424 | 7.379999999999997 | 1.570 |
| `{"dalpha_ch0_abs_slope": 5.0}` | 15/59 | 1 | 0.938 | 0.254 | 8.23999999999997 | 1.411 |
| `{"dalpha_ch0_abs_slope": 4.0, "pol_cc_ch2": 10.0}` | 33/59 | 15 | 0.688 | 0.559 | 7.980000000000043 | 1.281 |
| `{"dalpha_ch0_abs_slope": 8.0}` | 7/59 | 0 | 1.000 | 0.119 | 8.639999999999981 | 1.237 |
| `{"dalpha_ch0_abs_slope": 6.0}` | 10/59 | 1 | 0.909 | 0.169 | 9.190000000000005 | 1.213 |
| `{"dalpha_ch0_abs_slope": 5.0, "pol_cc_ch2": 10.0}` | 27/59 | 12 | 0.692 | 0.458 | 8.23999999999997 | 1.188 |
| `{"dalpha_ch0_abs_slope": 10.0}` | 4/59 | 0 | 1.000 | 0.068 | 8.17000000000001 | 1.136 |
| `{"dalpha_ch0_abs_slope": 12.0}` | 4/59 | 0 | 1.000 | 0.068 | 8.17000000000001 | 1.136 |
| `{"dalpha_ch0_abs_slope": 14.0}` | 2/59 | 0 | 1.000 | 0.034 | 3.4500000000000086 | 1.068 |
| `{"pol_omv_rms": 10.0}` | 24/59 | 12 | 0.667 | 0.407 | 5.305000000000032 | 1.060 |

## Per-Shot Selected Vs Baseline

| Shot | Baseline detected | Selected detected | Baseline false | Selected false |
| ---: | ---: | ---: | ---: | ---: |
| 30404 | 14/16 | 15/16 | 2 | 2 |
| 30407 | 5/6 | 6/6 | 20 | 25 |
| 30412 | 2/7 | 2/7 | 0 | 0 |
| 30417 | 5/10 | 7/10 | 3 | 3 |
| 30422 | 1/9 | 4/9 | 1 | 0 |
| 30424 | 8/11 | 9/11 | 4 | 7 |

## Interpretation

Search verdict: `train_selected_trigger_improves_fresh_test_score`.

This is a fresh unused-shot train/test search with machine morphology
labels. It can identify candidate trigger directions, but it is not
expert-reviewed or causal TCT validation.

# FAIR-MAST Fresh Trigger Search

- Status: `MAST_FRESH_TRIGGER_SEARCH_COMPLETED`
- Purpose: search unused FAIR-MAST shots for a cleaner trigger than fixed Mirnov6
- Train shots: `[30260, 30261, 30262, 30263, 30265, 30266, 30269, 30270, 30271, 30272]`
- Test shots: `[30275, 30278, 30279, 30280, 30281, 30282, 30288, 30289, 30291, 30298]`
- Candidate count: `231`
- Selected config: `{'tor_cc_all': 10.0}`

## Held-Out Fresh Test Result

| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline Mirnov6 | 102 | 73 | 29 | 9 | 0.890 | 0.716 | 11.226 ms | 2.007 |
| Train-selected trigger | 102 | 57 | 45 | 12 | 0.826 | 0.559 | 11.342 ms | 1.524 |

## Top Train Rows

| Config | Detected | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `{"tor_cc_all": 10.0}` | 79/126 | 5 | 0.940 | 0.627 | 10.082000000000036 | 2.019 |
| `{"pol_cc_ch2": 12.0}` | 70/126 | 4 | 0.946 | 0.556 | 10.081000000000035 | 1.917 |
| `{"tor_cc_all": 12.0}` | 64/126 | 3 | 0.955 | 0.508 | 10.247000000000062 | 1.866 |
| `{"pol_cc_ch2": 14.0}` | 59/126 | 2 | 0.967 | 0.468 | 10.207999999999995 | 1.834 |
| `{"pol_cc_all": 12.0}` | 72/126 | 7 | 0.911 | 0.571 | 9.981000000000018 | 1.809 |
| `{"pol_cc_all": 14.0}` | 59/126 | 3 | 0.952 | 0.468 | 10.196000000000094 | 1.783 |
| `{"pol_cc_ch2": 10.0, "saddle_tor_rms": 6.0}` | 85/126 | 13 | 0.867 | 0.675 | 9.706000000000047 | 1.762 |
| `{"pol_cc_ch2": 10.0}` | 84/126 | 13 | 0.866 | 0.667 | 10.067000000000077 | 1.744 |
| `{"dalpha_ch0_abs_slope": 8.0, "pol_cc_ch2": 10.0}` | 84/126 | 13 | 0.866 | 0.667 | 10.067000000000077 | 1.744 |
| `{"dalpha_ch0_abs_slope": 10.0, "pol_cc_ch2": 10.0}` | 84/126 | 13 | 0.866 | 0.667 | 10.067000000000077 | 1.744 |

## Top Exploratory Test Rows

These rows rank test labels directly and are for lead generation only.

| Config | Detected | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `{"pol_cc_ch2": 8.0, "pol_omv_rms": 4.0}` | 75/102 | 8 | 0.904 | 0.735 | 11.208000000000052 | 2.094 |
| `{"pol_cc_ch2": 6.0, "pol_omv_rms": 4.0}` | 78/102 | 10 | 0.886 | 0.765 | 11.104000000000003 | 2.066 |
| `{"pol_cc_ch2": 8.0, "pol_omv_rms": 6.0}` | 71/102 | 7 | 0.910 | 0.696 | 11.410000000000032 | 2.057 |
| `{"pol_cc_ch2": 6.0, "pol_omv_rms": 6.0}` | 75/102 | 9 | 0.893 | 0.735 | 11.108000000000008 | 2.048 |
| `{"pol_cc_ch2": 8.0, "pol_omv_rms": 5.0}` | 72/102 | 8 | 0.900 | 0.706 | 11.309000000000042 | 2.032 |
| `{"tor_cc_all": 6.0}` | 72/102 | 8 | 0.900 | 0.706 | 11.442000000000007 | 2.032 |
| `{"pol_cc_ch2": 8.0}` | 69/102 | 7 | 0.908 | 0.676 | 11.425999999999991 | 2.016 |
| `{"dalpha_ch0_abs_slope": 12.0, "pol_cc_ch2": 8.0}` | 69/102 | 7 | 0.908 | 0.676 | 11.425999999999991 | 2.016 |
| `{"dalpha_ch0_abs_slope": 14.0, "pol_cc_ch2": 8.0}` | 69/102 | 7 | 0.908 | 0.676 | 11.425999999999991 | 2.016 |
| `{"pol_cc_ch2": 8.0, "pol_omv_rms": 8.0}` | 69/102 | 7 | 0.908 | 0.676 | 11.425999999999991 | 2.016 |

## Per-Shot Selected Vs Baseline

| Shot | Baseline detected | Selected detected | Baseline false | Selected false |
| ---: | ---: | ---: | ---: | ---: |
| 30275 | 8/9 | 7/9 | 3 | 6 |
| 30278 | 10/12 | 10/12 | 0 | 0 |
| 30279 | 14/17 | 7/17 | 0 | 0 |
| 30280 | 9/14 | 9/14 | 1 | 1 |
| 30281 | 2/11 | 2/11 | 0 | 0 |
| 30282 | 10/12 | 9/12 | 1 | 0 |
| 30288 | 4/6 | 5/6 | 1 | 2 |
| 30289 | 8/8 | 4/8 | 1 | 0 |
| 30291 | 2/5 | 1/5 | 1 | 1 |
| 30298 | 6/8 | 3/8 | 1 | 2 |

## Interpretation

Search verdict: `no_train_selected_improvement_on_fresh_test`.

This is a fresh unused-shot train/test search with machine morphology
labels. It can identify candidate trigger directions, but it is not
expert-reviewed or causal TCT validation.

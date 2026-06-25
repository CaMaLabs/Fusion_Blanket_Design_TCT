# FAIR-MAST Other Trigger Screen

- Status: `MAST_OTHER_TRIGGER_SCREEN_COMPLETED`
- Purpose: screen additional public FAIR-MAST diagnostics as possible precursor triggers
- Train split: automatic D-alpha labels on shots `30311`, `30423`
- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`
- Candidate families: OMV/OMAHA/saddle magnetics, sparse BES, density-gradient, alternate D-alpha channels, bolometer, controller/gas, coil/passive-current, and summary radiation traces

## Held-Out Result

| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed Mirnov baseline | 59 | 39 | 20 | 8 | 0.830 | 0.661 | 8.384 ms |
| Selected other-trigger config | 59 | 39 | 20 | 8 | 0.830 | 0.661 | 8.384 ms |
| Best exploratory held-out config | 59 | 42 | 17 | 9 | 0.824 | 0.712 | 8.413 ms |

## Selected Config

- Config: `{'pol_cc_ch2': 6.0, 'pol_omv_rms': 10.0}`
- Train score: `2.309`
- Best exploratory held-out config: `{'pol_cc_ch2': 6.0, 'pol_omv_rms': 6.0}`
- Best exploratory held-out score: `1.858`

## Top Train-Selected Rows

| Split | Config | Detected | False triggers | Precision | Recall | Median lead | Score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `{"pol_cc_ch2": 6.0, "pol_omv_rms": 10.0}` | 37/45 | 3 | 0.925 | 0.822 | 6.118000000000068 | 2.309 |
| `train` | `{"pol_cc_ch2": 6.0, "pol_omv_rms": 8.0}` | 35/45 | 3 | 0.921 | 0.778 | 6.190000000000085 | 2.217 |
| `train` | `{"controller_zip_abs_slope": 5.0, "pol_cc_ch2": 6.0}` | 40/45 | 9 | 0.816 | 0.889 | 6.154000000000076 | 2.206 |
| `train` | `{"pol_cc_ch2": 6.0, "summary_radiated_abs_slope": 10.0}` | 41/45 | 11 | 0.788 | 0.911 | 5.012000000000016 | 2.178 |
| `train` | `{"pol_cc_ch2": 6.0, "pol_omv_rms": 6.0}` | 35/45 | 4 | 0.897 | 0.778 | 6.190000000000085 | 2.174 |
| `train` | `{"dalpha_ch0_abs_slope": 4.0, "pol_cc_ch2": 6.0}` | 35/45 | 4 | 0.897 | 0.778 | 6.510000000000016 | 2.174 |
| `train` | `{"pol_cc_ch2": 6.0, "pol_omv_rms": 5.0}` | 34/45 | 3 | 0.919 | 0.756 | 6.35000000000005 | 2.171 |
| `train` | `{"dalpha_ch0_abs_slope": 6.0, "pol_cc_ch2": 6.0}` | 34/45 | 3 | 0.919 | 0.756 | 6.35000000000005 | 2.171 |
| `train` | `{"dalpha_ch0_abs_slope": 8.0, "pol_cc_ch2": 6.0}` | 34/45 | 3 | 0.919 | 0.756 | 6.35000000000005 | 2.171 |
| `train` | `{"dalpha_ch0_abs_slope": 10.0, "pol_cc_ch2": 6.0}` | 34/45 | 3 | 0.919 | 0.756 | 6.35000000000005 | 2.171 |

## Top Exploratory Held-Out Rows

These rows are an oracle-style diagnostic screen over the held-out shots.
They are useful for finding leads, but they are not a clean validation
selection because the test labels are used for ranking.

| Split | Config | Detected | False triggers | Precision | Recall | Median lead | Score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `test_all` | `{"pol_cc_ch2": 6.0, "pol_omv_rms": 6.0}` | 42/59 | 9 | 0.824 | 0.712 | 8.413000000000004 | 1.858 |
| `test_all` | `{"pol_cc_ch2": 6.0, "pol_omv_rms": 8.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |
| `test_all` | `{"pol_cc_ch2": 6.0, "pol_omv_rms": 10.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |
| `test_all` | `{"pol_cc_ch2": 6.0, "tor_omaha_rms": 5.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |
| `test_all` | `{"pol_cc_ch2": 6.0, "tor_omaha_rms": 6.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |
| `test_all` | `{"pol_cc_ch2": 6.0, "tor_omaha_rms": 8.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |
| `test_all` | `{"pol_cc_ch2": 6.0, "tor_omaha_rms": 10.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |
| `test_all` | `{"pol_cc_ch2": 6.0, "saddle_tor_rms": 8.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |
| `test_all` | `{"pol_cc_ch2": 6.0, "saddle_tor_rms": 10.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |
| `test_all` | `{"dalpha_ch0_abs_slope": 8.0, "pol_cc_ch2": 6.0}` | 39/59 | 8 | 0.830 | 0.661 | 8.384000000000002 | 1.786 |

## Interpretation

No train-selected additional trigger family improved on the fixed Mirnov
baseline in held-out reviewed labels. The selected OMV augmentation was
neutral on the test split.

This is a broad trigger-discovery screen. A candidate should only be treated
as promising if held-out precision/false-trigger behavior is competitive
with the fixed Mirnov or Mirnov+toroidal references while retaining enough
lead for the fast biased-current response budget.

## Claim Boundary

This is diagnostic trigger discovery only. It is not causal TCT validation
or a deployable real-time trigger.

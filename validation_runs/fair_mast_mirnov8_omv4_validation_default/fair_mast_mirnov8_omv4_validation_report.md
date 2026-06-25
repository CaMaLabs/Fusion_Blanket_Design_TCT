# FAIR-MAST Mirnov8+OMV4 Validation

- Status: `MAST_MIRNOV8_OMV4_VALIDATION_COMPLETED`
- Purpose: validate the exploratory `pol_cc_ch2=8 + pol_omv_rms=4` trigger on later unused shots
- Discovery skip count: `20`
- Validation shots: `[30299, 30304, 30305, 30306, 30310, 30316, 30400, 30404, 30407, 30412]`
- Candidate fixed before this validation run: `{'pol_cc_ch2': 8.0, 'pol_omv_rms': 4.0}`

## Aggregate Validation Result

| Config | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline Mirnov6 | 78 | 43 | 35 | 27 | 0.614 | 0.551 | 6.384 ms | 0.772 |
| Mirnov8+OMV4 | 78 | 53 | 25 | 52 | 0.505 | 0.679 | 5.196 ms | 0.044 |

## Per-Shot Delta

| Shot | Baseline detected | Candidate detected | Detected delta | Baseline false | Candidate false | False delta |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30299 | 1/4 | 1/4 | +0 | 0 | 0 | +0 |
| 30304 | 0/5 | 0/5 | +0 | 0 | 0 | +0 |
| 30305 | 1/10 | 6/10 | +5 | 1 | 4 | +3 |
| 30306 | 8/10 | 7/10 | -1 | 2 | 1 | -1 |
| 30310 | 0/2 | 0/2 | +0 | 0 | 1 | +1 |
| 30316 | 2/8 | 2/8 | +0 | 0 | 1 | +1 |
| 30400 | 10/10 | 10/10 | +0 | 2 | 8 | +6 |
| 30404 | 14/16 | 15/16 | +1 | 2 | 13 | +11 |
| 30407 | 5/6 | 5/6 | +0 | 20 | 18 | -2 |
| 30412 | 2/7 | 7/7 | +5 | 0 | 6 | +6 |

## Interpretation

Validation verdict: `mixed_candidate_gain_with_noise_cost`.

This validates a candidate discovered on the previous fresh test block,
using the next unused public-shot block. Labels remain machine morphology
triage, not expert adjudication.

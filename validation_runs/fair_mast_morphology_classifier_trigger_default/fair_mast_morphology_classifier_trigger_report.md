# FAIR-MAST Morphology Classifier Trigger

- Status: `MAST_MORPHOLOGY_CLASSIFIER_TRIGGER_COMPLETED`
- Purpose: train a causal pre-trigger morphology classifier on fresh unused shots
- Train shots: `[30299, 30304, 30305, 30306, 30310, 30316, 30400]`
- Test shots: `[30404, 30407, 30412, 30417, 30422, 30424]`
- Selected classifier threshold: `0.195407`
- Candidate rows: train `320`, test `816`

## Held-Out Fresh Test Result

| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline Mirnov6 | 59 | 35 | 24 | 30 | 0.538 | 0.593 | 6.368 ms | 0.525 |
| Reference pol_cc_all5 | 59 | 43 | 16 | 37 | 0.537 | 0.729 | 5.160 ms | 0.515 |
| Morphology classifier | 59 | 33 | 26 | 43 | 0.434 | 0.559 | 5.198 ms | -0.167 |

## Top Train Thresholds

| Threshold | Detected | False triggers | Precision | Recall | Score |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.195407 | 18/49 | 7 | 0.720 | 0.367 | 1.175 |
| 0.175712 | 19/49 | 8 | 0.704 | 0.388 | 1.159 |
| 0.157959 | 20/49 | 9 | 0.690 | 0.408 | 1.146 |
| 0.205273 | 16/49 | 6 | 0.727 | 0.327 | 1.140 |
| 0.226376 | 14/49 | 5 | 0.737 | 0.286 | 1.108 |
| 0.133874 | 20/49 | 10 | 0.667 | 0.408 | 1.083 |
| 0.146629 | 20/49 | 10 | 0.667 | 0.408 | 1.083 |
| 0.243996 | 12/49 | 4 | 0.750 | 0.245 | 1.080 |
| 0.130101 | 21/49 | 12 | 0.636 | 0.429 | 1.014 |
| 0.302957 | 9/49 | 3 | 0.750 | 0.184 | 0.997 |

## Per-Shot Test Result

| Shot | Baseline detected/false | Reference detected/false | Classifier detected/false |
| ---: | ---: | ---: | ---: |
| 30404 | 14/16 / 2 | 15/16 / 2 | 9/16 / 2 |
| 30407 | 5/6 / 20 | 6/6 / 25 | 5/6 / 29 |
| 30412 | 2/7 / 0 | 2/7 / 0 | 2/7 / 0 |
| 30417 | 5/10 / 3 | 7/10 / 3 | 7/10 / 6 |
| 30422 | 1/9 / 1 | 4/9 / 0 | 2/9 / 1 |
| 30424 | 8/11 / 4 | 9/11 / 7 | 8/11 / 5 |

## Interpretation

Classifier verdict: `classifier_does_not_improve_baseline`.

Features are computed at or before the candidate trigger time. The event
labels are used only offline for training and evaluation.

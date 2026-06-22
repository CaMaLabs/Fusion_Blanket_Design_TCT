# FAIR-MAST Held-Out Precursor Test

- Status: `MAST_HELD_OUT_PRECURSOR_TEST_COMPLETED`
- Data: public real MAST Level-2 diagnostic archive
- Training shots: threshold multiplier selected only on the train split
- Test shots: fixed D-alpha channel, fixed Mirnov channel, fixed D-alpha threshold, trained Mirnov threshold multiplier
- Baseline normalization: first 40 ms of each analysis window; event labels are not used for trigger thresholding

## Trained Trigger

- D-alpha channel index: `1`
- Mirnov channel index: `2`
- D-alpha event prominence: `0.300 V`
- Selected Mirnov threshold multiplier: `6.0 sigma`

## Held-Out Result

- Test events: `73`
- Detected events: `47`
- Missed events: `26`
- False triggers: `1`
- Precision: `0.979`
- Recall: `0.644`
- F1: `0.777`
- Median detected-event lead: `8.233 ms`

| Split | Shot | Events | Detected | False triggers | Precision | Recall | Median lead |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | `30311` | 23 | 18 | 1 | 0.947 | 0.783 | 5.278 ms |
| train | `30423` | 22 | 16 | 2 | 0.889 | 0.727 | 8.011 ms |
| test | `30276` | 10 | 1 | 0 | 1.000 | 0.100 | 13.716 ms |
| test | `30277` | 13 | 7 | 0 | 1.000 | 0.538 | 11.266 ms |
| test | `30418` | 18 | 12 | 0 | 1.000 | 0.667 | 9.066 ms |
| test | `30419` | 13 | 8 | 0 | 1.000 | 0.615 | 8.410 ms |
| test | `30421` | 19 | 19 | 1 | 0.950 | 1.000 | 4.986 ms |

## Claim Boundary

This improves over the earlier retrospective precursor screen because the
threshold multiplier is selected on training shots and evaluated on held-out
shots. It is still not a deployed real-time controller: event labels are
automatic D-alpha peaks, channel choices are engineering choices rather than
machine-calibrated diagnostics, and the first-window baseline would need a
validated online equivalent.

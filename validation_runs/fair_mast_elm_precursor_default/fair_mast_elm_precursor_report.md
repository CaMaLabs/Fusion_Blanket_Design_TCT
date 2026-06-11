# FAIR-MAST Experimental ELM Precursor / Latency Screen

- Status: `MAST_EXPERIMENTAL_PRECURSOR_SCREEN_MIXED`
- Data: public, real MAST experimental Level-2 signals from FAIR-MAST
- Event marker: automatically detected D-alpha peaks
- Candidate precursor: high-pass/RMS envelope of a centre-column Mirnov channel
- Channel selection: per-shot D-alpha dynamic range and Mirnov standard deviation
- Analysis type: retrospective; thresholds use event labels to exclude event windows

## Results

| Shot | Operator log | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `30423` | 'Good shot - good repeat  - nice regular ELMS' | 6 | 6 | 0 | 12 | 0.333 | 1.000 | 6.166 ms |
| `30311` | 'Good shot - type I ELMs later in H-mode period' | 22 | 18 | 4 | 8 | 0.692 | 0.818 | 4.854 ms |

- Aggregate events: `28`
- Aggregate detected events: `24`
- Aggregate false triggers: `20`
- Aggregate precision: `0.545`
- Aggregate recall: `0.857`
- Detected-event median lead: `4.979 ms`

## Latency feasibility

| Required end-to-end latency | Events with enough measured lead | Fraction of all events |
| --- | ---: | ---: |
| `3 ms` | 18/28 | 0.643 |
| `5 ms` | 12/28 | 0.429 |
| `8 ms` | 2/28 | 0.071 |
| `12 ms` | 0/28 | 0.000 |

## Interpretation

The real MAST signals contain a detectable pre-event magnetic-envelope pattern
for many of the automatically marked ELMs, with millisecond-scale lead time.
The same fixed trigger also misses events and produces false triggers. This is
mixed experimental support for the precursor/latency prerequisite, not a
reliable real-time predictor.

## Claim boundary

This run does not test a TCT actuator, a TCT plasma configuration, causal
suppression, DIII-D behavior, or prospective real-time performance. The event
labels are automatic rather than manually reviewed, and threshold estimation
and per-shot channel selection are retrospective. A prospective train/test
split, preselected channels, independent event labels, additional diagnostics,
and actuator command/response data are required next.

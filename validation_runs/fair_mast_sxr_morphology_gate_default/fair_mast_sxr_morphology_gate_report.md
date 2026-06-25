# FAIR-MAST SXR Morphology Gate

- Status: `MAST_SXR_MORPHOLOGY_GATE_COMPLETED`
- Goal: keep SXR recognition gains while rejecting SXR-only false-trigger bursts
- Train split: automatic D-alpha labels on shots `30311`, `30423`
- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`
- Gate family: SXR threshold crossings plus causal magnetic level/recent-crossing requirements

## Selected Gate

- Selected config: `{'sxr_feature': 'sxr_tangential_all', 'sxr_sigma': 4.0, 'deadtime_ms': 0.35, 'mag_mode': 'none', 'mag_features': [], 'mag_sigma': 0.0, 'mag_window_ms': 0.0}`
- Train selection score: `2.388`

## Held-Out Accepted-Label Result

| Trigger | Events | Detected | Missed | False triggers | Precision | Recall | Median lead |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single-channel baseline | 59 | 39 | 20 | 8 | 0.830 | 0.661 | 8.376 ms |
| Mirnov+toroidal reference | 59 | 40 | 19 | 8 | 0.833 | 0.678 | 8.360 ms |
| Raw SXR reference | 59 | 58 | 1 | 54 | 0.518 | 0.983 | 3.877 ms |
| Selected morphology gate | 59 | 57 | 2 | 89 | 0.390 | 0.966 | 3.810 ms |

## Latency-Reachable Accepted Events

| Required latency | Baseline | Mirnov+toroidal | Raw SXR | Morphology gate |
| --- | ---: | ---: | ---: | ---: |
| `3_ms` | 38 | 38 | 32 | 34 |
| `5_ms` | 30 | 30 | 24 | 20 |
| `8_ms` | 23 | 23 | 10 | 11 |
| `12_ms` | 9 | 9 | 0 | 5 |

## Interpretation

This is a causal gate in the limited sense that it uses only current or
prior diagnostic state at the candidate trigger time. It does not use the
future D-alpha event label except during offline train/test scoring.

If the selected gate does not beat the Mirnov+toroidal reference on held-out
reviewed labels, then the fixed-threshold SXR morphology path should be
treated as useful diagnostic evidence but not an improved operational
trigger. A stronger model would need additional features, more shots, or
expert-reviewed labels.

## Claim Boundary

This is an offline public-data gate screen. It is not causal TCT validation,
a measured actuator response, or a deployable controller.

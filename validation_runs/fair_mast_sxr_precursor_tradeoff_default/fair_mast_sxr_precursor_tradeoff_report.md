# FAIR-MAST SXR Precursor Tradeoff

- Status: `MAST_SXR_PRECURSOR_TRADEOFF_COMPLETED`
- Purpose: test whether public soft-X-ray camera envelopes improve precursor recognition beyond Mirnov-only triggers
- Test split: accepted machine-reviewed `true_elm` labels on shots `30276`, `30277`, `30418`, `30419`, `30421`
- Candidate SXR features: lower horizontal, upper horizontal, and tangential camera aggregate RMS envelopes
- Deadtime values: `0.35`, `3`, `5`, and `8 ms` post-trigger merge/debounce windows

## Summary

| Case | Config | Detected | False triggers | Precision | Recall | Median lead |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Single-channel baseline | `baseline` | 39/59 | 8 | 0.830 | 0.661 | 8.376 ms |
| Mirnov toroidal fusion | `mirnov_toroidal` | 40/59 | 8 | 0.833 | 0.678 | 8.360 ms |
| Best raw SXR recognition | `sxr_upper_all_4sigma` | 58/59 | 54 | 0.518 | 0.983 | 3.877 ms |
| Best false-bounded SXR | `sxr_lower_all_4sigma` | 40/59 | 8 | 0.833 | 0.678 | 8.096 ms |
| Best false-bounded tested trigger | `mirnov_toroidal` | 40/59 | 8 | 0.833 | 0.678 | 8.360 ms |
| Best SXR with precision >= 0.75 | `sxr_tangential_all_8sigma` | 42/59 | 13 | 0.764 | 0.712 | 7.182 ms |

## Interpretation

SXR envelopes do contain additional event-recognition information. The best
raw SXR-assisted configuration detects nearly all accepted events, but it
does so with many more false triggers and shorter median lead than the
Mirnov baseline. That makes SXR useful as a precursor-family lead, not a
drop-in operational trigger under this simple threshold-fusion design.

The best false-bounded SXR result does not materially beat the already
tested Mirnov toroidal fusion. Improving this path likely requires a
classifier or morphology gate that rejects SXR-only event signatures and
shot-specific bursts, not just a fixed threshold.

## Claim Boundary

This is an exploratory held-out diagnostic tradeoff map. It is not a causal
TCT validation, expert label review, or deployable real-time controller.

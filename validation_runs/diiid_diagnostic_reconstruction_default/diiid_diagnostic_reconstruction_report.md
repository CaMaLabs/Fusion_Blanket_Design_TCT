# DIII-D Shot 158103 Diagnostic Reconstruction Package

- Status: `DIIID_DIAGNOSTIC_RECONSTRUCTION_READY_FOR_AUTHORIZED_REPLACEMENT`
- Reference: shot `158103` at `3796.325 ms`
- Input basis: public EFIT `g/a/p` snapshot
- Raw time-series diagnostics: `not present`

## Experiment-referenced baseline

- Plasma current: `1.339492e+06 A`
- Toroidal field: `-1.89776 T`
- Edge ne at psiN=0.95: `0.197679 1e20/m^3`
- Edge Te at psiN=0.95: `0.845668 keV`
- Edge total pressure at psiN=0.95: `6.12462 kPa`
- Edge Er at psiN=0.95: `-33.5146 kV/m`

## Falsifiable timing hypotheses

| Scenario | Assumed precursor lead | Reconstructed trigger lead | 3 ms feasible | 5 ms feasible | 8 ms feasible | 12 ms feasible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_weak` | 6.0 ms | 6.00 ms | True | True | False | False |
| `nominal` | 15.0 ms | 15.00 ms | True | True | True | True |
| `early_strong` | 25.0 ms | 25.00 ms | True | True | True | True |

These traces are reconstructed hypotheses, not measurements. They define the
signals, time window, thresholds, and pass/fail tests that raw DIII-D data can
directly replace.

## Requested access

The narrow request is read-only access to the listed channels for shot 158103
over 3756.325-3806.325 ms. The test asks whether a robust magnetic precursor
exists, whether ECE/density corroborate it, and whether measured lead time is
longer than plausible sensing and actuator latency.

## Claim boundary

This package demonstrates preparation for an experimental diagnostic test. It
does not demonstrate that the reconstructed precursor occurred, that the event
at the reference time is an ELM, or that a real actuator could respond in time.

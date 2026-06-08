# HW2D Delayed-Growth Predictive Validation

- Status: `HW2D_DELAYED_GROWTH_PREDICTIVE_SUPPORTED`
- Started: `2026-06-08T19:23:04.322577+00:00`

The independent HW2D-style case starts from low-amplitude perturbations, holds a quiet density-gradient drive until time 2, and ramps to the target drive by time 4. Both grids use the same controller thresholds, filter, noise, and delay.

| Grid | Predictive time | Magnitude time | Uncontrolled peak time | Before peak | Predictive earlier | Peak reduced | Integrated reduced | Noisy/delayed peak reduced | Noisy/delayed integrated reduced | Effort below fixed strong |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 4.305 | 7.980 | 12.000 | True | True | True | True | True | True | True |
| coarse | 4.400 | 8.000 | 12.000 | True | True | True | True | True | True | True |

## Interpretation

PASS: a single growth-rate threshold triggers before the magnitude threshold on both HW2D grids, reduces peak and integrated burden, remains beneficial with noise and delay, and uses less effort than fixed strong control. This remains a synthetic reduced-model check; the delayed drive is constructed rather than experimentally measured.

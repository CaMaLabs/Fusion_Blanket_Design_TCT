# Predictive TCT Validation

- Status: `PREDICTIVE_TRIGGER_BOUT_SUPPORTED_HW2D_LIMITED`
- Started: `2026-06-08T16:33:28.494887+00:00`

## Controller

The predictive controller triggers on measured global max-vorticity growth rate. It is compared directly with the prior max-vorticity magnitude threshold, fixed moderate control, and fixed strong control.

## Results

| Model | Grid | Predictive earlier | Peak vs uncontrolled | Peak vs magnitude | Integrated vs uncontrolled | Within 20% fixed moderate | Effort below fixed strong | Noisy predictor beneficial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BOUT++ | base | True | True | True | True | True | True | True |
| BOUT++ | coarse | True | True | True | True | True | True | True |
| HW2D-style | base | False | False | False | True | True | True | True |
| HW2D-style | coarse | False | False | False | True | True | True | True |

## Interpretation

PASS: growth-rate feedback triggers earlier than magnitude feedback, suppresses BOUT++ peak and integrated current, approaches fixed-moderate performance with less effort than fixed strong control, and remains beneficial with noise and delay. HW2D-style results remain a limitation because that initialized-decay setup is not a clean precursor-growth test.

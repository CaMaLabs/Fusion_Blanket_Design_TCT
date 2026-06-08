# Closed-Loop TCT Validation

- Status: `CLOSED_LOOP_REDUCED_MODEL_MIXED`
- Started: `2026-06-08T12:36:40.993366+00:00`

## Controller

The BOUT++ resolved current-sheet model uses a latched global max-vorticity threshold with configurable deterministic sensor noise and actuator delay. The HW2D-style model uses the same controller structure.

## Results

| Model | Grid | Closed-loop lowers integrated metric | Closed-loop lowers peak | Noisy delayed lowers integrated metric | Within 20% of fixed moderate | Effort below fixed strong |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| BOUT++ | base | True | False | True | False | True |
| BOUT++ | coarse | True | False | True | False | True |
| HW2D-style | base | True | False | True | True | False |
| HW2D-style | coarse | True | False | True | True | False |

## Interpretation

MIXED: threshold-triggered control reduced integrated burden in every tested model/grid and the noisy/delayed case remained beneficial, but it did not reduce the peak. In BOUT++, the vorticity threshold fired after the first reported current peak and did not approach fixed-moderate integrated performance within 20%. In HW2D-style cases, the initialized perturbation crossed the threshold at time zero, so that model does not validate precursor detection or lower effort than fixed strong control.

This remains reduced-model validation. The threshold, deterministic noise, and actuator-delay model are auditable control assumptions, not experimental sensor validation.

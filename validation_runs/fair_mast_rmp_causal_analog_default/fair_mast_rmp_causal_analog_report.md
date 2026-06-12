# FAIR-MAST Measured-RMP Causal-Analog Screen

- Status: `MAST_RMP_CAUSAL_ANALOG_DIRECTIONALLY_SUPPORTIVE_UNDERPOWERED`
- Data: public real MAST experimental Level-1 actuator and Level-2 diagnostic signals
- Common comparison window: `300-480 ms`
- Actuator exposure: measured `xma/rog_elm_l01` RMS
- Outcome: fixed-channel, fixed-threshold D-alpha event pacing and peak amplitude

## Shot-level results

| Shot | Measured actuator active | RMP catalog flag | Actuator RMS | Event rate | Median D-alpha peak |
| --- | --- | --- | ---: | ---: | ---: |
| `30276` | False | False | 0.0123 V RMS | 55.56 Hz | 1.6833 V |
| `30277` | True | None | 0.2114 V RMS | 72.22 Hz | 1.3452 V |
| `30418` | True | True | 0.2001 V RMS | 100.00 Hz | 0.9900 V |
| `30419` | True | True | 0.2421 V RMS | 77.78 Hz | 1.5637 V |
| `30421` | True | True | 0.3062 V RMS | 116.67 Hz | 1.3647 V |
| `30423` | False | False | 0.0146 V RMS | 61.11 Hz | 2.0557 V |

## Group contrast

- Active shots: `[30277, 30418, 30419, 30421]`
- Inactive shots: `[30276, 30423]`
- Event-rate change: `+0.571` (58.33 to 91.67 Hz)
- Median D-alpha peak change: `-0.296` (1.8695 to 1.3159 V)
- Directional exact permutation p, higher event rate: `0.0667`
- Directional exact permutation p, lower median peak: `0.0667`

The measured RMP-active group has more frequent, lower-median-amplitude
D-alpha events. This is experimentally consistent with continuous/moderate
preventative edge-event mitigation rather than waiting for a late trigger.

## Covariate warning

| Group | Mean plasma current | Mean line density | Mean NBI power |
| --- | ---: | ---: | ---: |
| Actuator active | 5.2434e+05 A | 4.9257e+19 m^-3 | 3.4270e+06 W |
| Actuator inactive | 4.4838e+05 A | 2.5197e+19 m^-3 | 3.1053e+06 W |

These groups are not balanced on plasma state, so the contrast cannot isolate
the actuator effect.

## Causal boundary

This is a causal analog, not a causal TCT validation. The actuator exposure is
measured and temporally prior to the outcomes, but shots were not randomized,
the sample contains only six shots, scenario and plasma-state confounding remain,
and RMP coils are not a TCT actuator. The exact permutation tests are underpowered
and do not reach the conventional 0.05 threshold. The result justifies a
precommitted matched-shot or randomized actuator experiment; it does not prove
that TCT causes mitigation.

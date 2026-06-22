# FAIR-MAST Expanded Measured-RMP Causal-Analog Screen

- Status: `MAST_RMP_EXPANDED_CAUSAL_ANALOG_COMPLETED`
- Data: public real MAST Level-1 actuator and Level-2 diagnostic signals
- Candidate shots: `[30275, 30276, 30277, 30285, 30311, 30418, 30419, 30421, 30423]`
- Usable shots: `[30275, 30276, 30277, 30285, 30311, 30418, 30419, 30421, 30423]`
- Skipped shots: `[]`
- Common comparison window: `300-480 ms`
- Actuator exposure: measured `xma/rog_elm_l01` RMS, not catalog flags

## Shot-Level Results

| Shot | Active | Catalog RMP | Actuator RMS | Event rate | Median D-alpha peak |
| ---: | --- | --- | ---: | ---: | ---: |
| `30275` | False | None | 0.0182 V RMS | 77.78 Hz | 1.1340 V |
| `30276` | False | None | 0.0123 V RMS | 55.56 Hz | 1.6833 V |
| `30277` | True | None | 0.2114 V RMS | 72.22 Hz | 1.3452 V |
| `30285` | False | None | 0.0204 V RMS | 22.22 Hz | 3.2434 V |
| `30311` | False | None | 0.0176 V RMS | 27.78 Hz | 0.9814 V |
| `30418` | True | None | 0.2001 V RMS | 100.00 Hz | 0.9900 V |
| `30419` | True | None | 0.2421 V RMS | 77.78 Hz | 1.5637 V |
| `30421` | True | None | 0.3062 V RMS | 116.67 Hz | 1.3647 V |
| `30423` | False | None | 0.0146 V RMS | 61.11 Hz | 2.0435 V |

## Group Contrast

- Active shots: `[30277, 30418, 30419, 30421]`
- Inactive shots: `[30275, 30276, 30285, 30311, 30423]`
- Event-rate relative change: `0.875`
- Median D-alpha peak relative change: `-0.276`
- Directional exact permutation p, higher event rate: `0.0238`
- Directional exact permutation p, lower median peak: `0.1825`

## Covariate Warning

| Group | Mean plasma current | Mean line density | Mean NBI power |
| --- | ---: | ---: | ---: |
| Actuator active | 5.2442e+05 A | 4.9194e+19 m^-3 | 3.4278e+06 W |
| Actuator inactive | 4.7942e+05 A | 4.1918e+19 m^-3 | 2.2669e+06 W |

## Claim Boundary

This is still a causal analog rather than causal TCT validation. The exposure
is measured before the outcomes, but shots are non-randomized, plasma-state
covariates are not balanced, MAST RMP coils are not a TCT actuator, and the
D-alpha event labels are automatic. A convincing next step remains a
precommitted matched-shot or randomized actuator experiment with an actual
TCT-like actuator command and independent diagnostics.

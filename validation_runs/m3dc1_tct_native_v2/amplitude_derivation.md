# Amplitude Derivation

The BOUT handoff artifacts contain actual reduced-model actuator parameters in `validation_runs/bout_tct_actuator_robustness_default/tct_actuator_robustness_summary.json`: nominal `tct_strength=0.11243167604751647`, `omega_tct_strength=0.056215838023758236`, `actuator_center=0.5`, `actuator_width=0.0935`, and timing variants including delayed turn-on. Those parameters act as reduced-model damping/source coefficients and are not dimensionally calibrated current-drive amplitudes for native M3D-C1.

Therefore the V2 native amplitude is explicitly:

`FIRST_NATIVE_PERTURBATION_SCALE_NOT_PHYSICAL_CALIBRATION`

Frozen choice before running controlled case:

- `J_0cd = -0.0203083`
- basis: 1% of the baseline t=0 max element-center `|jphi| = 2.03083`
- sign: opposite the local positive baseline `jphi` at the element nearest the X-point-centered actuator
- no amplitude sweep was performed

The BOUT outcome reductions, including the prior ~14.3% peak-current reduction, were not used as native amplitude.

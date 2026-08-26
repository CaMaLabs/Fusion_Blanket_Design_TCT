# V2 Actuator Definition

Native mechanism: built-in M3D-C1 `icd_source=1` current-drive source.

Equation affected: flux/induction equation residual through `flux_nolin()`; for this `jadv=1` run the source contribution is proportional to `-dt * eta * cd_source`.

Profile:

`cd_source(R,Z,t) = G(t) * J_0cd * exp(-((R-R_0cd)^2/W_cd^2) - ((Z-Z_0cd)^2/W_cd^2))` inside the plasma region.

Frozen controlled settings:

- `icd_source = 1`
- `J_0cd = -0.0203083`
- `R_0cd = 10.0`
- `Z_0cd = 1.0`
- `W_cd = 0.561`
- `delta_cd = 0.0`
- `cd_t_on = 0.05`
- `cd_t_ramp = 0.05`
- `cd_t_off = 0.25`

The baseline and controlled decks keep the same GEM initial perturbation `eps=1e-3`; the actuator is zero at t=0 and turns on only after initialization.

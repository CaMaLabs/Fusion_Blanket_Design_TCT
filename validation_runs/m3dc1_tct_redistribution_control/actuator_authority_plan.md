# M3D-C1 Native Redistribution Authority Plan

Actuator mode: `icd_source = 4`, through native `cd_func()` current-drive source path.

Spatial form:

`S = A * (-G_center + 0.5 G_lower_shoulder + 0.5 G_upper_shoulder)`

The source is numerically mean-subtracted over plasma quadrature points before projection, so the applied redistribution is net-current-neutral on the same native source path.

Frozen geometry:

- `R_0cd = 10.0`
- `Z_0cd = 1.0`
- `W_cd = 0.2805`
- `delta_cd = 0.561`
- `W_cd_shoulder = 0.2805`
- active window: `0.05 <= t < 0.25`, ramp `0.05`

Frozen amplitudes before execution:

- A1: `J_0cd = 0.0203083` = 1x previous native local source scale
- A2: `J_0cd = 0.0812332` = 4x previous native local source scale
- A3: `J_0cd = 0.1624664` = 8x previous native local source scale

Purpose: identify whether native redistribution can oppose the measured natural sheet-narrowing rate, not tune reconnection output.

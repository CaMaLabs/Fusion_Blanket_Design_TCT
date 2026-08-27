# M3D-C1 Native Redistribution Authority Result

Classification: `M3DC1_TCT_CONTROL_AUTHORITY_INSUFFICIENT`

Native source change: `icd_source = 4` adds a net-current-neutral center-plus-shoulder redistribution profile through the existing `cd_func()` current-drive path. The actuator remains off by default, and the zero-amplitude controller path is exactly equivalent to the baseline.

Zero-controller equivalence:

- controller path: `icd_source=4` with `J_0cd=0`
- run status: `return_code=0`
- C1ke maximum absolute difference: `0.0`
- localized `Jpk`, `Jint`, sheet width, `Reconnected_Flux`, magnetic energy, kinetic energy, and total energy maximum absolute differences: `0.0`

Frozen natural baseline dynamics from the validated GEM baseline:

- uncontrolled peak-current time: `t=0.05`
- uncontrolled peak `Jpk`: `2.34622`
- rapid current-growth time: `t=0.05`
- maximum current-growth rate: `15.698800000000004`
- maximum narrowing-rate time: `t=0.25`
- maximum narrowing rate: `-1.8390386614487313`
- peak absolute reconnection-rate proxy: `0.0044172199999999995`

Frozen authority cases, chosen before execution from the previous native source scale `0.0203083`:

- A1: `J_0cd = +0.0203083`
- A2: `J_0cd = +0.0812332`
- A3: `J_0cd = +0.1624664`

All three cases ran successfully and remained net-current-neutral by the diagnostic source integral:

- A1 max net/absolute source ratio: `3.475774473584426e-17`
- A2 max net/absolute source ratio: `3.475774473584426e-17`
- A3 max net/absolute source ratio: `3.475774473584426e-17`

Authority outcome:

- baseline active-window minimum `dW/dt`: `-1.8390386614487313`
- A1 active-window minimum `dW/dt`: `-1.8609495442099093`
- A2 active-window minimum `dW/dt`: `-1.9263370988563682`
- A3 active-window minimum `dW/dt`: `-2.014113353398233`
- no predeclared authority case measurably opposed the natural narrowing rate
- active-window peak `Jpk` was unchanged at this output cadence
- final `Reconnected_Flux` change was `0.0%` for A1/A2/A3

Interpretation: this rung identifies actuator/control authority as the bottleneck. The current-sheet mechanism is not falsified because the native redistribution source did not maintain a wider sheet.

The next closed-loop topology run should not be interpreted as a mechanism test unless a native actuator first demonstrates a positive sustained width gain over the vulnerable interval.

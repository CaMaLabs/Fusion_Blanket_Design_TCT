# M3D-C1 Magnetic Pulse-Train Audit

Primary classification: `M3DC1_MAGNETIC_PULSE_TRAIN_NO_FULL_SUSTAINED_CONTROL_FOUND`

## Frozen design

- amplitude: `-0.01`
- dt: `0.01`
- train window: `0.0 <= t < 0.35`
- amplitude was not tuned; only pulse period/on-time were varied.

## Results

- `single_reference`: `M3DC1_MAGNETIC_PULSE_TRAIN_WIDTH_ONLY`; mean width 0.220997%, positive-width fraction 0.677, max Jpk 0.658138%, integrated high-J -2.01522%.
- `train_p040_w020`: `M3DC1_MAGNETIC_PULSE_TRAIN_J_WORSE`; mean width -1.497%, positive-width fraction 0.226, max Jpk 0.833975%, integrated high-J 0.74124%.
- `train_p050_w020`: `M3DC1_MAGNETIC_PULSE_TRAIN_J_WORSE`; mean width -1.17496%, positive-width fraction 0.258, max Jpk 0.921577%, integrated high-J -0.529735%.
- `train_p060_w020`: `M3DC1_MAGNETIC_PULSE_TRAIN_J_WORSE`; mean width -1.34535%, positive-width fraction 0.161, max Jpk 0.971747%, integrated high-J 0.668259%.
- `train_p050_w030`: `M3DC1_MAGNETIC_PULSE_TRAIN_J_WORSE`; mean width -1.66475%, positive-width fraction 0.194, max Jpk 0.892894%, integrated high-J -1.57147%.

## Interpretation gate

A pulse train counts as sustained control only if it maintains a positive mean sheet-width gain for most of the active window while also reducing integrated high-|J| loading without exceeding the predeclared peak-J worsening tolerance.

## Claim boundary

Native normalized GEM magnetic pulse-train audit only; no lithium dimensional transfer, reactor stabilization, or experimental TCT validation is implied.

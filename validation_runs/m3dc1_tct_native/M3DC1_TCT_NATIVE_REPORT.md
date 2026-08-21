# Native M3D-C1 TCT RMP Actuator Mapping Study

Primary classification: `NATIVE_TCT_NO_EFFECT`

A native M3D-C1 first-rung paired test was run using the smallest official non-KPRAD case that passed initialization on this runtime: `RMP` with the bundled single-part source mesh and `m3dc1_2d_complex`. The partitioned `RMP` and `RMP_nonlin` meshes failed hard initialization gates, so they were not used as physics baselines.

Baseline and controlled runs both completed with return code 0. Baseline exactly matches the bundled `RMP/base/C1ke` under upstream `compare.py`. The controlled case differs by one scalar only: `scale_ext_field = 0.8566360855`.

## Result

| metric | baseline | controlled | change |
|---|---:|---:|---:|
| peak current proxy `max|toroidal_current|` | 1.7078726296939981 | 1.7078726296939981 | -0% reduction |
| integrated current proxy | 3.4157305308568215 | 3.4157305308568215 | 0% |
| final magnetic-energy block | 5.7209129999999996e-05 | 5.7209129999999996e-05 | 0% |
| DERIVED flux-transfer proxy | 1.5307958086907547e-05 | 1.5307958086907547e-05 | 0% |

The controlled C1ke/native scalar trajectory is identical to baseline for this official one-step response. The sign-reversed falsification control is also identical. No refinement was run because the paired effect is zero and the refinement gate requires a nonzero stable effect.

## What this establishes

This establishes that the direct `scale_ext_field` mapping of the BOUT peak-current reduction fraction does not produce a measurable current-loading or topology-proxy change in the smallest valid official native M3D-C1 RMP rung.

## What this does not establish

It does not establish reactor stabilization, ELM suppression, experimental validation, reconnection suppression, liquid-lithium actuator transfer, ignition improvement, or net energy gain. It also does not rule out a more physically localized native current-source or electric-field actuator in a nonlinear M3D-C1 case; the available nonlinear/partitioned official candidates failed initialization on this runtime.

# DIII-D BOUT++ elm-pb Serial-Topology Solution Convergence

- Status: `DIIID_ELM_PB_SERIAL_SOLUTION_CONVERGENCE_SUPPORTED`
- Generated: `2026-06-11T14:09:31.624234+00:00`

| Case | Mesh | MZ | dt | Final U L2 | Final P L2 | Final Psi L2 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `coarse` | coarse | 8 | 1.0e-04 | 1.177968e-08 | 6.483958e-14 | 1.541446e-14 |
| `base` | base | 8 | 1.0e-04 | 1.170991e-08 | 9.696271e-14 | 2.826754e-14 |
| `fine` | fine | 8 | 1.0e-04 | 1.167116e-08 | 1.259874e-13 | 3.884708e-14 |
| `base_dt_half` | base | 8 | 5.0e-05 | 1.170991e-08 | 9.696271e-14 | 2.826754e-14 |
| `base_mz16` | base | 16 | 1.0e-04 | 1.170991e-08 | 9.708489e-14 | 2.826754e-14 |

- All physical-domain histories finite: `True`
- Base timestep-halving maximum scalar difference: `2.917604e-11`
- Base MZ 8-to-16 maximum scalar difference: `1.258540e-03`

The proportional mesh cases quantify solution sensitivity but are not required
to agree tightly because each Hypnotoad mesh changes the discrete machine
geometry and metric representation. The timestep and toroidal checks isolate
numerical sensitivities on the same base mesh.

## Claim boundary

This is short-duration linear evolution convergence with the serial topology
override and without Jpar0. It is not exact-X-point evolution, validated ELM
growth, nonlinear saturation, TCT control validation, or experimental agreement.

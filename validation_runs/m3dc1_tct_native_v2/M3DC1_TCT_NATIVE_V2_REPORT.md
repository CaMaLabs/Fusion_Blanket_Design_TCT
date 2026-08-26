# Native M3D-C1 TCT V2 Local Current-Drive Rung

Primary classification: `NATIVE_TCT_V2_LOCAL_CURRENT_AND_TOPOLOGY_IMPROVEMENT`

This rung addresses the remaining actuator question by keeping the GEM initial condition identical between baseline and controlled runs and applying a localized native current-drive source only after initialization. It does not repeat `scale_ext_field` or GEM `eps` scaling.

## Case

- native case: valid GEM circle/source mesh configuration from the prior exploratory rung
- baseline: `/home/ubuntu/m3dc1_runs/TCT_NATIVE_V2_BASELINE`
- zero-amplitude equivalence: `/home/ubuntu/m3dc1_runs/TCT_NATIVE_V2_ZERO_AMP`
- controlled: `/home/ubuntu/m3dc1_runs/TCT_NATIVE_V2_CONTROLLED`
- falsification: `/home/ubuntu/m3dc1_runs/TCT_NATIVE_V2_FALSIFICATION_DISPLACED`
- same `eps=1e-3` in baseline, zero-amplitude, controlled, and falsification decks

## Initialization Gate

- baseline gate: `PASS`
- zero-amplitude equivalence: `PASS` with exact t=0 scalar and field agreement to baseline
- controlled t=0 equivalence: `PASS`

## Actuator

Built-in `icd_source=1` Gaussian current-drive source in the flux equation. Frozen controlled settings: `J_0cd=-0.0203083`, `R_0cd=10.0`, `Z_0cd=1.0`, `W_cd=0.561`, `cd_t_on=0.05`, `cd_t_ramp=0.05`, `cd_t_off=0.25`.

Amplitude label: `FIRST_NATIVE_PERTURBATION_SCALE_NOT_PHYSICAL_CALIBRATION`.

## Paired Result

| metric | baseline | controlled | fractional change |
|---|---:|---:|---:|
| peak element-center `|jphi|` | 9.45085 | 9.45036 | -5.1847188e-05 |
| integrated high-`|jphi|` loading | 92.680507 | 92.630499 | -0.00053957409 |
| final `Reconnected_Flux` | 0.000349069 | 0.000349067 | -5.7295263e-06 |
| peak reconnection-rate proxy | baseline | controlled | 0 |
| final magnetic energy | baseline | controlled | -2.4051528e-05 |

The localized source reduces high-current loading weakly and does not worsen the native reconnection scalar or finite-difference reconnection-rate proxy over this short GEM window.

## Falsification

The displaced same-amplitude source produced peak `|jphi|` change `0.00032695472` and integrated high-`|jphi|` change `6.9108383e-05`. It did not reproduce the local current reduction, so the response is not simply a generic consequence of enabling `icd_source`.

## Refinement

`REFINEMENT_BLOCKED_BY_MESH_TOOLCHAIN`: no known valid same-physics finer GEM circle mesh was available, and known checked-in partitioned meshes remain quarantined by initialization failures.

## Claim Boundary

This is weak first-rung native evidence that a localized time-dependent current-drive source can slightly reduce current-sheet loading without worsening native reconnection/topology diagnostics in a short GEM run. It does not establish reactor stabilization, experimental validation, ELM suppression, liquid-lithium transfer validation, ignition improvement, or net energy gain.

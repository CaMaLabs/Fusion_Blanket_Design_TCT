# Native M3D-C1 Time-Dependent Actuator Inventory

Search scope: `/home/ubuntu/M3DC1-official/unstructured` at upstream commit `e17c0b7e`, excluding the resolved KPRAD provenance path.

## Recommended Candidate: `icd_source` Current Drive

- variable/input: `icd_source`, `J_0cd`, `R_0cd`, `Z_0cd`, `W_cd`, `delta_cd`, `cd_t_on`, `cd_t_ramp`, `cd_t_off`
- source files/routines: `input.f90` declares inputs; `transport.f90:cd_func()` builds the Gaussian source and smooth time gate; `transport.f90` solves `cd_field`; `m3dc1_nint.f90` evaluates `cd79`; `ludef_t.f90:flux_nolin()` inserts the term into the flux equation.
- equation affected: flux/induction equation residual. In `flux_nolin`, `icd_source.gt.0` adds a term proportional to `-dt * eta * cd79` for this `jadv=1` GEM run.
- spatial localization available: yes, Gaussian in native R,Z for `icd_source=1`.
- time gating available: yes, off before `cd_t_on`, smoothstep ramp over `cd_t_ramp`, off after `cd_t_off`.
- sign control: yes through `J_0cd`.
- amplitude control: yes through `J_0cd`.
- suitable for current-sheet forcing: yes, closest built-in native hook for a localized current/electric-field-like actuator applied during evolution.
- requires code patch: no.
- recommendation: use for V2; require `cd_t_on > 0` and a zero-amplitude equivalence gate.

## Other Candidates

- `vloop` / current controller: affects loop voltage globally in `newpar.f90`, `model.f90`, and `ludef_t.f90`; time dependence/control exists but no local spatial profile, so it is not a current-sheet actuator.
- RMP/external-field machinery: native topology machinery exists in `rmp.f90`, but the prior `scale_ext_field` rung was global and null; do not repeat for V2.
- heat, density, beam, momentum sources: localized source frameworks exist, but they do not directly actuate magnetic/current evolution and are lower-priority substitutes.
- custom source patch: unnecessary for this rung because `icd_source` already satisfies the required form `S_TCT(R,Z,t)=A0*S_space(R,Z)*G_time(t)`.

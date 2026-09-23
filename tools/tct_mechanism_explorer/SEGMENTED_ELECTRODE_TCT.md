# Segmented-electrode TCT actuator audit

## What existed before

The current branch already contains native/localized magnetic control, current-drive/current-redistribution operators, and a standing native poloidal-momentum source. The momentum source was used as a flow/shear proxy. It is **not** a segmented-electrode model and does not explicitly solve or command `E_r(r,z,t)`.

## What is added

`segmented_electrodes.py` adds a reduced actuator layer with an arbitrary number of independently commanded zones. Each zone has radial/axial position and width, polarity, voltage/current/slew limits, latency, first-order response time, and a reduced RC plasma-loading model. Zone fields overlap spatially.

The array computes:

- `E_r(r,z,t)`
- signed `v_ExB = E_r B / B^2` for the dominant toroidal-field approximation
- `dv_ExB/dr`
- actuator voltage/current/power and integrated reduced actuator energy
- a conservative shear-decorrelation transport multiplier for hypothesis ranking/falsification
- reduced guiding-center diagnostics for electrons, thermal fuel ions, and alpha particles

The ExB component is species independent. Species-dependent grad-B terms are tracked separately. The reduced model does **not** claim species separation.

## Controller architecture

The actuator is intended to sit inside the existing architecture without replacing precursor work:

`standing/preventative bias -> Mirnov/toroidal precursor -> response-time feasibility gate -> bounded spatially shaped electrode response -> NO ACTION if too late`

## Comparison/falsification matrix

`run_segmented_electrode_audit.py` evaluates representative cases for:

- no electrode actuation
- uniform/static bias
- radially segmented static bias
- open-loop time-varying segmented bias
- precursor-triggered segmented bias
- a small zone-count optimization sweep
- wrong polarity
- no-shear control
- excessive shear
- deliberately late actuation
- misplaced shear layer
- unsegmented comparison channel for energy-matched follow-up

The frozen TCT gates remain `width gain > +0.020%` and `Jpk change <= +0.10%`.

## Claim boundary and higher-fidelity handoff

This implementation is a reduced TCT control model. Native M3D-C1 on this branch does not yet contain validated electrode sheath/boundary physics, so reduced-model improvement must not be called native M3D-C1 stabilization evidence.

For BOUT++, the handoff is an explicit `E_r(r,z,t)` / electrostatic-potential or vorticity boundary/source mapping. For M3D-C1, the next fidelity rung is an electrode-compatible electrostatic boundary/source operator with mandatory zero-equivalence, spatially misplaced, wrong-polarity, late-actuation, and equal-energy controls before any efficacy claim.

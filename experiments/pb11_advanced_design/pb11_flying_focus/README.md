# p-B11 Flying-Focus Audit Program

This directory is a staged falsification/optimization program for applying
flying-focus proton acceleration and rephasing to the advanced p-B11 branch.
It remains separate from `m3dc1_tct_hybrid_bridge.py`; physical effects are not
promoted into the reactor surrogate until their downstream gates survive.

## Current canonical result

**GEOMETRY_CONDITIONAL_PASS_RESIDENCE_AND_ROUTING_UPGRADE_REQUIRED**

## Stage chronology

1. `results/` — repeated FF rephasing identified as the useful resonance mechanism.
2. `ignition_bridge/` — first energy bridge; retained for provenance.
3. `physical_channel/` — corrected CM/lab energy handling and physical stopping.
4. `power_flow/` — conserved alpha power and identified electron drag as the dominant burden.
5. `distribution_kinetic/` — isotropic drag suppression fails its recirculating-power gate.
6. `anisotropic_kinetic/` — directed/two-stream drag suppression also fails its power/stability gate.
7. `surviving_optimizer/` — accepts classical drag and identifies the ~584–600-keV / ~4%-fast-proton recovery window.
8. `orbit_energy_routing/` — couples that window to Candidate-0 orbit geometry, betaN, wall clearance, corrected compression semantics, and the repository electron-exhaust routing model.

## Current FF operating targets

- **~638 keV lab** — maximum `<sigma v>` / instantaneous p-B11 rate.
- **~616 keV lab** — maximum fusion probability per unit path.
- **~600 keV lab** — minimum classical drag + fused-proton replacement per fusion energy.
- **~584–600 keV lab with ~4% fast protons** — current hybrid drag-recovery / bremsstrahlung compromise.

## Compression correction

The prior Stage-7 interpretation of `volume_compression_factor = 0.074` as a
physical remaining-volume fraction was incorrect.

The bridge computes it as a bounded actuator/proxy magnitude. Therefore
`1/0.074 ~= 13.5x` density and the associated `~0.76 s` residence are
superseded.

The explicit selected `compression_amplitude_pct = 10%` supports only a
bounded geometric sensitivity of roughly `1.23–1.37x` particle-conserving
density, leaving the inherited burn-target residence near **7.5–8.4 s**.

## Stage-8 geometry result

Candidate-0 machine anchors are `R=5.5 m`, `a=1.8 m`, `B0=7.2 T`,
`Ip=14 MA`, `kappa=1.9`.

At 584 keV, a small-pitch passing proton packet has a centimeter-scale orbit
envelope. A narrow edge-biased reaction sheet can pass simple wall-clearance,
classical radial-diffusion, and volume-averaged betaN screens.

But multi-second residence still means roughly **2–3 million toroidal
circuits**. The selected handoff has `edge_racetrack = off` and
`racetrack_guidance_factor = 0`, so long residence remains unvalidated.

## Stage-8 routing result

The upstream fast-loop requires **73.8% returned electron-drag energy**.

The selected repository state has about **29.6% electron exhaust**. Sweeping
the existing electron-channel and RF-grating controls only reaches about
**68.4%**.

At **92% electron-energy conversion** and **95% return-to-FF efficiency**, the
required extraction fraction is about **84.4%**.

Therefore the current electron-channel equations cannot close the fast-proton
loop. A dedicated electron-energy collector/routing extension is required.

## Current decision

Do not promote `pB11_net_delta`, ignition margin, or a p-B11 net-power claim.

The next two gates are:

1. guiding-center orbit integration over the required multi-second residence
   with ripple/TCT-event perturbations and wall geometry;
2. a redesigned electron-energy collector model with separate extraction,
   conversion, and FF-return efficiencies.

Only a case that survives both should be promoted into the reactor surrogate.

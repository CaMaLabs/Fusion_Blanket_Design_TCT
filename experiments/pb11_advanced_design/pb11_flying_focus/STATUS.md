# Flying-Focus p-B11 Audit Status

Current canonical result:

**GEOMETRY_CONDITIONAL_PASS_RESIDENCE_AND_ROUTING_UPGRADE_REQUIRED**

Study chronology:

1. `results/` — repeated FF rephasing identified as the useful resonance mechanism.
2. `ignition_bridge/` — first energy bridge; retained for provenance.
3. `physical_channel/` — corrected CM/lab target to ~638 keV and physicalized stopping.
4. `power_flow/` — conserved alpha power and identified electron drag as the dominant remaining burden.
5. `distribution_kinetic/` — isotropic electron holes suppress drag but fail by ~2.2e3 `P_fusion` of maintenance.
6. `anisotropic_kinetic/` — directed/two-stream electrons suppress drag but fail at ~2e2 `P_fusion` maintenance plus instability risk.
7. `surviving_optimizer/` — accepts the drag floor and identifies the ~584–600-keV / ~4%-fast-proton drag-recovery window.
8. `orbit_energy_routing/` — current result. Candidate-0 orbit size, wall clearance, classical-diffusion lower bound, and betaN volume screening are conditionally compatible with a narrow edge-biased reaction sheet, but the corrected residence remains multi-second and the existing electron-energy routing equations cannot meet the required recovery.

## Compression-semantics correction

`volume_compression_factor = 0.074` is an actuator/proxy magnitude in
`m3dc1_tct_hybrid_bridge.py`, not a remaining-volume fraction.

The previous `1/0.074 ~= 13.5x` density interpretation and `~0.76 s` residence
sensitivity are superseded.

Using the explicit selected `compression_amplitude_pct = 10%` only as a
particle-conserving geometric sensitivity gives about `1.23–1.37x` density and
about `8.35–7.52 s` residence.

## Current surviving geometry

For the 584-keV, 4%-fast-proton center, an edge-biased passing packet can fit
inside a few-centimeter reaction sheet with large LCFS clearance and remain
below the Candidate-0 `betaN = 2.7` volume screen.

However, the required burn-target residence still corresponds to roughly
2–3 million toroidal circuits. The selected handoff has `edge_racetrack = off`
and `racetrack_guidance_factor = 0`, so that residence is not validated.

## Current failing gate

Stage 7 requires 73.8% returned electron-drag energy.

- selected exhaust proxy: ~29.6%
- maximum reachable with the current repository channel/RF controls: ~68.4%
- required extraction at 92% conversion × 95% FF return: ~84.4%

The existing electron-channel equations therefore fail the routing gate.

Do **not** promote `pB11_net_delta` or ignition margin.

Next gate: explicit guiding-center orbit integration plus a redesigned
electron-energy collector model with independent extraction, conversion, and
return efficiencies.

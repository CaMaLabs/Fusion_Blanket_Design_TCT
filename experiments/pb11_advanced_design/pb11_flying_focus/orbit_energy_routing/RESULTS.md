# Orbit / Geometry + Collision-Energy Routing Audit — 2026-08-12

## Classification

**GEOMETRY_CONDITIONAL_PASS_RESIDENCE_AND_ROUTING_UPGRADE_REQUIRED**

This is Stage 8 of the p-B11 flying-focus falsification/optimization program. It takes the surviving `~0.58–0.60 MeV`, `n_fast/ne ~ 0.04` window and couples it to Candidate-0 geometry and the repository electron-channel routing formulas. It does **not** promote `pB11_net_delta`, ignition margin, or reactor net power.

## Compression-semantics correction

Inspection of `m3dc1_tct_hybrid_bridge.py` shows that `volume_compression_factor` is computed as a bounded actuator/proxy magnitude, not as a physical remaining-volume fraction. Therefore the previous Stage-7 sensitivity `1/0.074 ~= 13.5x density -> ~0.76 s residence` is **superseded**.

The selected scenario separately has `compression_amplitude_pct = 10%`. If that is used only as a particle-conserving geometric sensitivity:

- fixed-major-radius / cross-sectional compression: **1.235x density**;
- generous isotropic-linear upper sensitivity: **1.372x density**;
- corresponding inherited 23.033% burn-target residence: **8.35–7.52 s**.

Compression in the current repository therefore does not by itself solve the residence requirement.

## Candidate-0 geometry screen

Machine anchors are `R=5.5 m`, `a=1.8 m`, `B0=7.2 T`, `Ip=14 MA`, `kappa=1.9`, current `betaN_proxy=1.153`, and target `betaN=2.7`. The bridge fallback q-star formula gives `q* = 3.492`.

At `584 keV`, the full-perpendicular proton Larmor radius is about **1.53 cm**. The canonical Stage-8 geometry is constrained to the edge region (`r/a >= 0.80`). The best physical screening point is:

- center: **r/a = 0.80**;
- pitch: **5°**;
- passing-orbit half-width: **0.47 cm**;
- trapped-orbit comparison width: **0.82 cm**;
- reaction-sheet full width including a 1-cm steering margin: **2.93 cm**;
- LCFS clearance after orbit envelope + margin: **0.345 m**;
- channel volume fraction: **2.61%**;
- total betaN screen: **1.300 < 2.7**.

A narrow edge-biased passing-proton sheet is therefore not excluded by simple orbit width or volume-averaged betaN.

## Residence / orbit-loss requirement

The same point still requires:

- proton residence: **7.52 s**;
- toroidal circuits: **2.249e+06**;
- allowed loss probability per circuit for a 3% wall-loss budget: **1.355e-08**.

The selected handoff has `edge_racetrack = off` and `racetrack_guidance_factor = 0`, so `resonant_orbit_closure = strong` is not treated as physical proof of this lifetime.

The classical radial-diffusion lower-bound comparison is favorable:

- classical estimate: **3.856e-06 m²/s**;
- maximum diffusion compatible with the 3% screen: **4.833e-04 m²/s**;
- margin: **125.3x**.

That margin must still absorb ripple, turbulence, MHD/TCT events, charge exchange, steering error, and non-axisymmetric geometry. The added average fast-proton wall flux at the full 3% loss allocation is only about **0.122 kW/m²**; the difficult requirement is sustaining the tiny orbit-loss fraction, not average proton wall heating.

## Electron-energy routing fails with the current architecture

Stage 7 requires **73.8% of non-radiative electron-drag energy to be returned to the fast-proton loop**.

The selected repository state reproduces an electron-exhaust fraction of **29.6%**. Sweeping the existing electron-channel and RF-grating controls reaches only **68.4%**.

With 92% electron-energy conversion and 95% return-to-FF efficiency, the extraction requirement is **84.4%**.

At the best existing repository controls at 92% × 95%:

- returned electron-drag energy: **3.814 P_pB11**;
- residual fast-loop deficit: **0.895 P_pB11**;
- routing gate: **FAIL**.

Even perfect conversion and return cannot close the electron-only loop at the current ~68.4% extraction maximum. The hard 85% exhaust clamp would only barely clear the required chain at 92% × 95%, but the present equations cannot reach that clamp.

## Combined decision

- orbit-size / wall-clearance geometry: **conditional pass**;
- classical radial-diffusion lower bound: **conditional pass**;
- Candidate-0 betaN volume screen: **pass** for a narrow sheet;
- compression / residence: **unresolved**; corrected residence remains multi-second;
- electron-energy routing: **fail** with the current architecture.

The canonical Stage-8 classification is therefore:

**GEOMETRY_CONDITIONAL_PASS_RESIDENCE_AND_ROUTING_UPGRADE_REQUIRED**

A viable electron-only collector at the current operating center needs approximately **>=84% extraction × 92% conversion × 95% return-to-FF**. That is a new subsystem requirement, not a tuning of the present `electron_channel` knob.

## Next gate

Proceed in parallel with:

1. guiding-center orbit integration for the `~0.58–0.60 MeV` packet over the required multi-second residence, including ripple, pitch spread, TCT/event perturbations, and wall geometry;
2. a dedicated electron-energy-collector extension with independent extraction, direct-conversion, and return-to-FF efficiencies.

Only if both the long-orbit loss budget and the collector chain survive should this branch be promoted into the reactor surrogate.

## Claim boundary

- analytic guiding-center screening is not orbit integration;
- classical radial diffusion is a lower bound, not a transport prediction;
- the 3% wall-loss allocation is a screening budget;
- `electron_exhaust_fraction` is a surrogate extraction proxy, not measured energy recovery;
- the 10% compression density interpretations are bounded sensitivities, not validated compression;
- the Stage-7 13.5x compression interpretation is superseded;
- no p-B11 ignition or reactor-net-power claim is made.

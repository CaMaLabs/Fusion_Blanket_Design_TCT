# Corrected Flying-Focus Ignition Bridge — 2026-08-11

## Classification

**CONDITIONAL_IGNITION_ASSISTANCE_CANDIDATE**

The earlier cold-boron-film interpretation is rejected for this architecture. `be_outer_kill / be_outer_killer`, liquid lithium/current, and the magnetized/pulsed p-B11 channel must be kept distinct from cold-solid stopping.

## Architecture credit retained

- OpenMC 55-cm attenuation: `0.99971`; TBR: `2.2155`. This is blanket neutronics, not proton stopping.
- Liquid-wall proxy wall-load relief: `18.1%`; wall-temperature relief: `26.3%`; front-heating relief: `16.6%`.
- FAIR-MAST best control policy proxy loss reduction remains `51.5%`, but is not multiplied into the FF energy balance.

## What changed in the FF calculation

- Uses the 2026 Wang et al. analytic p-11B cross-section and a `sigma*v` exposure metric; finite-width target scan selects `600 keV`.
- Sweeps 1–50 keV effective energy loss per reaction encounter instead of assuming 20 keV is physical.
- Separates gross acceleration from recoverable deceleration during phase compression.
- Tests 0–100% phase-energy recovery and a 1–3x all-species collision-power burden.
- Keeps the repository's 23.033% burnup only as an explicit surrogate anchor.

## Key boundary

Under the peer-reviewed 2026 non-Maxwellian benchmark (+~25% fusion power at Ti≈300 keV under optimistic self-heating assumptions), FF becomes energetically plausible only when the reaction channel is genuinely low-loss and/or phase energy is strongly recovered. Exact thresholds are in `energy_balance_key_boundaries.csv`.

The result therefore **does not kill FF for this design**. It converts the problem into a measurable requirement: determine the actual keV lost per pass through the magnetized boron interaction region and the fraction of phase/deceleration energy that can be recovered.

## Next physics gate

Replace the unitless surrogate `boron_areal_density` with a physical boron density/areal-density and path-length profile, then calculate proton stopping/straggling in that hot magnetized region. That value decides whether FF merely raises reaction rate or actually improves ignition margin.

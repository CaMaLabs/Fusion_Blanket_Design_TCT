# p-B11 Flying-Focus Audit Status — 2026-08-11

This file is the canonical status note for the flying-focus work in this branch.
Earlier result directories are retained as provenance rather than rewritten.

## Audit sequence

1. `results/` — first-stage normalized resonance/rephasing study. It established that repeated rephasing, not narrow injection alone, is the useful FF mechanism. Its 675-keV target and user-swept 1–50 keV stopping values were exploratory.
2. `ignition_bridge/` — replaced the normalized resonance score with the Wang et al. 2026 cross-section and separated recoverable phase-compression energy from true stopping. It found a 600-keV optimum **when the Wang fit energy was inadvertently treated as proton lab energy**.
3. `physical_channel/` — current audit. It corrects the frame conversion, convolves the proton packet against the repository boron-ion temperature, and calculates classical hot-plasma Coulomb stopping from physical density/column variables.

## Current result

- rate-optimal FF packet: **~638 keV proton lab energy** at the current `Ti=55.358 keV`;
- path-optimal packet: **~616–618 keV lab**;
- physical boron column needed per effective pass to reconcile the current `419246.468` effective passes with the surrogate `23.033%` burnup: **~6.59e21 B-11 ions/m^2**;
- at current `Te=16.67 keV` and `lnLambda=15`, that column costs only tens to hundreds of eV per pass in boron-rich cases, not keV/pass;
- nevertheless, integrated Coulomb stopping still exceeds p-B11 fusion energy at the current electron temperature. The local fusion-energy / collisional-loss ratio is ~0.058 at `5 nB/ne=0.5`, ~0.089 at `0.75`, and ~0.122 at `1.0`.

## Interpretation

The `be_outer_killer` + liquid-lithium/current + TCT architecture remains valuable because it can suppress wall/transport losses and make very long material-avoiding recirculation physically more plausible. It does not directly suppress Coulomb energy transfer inside the reaction plasma.

Flying focus remains useful as a reaction-rate / phase-space actuator, but at the currently selected electron temperature it is not yet a self-powered p-B11 ignition mechanism. The next promotion gate is a kinetic electron/alpha power-flow model testing whether the actual non-Maxwellian electron distribution plus alpha-to-proton channeling can reduce the effective recirculating-power burden without paying the gain back in bremsstrahlung.

See `physical_channel/RESULTS.md` and `physical_channel/summary.json` for the current result.

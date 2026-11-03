# Physical p-B11 Flying-Focus Reaction-Channel Audit — 2026-08-11

## Classification

**PHYSICAL_CHANNEL_CONSTRAINT_IDENTIFIED**

This run replaces the unitless p-B11 `boron_areal_density` knob with a physical boron column and classical hot-plasma stopping calculation. It preserves the `be_outer_killer` / liquid-lithium / current / TCT architecture as transport-and-wall context, but does not use OpenMC attenuation as proton stopping suppression.

## Correct FF energy target

The Wang et al. 2026 cross-section uses **center-of-mass energy**. After transforming from a lab-frame proton packet and convolving the 3.7% FF packet with the repository's `Ti = 55.358 keV` boron Maxwellian:

- maximum reaction rate per time (`<sigma v>`) occurs at **638 keV lab**;
- maximum fusion probability per meter occurs at **~616–618 keV lab**;
- the rate-optimal packet samples mean center-of-mass energy near **591.3 keV**.

So the earlier 600-keV result was a frame-conversion error; the corrected operating target is roughly **0.64 MeV lab** for the current ion temperature.

## Physical density anchor

Candidate-0 gives `Ip=14 MA`, `a=1.8 m`, and Greenwald fraction `0.83`, which implies an electron-density anchor of **1.142e+20 m^-3**. Multiplying by the p-B11 surrogate's `density_norm=1.171` gives **1.337e+20 m^-3**, used only as a readable path-length anchor. The local energy merit below is essentially density-independent because both fusion probability and Coulomb stopping scale linearly with column density.

## What the current 419k-pass / 23.033% burnup surrogate would physically require

If both repository anchors are imposed literally, each effective pass would need a boron column of approximately:

- **6.592e+21 B-11 ions/m^2 per effective pass**;
- **1.205e-05 g/cm^2** B-11 mass areal density;
- fusion hazard **6.244e-07 per effective pass**.

At the repository temperature and `lnLambda=15`, that column costs approximately:

| Boron charge fraction `5 nB/ne` | Collision loss / effective pass | Fusion energy / collision loss |
|---:|---:|---:|
| 0.50 | 94.4 eV | 0.058 |
| 0.75 | 61.1 eV | 0.089 |
| 1.00 | 44.5 eV | 0.122 |

This is an important correction: **the relevant hot-plasma loss is tens to hundreds of eV per effective pass, not automatically keV/pass**. The material-avoiding racetrack architecture can therefore make the per-pass FF correction small.

## But the total ignition balance is still constrained

The same low column that gives low stopping also gives low fusion probability. At fixed composition and temperatures, raising density or interaction length increases fusion and Coulomb loss together. The density/path knobs therefore do not by themselves solve the local p-B11 energy balance.

At the current `Te=16.67 keV`, `Ti=55.358 keV`, and `lnLambda=15`:

- `5 nB/ne = 0.50`: fusion/collisional-loss merit = **0.058**;
- `5 nB/ne = 0.75`: merit = **0.089**;
- `5 nB/ne = 1.00`: merit = **0.122**.

A value above 1 is the bare minimum for local fusion energy to replace classical beam stopping at perfect conversion efficiency. None of the current-temperature cases reach it.

## The lever that does move the boundary

Electron drag dominates the current-temperature stopping budget. The sweep shows that making the interaction region **boron-rich** and reducing effective electron drag — in this classical Maxwellian model primarily by increasing the local electron velocity scale — can cross the local-energy boundary. See `temperature_thresholds.csv` for the exact `Te` threshold versus boron fraction and Coulomb logarithm.

That is a real design trade: hotter electrons reduce fast-proton drag but increase bremsstrahlung, so the next higher-fidelity model needs the actual electron distribution, not merely a scalar `Te`.

## What this means for flying focus

Flying focus still has a useful role: it can keep the proton packet near the corrected ~0.64-MeV rate optimum and counter small per-pass drift without intersecting dense material. But **at the currently selected electron temperature, it is an externally subsidized reaction-rate actuator, not yet a self-powered p-B11 ignition mechanism**.

The architecture can still improve total hybrid ignition margin through TCT confinement, wall-loss suppression, alpha extraction, direct conversion, and DT-assisted power flow. Those credits need to be combined in a full power-flow audit rather than hidden inside a proton stopping multiplier.

## Next gate

The decisive follow-up is a 0D/1D kinetic power-flow model using the actual non-Maxwellian electron distribution and alpha-channeling return path. That can test whether TCT electron exhaust + alpha-to-proton channeling lowers the **effective** electron drag/recirculating-power burden enough to cross the local merit boundary without paying it back in bremsstrahlung.

## Physics references

- H.-Y. Wang, Y.-Q. Li, Q. Wu, and Z.-F. Cui, *Revisiting p-11B Fusion: Updated Cross-sections, Reactivity, and Energy Balance*, arXiv:2601.00241 (2026).
- A. Beresnyak, *2023 NRL Plasma Formulary*, U.S. Naval Research Laboratory (2023), relaxation-rate section.
- S. Liu et al., *A zero-dimensional kinetic study of p-11B fusion gain via the non-Maxwellian proton distribution*, Plasma Physics and Controlled Fusion 68, 065045 (2026), DOI: 10.1088/1361-6587/ae72c9.

The Wang cross-section is used directly. The NRL relaxation formula is used as a classical Maxwellian stopping screen. Liu et al. is a higher-fidelity comparison target for the next non-Maxwellian power-flow step; its results are not multiplied into this audit.

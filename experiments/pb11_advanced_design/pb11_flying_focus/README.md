# p-B11 Flying-Focus Audit Program

This directory contains a staged falsification/optimization program for applying flying-focus (FF) proton acceleration and rephasing to the advanced p-B11 branch. It remains intentionally separate from `m3dc1_tct_hybrid_bridge.py`: results are promoted only after each physical power-flow gate survives.

## Current canonical result

**SURVIVING_FF_WINDOW_IDENTIFIED_DRAG_RECOVERY_REQUIRED**

The current program no longer assumes that electron drag can be cheaply suppressed. Both isotropic and directed electron-distribution approaches failed their recirculating-power gates. The surviving strategy is to accept classical drag, optimize p-B11 reaction probability and charged-particle return per unit drag, and ask whether the deposited collision energy can be recovered.

## Stage chronology

1. `results/` — resonance/rephasing screen. Repeated FF rephasing, not narrow injection by itself, is the useful mechanism.
2. `ignition_bridge/` — first energy-accounting bridge; retained for provenance.
3. `physical_channel/` — corrected center-of-mass/lab energy handling, physicalized the boron column, and calculated classical stopping.
4. `power_flow/` — conserved alpha power and identified electron drag as the dominant remaining burden.
5. `distribution_kinetic/` — isotropic sub-keV electron holes suppress drag but require ~2.2e3 `P_fusion` of distribution maintenance.
6. `anisotropic_kinetic/` — directed/two-stream electrons suppress drag more efficiently but still require ~2e2 `P_fusion` of maintenance and enter an instability-risk regime.
7. `surviving_optimizer/` — accepts the drag floor and optimizes FF energy, fast-proton fraction, alpha return, phase recovery, residence, compression, bremsstrahlung, and recoverable collision energy.

## Current FF operating targets

The physically useful FF setpoint depends on the objective:

- **~638 keV lab** — maximum `<sigma v>` / peak instantaneous reaction rate.
- **~616 keV lab** — maximum fusion probability per unit path.
- **~600 keV lab** — minimum classical collision burden plus fused-proton replacement per p-B11 fusion energy.
- **~584–600 keV lab with ~4% fast protons** — current hybrid compromise after adding the bremsstrahlung and drag-recovery gates.

The FF actuator should therefore be treated as programmable rather than assigned one immutable p-B11 target.

## Current promotion gate: recover the drag energy

At the recovery-gated center (`~584 keV`, `n_fast ~ 0.04 ne`) and using 90% alpha-to-fast-proton coupling, 95% FF phase-energy recovery, and the selected DT-alpha-assist cap, the reduced model requires approximately:

- **64.3% recovery of total non-radiative electron + boron collision energy**, or
- **73.8% recovery of the non-radiative electron-drag/exhaust stream alone**

to close the remaining fast-proton support deficit.

These are thresholds, not efficiencies credited to the design.

The same point has `P_brem/P_pB11 ~ 0.997`, so a fast-proton fraction near 4% is a natural reduced-model knee: lower beam fraction improves drag economy but lets bremsstrahlung exceed p-B11 fusion power density.

## Residence / compression requirement

Using the inherited 23.033% burn target only as a hazard target:

- readable density anchor (`ne ~ 1.34e20 m^-3`): **~10.3 s** proton residence;
- `419246` effective passes: **~260 m effective reaction path/pass**, **~45 eV/pass** collision loss;
- `100000` hardware passes: **~1090 m/pass**, **~190 eV/pass**.

A particle-conserving interpretation of the surrogate `volume_compression_factor = 0.074` corresponds to ~13.5x whole-channel density and reduces the residence target to **~0.76 s**, but raises the local beta=1-equivalent field to **~5.6 T** and the p-B11 power density to **~35 MW/m^3**. This is an engineering sensitivity, not a claim that the reactor achieves that compression.

## Claim boundary

- Wang et al. 2026 p-B11 cross section is evaluated in center-of-mass energy and convolved with the selected B-11 ion temperature.
- The 3.7% FF packet spread is an optimistic literature anchor, not a demonstrated 0.6-MeV reactor injector result.
- Classical Maxwellian stopping remains the drag floor; no magnetic or exotic-electron suppression multiplier is applied.
- OpenMC blanket attenuation is not proton stopping.
- DT-alpha assist is mapped from repository surrogate power ratios and is explicitly an opportunity cost, not free power.
- The 23.033% burn fraction is a surrogate anchor/target hazard, not a validated burn prediction.
- No reactor net-power or p-B11 ignition claim is made.

## Next gate

Build a coupled orbit/geometry + collision-energy-routing audit around the `~0.58–0.60 MeV`, `~4% fast-proton` window. A candidate must simultaneously preserve wall clearance and residence, achieve a defensible compression/dwell time, meet the 64–74% drag-recovery threshold, and remain compatible with TCT/MHD and liquid-lithium wall constraints before anything is promoted into the reactor surrogate.

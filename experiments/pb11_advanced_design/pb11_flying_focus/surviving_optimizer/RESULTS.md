# Surviving-Architecture Optimization — 2026-08-11

## Classification

**SURVIVING_FF_WINDOW_IDENTIFIED_DRAG_RECOVERY_REQUIRED**

This stage changes the optimization objective after both electron-distribution drag-cancellation routes failed. It does **not** attempt to suppress the classical electron-drag floor.

Instead it maximizes reaction probability and recoverable charged-particle value per unit of unavoidable drag while keeping p-B11 alpha power, DT-alpha assist, alpha-to-fast-proton coupling, fused-proton replacement, FF phase recovery, bremsstrahlung, direct conversion, and collision-deposited energy separate.

No increase to `pB11_net_delta` or the ignition proxy is authorized by this audit.

## The FF target is mode-dependent

The Wang-2026 cross-section convolved with the selected `Ti = 55.358 keV` B-11 distribution gives three distinct useful targets:

| Objective | Proton lab energy |
|---|---:|
| maximum `<sigma v>` / peak rate | **638 keV** |
| maximum fusion probability per path | **616 keV** |
| minimum classical drag + fused-proton replacement per fusion energy | **~600 keV** |

So `638 keV` remains the **rate-lock** target, while the **drag-economy** target is closer to `0.60 MeV`. The FF actuator should therefore be treated as programmable rather than assigned one immutable p-B11 setpoint.

## Corrected DT-alpha normalization

The prior power-flow screen normalized DT-alpha power to `pB11_alpha_yield = 2.363`. For physical energy accounting, the selected `pB11_gross_power = 3.28` is the more appropriate p-B11 energy denominator.

This stage therefore uses:

- gross DT-alpha / p-B11-gross ratio: **0.831**;
- after the selected 85% DT-alpha-assist cap: **~0.706** of the baseline p-B11-gross anchor;
- physical screening baseline at `638 keV`, `n_fast = 0.20 ne`: **~833 kW/m^3** p-B11 fusion power density.

This is more conservative than the prior hybrid screen.

## Natural fast-proton fraction knee

Quasineutrality is enforced as

`ne = n_fast + 5 nB`.

Reducing `n_fast/ne` improves fusion energy per unit drag because it leaves more positive charge available to boron, but at very small fast-proton fraction the p-B11 power density falls below bremsstrahlung.

The first combined optimum that minimizes the drag-recovery requirement while passing the simple gate `P_brem <= P_pB11` is:

- proton energy: **584 keV**;
- fast-proton density: **4.0% of ne**;
- `P_brem/P_pB11 = 0.997`;
- classical collision burden: **8.318 P_pB11**.

The bremsstrahlung break-even itself lies very close to 4% fast protons, so this is a physical knee in the reduced model rather than an arbitrary optimizer preference.

## Drag recovery is the constructive gate

At the `~584 keV`, `~4%` center, with 90% alpha-to-fast-proton coupling, 95% FF phase-energy recovery, and the selected DT-alpha assist:

- fast-loop deficit after p-B11 + DT alpha: **4.709 P_pB11**;
- non-radiative electron + boron drag available: **7.321 P_pB11**;
- non-radiative electron-drag/exhaust stream alone: **6.381 P_pB11**;
- required recovery of all non-radiative drag: **64.3%**;
- required recovery if only the electron-exhaust stream is usable: **73.8%**.

These are **promotion thresholds**, not efficiencies credited to the design.

This route is materially better than maintaining exotic electron distributions: the previous isotropic and directed distribution schemes required roughly `2e2–2e3 P_fusion` of phase-space maintenance. Here the collisions are accepted and their deposited energy is treated as a potentially recoverable stream.

## FF phase recovery is secondary

At the least-deficit `600 keV`, `4%` case:

- collision burden: **8.283 P_pB11**;
- fused-proton replacement: **0.069 P_pB11**;
- gross FF packet-shape lower bound: **0.0352 P_pB11**;
- after 95% phase recovery: **~0.0018 P_pB11**.

Thus FF phase-energy recovery remains useful, but moving from good to excellent recovery is second-order relative to collision-energy routing.

## Residence / density trade

At the readable density anchor (`ne ~ 1.34e20 m^-3`), the inherited 23.033% burn target requires about **10.3 s** of proton residence.

With the repository pass anchors:

- `419246` effective passes -> **~260 m** effective reaction path/pass and **~45 eV/pass** collision loss;
- `100000` hardware passes -> **~1090 m/pass** and **~190 eV/pass**.

The total residence/path requirement is effectively unchanged by how the path is segmented into passes.

If the surrogate `volume_compression_factor = 0.074` were interpreted optimistically as particle-conserving compression, the whole-channel density multiplier would be `~13.5x`:

- 23% burn residence: **~0.763 s**;
- beta=1 equivalent field for local thermal + fast-particle pressure: **~5.58 T**;
- local p-B11 fusion power density: **~34.6 MW/m^3**.

At `100x` density, residence falls to `~0.103 s`, but the beta=1 equivalent field rises to `~15.2 T` and local p-B11 power density to `~1.89 GW/m^3`. Density concentration is therefore a real residence lever, but rapidly becomes a pressure/heat-flux problem.

## Decision

The most defensible FF region is now a programmable band rather than one point:

- **~638 keV** for peak instantaneous reaction rate;
- **~616 keV** for maximum reaction probability per path;
- **~600 keV** for intrinsic drag economy;
- **~584–600 keV with ~4% fast protons** for the current hybrid drag-recovery / bremsstrahlung compromise.

The new bottleneck is explicit: can the electron-exhaust / charged-particle routing architecture recover roughly **64% of total non-radiative collision energy**, or roughly **74% of the electron-drag stream alone**, while preserving alpha return, TCT stability, and direct conversion?

Until that is demonstrated, the p-B11 branch remains a **hybrid-assisted candidate**, not a self-powered p-B11 ignition result.

## Next gate

Build an orbit/geometry + energy-routing audit centered on the `~0.58–0.60 MeV`, `~4% fast-proton` window. It must simultaneously test wall-free residence/path, defensible compression, the 64–74% drag-recovery threshold, and MHD/TCT/liquid-lithium compatibility. Only a case that passes all four should be handed back into the reactor surrogate.

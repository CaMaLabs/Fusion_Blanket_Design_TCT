# Distribution-Resolved Kinetic Audit — 2026-08-11

## Classification

**ISOTROPIC_ELECTRON_HOLE_RECIRCULATION_FAILS_POWER_GATE**

This is the first audit in this branch that uses an explicit non-Maxwellian
electron energy distribution for **both** fast-proton drag and bremsstrahlung.
It also enforces quasineutrality with the fast-proton minority included, charges
the kinetic energy of replacement protons consumed by fusion, and adds a
phase-space recirculation term for maintaining the narrow FF proton packet.

The result does **not** support promoting isotropic electron-hole shaping into
the reactor surrogate.

## Model

The electron distribution starts from the repository `Te = 16.67 keV`
Maxwellian and is modified by a smooth depletion of low-energy electrons.
Removed particles are re-injected into a low-keV shoulder, conserving electron
number. The same numerical distribution determines:

- the fraction of electrons slower than a `638 keV` proton, which controls the
  heavy-test-particle electron-drag term;
- the arbitrary-distribution bremsstrahlung moment;
- the e-e collisional relaxation that refills the depleted phase-space region.

The relaxation screen uses a projected energy-space operator that relaxes
toward a Maxwellian with the same particle number and mean energy. Number and
energy moments are projected out to machine precision. It is a reduced
Fokker-Planck-like screen, **not** a replacement for a full Landau operator.

## Why the sub-keV electron region matters

A `638 keV` proton moves at the same speed as an electron with only about
**0.3475 keV** kinetic energy. At the repository's `16.67 keV` electron
temperature, most electrons are already faster than the proton; the proton's
electron drag is controlled by the small slow-electron population.

That means a low-energy electron hole can strongly reduce proton drag without
raising the mean electron energy very much.

## Quasineutrality correction

The earlier boron-rich screening cases treated the fast proton packet as a test
population. This audit includes its charge explicitly:

`ne = n_fast + 5 n_B`

For the strongest screened case, `n_fast = 0.20 ne`, so the boron charge
fraction is `5 n_B / ne = 0.80`, not `1.0`.

This correction is retained in all results below.

## Baseline

For `n_fast = 0.20 ne` with the unmodified `16.67 keV` Maxwellian:

- collision burden = **10.015 P_fusion**
- fusion-consumed proton replacement = **0.0733 P_fusion**
- total useful proton-maintenance demand = **10.089 P_fusion**
- the selected p-B11 + DT-alpha channel cannot close that loop
- `P_brem / P_fusion = 0.205`

## Moderate depletion

A 50% depletion around a `0.35 keV` cutoff:

- cuts electron drag to **55.6%** of baseline;
- lowers proton-maintenance demand to **6.02 P_fusion**;
- still does not close the alpha-supported fast-proton loop;
- costs approximately **907 P_fusion** of gross electron phase-space
  recirculating power in the relaxation screen;
- leaves bremsstrahlung almost unchanged at `~0.205 P_fusion`.

This is consistent with the basic expectation that changing a small
low-energy part of the electron distribution can alter proton drag much more
strongly than it alters total bremsstrahlung.

## Deep-hole case

The least-bad loop-closed case in the sweep is:

- `n_fast = 0.20 ne`
- boron charge fraction `5 n_B/ne = 0.80`
- hole cutoff `0.50 keV`
- hole depth `99%`
- only **0.402%** of the electron population is moved into the shoulder
- mean electron energy remains approximately **25.007 keV** (`3/2 Te` scale)
- electron drag falls to **1.83%** of the original Maxwellian value
- collision burden falls to **1.018 P_fusion**
- adding burned-proton replacement gives **1.091 P_fusion** useful proton demand
- the p-B11 + selected DT-alpha channel **does close the proton loop**
- `P_brem/P_fusion = 0.205`

So the desired *drag physics* works.

The failure comes from maintaining the electron distribution:

- gross e-e phase-space recirculation: **2215.7 P_fusion**
- fast-proton self-shape recirculation: **0.203 P_fusion**
- total shape recirculation: **2215.9 P_fusion**
- direct-electric stream left after proton support: **0.688 P_fusion**
- required phase-space energy recovery to pay that recirculation from the
  remaining direct-electric stream: **99.96895%**
- alternatively, with no recovery, the repo DT-alpha wave-power density would
  need to be spatially concentrated by approximately **2260x**

Even `99.9%` phase-space energy recovery leaves about `2.22 P_fusion` of
unrecovered shape power, still larger than the `0.688 P_fusion` direct-electric
stream. The sign only becomes positive at about the `99.97%` level before any
other plant or confinement loads.

## Bremsstrahlung result

The low-energy hole barely changes bremsstrahlung because it moves less than
half a percent of the electrons and leaves the overall electron-energy moments
nearly unchanged.

That is helpful for separating the problem:

**the isotropic electron-hole concept fails because of collisional phase-space
refill power, not because the hole raises bremsstrahlung.**

## Validation

- Maxwellian electron drag factor: `1.0`
- Maxwellian electron-shape recirculation: `0.0`
- maximum projected particle-number residual: `< 4e-12 s^-1`
- maximum projected electron-energy residual: `< 1.2e-10 keV/s`
- same electron distribution used for drag and bremsstrahlung: yes
- fast-proton charge included in quasineutrality: yes
- fusion-consumed proton replacement energy included: yes
- alpha/direct-conversion partition remains conserved: yes

## Literature anchors

- Shujun Liu et al., *Plasma Physics and Controlled Fusion* 68, 065045 (2026),
  DOI `10.1088/1361-6587/ae72c9`: 0D isotropic Fokker-Planck treatment of
  non-Maxwellian p-B11 proton distributions and recirculating power.
- S. J. Liu et al., arXiv `2405.13260`: Rider-style nonthermal p-B11
  recirculating-power reassessment, including non-Maxwellian electron cases.
- I. E. Ochs et al., arXiv `2210.08076`: alpha channeling into fast/thermal
  protons as a p-B11 power-flow lever.
- C. Yang, K. Li, H. Xie, arXiv `2504.17191`: bremsstrahlung dependence on
  non-Maxwellian electron-distribution shape.
- H.-Y. Wang et al., arXiv `2601.00241`: updated p-B11 cross-section used by the
  upstream frame-corrected physical audit.

## Decision

**Do not promote isotropic low-energy electron-hole shaping.**

The previous `~70–100 keV Maxwellian-equivalent` closure window was useful for
identifying electron drag as the lever, but it did not charge the work required
to maintain an explicit electron distribution. Once that cost is included, the
isotropic solution fails by orders of magnitude.

## Remaining credible escape routes

The next useful calculations are narrower:

1. **anisotropic / directed electron phase-space control**, where velocity-space
   geometry rather than an isotropic speed hole reduces proton-electron drag;
2. a full Landau/Fokker-Planck solver with a physically specified RF/wave
   operator to determine whether the projected relaxation screen materially
   overstates the required recirculating power;
3. spatial alpha-power concentration into a very small reaction channel,
   because the current no-recovery requirement is a quantified `~2260x`;
4. magnetization-dependent collision physics only if the actual channel field
   enters a regime where classical unmagnetized collision coefficients cease to
   be adequate.

Until one of those survives, this result should **not** increase
`pB11_net_delta` or the reactor ignition proxy.

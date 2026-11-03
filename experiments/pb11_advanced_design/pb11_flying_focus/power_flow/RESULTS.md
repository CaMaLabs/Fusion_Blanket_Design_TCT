# Kinetic Power-Flow Audit — 2026-08-11

## Classification

**HYBRID_ALPHA_LOOP_CONDITIONAL_WINDOW_IDENTIFIED**

This audit closes the fast-proton maintenance loop downstream of the physical
reaction-channel calculation. It does **not** claim reactor ignition. It asks
whether the existing p-B11 alpha stream, the selected DT-alpha assist, and a
flying-focus proton packet can balance classical fast-proton drag while
conserving the alpha-energy partition.

## Structural correction to the existing surrogate

The current reactor bridge reports `alpha_capture_fraction = 0.98` and then
limits alpha-channeling power to the small residual thermalizing alpha fraction.
That is appropriate for a post-extraction thermalization channel, but it cannot
represent the Ochs/Kolmes/Fisch alpha-channeling concept, which redirects a
chosen fraction of energetic alpha power into protons *before* that energy is
thermalized or sent to direct conversion.

This audit therefore treats the p-B11 alpha power as one conserved stream:

`fusion alpha -> wave channeling to fast protons OR direct conversion OR residual heat/loss`

No alpha joule is counted twice.

## Current drag partition

At the frame-corrected `638 keV` proton target, `Te = 16.67 keV`,
`Ti = 55.358 keV`, `lnLambda = 15`, and the boron-rich limit:

- electron share of classical fast-proton drag: **89.610%**
- boron-ion share: **10.390%**
- collision power per p-B11 fusion-power unit: **8.182**
- local fusion/collision merit: **0.122**

This is why electron phase-space engineering is the dominant lever.

## Alpha-loop closure thresholds

The selected hybrid has enough DT fusion power that its gross DT-alpha power is
about **1.153x** the present p-B11 alpha-power proxy. The selected
`dt_alpha_assist_fraction = 0.85` is retained as a *maximum available assist*,
not treated as free energy.

In the boron-rich channel, using all captured p-B11 alpha plus up to the selected
85% DT-alpha assist, the **Maxwellian-equivalent local electron velocity scale**
needed to close the fast-proton drag loop is:

| alpha -> fast-proton transfer efficiency | closure Te |
|---:|---:|
| 60% | **112.1 keV** |
| 75% | **78.2 keV** |
| 90% | **62.2 keV** |

For comparison, p-B11 alpha alone does not close below 500 keV at 60% or 75%
transfer efficiency, and needs roughly **295 keV** even at 90% in this screen.

The key result is therefore **hybrid**, not pure p-B11: the DT-alpha stream
changes the required electron-drag suppression by a large amount.

## A useful candidate point

At `Te = 80 keV`, boron-rich composition, 90% alpha-to-fast-proton transfer,
and the selected DT-alpha assist:

- the fast-proton maintenance loop closes;
- only **63.8%** of the p-B11 alpha stream is needed for channeling;
- **36.2%** remains available for direct conversion;
- at the repository's staged 92% direct-conversion ceiling, that remainder is
  **0.326 electrical-energy units per p-B11 fusion-energy unit**
  before plant/confinement loads.

This does not mean that 80-keV electrons are desirable everywhere in the
reactor. It is a **local interaction-channel target** for the next kinetic model.

## Bremsstrahlung screen

Electron-tail suppression is kept separate from fast-proton drag suppression.
The literature supports reducing bremsstrahlung by modifying superthermal
electrons, but that is not automatically the same as reducing the collisional
drag on a 638-keV proton.

Using a simple optically-thin free-free screen and a minority fast-proton
population equal to 10% of `ne`, the boron-rich channel gives:

- 62 keV: `Pbrems/Pfusion = 0.721`
- 80 keV: `Pbrems/Pfusion = 0.819`
- 112 keV: `Pbrems/Pfusion = 0.969`

Thus the 60–100 keV closure region is **not automatically destroyed by
bremsstrahlung** at a ~10% minority fast-proton density. A 50% tail-radiation
suppression, if physically realizable, cuts these ratios in half in this
screening model.

## What is genuinely promising

The best current combined window is approximately:

- proton packet: **~0.64 MeV lab**
- boron charge fraction: **very high / boron-rich reaction channel**
- local electron velocity scale: **~70–100 keV equivalent**
- alpha -> fast-proton transfer: **~75–90%**
- DT-alpha assist: **up to the existing 85% surrogate setting**
- minority fast-proton density: **order 0.1 ne**
- electron-tail shaping: useful for bremsstrahlung, but not credited as drag
  suppression without a kinetic calculation

## Critical caveats

1. Raising a Maxwellian `Te` is only a proxy for lowering electron drag. The
   desired device may instead use a non-Maxwellian distribution; the next model
   must calculate that distribution directly.
2. Diverting DT alpha into the p-B11 fast-proton loop reduces DT alpha
   self-heating. The current DT margin is only context; this audit does not
   assume the diversion is free.
3. The fast-proton beam fraction is not yet represented self-consistently in
   quasineutrality or MHD pressure.
4. The free-free bremsstrahlung screen omits relativistic, Gaunt-factor,
   opacity, synchrotron, and detailed non-Maxwellian corrections.
5. The alpha-channel transfer efficiencies are sweep variables, not measured
   efficiencies for this geometry.
6. This is still not PIC/Fokker-Planck validation or an ignition claim.

## Next gate

The next genuinely higher-fidelity calculation is a reduced **0D/1D
Fokker-Planck-like distribution model** with:

- a 638-keV flying-focus proton source/rephaser,
- explicit electron distribution shaping rather than scalar `Te`,
- p-B11 and DT alpha source terms,
- wave-mediated alpha-to-proton energy transfer,
- electron drag and bremsstrahlung computed from the same distribution,
- DT-alpha diversion penalty,
- alpha/direct-conversion competition,
- ash removal and charged-particle exhaust.

Only if that model preserves a closed power loop should the result be promoted
back into `m3dc1_tct_hybrid_bridge.py`.

# Liquid Lithium Stabilization Literature Synthesis

This note translates three supplied literature directions into conservative,
testable reduced-model terms for the repository's liquid-lithium surface
stability module.

It does not claim that these mechanisms are validated for lithium, tokamak
walls, neutron environments, plasma-facing components, or TCT actuation.

## Source 1: Ionized-Gas / Plasma-Assisted Liquid-Surface Stabilization

Primary source:

- Park, Choe, Lee, Park, Kim, Moon, and Cvelbar, "Stabilization of liquid
  instabilities with ionized gas jets," *Nature* 592, 49-53 (2021),
  DOI: [10.1038/s41586-021-03359-9](https://doi.org/10.1038/s41586-021-03359-9),
  PubMed: [33790448](https://pubmed.ncbi.nlm.nih.gov/33790448/).

Relevant mechanism:

- A weakly ionized impinging gas jet can stabilize liquid-surface instabilities
  relative to a neutral gas jet.
- The reported mechanism is tied to electrohydrodynamic gas flow, often called
  electric wind, where charged-particle momentum transfer drives neutral gas and
  changes the interfacial forcing.
- The demonstrated working fluid was water, not lithium.

Conservative lithium mapping:

- Model as an `argon plasma / ion-wind surface-shear damping term`.
- Treat as boundary-layer damping and bubble/coalescence suppression only.
- Do not model it as direct proof of lithium compatibility, plasma-facing
  operation, sheath stability, or reactor wall stabilization.

Reduced-model hook:

```text
plasma_shear_damping > 0
bubble_coalescence_suppression += small contribution
```

Failure modes:

- Plasma shear too weak.
- Plasma forcing destabilizes rather than damps the interface.
- Plasma chemistry, sputtering, sheath effects, or heat loading dominate.
- Gas injection is incompatible with the target fusion boundary condition.

## Source 2: Liquid-Surface Stabilization and Cavitation/Bubble Suppression

Primary source:

- Ohashi, Lee, and Yamamoto, "Effects of surfactant and liquid surface
  stabilization on the initial growth of cavitation bubbles," *Japanese Journal
  of Applied Physics* 65, 03SP05 (2026),
  DOI: [10.35848/1347-4065/ae38ed](https://doi.org/10.35848/1347-4065/ae38ed).

Relevant mechanism:

- The abstract reports experiments with Ar-saturated water, sodium dodecyl
  sulfate, free surfaces, and stabilized liquid surfaces.
- Bubble growth was suppressed by surfactant and liquid-surface stabilization.
- The authors interpret initial bubble growth as governed primarily by
  coalescence rather than rectified diffusion.

Conservative lithium mapping:

- Lithium does not use water surfactant chemistry, so the model must not import
  SDS physics directly.
- The transferable idea is only the suppression of bubble/cavity coalescence by
  surface stabilization or boundary modification.
- Model as a `bubble/cavity coalescence suppression term`.

Reduced-model hook:

```text
bubble_coalescence_suppression > 0
bubble_coalescence_risk_score decreases
```

Failure modes:

- Cavities form from vapor blanketing, impurity gas, boiling, or MHD forcing
  faster than the stabilizing mechanism can suppress coalescence.
- The stabilizing layer dries out or saturates.
- Surface stabilization reduces bubble coalescence but worsens heat transfer or
  retention.

## Source 3: Leidenfrost / Vapor-Layer Stability and Surface Texture

Supplied report:

- PatSnap Eureka, "Leidenfrost Dynamics: Best Nano-Textures for Surface
  Stabilization" (2026),
  [report link](https://eureka.patsnap.com/report-leidenfrost-dynamics-best-nano-textures-for-surface-stabilization).

Technical anchor used for conservative mapping:

- Kwon, Bird, and Varanasi, "Increasing Leidenfrost point using micro-nano
  hierarchical surface structures," *Applied Physics Letters* 103, 201601
  (2013), DOI: [10.1063/1.4828673](https://doi.org/10.1063/1.4828673).

Relevant mechanism:

- Leidenfrost vapor layers can decouple liquid from a hot solid surface and
  strongly reduce direct heat transfer.
- Surface micro/nanotexture changes vapor-layer behavior and rewetting.
- The APL work frames the transition as a competition between capillary wetting
  pressure and dewetting vapor pressure, and reports that hierarchical textures
  can raise the Leidenfrost point by promoting capillary wicking/rewetting.

Conservative lithium mapping:

- Model favorable texture as `microtexture wetting / rewetting` and
  `capillary/porous substrate stabilization`.
- Model unfavorable hot-surface conditions as a `vapor-film or Leidenfrost
  penalty`.
- Do not claim that water-droplet Leidenfrost results transfer quantitatively to
  molten lithium, magnetic fields, neutron damage, plasma heat flux, or PFC
  chemistry.

Reduced-model hook:

```text
microtexture_wetting > 0
rewetting_strength > 0
capillary_stabilization > 0
vapor_film_penalty increases when heat flux/dryout is high
```

Failure modes:

- High heat flux overwhelms capillary rewetting.
- Texture geometry traps vapor rather than enabling rewetting.
- Porous substrate saturates, clogs, or dries out.
- Lithium wetting/contact-angle behavior differs from the water/silicon analogy.

## Reduced-Model Interpretation

The implemented module intentionally separates:

- **Physical claims:** the cited papers demonstrate stabilization mechanisms in
  their own systems.
- **Reduced-model assumptions:** the repo maps those mechanisms to damping,
  capillary retention, rewetting, vapor-risk, and bubble-risk scalar terms.
- **Speculative extrapolations:** applying these terms to liquid lithium in a
  fusion setting is a bench-test hypothesis, not a validation result.

Conservative conclusion:

> The reduced model supports prioritizing capillary/porous confinement, wetting
> microtexture, inert-gas/plasma boundary damping, and magnetic damping for
> follow-up bench testing. It does not show that liquid lithium is stabilized in
> a reactor.

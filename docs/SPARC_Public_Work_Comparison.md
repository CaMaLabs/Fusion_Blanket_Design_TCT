# SPARC / ARC Public Work Comparison for TCT

This note extracts useful public-facing research patterns from Commonwealth Fusion Systems / MIT SPARC and ARC publications and maps them into a cleaner validation path for this repository.

The goal is not to copy proprietary work. The goal is to learn from the public structure of a credible fusion program: baseline physics, narrowly scoped claims, measurable validation targets, explicit uncertainty, and staged hardware risk reduction.

## Executive positioning

TCT should be framed as an **auxiliary stability-control and edge-response shaping hypothesis**, not as a complete alternative reactor architecture.

Recommended one-line framing:

> TCT is proposed as an auxiliary plasma-edge and current-sheet control concept to be tested against conventional tokamak baselines using public equilibrium, MHD, transport, and neutronics validation workflows.

This framing is intentionally conservative. It makes the concept easier to test, easier to criticize constructively, and harder to dismiss as an unsupported reactor claim.

## What to borrow from SPARC-style public validation

| SPARC / ARC public pattern | Why it works | TCT repository adaptation |
| --- | --- | --- |
| Start from a recognizable tokamak baseline | Reviewers know what is being perturbed | Treat TCT as an add-on to a conventional equilibrium, not a replacement for tokamak confinement |
| Publish physics basis separately from plant extrapolation | Prevents speculative engineering from weakening core physics claims | Split TCT stability claims from wall, blanket, direct-conversion, and plant-level speculation |
| Use named validation buckets | Makes progress auditable | Maintain separate docs for MHD stability, edge exhaust, neutronics, transport, and failure modes |
| Quantify uncertainty and failure modes | Shows seriousness | Add thresholds where TCT is too weak, useful, or harmful |
| Emphasize simulation-before-hardware | Reduces credibility risk | Require BOUT++ / M3D-C1 / FreeGSNKE-style checks before strong claims |
| Compare to known control methods | Gives context | Compare TCT against resonant magnetic perturbation coils, error-field correction coils, liquid metal wall concepts, and edge-localized-mode mitigation |

## Concept separation

TCT-related ideas should be separated into tiers so speculative pieces do not contaminate the more defensible plasma-control work.

### Tier A — most defensible

- Edge-response shaping
- Current-sheet / reconnection-region control hypothesis
- ELM / plasmoid / locked-mode mitigation analogies
- Perturbation-field optimization
- Validation against known MHD baselines

### Tier B — plausible but needs stronger modeling

- Lithium-facing-wall coupling
- Conductive wall / liquid-metal response effects
- Blanket / first-wall survivability optimization
- Event-severity reduction as an engineering objective

### Tier C — speculative and should be quarantined

- Direct alpha/electron energy extraction
- Graphene channel charge separation
- Full reactor plant extrapolation
- Claims of net power improvement from TCT without validated plasma transport support

## Public-work insight: correction-field logic

A useful public SPARC-adjacent lesson is that modern tokamak control is not only about stronger confinement fields. It is also about small, optimized, non-axisymmetric correction fields that prevent error fields, locked modes, or edge instabilities from growing into machine-limiting events.

TCT should be tested in that same conceptual lane:

1. Define a baseline axisymmetric equilibrium.
2. Introduce a controlled TCT perturbation or boundary response term.
3. Sweep perturbation amplitude, phasing, geometry, and response time.
4. Measure whether instability metrics improve or degrade.
5. Identify operating windows rather than claiming universal benefit.

## Required TCT validation metrics

A serious TCT claim should report at least these metrics:

| Metric | Desired direction | Notes |
| --- | --- | --- |
| Linear growth rate of target instability | Down | Primary stability metric |
| Mode amplitude after perturbation | Down or bounded | Must not simply move instability elsewhere |
| Core confinement proxy | No major degradation | TCT should not improve edge stability by destroying confinement |
| Edge heat-flux peaking | Down | Especially important for first-wall relevance |
| Reconnection / plasmoid proxy | Down or delayed | Relevant to TCT naming and hypothesis |
| Required field/current amplitude | Physically plausible | Avoid impossible coil/current assumptions |
| Sensitivity to alignment/tolerance | Low or bounded | Credibility depends on manufacturable tolerances |
| Failure-mode severity | Characterized | Must document when TCT makes behavior worse |

## Practical validation matrix

| Phase | Tool / method | Output artifact | Pass condition |
| --- | --- | --- | --- |
| 0 | Literature mapping | `docs/SPARC_Public_Work_Comparison.md` | TCT claims separated into Tier A/B/C |
| 1 | Analytic toy model | `docs/TCT_Physics_Basis.md` | Mechanism written in equations/variables, not only prose |
| 2 | Equilibrium baseline | FreeGSNKE / EFIT-like GEQDSK | Reproducible reference equilibrium committed |
| 3 | Edge/MHD perturbation scan | BOUT++ or M3D-C1 bridge | Growth-rate or mode-amplitude comparison vs baseline |
| 4 | Neutronics / blanket check | OpenMC | TBR, shielding, heat deposition, leakage metrics |
| 5 | Failure-mode report | Markdown + result JSON | Cases where TCT degrades performance are explicitly listed |
| 6 | Bench analog | Low-energy plasma / field visualizer | Qualitative field-response demo only, no reactor claim |

## Language to avoid

Avoid:

- “TCT solves fusion.”
- “Graphene channels extract alpha energy” as a main claim.
- “Plasmoid marginality” unless carefully defined.
- “Validated reactor” without high-fidelity support.
- Any implication that blanket optimization proves plasma stability.

Use instead:

- “TCT is a testable auxiliary control hypothesis.”
- “This repository screens candidate mechanisms before high-fidelity validation.”
- “The present results are exploratory until benchmarked against external MHD and neutronics workflows.”
- “The goal is to identify whether a bounded operating window exists where structured perturbations improve edge stability without unacceptable confinement penalty.”

## Near-term repository priorities

1. Add a short TCT physics-basis document.
2. Add a validation matrix with named pass/fail criteria.
3. Add a baseline GEQDSK / equilibrium placeholder or fixture.
4. Keep OpenMC blanket work clearly separate from MHD stability work.
5. Add a `failure_modes.md` document before making stronger claims.
6. Add result JSON schemas so future validation runs are machine-readable.

## Bottom line

The strongest path is not to present TCT as a finished reactor idea. The strongest path is to present it as a measurable perturbation-control hypothesis inspired by real tokamak stability-control problems.

That makes the work easier to compare with SPARC-like public validation, easier to simulate, easier to defend, and easier for outside plasma physicists to engage with.

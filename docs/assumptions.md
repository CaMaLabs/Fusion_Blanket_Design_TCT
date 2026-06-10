# Assumptions Registry

This document collects assumptions that must be visible to reviewers before any result is treated as evidence.

Status labels:

- **Implemented**: represented in code or committed outputs.
- **Literature-derived**: based on external published work, not yet independently reproduced here.
- **Estimated**: engineering estimate or placeholder.
- **Speculative**: hypothesis-level and not yet validated.
- **Falsification target**: should be tested early because failure would redirect or weaken the concept.

## Plasma / edge-control assumptions

| Assumption | Current status | Why it matters | First falsification path |
|---|---:|---|---|
| Current-sheet thinning, aspect ratio, or plasmoid marginality may be useful variables for describing some damaging edge/reconnection event pathways. | Speculative / falsification target | This is the core TCT framing. | Ask an MHD / reconnection reviewer whether the framing maps cleanly to a reduced benchmark before using tokamak-scale language. |
| A TCT-style control proxy can be represented in screening code before high-fidelity nonlinear MHD validation. | Implemented as proxy / speculative physically | The code can screen ideas, but proxy validity is unproven. | Compare proxy behavior against a simple reduced-MHD or reconnection benchmark. |
| ELM-like event severity can be usefully connected to pre-event edge-current or reconnection conditions. | Speculative | Links TCT framing to tokamak edge stability. | Reformulate in standard peeling-ballooning / pedestal / RMP / SOL-divertor terms and check whether thickness language adds value. |

## Blanket / wall assumptions

| Assumption | Current status | Why it matters | First falsification path |
|---|---:|---|---|
| Candidate blanket stacks can be screened by simplified optimizer variables before full neutronics validation. | Implemented as screening | Enables rapid search, but can mislead if constraints are weak. | Re-run a small set of finalists in an explicit OpenMC-style model or comparable benchmark. |
| Liquid-lithium or lithium-coupled wall behavior can be included as an engineering/control variable. | Speculative / estimated | Wall handling is central to survivability and edge coupling. | Separate wall survivability from MHD claims; check heat flux, evaporation, compatibility, and maintenance constraints independently. |
| The wall / blanket stack can survive realistic heat and neutron loads. | Not validated | This is a hard engineering constraint. | Build an explicit heat-flux and material survivability checklist before claiming reactor relevance. |
| Tritium breeding ratio can remain acceptable under final geometry. | Not validated | DT blanket feasibility depends on it. | Run finalist geometries through explicit neutronics validation before using TBR in claims. |

## Software / reproducibility assumptions

| Assumption | Current status | Why it matters | First falsification path |
|---|---:|---|---|
| Public repository structure is sufficient for an outside reviewer to understand scope and claims. | In progress | Visibility is useless if the repo is hard to review. | Ask reviewers to follow the 5-minute and 30-minute review paths and report blockers. |
| Lightweight CI smoke checks help establish basic repository health. | Implemented | CI does not validate physics, but it signals maintainability. | Keep CI limited to syntax / lightweight checks unless heavyweight dependencies are explicitly supported. |
| The pipeline can be generalized beyond TCT. | Planned | Funding and collaboration are stronger if the pipeline is broadly useful. | Demonstrate a second non-TCT benchmark or validation handoff path. |

## Rules for interpreting outputs

- Screening outputs are not validation.
- CI success is not physics validation.
- Optimizer finalists are candidates, not designs.
- TCT is a hypothesis-level framing until mapped to accepted MHD / edge-stability variables or rejected by a benchmark.
- Negative results should be preserved because they improve the validation pipeline.

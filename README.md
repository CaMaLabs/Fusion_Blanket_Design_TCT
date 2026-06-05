# Fusion Engine v5 / Fusion Blanket Design with TCT

This repository is Chase Lunsford's public research workspace for fusion blanket optimization and thickness-controlled tokamak (TCT) concept exploration.

The project combines a plasma/plant optimizer, blanket design search, TCT/plasmoid-control proxies, wall-event modeling, lithium-wall thermal handling, and OpenMC-style finalist validation workflows.

## Citation / attribution

If this repository, its concepts, simulation structure, candidate geometries, validation workflow, or documentation influence downstream work, please cite or link back to this repository and credit:

> Chase Lunsford / `@chaseakat`  
> Fusion Blanket Design with TCT  
> https://github.com/CaMaLabs/Fusion_Blanket_Design_TCT

Citation metadata is provided in [`CITATION.cff`](CITATION.cff). Provenance details are provided in [`PROVENANCE.md`](PROVENANCE.md).

## Current status

This is an active independent research and simulation repository. It should be read as a computational research workspace, not as a finished reactor design or validated engineering claim.

Current emphasis:

- explore blanket candidates and control-coupled operating regimes,
- separate speculative concept work from simulation outputs,
- preserve reproducible scripts and result files,
- identify candidates worthy of higher-fidelity validation,
- and bridge the strongest candidates into external validation workflows such as OpenMC and M3D-C1-style plasma validation.

## Research purpose

The central research question is whether a fusion reactor design can improve stability and survivability by combining:

- a liquid-lithium-facing wall or lithium-coupled first-wall layer,
- solid breeder / multiplier / armor blanket stacks,
- TCT-style current-sheet thickness control for plasmoid/reconnection suppression,
- event-severity reduction as a design objective,
- and neutronics / power-balance validation of promising blanket candidates.

This repo is intended to preserve the development path, code, assumptions, and candidate designs in a timestamped public form.

## Validation and public positioning

TCT is currently treated as an exploratory auxiliary-control hypothesis. Specific results should be interpreted according to the validation levels in [`docs/TCT_Validation_Matrix.md`](docs/TCT_Validation_Matrix.md).

Public wording and scope guidance are maintained in [`docs/TCT_Public_Positioning.md`](docs/TCT_Public_Positioning.md).

## What is validated vs. exploratory

### More concrete / implemented

- Python-based optimizer and simulation workflows.
- Integrated design variables for blanket, wall, plasma, TCT, and plant-power proxies.
- Candidate scoring and filtering logic.
- Explicit-layer validation concepts for finalist blanket candidates.
- Reproducible scripts and committed outputs where available.

### Exploratory / hypothesis-level

- Whether TCT-style current-sheet thickness control can be engineered into a practical tokamak control mechanism.
- Whether lithium-current coupling provides useful stabilizing leverage in the real plasma edge.
- Whether the best optimizer candidates survive high-fidelity neutronics and MHD validation.
- Whether event-severity reductions translate into reactor-level reliability improvements.

## Provenance

Author / researcher: Chase Lunsford (`@chaseakat`).

This repo was made public to establish visible provenance for the fusion blanket / TCT research path. The commit history, scripts, candidate files, and README notes should be treated as part of the public timestamped record of development.

See [`PROVENANCE.md`](PROVENANCE.md) for the full provenance note.

## Settings

- Population size: 64
- Generations: 30
- Top 5 validated each generation
- OpenMC batches: 80
- OpenMC particles: 300000

## Run

```bash
pip install -r requirements.txt
python run_reactor_optimizer.py
```

## Notes

- Every design includes plasma + blanket + TCT + wall + plant variables.
- Top 5 each generation go through explicit-layer OpenMC validation.
- The rest use the fast surrogate to keep runtime manageable.
- Results should be interpreted as screening outputs until independently validated.

## Suggested reading order

1. Start with this README.
2. Review [`PROVENANCE.md`](PROVENANCE.md) and [`CITATION.cff`](CITATION.cff).
3. Read [`docs/TCT_Public_Positioning.md`](docs/TCT_Public_Positioning.md).
4. Read [`docs/TCT_Validation_Matrix.md`](docs/TCT_Validation_Matrix.md).
5. Inspect optimizer and candidate-generation scripts.
6. Review committed result files and finalist candidates.
7. Compare finalist assumptions against higher-fidelity OpenMC / M3D-C1 validation work.

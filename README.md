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

This repository is a conceptual and computational design study, not a demonstrated reactor design.

Validated / implemented:

- Open repository structure for blanket / TCT design notes.
- Python-based optimizer and simulation workflows.
- Initial geometry and material-stack assumptions.
- Integrated design variables for blanket, wall, plasma, TCT, and plant-power proxies.
- Candidate scoring and filtering logic.
- Explicit-layer validation concepts for finalist blanket candidates.
- Reproducible scripts and committed outputs where available.
- Draft reproducibility path for testing assumptions against higher-fidelity validation workflows, including OpenMC-style neutronics and companion M3D-C1/BOUT++/FreeGSNKE validation work.

Speculative / not yet validated:

- Net stabilization effect of the proposed TCT geometry.
- Practical alpha / electron channel separation.
- Full thermal survival of the proposed wall stack.
- Tritium breeding ratio under final geometry.
- Manufacturability of ribbed / channeled structures.
- Whether TCT-style current-sheet thickness control can be engineered into a practical tokamak control mechanism.
- Whether lithium-current coupling provides useful stabilizing leverage in the real plasma edge.
- Whether event-severity reductions translate into reactor-level reliability improvements.

## Project roadmap and funding alignment

- [`VALIDATION_STATUS.md`](VALIDATION_STATUS.md) gives the current validation-status matrix and claim boundaries.
- [`ROADMAP.md`](ROADMAP.md) frames the repository as a validation and reproducibility pipeline for fusion concept screening.
- [`FUNDING.md`](FUNDING.md) maps the pipeline to realistic SBIR/STTR, INFUSE-style partnership, AI-for-science, and later-stage funding paths.
- [`ARCHIVE_INDEX.md`](ARCHIVE_INDEX.md) explains how historical logs, backups, generated outputs, and validation-run folders should be interpreted without deleting provenance.
- [`docs/assumptions.md`](docs/assumptions.md) lists the assumptions that need review before any result is interpreted as evidence.
- [`docs/falsification_tests.md`](docs/falsification_tests.md) defines tests that could reject, redirect, or narrow the TCT framing.
- [`docs/benchmark_targets.md`](docs/benchmark_targets.md) lists candidate benchmark directions for MHD, blanket, and wall validation.

The recommended external framing is:

> Open-source validation and reproducibility pipeline for fusion concept screening and handoff to higher-fidelity neutronics and MHD workflows.

TCT is the first demonstration case. The pipeline should be evaluated independently of whether the specific TCT hypothesis survives later validation.

## What I am looking for

I am looking for technical critique on:

1. plasma stability assumptions,
2. blanket neutronics / TBR assumptions,
3. heat-flux handling,
4. material survivability,
5. validation strategy.

The most useful response would be to identify a wrong assumption, suggest a better simulation path, point to a benchmark case, or open an issue with a falsification test.

For a narrowly scoped DIII-D diagnostic collaboration request, review:

- [`validation_runs/diiid_diagnostic_reconstruction_default/DIIID_LIMITED_DATA_ACCESS_REQUEST.md`](validation_runs/diiid_diagnostic_reconstruction_default/DIIID_LIMITED_DATA_ACCESS_REQUEST.md)
- [`validation_runs/diiid_diagnostic_reconstruction_default/diiid_diagnostic_reconstruction_report.md`](validation_runs/diiid_diagnostic_reconstruction_default/diiid_diagnostic_reconstruction_report.md)
- [`validation_runs/diiid_diagnostic_reconstruction_default/diagnostic_replacement_contract.json`](validation_runs/diiid_diagnostic_reconstruction_default/diagnostic_replacement_contract.json)

## Fast technical review path

If you have 5 minutes:

1. Read this README.
2. Read [`VALIDATION_STATUS.md`](VALIDATION_STATUS.md).
3. Read [`docs/assumptions.md`](docs/assumptions.md).
4. Read [`docs/falsification_tests.md`](docs/falsification_tests.md).

If you have 30 minutes:

1. Review [`ROADMAP.md`](ROADMAP.md).
2. Review [`docs/benchmark_targets.md`](docs/benchmark_targets.md).
3. Review [`ARCHIVE_INDEX.md`](ARCHIVE_INDEX.md) before interpreting historical logs or generated outputs.
4. Review the proposed wall / blanket stack assumptions.
5. Review the magnetic / electrostatic channeling assumptions.
6. Inspect optimizer and candidate-generation scripts.
7. Compare finalist assumptions against higher-fidelity OpenMC / M3D-C1 validation work.

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

## Provenance

Author / researcher: Chase Lunsford (`@chaseakat`).

This repo was made public to establish visible provenance for the fusion blanket / TCT research path. The commit history, scripts, candidate files, and README notes should be treated as part of the public timestamped record of development.

See [`PROVENANCE.md`](PROVENANCE.md) for the full provenance note. See [`ARCHIVE_INDEX.md`](ARCHIVE_INDEX.md) before interpreting historical logs, backups, generated outputs, or preliminary validation-run folders.

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
2. Read [`VALIDATION_STATUS.md`](VALIDATION_STATUS.md).
3. Read [`docs/assumptions.md`](docs/assumptions.md), [`docs/falsification_tests.md`](docs/falsification_tests.md), and [`docs/benchmark_targets.md`](docs/benchmark_targets.md).
4. Review [`ROADMAP.md`](ROADMAP.md) and [`FUNDING.md`](FUNDING.md).
5. Review [`PROVENANCE.md`](PROVENANCE.md), [`ARCHIVE_INDEX.md`](ARCHIVE_INDEX.md), and [`CITATION.cff`](CITATION.cff).
6. Read [`docs/TCT_Public_Positioning.md`](docs/TCT_Public_Positioning.md).
7. Read [`docs/TCT_Validation_Matrix.md`](docs/TCT_Validation_Matrix.md).
8. Inspect optimizer and candidate-generation scripts.
9. Review committed result files and finalist candidates.
10. Compare finalist assumptions against higher-fidelity OpenMC / M3D-C1 validation work.

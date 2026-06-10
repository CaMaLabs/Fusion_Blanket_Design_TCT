# Archive Index

This repository intentionally preserves historical outputs, logs, backups, and intermediate validation artifacts as part of the public provenance record.

Files listed here are not necessarily current recommended entry points. They are retained so the development path remains auditable.

## How to interpret archived material

- Archived files are evidence of development history, not final validation.
- Logs and old outputs may contain failed runs, stale assumptions, or superseded parameters.
- Backup files are retained for provenance unless explicitly superseded by a documented cleanup commit.
- Current reviewer-facing interpretation should start from `README.md`, `ROADMAP.md`, `docs/assumptions.md`, `docs/falsification_tests.md`, and `docs/benchmark_targets.md`.

## High-level categories

### Historical run logs

Examples:

- `run.log`
- `overnight_campaign.log`
- `evo_blanket_search_v5.out`

Interpretation:

These are historical execution traces. They may be useful for reconstructing development decisions, but they should not be treated as curated validation reports.

### Generated optimizer outputs

Examples:

- `gen_*/leaderboard.csv`
- `gen_*/pareto_front.json`
- `gen_*/reactor_*.json`

Interpretation:

These are screening artifacts from optimizer campaigns. They identify candidate configurations and search behavior, but they are not final reactor designs or high-fidelity validation results.

### Backup / recovery files

Examples:

- `*.bak`
- `*.broken`
- timestamped backup files

Interpretation:

These preserve the development path. They may contain superseded or broken code. Reviewers should not assume backup files are active code paths.

### Validation-run folders

Examples:

- `validation_runs/bout_controlled_sweep_default/`
- `validation_runs/bout_robustness_sweep_default/`
- `validation_runs/m3dc1_bout_cross_validation_default/`

Interpretation:

These folders contain preliminary scaffolding and outputs for validation directions. They should be read with the limitations described in `docs/benchmark_targets.md` and `docs/falsification_tests.md`.

## Current review entry points

Use these first:

1. `README.md`
2. `ROADMAP.md`
3. `docs/assumptions.md`
4. `docs/falsification_tests.md`
5. `docs/benchmark_targets.md`
6. `docs/TCT_Public_Positioning.md`
7. `docs/TCT_Validation_Matrix.md`
8. `FUNDING.md`

## Cleanup policy

Do not delete historical files merely because they are messy. Prefer one of these approaches:

1. Document the file here.
2. Mark it as historical / superseded in a nearby README.
3. Move future generated outputs into `validation/results/` or another documented output directory.
4. Only delete files when they are duplicate noise, generated cache files, or clearly unrelated to provenance.

## Future organization target

Future commits should gradually move toward this structure:

```text
README.md
ROADMAP.md
FUNDING.md
ARCHIVE_INDEX.md
PROVENANCE.md
CITATION.cff

docs/
  assumptions.md
  falsification_tests.md
  benchmark_targets.md
  TCT_Public_Positioning.md
  TCT_Validation_Matrix.md

fusion_engine_v5/
  ... active package code ...

scripts/
  ... runnable utilities and validation runners ...

validation/
  manifests/
  results/
  reports/

validation_runs/
  ... historical and preliminary run outputs ...
```

The goal is not to erase the messy history. The goal is to make clear which files are current, which are historical, and which claims remain unvalidated.

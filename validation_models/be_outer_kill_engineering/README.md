# `be_outer_kill` Engineering-Degradation Validation Family

This validation family is intentionally downstream of the existing idealized
`be_outer_kill` blanket ordering work. It does **not** replace or modify the
historical baseline scripts.

## Question

How much do explicit engineering parasitics degrade the local idealized
`be_outer_kill` OpenMC control when structure, coolant channels, radial ports,
and shielding consume real geometry?

The frozen material order is:

```text
plasma -> liquid Li -> Be -> Li2O -> Li2O -> W-Ti-B4C -> Be -> outer shield
```

The control omits engineering parasitics. Three sensitivity cases progressively
add:

- reduced ferritic-steel structural skins inside each radial layer,
- explicit helium coolant channels,
- finite radial port voids,
- a borated-steel outer shield,
- declared breeder-packing and Li-6-enrichment sensitivity factors.

These are **sensitivity assumptions**, not claimed final CAD dimensions.

## Ubuntu usage

From the repository root with the OpenMC environment active:

```bash
bash run_be_outer_kill_engineering.sh --plan-only --check
```

That performs a dependency-free plan/smoke check without launching transport.

Run the default OpenMC matrix:

```bash
bash run_be_outer_kill_engineering.sh
```

The default matrix is four geometry cases x three deterministic transport seeds,
with 8,000 particles per batch and 20 batches per seed. Override as needed:

```bash
bash run_be_outer_kill_engineering.sh \
  --particles 20000 \
  --batches 40 \
  --seeds 104729,130363,169087,196613
```

Run only the nominal engineering case:

```bash
bash run_be_outer_kill_engineering.sh \
  --case engineering_nominal \
  --seeds 104729,130363,169087
```

If `OPENMC_CROSS_SECTIONS` is not already set, provide it explicitly:

```bash
bash run_be_outer_kill_engineering.sh \
  --cross-sections /path/to/cross_sections.xml
```

## Outputs

Default output root:

```text
validation_runs/be_outer_kill_engineering_default/
```

Key artifacts:

- `engineering_plan.json` — exact frozen geometry/sensitivity assumptions.
- `engineering_seed_results.csv` — per-seed TBR, tally uncertainty, radial flux,
  heating and port/shield diagnostics.
- `engineering_case_summary.csv` — seed-aggregated results and degradation versus
  the idealized control.
- `engineering_summary.json` — compact machine-readable summary.
- `BE_OUTER_KILL_ENGINEERING_REPORT.md` — reviewer-facing interpretation.
- `<case>/seed_<seed>/manifest.json` — exact per-run geometry and transport inputs.
- `<case>/seed_<seed>/statepoint.*.h5` — native OpenMC statepoint.

## Interpretation boundary

A successful run can quantify how much this **reduced cylindrical model** loses
when explicit parasitic geometry is inserted. It does not by itself close the D
engineering blanket gate.

Still outside this family:

- CAD-derived toroidal blanket sectors and real port shapes/coverage,
- manifolds and coolant thermohydraulics,
- first-wall and blanket support mechanics,
- magnet/shield integration,
- tritium extraction and inventory,
- activation, DPA and helium-production lifetime calculations,
- thermal stress and fatigue,
- manufacturing tolerances and maintenance segmentation.

The correct promotion path is therefore:

```text
idealized ordering
    -> explicit engineering-degradation OpenMC family (this module)
    -> CAD/sector neutronics with real penetrations and supports
    -> coupled thermal-hydraulic/material/lifetime validation
```

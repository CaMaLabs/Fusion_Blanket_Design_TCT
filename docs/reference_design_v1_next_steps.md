# Reference Design V1 Next Steps

This checklist tracks the highest-value follow-up work now that the repository has a frozen Reference Design V1, a winning-configuration summary, terminology translation guidance, and a hand-authored SVG cover figure.

## Immediate cleanup

- [ ] Confirm GitHub README renders `docs/reference_design_v1_diagram.svg` correctly.
- [ ] Review the SVG labels for spelling, spacing, and scientific wording.
- [ ] Export the SVG to PNG and PDF for outreach packages.
- [ ] Add alt-text / caption language for the figure in README and external materials.

## OpenMC reference package

Create a single canonical folder:

```text
reference_design_v1/
  geometry.json
  materials.json
  openmc_input.py
  assumptions.md
  expected_outputs.md
  results_manifest.md
```

The package should freeze:

- `be_outer_kill` / `be_outer_killer` topology,
- Be -> Li2O -> Li2O -> W-Ti-B4C -> Be layer order,
- split `(0.15, 0.20, 0.40, 0.15, 0.10)`,
- liquid lithium wall assumptions,
- `li_current = 0.1` hypothesis flag,
- OpenMC seed / particle / batch settings,
- uncertainty and result interpretation rules.

## Validation language

- [ ] Replace strong language such as "stabilizes," "validated," or "winning reactor" with conservative alternatives where appropriate.
- [ ] Prefer "current best validation basin," "reference design," "TCT-inspired edge-control hypothesis," and "reduced-order proxy evidence."
- [ ] Link `TCT_LANGUAGE_TRANSLATION.md` from any public-facing discussion of TCT.

## External-review package

- [ ] Add a one-page reviewer brief.
- [ ] Add a copy-paste outreach email.
- [ ] Add a short issue template asking reviewers to identify false assumptions.
- [ ] Add benchmark-comparison placeholders for ITER / SPARC / DEMO-style blanket assumptions.

## Technical priorities

1. Reproduce the OpenMC be_outer_killer basin from a clean script and manifest.
2. Add explicit uncertainty bars and seed control.
3. Keep `be_sandwich` as the nearest competitor.
4. Keep PbLi as a future variant, not the mainline design.
5. Map the edge-control proxy onto accepted reduced-MHD / reconnection / edge-stability terminology.
6. Prepare the Candidate-0 M3D-C1/BOUT++ validation handoff.

## Current public position

Reference Design V1 is the current mainline screening and validation target, not a demonstrated reactor.

The strongest defensible statement is:

> The repository has converged on a reproducible DT tokamak reference design basin combining a liquid-lithium-facing wall, `be_outer_kill` / `be_outer_killer` Be/Li2O/W-Ti-B4C/Be blanket topology, and Mirnov/toroidal-triggered TCT-inspired edge-control proxy for follow-on OpenMC, MHD, thermal, and controls validation.

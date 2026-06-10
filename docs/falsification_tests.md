# Falsification Test Plan

This project should be organized around tests that can reject, redirect, or narrow the TCT framing.

The purpose of this document is to define what would count as useful failure.

## Test 1 — Does current-sheet thickness add value as a variable?

Question:

> Is current-sheet thickness / aspect ratio / plasmoid marginality a meaningful control or diagnostic variable for the target event class?

Minimum useful outcome:

- A reviewer identifies an accepted variable set that should replace the TCT wording.
- A reduced benchmark shows the proxy is not connected to event onset.
- A reduced benchmark shows the proxy is connected but only under limited assumptions.

Possible benchmark direction:

- reduced-MHD reconnection problem,
- plasmoid instability onset benchmark,
- tearing-mode / current-sheet thinning benchmark,
- BOUT++ or comparable edge proxy only after the reduced framing is clear.

Failure condition:

- Thickness variables cannot be mapped to accepted diagnostics or nondimensional parameters.

Consequence:

- Rename or retire the TCT framing and express the idea in standard edge-stability language.

## Test 2 — Can the screening optimizer produce reproducible candidates?

Question:

> Can another machine reproduce candidate generation and summary outputs without hidden local state?

Minimum useful outcome:

- Deterministic seed path exists.
- Output manifest records inputs, parameters, commit hash, and generated files.
- CI can run a lightweight non-physics smoke path.

Failure condition:

- Outputs depend on local files or long-running processes that are not documented.

Consequence:

- Freeze optimizer claims until deterministic runs and manifests exist.

## Test 3 — Can finalist blanket candidates survive explicit neutronics review?

Question:

> Do simplified finalist candidates remain plausible when moved to explicit neutronics validation?

Minimum useful outcome:

- One finalist geometry is exported in a form suitable for OpenMC-style review.
- Material stack assumptions are documented.
- TBR, heating, and shielding metrics are reported as screening outputs, not final design claims.

Failure condition:

- Finalists fail basic TBR / shielding / heat constraints.

Consequence:

- Treat optimizer scoring as invalid or incomplete until corrected.

## Test 4 — Can wall survivability be separated from plasma-control claims?

Question:

> Does the proposed wall / lithium / blanket stack survive a conservative thermal and materials sanity check independent of TCT?

Minimum useful outcome:

- Heat flux assumptions are stated.
- Thermal limits and material compatibility are listed.
- Lithium-wall claims are separated from MHD claims.

Failure condition:

- The wall concept fails basic heat or material constraints.

Consequence:

- Keep TCT/MHD work separate from wall-stack claims.

## Test 5 — Can an external reviewer find the first wrong assumption quickly?

Question:

> Can a qualified reviewer understand the claim boundaries and identify the first weak assumption in under 30 minutes?

Minimum useful outcome:

- Reviewer can follow README → ROADMAP → assumptions → falsification tests.
- Reviewer can open an issue with one concrete objection.
- Reviewer does not have to infer what is validated vs. speculative.

Failure condition:

- Reviewer confusion, broad dismissal, or inability to find the technical ask.

Consequence:

- Improve documentation before adding more code.

## Priority order

1. Current-sheet / plasmoid framing.
2. Reproducible smoke path.
3. Benchmark target selection.
4. Blanket neutronics sanity check.
5. Wall survivability sanity check.
6. Commercial / funding packaging.

## Interpretation rule

A failed test is a result. The goal is not to defend the original framing at all costs; the goal is to turn the work into a pipeline that can identify when a fusion concept should be redirected, narrowed, or abandoned.

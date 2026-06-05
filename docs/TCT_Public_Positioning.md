# TCT Public Positioning

This document keeps the public framing of the repository clean, conservative, and testable.

## Recommended short description

> Independent fusion blanket and plasma-control research workspace exploring whether structured wall, blanket, and edge-response mechanisms can improve survivability and stability metrics under reproducible simulation workflows.

## Recommended TCT description

> TCT is an exploratory auxiliary-control hypothesis. It investigates whether structured boundary response, current-sheet behavior, or edge perturbation geometry can reduce selected instability or event-severity metrics compared with a conventional baseline.

## What this repository is

- A public research workspace.
- A timestamped development record.
- A collection of simulation scripts, candidate designs, validation notes, and result artifacts.
- A screening environment for ideas that may deserve higher-fidelity validation.

## What this repository is not

- Not a finished reactor design.
- Not a demonstrated net-power system.
- Not proof that TCT improves tokamak performance.
- Not proof that any blanket candidate is deployable without further engineering validation.

## Strong wording

Use:

- exploratory
- hypothesis-level
- baseline comparison
- validation workflow
- candidate screening
- structured perturbation
- bounded operating window
- failure-mode documentation
- external-code validation

## Weak or risky wording

Avoid:

- proves
- solves fusion
- reactor-ready
- guaranteed stability
- validated plant
- direct alpha extraction as a central claim
- any named comparison to an active private program unless intentionally publishing a literature comparison

## Preferred one-paragraph summary

This repository explores fusion blanket optimization and TCT-style plasma-control concepts using reproducible computational workflows. The work is currently hypothesis-level unless a specific result is backed by committed scripts, baseline comparison, result artifacts, and external validation. The immediate goal is to identify candidate mechanisms that may reduce edge/MHD event severity or improve first-wall survivability without overstating reactor-level implications.

## Review posture

The project should invite criticism by making claims narrow and testable:

1. State the baseline.
2. State what changed.
3. State the metric.
4. State the result.
5. State the uncertainty.
6. State the failure modes.
7. State what remains unvalidated.

## Useful repository labels

- `implemented`
- `screened`
- `baseline-compared`
- `externally-validated`
- `speculative`
- `rejected-or-harmful`

## Bottom line

The public presentation should make the work look disciplined, not defensive. The strongest claim is that TCT is being converted from a concept into a set of falsifiable validation targets.

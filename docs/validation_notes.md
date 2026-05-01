# Validation Notes

This document defines how project evidence should be handled before sharing with outside researchers.

## Evidence levels

### Level 0 — Concept
A qualitative idea or proposed mechanism.

### Level 1 — Toy model signal
A result observed in a simplified or heuristic model.

### Level 2 — Internal robustness
The same signal survives parameter sweeps, alternate controller implementations, or numerical-resolution checks.

### Level 3 — Cross-model support
The signal appears in an independent model family, such as reduced-MHD, OpenMC wall/transport coupling, kinetic approximations, or separate scripts.

### Level 4 — External comparison
The result can be compared meaningfully against published experimental regimes or known simulation literature.

### Level 5 — Experimental evidence
The effect is observed in an experimental device or by an external lab.

Most current TCT results should be treated as Level 1–2 unless explicitly cross-validated.

## Current preferred framing

Use careful language:

- “model-supported”
- “observed in simulation”
- “consistent with a distributed dissipation interpretation”
- “requires higher-fidelity validation”
- “candidate control mechanism”

Avoid:

- “proven”
- “confirmed reactor technology”
- “solves fusion”
- “ready for publication” unless a real manuscript is prepared

## Minimum package for external review

A credible external review packet should include:

1. One-page summary.
2. Clear figure with exact data provenance.
3. Script or notebook that reproduces the figure.
4. Inputs and configuration file.
5. Limitations section.
6. What question the recipient is being asked.

## Figure policy

Figures must not be manually reconstructed if values matter. If a figure is rebuilt, it must be generated from source arrays, CSVs, or scripts. If only an image exists, label any digitized values as approximate.

## TCT email-contact packet

For first contact, lead with the narrowest defensible claim:

> TCT-like current-sheet control appears to shift modeled behavior from lower-frequency, higher-damage events toward higher-frequency, lower-damage distributed dissipation, with improved survivability and net-power proxies in the studied cases.

Do not lead with p-B11, propulsion, vortex channels, plasma mirrors, or full reactor claims in first-contact emails.

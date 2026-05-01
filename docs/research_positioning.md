# Research Positioning

This repository is an independent computational research workspace for exploring fusion blanket behavior, current-sheet control ideas, and reactor-adjacent stability heuristics.

## Current status

This project should be treated as **computational exploratory research**, not experimental validation. Results are model-supported and should be interpreted as hypotheses, screening signals, or design-space indicators unless separately verified with higher-fidelity tools or experimental data.

## Core themes

- Layered fusion blanket optimization
- Neutron transport shaping and tritium breeding considerations
- Liquid lithium wall / blanket concepts
- TCT-style current-sheet / instability severity control concepts
- Stability and survivability scoring under heuristic control models
- Preparation of shareable, timestamped research snapshots

## Claim levels

Use this structure when writing summaries or sharing results:

1. **Observed in simulation** — directly produced by scripts, sweeps, or saved artifacts.
2. **Supported by robustness checks** — appears across parameter sweeps, controller variants, or resolution checks.
3. **Hypothesized mechanism** — physically plausible interpretation, not yet proven.
4. **Speculative extension** — future reactor, propulsion, p-B11, vortex, or plasma-wave applications.
5. **Requires validation** — anything needing OpenMC, MHD, kinetic, PIC, or experimental confirmation.

## Recommended external framing

> This is an independent computational research package exploring current-sheet control and blanket/wall design heuristics for fusion systems. The work is not an experimental demonstration. If the concepts, data, or code inform further research, publications, or experimental planning, please cite or contact the author.

## Sharing guidance

For now, prefer selective private sharing over broad public release. Keep implementation-heavy raw bundles and exploratory files in an archive area until they are reviewed and labeled.

Before public release:

- remove secrets / credentials / private notes
- separate raw experiments from curated results
- include provenance and date stamps
- include limitations and uncertainty
- choose a license intentionally
- preserve authorship and attribution metadata

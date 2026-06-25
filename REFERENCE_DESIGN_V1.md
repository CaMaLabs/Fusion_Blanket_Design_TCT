# Reference Design V1

This document freezes the current best-known configuration into a single reference design for future OpenMC, M3D-C1, BOUT++, and experimental comparison work.

## Reference topology

Topology: be_outer_kill / be_outer_killer

Layer order:

Be -> Li2O -> Li2O -> W_Ti_B4C_60_30_10_wt -> Be

Preferred split:

(0.15, 0.20, 0.40, 0.15, 0.10)

## Control configuration

- Liquid lithium wall active
- li_current = 0.1
- TCT enabled
- Severity scale = 0.6
- Standing preventative bias
- Fast bounded boost
- Mirnov/toroidal precursor trigger

## Companion validation target

Candidate-0 be_outer_killer M3D-C1 configuration is the frozen validation target until superseded.

## Immediate validation goals

1. Reproduce OpenMC ordering results with fixed seeds.
2. Produce uncertainty bars.
3. Compare against ITER-style blanket assumptions.
4. Compare against SPARC-style blanket assumptions.
5. Generate publication-quality cross-sectional figure.

## Status

Current repository mainline design as of June 2026.
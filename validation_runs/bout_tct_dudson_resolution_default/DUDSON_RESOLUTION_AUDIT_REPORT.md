# Dudson-aligned BOUT++ current-sheet resolution audit

Status: `FIXED_GRID_EFFECT_CONVERGED_AT_CONFIGURED_GATE`

This study freezes the current-sheet initial condition and TCT actuator width
while refining the global BOUT++ mesh.

It tests whether the reported TCT effect survives better resolution of the
current sheet.

It is **not adaptive mesh refinement** and does not replace M3D-C1
topology-changing validation.

Finest pair: `192 -> 256`

- Finest minimum measured peak-sheet FWHM:
  `12.000` cells

- Configured adequacy heuristic:
  `8.000` cells

- Peak-J effect relative change:
  `0.00130014`

- Integrated-J effect relative change:
  `0.00072813`

- Configured effect-convergence tolerance:
  `0.1`

## Interpretation boundary

The `psi` centre-span derivative is a topology-sensitive reduced proxy,
not a formal reconnection rate.

A favorable result supports promotion to M3D-C1 using topology/island
evolution and a code-native reconnection diagnostic.

A failure means the present BOUTresolution-sensitive
and should not be promoted as physical.

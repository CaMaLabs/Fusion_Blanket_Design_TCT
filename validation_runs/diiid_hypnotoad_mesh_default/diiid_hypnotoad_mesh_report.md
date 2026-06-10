# DIII-D Hypnotoad Field-Aligned Mesh

- Status: `DIIID_HYPNOTOAD_FIELD_ALIGNED_MESH_READY`
- Generated: `2026-06-10T00:18:52.183261+00:00`
- Source equilibrium: DIII-D shot `158103` at `3796 ms`
- GEQDSK SHA-256: `1a5db6deb2494e9805f08c1dae5ee27fd2d6e87f8a73641df46b9fcbc087a51e`
- Mesh SHA-256: `0429fbb4c0163512902ee3807b7c4b275772d6ff27b8e8f54846e359a89d5f9e`
- Hypnotoad: `0.5.2`
- Parallel transform: `shiftedmetric`

## Mesh checks

- Dimensions: `40 x 112`
- Separatrix indices: `ixseps1=24`, `ixseps2=40`
- Y topology: `23, 56, 56, 87`
- Topology consistency: `True`
- Required geometry, magnetic, Jacobian, and metric fields finite: `True`
- Embedded Hypnotoad inputs present: `True`

## Topology choice

The imported equilibrium contains a primary lower X-point at normalized flux 1.0
and a secondary upper X-point near normalized flux 1.089. The mesh uses
`psinorm_sol = 1.05`, selecting a lower-single-null topology and excluding
the secondary upper X-point from the generated SOL.

## Auxiliary non-finite values

Hypnotoad leaves some topology-dependent auxiliary shift/angle arrays undefined
outside the regions where they apply. These do not occur in the required core
geometry, magnetic-field, Jacobian, or metric arrays checked above.

- `ShiftTorsion_xlow`: 0 / 4480 finite values
- `total_poloidal_distance`: 24 / 40 finite values
- `ShiftAngle`: 24 / 40 finite values
- `chi`: 1536 / 4480 finite values
- `chi_xlow`: 0 / 4480 finite values
- `chi_ylow`: 1536 / 4480 finite values

## Claim boundary

This closes the missing field-aligned DIII-D BOUT++ mesh-input gap.
It is not a BOUT++ machine-geometry physics pass, mesh-convergence result,
or validation against DIII-D experimental diagnostics. The next step is to
run a machine-geometry BOUT++ model on this grid and compare resolutions and
diagnostic-anchored observables.

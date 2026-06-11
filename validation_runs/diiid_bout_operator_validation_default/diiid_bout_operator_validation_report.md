# DIII-D BOUT++ Machine-Mesh Operator Validation

- Status: `DIIID_BOUT_OPERATOR_IDENTITIES_SUPPORTED_SERIAL_TOPOLOGY`
- Generated: `2026-06-11T03:40:01.763481+00:00`
- Model: custom static probe using BOUT++ derivative/operator implementations

## Operator identities

The probe evaluates these manufactured identities away from radial and
poloidal guard/boundary cells:

- `DDX(psixy) = 1`
- `DDY(psixy) = 0`
- `Grad_par(psixy) = 0`
- `Delp2(1) = 0`
- `bracket(psixy, psixy) = 0`

| Operator | Coarse RMS error | Base RMS error | Fine RMS error | Improves coarse-to-fine |
| --- | ---: | ---: | ---: | ---: |
| `ddx_psi` | 2.269940e-03 | 5.528177e-04 | 2.436152e-04 | True |
| `ddy_psi` | 9.310728e-14 | 1.711619e-13 | 2.951422e-13 | False |
| `gradpar_psi` | 5.757634e-14 | 1.661901e-13 | 3.874363e-13 | False |
| `delp2_one` | 1.754072e-12 | 2.928572e-12 | 1.064645e-11 | False |
| `bracket_self` | 8.006338e-19 | 8.009722e-19 | 7.201987e-19 | True |

- All physical-domain operator outputs finite: `True`
- Identity checks within tolerances: `True`

## Topology boundary

Exact lower-single-null topology requires a compatible multi-rank MPI
decomposition that is blocked on the current host. As in the machine-mesh
startup smoke, temporary serial-topology copies disable X-point connections
and fill undefined `ShiftAngle` values with zero. Geometry and metric fields
are otherwise unchanged.

## Claim boundary

This validates a focused set of BOUT++ operator identities on the DIII-D
machine geometry. It is not a complete MMS suite, exact-X-point operator
validation, physics-solution convergence result, or TCT validation.

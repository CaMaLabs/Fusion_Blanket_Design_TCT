# DIII-D BOUT++ elm-pb Machine-Mesh Smoke

- Status: `DIIID_BOUT_ELM_PB_SERIAL_TOPOLOGY_SMOKE_PASS_EXACT_TOPOLOGY_MPI_BLOCKED`
- Generated: `2026-06-10T03:06:24.563106+00:00`
- BOUT++ revision: `3e317cbc18b4ad3839cfff67aded3bff4b5fb9f9`
- Source mesh SHA-256: `0429fbb4c0163512902ee3807b7c4b275772d6ff27b8e8f54846e359a89d5f9e`
- Model: official BOUT++ `elm-pb` high-beta reduced MHD

## Results

| MZ | Final time | U finite | P finite | Psi finite | Final max abs U |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 0.0002 | True | True | True | 3.95097097e-08 |
| 16 | 0.0002 | True | True | True | 3.95097097e-08 |

Both toroidal resolutions loaded the DIII-D geometry, pressure, curvature,
magnetic, Jacobian, and shifted-metric fields and completed reduced-MHD time
evolution with finite evolved fields in the physical domain.

- Final max-abs U relative difference: `1.67489079e-16`
- Final max-abs P relative difference: `4.92985141e-05`
- Final max-abs Psi relative difference: `4.12822054e-02`

## Topology and physics boundary

The exact lower-single-null mesh loads successfully, but BOUT++ requires a
14-rank Y decomposition for its 24/32-cell divertor/core regions. This host
cannot launch multi-rank MPI because network-interface access is denied.
For the completed serial smoke cases, the runner creates a temporary grid
copy that disables X-point connections while leaving geometry, magnetic,
pressure, curvature, Jacobian, and metric fields unchanged. Undefined
`ShiftAngle` values outside their original applicable region are set to zero
for the temporary serial topology.

The equilibrium grid does not contain `Jpar0`, so equilibrium-current drive
is disabled. The cases are linear, short-duration startup tests with a small
vorticity perturbation. This validates BOUT++ machine-mesh ingestion and
finite reduced-MHD evolution only; it does not validate ELM growth, TCT
control, exact divertor topology evolution, or experimental diagnostics.

## Next step

Run the unchanged exact-topology grid with 14 MPI ranks on a conventional
Linux/HPC host, add a defensible `Jpar0` equilibrium-current profile, then
perform linear growth-rate and controlled/uncontrolled comparisons.

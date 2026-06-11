# DIII-D GEQDSK Jpar0 Reconstruction

- Status: `DIIID_GEQDSK_JPAR0_PROVISIONAL_SUPPORTED`
- Generated: `2026-06-11T14:03:45.202772+00:00`

## Current reconstruction check

- EFIT-reported plasma current: `1.33949225e+06` A
- Reconstructed toroidal-current integral: `1.37304821e+06` A
- Relative difference: `2.505125%`

## Machine-mesh Jpar0

- All values finite: `True`
- Minimum: `-1.22082577e+06` A/m^2
- Maximum: `0.00000000e+00` A/m^2
- RMS: `3.11863818e+05` A/m^2

The generated grid is retained only when `--keep-grid` is supplied. The summary
records the reproducible reconstruction and its total-current residual.

## Claim boundary

This is a provisional axisymmetric GEQDSK-derived equilibrium-current field.
It passes a total-current consistency check, but has not been independently
verified against an EFIT-exported Jpar profile, exact-X-point BOUT++ evolution,
or experimental current diagnostics.

# Machine Equilibrium Readiness

Generated: `2026-06-03T12:41:16.980074+00:00`

Overall status: **PARTIAL_MACHINE_EQUILIBRIUM_READY**

## Machine Inputs

| Machine | Status | GEQDSK | AEQDSK | Profiles | Coil file | Raw diagnostics |
| --- | --- | --- | --- | --- | --- | --- |
| DIII-D | ready_with_public_efit | yes | yes | yes | yes | no |
| NSTX-U | blocked_missing_real_efit | no | no | no | yes | no |
| ITER | template_only_missing_public_efit | no | no | no | yes | no |

## Interpretation

This package adds a real public DIII-D EFIT/GEQDSK anchor from the CaMaLabs M3DC1 public template set.
NSTX-U and ITER currently have M3D-C1 machine templates and coil/current material, but no public EFIT GEQDSK was found in the local public package during this scan.
No raw experimental diagnostic archive is packaged here; the DIII-D material is an EFIT/profile anchor, not a diagnostic validation set.
Therefore the experimental-equilibrium gate is only partially satisfied: DIII-D is ready for EFIT-backed follow-up, while NSTX-U and ITER remain template-only until real equilibrium files are added.

## M3D-C1 Integration Points

- `idevice = 2`: NSTX family
- `idevice = 3`: ITER
- `idevice = 4`: DIII-D
- `iread_eqdsk = 1`: read EFIT g-file named `geqdsk`
- `icalc_scalars = 1`: scalar diagnostics enabled

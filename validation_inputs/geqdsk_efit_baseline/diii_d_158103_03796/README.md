# DIII-D GEQDSK / EFIT Baseline Case

This directory is a concrete EFIT/GEQDSK baseline input package for follow-up M3D-C1/BOUT++ validation.
It is not evidence that a completed M3D-C1 nonlinear run has been performed from this case.

## Provenance

- Machine: `DIII-D`
- Shot/time: `158103 @ 3796 ms`
- Source package: public `CaMaLabs/M3DC1` template mirror
- Source GEQDSK path before import: `/root/CaMaLabs_M3DC1/templates_from_autoc1/DIII-D/efit/g158103.03796`
- Source AEQDSK path before import: `/root/CaMaLabs_M3DC1/templates_from_autoc1/DIII-D/efit/a158103.03796`
- Source profile path before import: `/root/CaMaLabs_M3DC1/templates_from_autoc1/DIII-D/efit/p158103.03796`

## GEQDSK Header

```text
EFITD    06/25/2013    #158103  3796ms           3 129 129
```

## Parsed Checks

- Grid: `129 x 129`
- R dimension: `1.7` m
- Z dimension: `3.2` m
- Magnetic axis: R=`1.73854887` m, Z=`0.0128069012` m
- Central field: `-1.8977622` T
- Plasma current: `1339492.25` A
- q range: `1.1` to `8.45323831`

## Files

- `geqdsk`: solver-facing copy expected by M3D-C1 when `iread_eqdsk = 1`
- `efit/g158103.03796`: original GEQDSK filename
- `efit/a158103.03796`: original AEQDSK-style metadata file
- `efit/p158103.03796`: profile file used to derive `profile_density.csv`
- `C1input.geqdsk_baseline`: filled M3D-C1 input deck for this baseline
- `profile_density.csv`: parsed density profile table

## SHA-256

| File | SHA-256 |
| --- | --- |
| `geqdsk` | `1a5db6deb2494e9805f08c1dae5ee27fd2d6e87f8a73641df46b9fcbc087a51e` |
| `efit/g158103.03796` | `1a5db6deb2494e9805f08c1dae5ee27fd2d6e87f8a73641df46b9fcbc087a51e` |
| `efit/a158103.03796` | `93b33723e39f8b53fb14a4a3a05c1b66cbce84ddb6eee23980381cba935e0c79` |
| `efit/p158103.03796` | `e3e90776e20d3eb4deedc0a02538995d51e0b050c3e0d4300d06c7e74317c065` |
| `C1input.geqdsk_baseline` | `db09f2f76bc94858e7bae0d6ebb4001f280c37af233eb429e0ced3a645041f39` |

## Claim Boundary

This is a real imported DIII-D EFIT/GEQDSK baseline input package.
It is not a completed experimental validation result, not an NSTX/ITER baseline, and not a raw diagnostic archive.

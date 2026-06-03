# GEQDSK / EFIT Baseline Case

Generated: `2026-06-03T14:18:51.522193+00:00`

Status: **GEQDSK_EFIT_BASELINE_READY**

## Case

- Machine: `DIII-D`
- Shot/time: `158103 @ 3796 ms`
- Baseline case directory: `validation_inputs/geqdsk_efit_baseline/diii_d_158103_03796`
- M3D-C1 input deck: `validation_inputs/geqdsk_efit_baseline/diii_d_158103_03796/C1input.geqdsk_baseline`
- Solver-facing GEQDSK filename: `validation_inputs/geqdsk_efit_baseline/diii_d_158103_03796/geqdsk`

## Parsed GEQDSK

- Grid: `129 x 129`
- R dimension: `1.7` m
- Z dimension: `3.2` m
- Magnetic axis: R=`1.73854887` m, Z=`0.0128069012` m
- Boundary flux: `0.0637294348` Wb
- Central field: `-1.8977622` T
- Plasma current: `1339492.25` A
- q range: `1.1` to `8.45323831`

## Profile Anchor

- Profile rows: `256`
- Density range: `0.061854` to `0.452709` 1e20 m^-3

## Boundary

This is an EFIT-backed baseline input package, not a completed M3D-C1 or BOUT++ machine-geometry run.
It is the correct next anchor for replacing the reduced slab/current-sheet validation chain with an experiment-referenced equilibrium.
Raw experimental diagnostic archives are still absent.

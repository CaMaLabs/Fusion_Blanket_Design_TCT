# M3D-C1 DIII-D GEQDSK Smoke Run

- Status: `M3DC1_STARTUP_SMOKE_PASSED`
- Started: `2026-06-04T23:53:13.614064+00:00`
- Runtime: `23.305` seconds
- Return code: `0`
- Timed out: `False`
- M3D-C1 binary: `/root/M3DC1/unstructured/build-mpich325/m3dc1_2d`
- Run directory: `/root/Fusion_Blanket_Design_TCT/validation_runs/m3dc1_geqdsk_diiid_smoke_default`
- GEQDSK header: `  EFITD    06/25/2013    #158103  3796ms           3 129 129`
- GEQDSK grid: `129 x 129`
- M3D-C1 smoke flags: `M3DC1_SKIP_WALL_DIST_SOLVE=1`

## What This Validates

This is a solver startup smoke test using the imported DIII-D shot 158103 / 3796 ms GEQDSK as the solver-facing `geqdsk` input.
The run uses the local M3D-C1 first-linear DIII-D SCOREC mesh/wall scaffold because the public EFIT package does not include a shot-specific mesh model.

## What This Does Not Validate

This is not a completed nonlinear M3D-C1 campaign, not a BOUT++ machine-geometry run, and not a direct comparison to raw DIII-D diagnostics.
It should be treated as the first executable gate after GEQDSK/EFIT import: the solver can be launched against the imported equilibrium package and any emitted HDF5 artifacts are inventoried below.
This run is also not a validation of the M3D-C1 wall-distance auxiliary solve; the smoke harness sets `M3DC1_SKIP_WALL_DIST_SOLVE=1` so the imported-equilibrium startup gate can proceed while keeping `wall_dist` as a neutral zero field.

## Output Artifacts

| File | Exists | Size bytes | HDF5 readable | Notes |
| --- | ---: | ---: | ---: | --- |
| `C1.h5` | True | 290864 | True |  |
| `equilibrium.h5` | True | 24178968 | True |  |
| `time_000.h5` | True | 19855960 | True |  |

## Log Tail

```text
 Writing ne
 Writing psi_coil
 Writing wall_dist
 Writing jphi
 Writing torque_em
 Writing torque_ntv
 Writing bdotgradp
 Writing bdotgradt
 Writing zeff
 Writing magnetic_region
 Writing mesh_zone
 Writing E_R
 Writing E_PHI
 Writing E_Z
 Writing E_par
 Writing eta_J
   Done writing fields            0
  Writing wall regions
 linking time_000.h5        
   End of hdf5_write_time_slice 
   flushing data to file
   finalizing output...
   deleting matrices...
   unloading mesh...
 destroy field  1
 destroy field  2
 destroy field  3
 destroy field  4
 destroy field  5
 destroy field  6
 destroy field  7
 destroy field  8
 destroy field  9
 destroy field 10
 destroy field 11
 destroy field 12
 destroy field 13
 destroy field 14
 destroy field 15
 destroy field 16
 destroy field 17
 destroy field 18
 destroy field 19
 destroy field 20
 destroy field 21
 destroy field 22
 destroy field 23
 destroy field 24
 destroy field 25
 destroy field 26
 destroy field 27
 destroy field 28
 destroy field 64
 destroy field 65
 destroy field 66
 destroy field 67
 destroy field 68
 destroy field 69
 destroy field 70
 destroy field 71
 destroy field 72
 destroy field 73
 destroy field 74
 destroy field 75
 destroy field 76
 destroy field 77
 destroy field 78
 destroy field 79
 destroy field 80

* [M3D-C1 INFO] run time: 22.1514 (sec)
   finalizing PETSC...
 ==============================================================
 END DATE: 2026 06 04   TIME: 16:53:36.8

   finalizing MPI...
 Stopped at           0

--- STDERR ---
[localhost:10613] pmix_ifinit: ioctl(SIOCGIFHWADDR) failed with errno=13
```

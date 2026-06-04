# M3D-C1 DIII-D GEQDSK Smoke Run

- Status: `M3DC1_STARTUP_PETSC_ABORT_NO_HDF5`
- Started: `2026-06-04T04:38:00.105277+00:00`
- Runtime: `4.287` seconds
- Return code: `15`
- Timed out: `False`
- M3D-C1 binary: `/root/M3DC1/unstructured/build-mpich325/m3dc1_2d`
- Run directory: `/root/Fusion_Blanket_Design_TCT/validation_runs/m3dc1_geqdsk_diiid_smoke_default`
- GEQDSK header: `  EFITD    06/25/2013    #158103  3796ms           3 129 129`
- GEQDSK grid: `129 x 129`

## What This Validates

This is a solver startup smoke test using the imported DIII-D shot 158103 / 3796 ms GEQDSK as the solver-facing `geqdsk` input.
The run uses the local M3D-C1 first-linear DIII-D SCOREC mesh/wall scaffold because the public EFIT package does not include a shot-specific mesh model.

## What This Does Not Validate

This is not a completed nonlinear M3D-C1 campaign, not a BOUT++ machine-geometry run, and not a direct comparison to raw DIII-D diagnostics.
It should be treated as the first executable gate after GEQDSK/EFIT import: the solver can be launched against the imported equilibrium package and any emitted HDF5 artifacts are inventoried below.

## Output Artifacts

| File | Exists | Size bytes | HDF5 readable | Notes |
| --- | ---: | ---: | ---: | --- |
| `C1.h5` | False | 0 |  |  |
| `equilibrium.h5` | False | 0 |  |  |
| `time_000.h5` | False | 0 |  |  |

## Log Tail

```text
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27316
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27317
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27318
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27328
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27329
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27330
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27334
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27335
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27336
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27340
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27341
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27342
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27346
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27347
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27348
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27364
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27365
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27366
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27370
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27371
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27372
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27376
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27377
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27378
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27382
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27394
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27395
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27396
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27401
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27402
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27408
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27418
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27419
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27420
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27425
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27426
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27430
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27431
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27432
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27436
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27437
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27438
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27442
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27443
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27444
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27448
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27449
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27450
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27454
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27455
[M3DC1 DEBUG] assemble: matrix 22 regularized near-zero diagonal row 27456
  done.
  populating matrix...           1           1
  done.
  populating matrix...           1           1
  done.
  populating matrix...           1           1
  applying bcs...
 [M3DC1 DEBUG] create_vector id=          43  name=43\x00\x00\x00\x00
[M3D-C1 INFO] m3dc1_field_create_: field 43, #values 1, #dofs 6, name 43
 boundary_dc called
 boundary_dc done
  done.
 [M3DC1 DEBUG] create_vector id=          44  name=44\x00\x00\x00\x00
[M3D-C1 INFO] m3dc1_field_create_: field 44, #values 1, #dofs 6, name 44
 boundary_wall_dist called
[M3DC1 DEBUG] solve: matrix 64 fieldOrdering= 1 rhs=44 field_id=44
[M3DC1 INFO] copyField2PetscVec_5: MatCreateVecs

--- STDERR ---
[localhost:06563] pmix_ifinit: ioctl(SIOCGIFHWADDR) failed with errno=13
The 4-th row of A is exactly zero
[0]PETSC ERROR: ------------------------------------------------------------------------
[0]PETSC ERROR: Caught signal number 11 SEGV: Segmentation Violation, probably memory access out of range
[0]PETSC ERROR: Try option -start_in_debugger or -on_error_attach_debugger
[0]PETSC ERROR: or see https://petsc.org/release/faq/#valgrind and https://petsc.org/release/faq/
[0]PETSC ERROR: configure using --with-debugging=yes, recompile, link, and run 
[0]PETSC ERROR: to get more information on the crash.
[0]PETSC ERROR: Run with -malloc_debug to check if memory corruption is causing the crash.
Abort(59) on node 0 (rank 0 in comm 0): application called MPI_Abort(MPI_COMM_WORLD, 59) - process 0
```

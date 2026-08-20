# M3D-C1 Native Smoke Report

Status: `NATIVE_M3DC1_BUILD_PASS_REGRESSION_NOT_YET_PASSING`

This package records a native execution attempt using the public Princeton M3D-C1 solver. It is not a TCT physics result and does not validate reconnection suppression, reactor behavior, or plasma predictive capability.

## Build

- Upstream: `PrincetonUniversity/M3DC1`
- Upstream commit: `e17c0b7ee06e6f19955d8baf65e8dd6452f5bd4b`
- Build directory: `/home/ubuntu/M3DC1-official/build-ubuntu-2d`
- Binary: `/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d`
- Local build-system compatibility patch: added `signal_handler.f90` to `unstructured/CMakeLists.txt`
- CMake compatibility flag: `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`
- MPI stack: Spack `m3dc1-deps`, OpenMPI-only dependency DAG

## Safestop Diagnosis

The earlier 1-rank `KPRAD_2D` run reached `Defining initial conditions`, printed `Error reading geqdsk file`, and exited with `Stopped at 1`. The immediate cause was missing `geqdsk` in the staged run directory, not an HDF5 restart path.

A correctly staged 1-rank diagnostic with `geqdsk` present still is not a valid official regression substitute because PUMI reports that the shipped mesh partition count does not match the MPI rank count.

## Native Official Case Execution

- Case: `unstructured/regtest/KPRAD_2D/base`
- Mesh staging: bundled 48 `part*.smb` files from `unstructured/regtest/KPRAD_2D/mesh`
- Ranks: `48` with OpenMPI `--oversubscribe` on a 16-core Ubuntu host
- Command: `mpirun --oversubscribe -n 48 /home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d -pc_factor_mat_solver_type mumps`
- Return code: `0`
- Final solver line: `Stopped at           0`
- Timesteps reached: yes, `TIME STEP` entries 1 through 5
- Native `C1.h5`: populated; `328296` bytes in the run directory

## C1ke Reference Comparison

The generated `C1ke` has the same row and column count as the bundled reference, but it fails the upstream `compare.py` tolerance.

- Upstream tolerance: fractional `1e-3`, with `etot` skipped
- Comparison pass: `False`
- First failing row/column: row `0`, `emagp`
- Reference value: `0.11787`
- Generated value: `2.8222e+24`
- Maximum absolute difference: `3.811100e+25`
- Maximum finite relative difference: `2.394333e+25`

This means Level 3 and Level 5 evidence were achieved, but Level 4 reference reproduction was not achieved.

## Evidence Level

- Level 1: real public M3D-C1 source compiled into `m3dc1_2d`: achieved.
- Level 2: MPI/PETSc/SCOREC/native runtime initialization: achieved.
- Level 3: official bundled case reaches timestep loop and exits normally: achieved for 48-rank KPRAD_2D staging.
- Level 4: generated `C1ke` reproduces official reference: not achieved.
- Level 5: populated native `C1.h5` produced: achieved.
- Level 6: baseline-vs-TCT M3D-C1 handoff: not attempted.

## Claim Boundary

This establishes that the public M3D-C1 executable can be built and can run the bundled `KPRAD_2D` case to normal solver termination in this Ubuntu/Spack/OpenMPI environment. It does not establish an official passing M3D-C1 regression, because the `C1ke` reference comparison fails. It does not validate TCT physics, reactor behavior, or plasma predictive capability.

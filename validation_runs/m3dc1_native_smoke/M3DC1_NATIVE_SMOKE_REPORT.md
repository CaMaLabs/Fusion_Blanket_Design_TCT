# Native M3D-C1 Smoke And KPRAD Reference Provenance

Status: `NATIVE_M3DC1_EXECUTION_PASS_REFERENCE_REGRESSION_UNRESOLVED`

A 48-rank native M3D-C1 run completed all five KPRAD_2D timesteps and wrote populated HDF5 output, proving native execution. It fails the bundled C1ke regression at t=0 on magnetic-energy columns.

The bundled C1ke reference belongs to the historical single-mesh/split_smb workflow. Evidence: current source with the stored single-part `analytic-2K0.smb` plus `geqdsk` reproduces the bundled C1ke under upstream `compare.py` (return code 0). The checked-in 48-part mesh, introduced later, gives `Volume=0` and `emagp=2.8222e24` at t=0.

Do not update `unstructured/regtest/KPRAD_2D/base/C1ke` from the 48-rank run. The current public 48-part mesh is not demonstrated to be a faithful replacement for the historical split_smb partitioning in this environment.

Key files: `KPRAD_REFERENCE_TIMELINE.md`, `c1ke_column_provenance.md`, `C1ke_t0_comparison.csv`, `kprad_t0_initialization_trace.txt`, `mesh_provenance_comparison.md`.

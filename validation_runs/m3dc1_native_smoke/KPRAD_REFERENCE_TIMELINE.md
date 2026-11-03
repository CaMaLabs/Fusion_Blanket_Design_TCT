# KPRAD_2D Reference Timeline

| date | commit | affected file | change | possible relevance to current mismatch |
|---|---|---|---|---|
| 2019-05-10 | e68a254d | KPRAD_2D/base/C1ke,C1input,geqdsk | new KPRAD_2D regtest introduced | origin of this test family |
| 2019-05-22 | cce2de4a/496ddb1f | analytic-2K0.smb,C1ke | single-part .smb files stored; C1ke updated | mesh source for historical path |
| 2019-06-12/18 | 80a47f1b/c931bd81 | C1input | kappai_fac option added then removed from KPRAD_2D input | C1input unchanged since 2019-06-18 |
| 2019-08-16 | 516bf129 | C1ke | transport coefficients moved before time advance; KPRAD/reference updated | physics/output change affects scalar values |
| 2019-12-10 | b4e68bc6 | C1ke,diagnostics | kinetic-energy definition changed to include rho; references updated | explicit C1ke semantic change |
| 2020-08-26 | 8964f6bf | C1ke | p/T source-term fix; KPRAD references updated | current bundled C1ke last changed here |
| 2020-11-16/17 | 1b4ed1ed/715a8040 | scorec_mesh.f90 | SCOREC adjacency and global element numbering added | post-reference mesh/geometry infrastructure changed |
| 2021-08-30 | 62d5cbc7 | KPRAD_2D/mesh/part*.smb | 48 checked-in partition files added | mesh not contemporaneous with last C1ke update |
| 2021-09-17+ | b074847e and later | scorec_mesh.f90,diagnostics.f90 | zone_type constants and geometry-class indirection introduced | current source maps getgeomclass result through zone_type; old source used class directly |
| 2023-02-22 | a3fb7b7f | diagnostics.f90,output.f90 | new conductor/vacuum magnetic-energy diagnostics and tpi_factors change | post-reference output semantics changed, but not the main C1ke column order |
| 2026-08-20 | local run | runtime evidence | single-part diagnostic reproduces reference; checked-in 48 mesh does not | supports mesh metadata/provenance explanation |

Key IDs:
- Current C1ke reference introduced with KPRAD_2D at `e68a254d` and last changed at `8964f6bf`.
- Checked-in 48-part mesh introduced later at `62d5cbc7`.
- `C1input` changed after C1ke origin but before final C1ke update; it has not changed after the current C1ke reference.
- `geqdsk` has not changed since KPRAD_2D introduction.
- Current 48-part run fails at t=0; current single-part `analytic-2K0.smb` diagnostic passes upstream compare.

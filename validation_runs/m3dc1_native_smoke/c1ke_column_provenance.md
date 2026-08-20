# C1ke Column Provenance

The C1ke file is opened by `unstructured/output.f90` in `initialize_output()` using the fixed filename `C1ke`. It is written in `output()` with this format and column order:

```fortran
write(ke_file, '(I8, 1p3e12.4,2x,1p3e12.4,2x,1p3e12.4,2x,1pe13.5)') &
     ntime, time, ekin, gamma_gr, &
     ekinp,ekint,ekin3, emagp, emagt, emag3, etot
```

| Column | Variable | Source routine | Normalization / units observed in source | Equilibrium or perturbation quantity |
|---:|---|---|---|---|
| 1 | `ntime` | `output.f90:output` | integer timestep counter | simulation state counter |
| 2 | `time` | global time state, written by `output.f90` | reduced/native M3D-C1 time used by the case | simulation time |
| 3 | `ekin` | `diagnostics.f90:calculate_scalars`; `ekin = ekinp + ekint + ekin3` | reduced/native diagnostic energy | total kinetic energy diagnostic |
| 4 | `gamma_gr` | `output.f90:output`; `(ekin - ekino)/((ekin+ekino)*dtold)` except zero/ntime guards | growth-rate diagnostic from kinetic energy | derived perturbation growth diagnostic |
| 5 | `ekinp` | `diagnostics.f90:calculate_scalars`; `twopi*energy_kp()/tpifac` | reduced/native diagnostic energy, toroidal-period adjusted by `tpi_factors` | poloidal-flow kinetic component |
| 6 | `ekint` | `diagnostics.f90:calculate_scalars`; `twopi*energy_kt()/tpifac` | reduced/native diagnostic energy, toroidal-period adjusted | toroidal-flow kinetic component |
| 7 | `ekin3` | `diagnostics.f90:calculate_scalars`; `twopi*energy_k3()/tpifac` | reduced/native diagnostic energy, toroidal-period adjusted | third/chi kinetic component |
| 8 | `emagp` | `diagnostics.f90:calculate_scalars`; `twopi*energy_mp()/tpifac` | reduced/native diagnostic magnetic energy, toroidal-period adjusted | poloidal magnetic-energy component |
| 9 | `emagt` | `diagnostics.f90:calculate_scalars`; `twopi*energy_mt()/tpifac` | reduced/native diagnostic magnetic energy, toroidal-period adjusted | toroidal magnetic-energy component |
| 10 | `emag3` | `diagnostics.f90:calculate_scalars`; `twopi*energy_p()/tpifac` | reduced/native pressure/third energy term as named in current source | third magnetic/pressure-associated diagnostic column historically labelled `emag3` |
| 11 | `etot` | `diagnostics.f90:calculate_scalars`; `etot = ekin + emag - ptoto` | total diagnostic energy; upstream compare.py explicitly skips this column | aggregate diagnostic energy |

The current source also writes the same energy variables into native HDF5 scalar datasets (`E_MP`, `E_MT`, `E_P`, `E_KP`, `E_KT`, `E_K3`, etc.) in `output.f90:hdf5_write_scalars`.

## Time-zero mismatch implication

The first upstream comparison failure occurs at row 0 before timestep evolution. The failed columns are the magnetic-energy diagnostics (`emagp`, `emagt`, `emag3`) and total energy. That points to initialization, diagnostic normalization, or reference provenance rather than timestep instability.

## Reference provenance

`unstructured/regtest/KPRAD_2D/base/C1ke` was last updated in 2020 (`8964f6bf`, plus row 0 inherited from 2019). Current `diagnostics.f90` has multiple later diagnostic changes, including 2023 magnetic-energy scalar additions and 2026 energy/harmonic diagnostic changes. This is evidence of a plausible reference/code-era mismatch, but it is not by itself a numerical regression pass.

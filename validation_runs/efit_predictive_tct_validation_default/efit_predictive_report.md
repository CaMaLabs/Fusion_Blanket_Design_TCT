# DIII-D EFIT-Grid Predictive TCT Validation

- Status: `DIIID_EFIT_GRID_PREDICTIVE_REDUCED_SUPPORTED`
- GEQDSK: `EFITD    06/25/2013    #158103  3796ms           3 129 129`
- GEQDSK SHA-256: `1a5db6deb2494e9805f08c1dae5ee27fd2d6e87f8a73641df46b9fcbc087a51e`

This campaign evolves a reduced perturbation-flux equation directly on the real DIII-D EFIT R-Z grid. The EFIT normalized-flux separatrix geometry defines both the edge perturbation and actuator localization. The delayed perturbation drive is synthetic.

| Grid | Predictive time | Magnitude time | Peak time | Earlier than magnitude | Before peak | Peak reduced | Integrated reduced | Noisy/delayed peak reduced | Noisy/delayed integrated reduced |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| coarse | 2.500 | 4.300 | 12.000 | True | True | True | True | True | True |
| native | 2.500 | 4.200 | 12.000 | True | True | True | True | True | True |

## Interpretation

PASS: one predictive controller configuration triggers before magnitude feedback and the uncontrolled peak on native and coarse DIII-D EFIT grids, reduces peak and integrated perturbation current, remains beneficial with noise and delay, and approaches fixed-moderate performance with lower effort than fixed strong control. This is an EFIT-backed reduced R-Z model, not a field-aligned BOUT++ or nonlinear M3D-C1 machine-geometry validation; the perturbation drive is synthetic and raw diagnostic timing is unavailable.

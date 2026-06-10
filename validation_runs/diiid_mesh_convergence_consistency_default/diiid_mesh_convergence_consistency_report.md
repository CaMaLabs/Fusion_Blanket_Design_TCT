# DIII-D Mesh Resolution Convergence and GEQDSK Consistency

- Status: `DIIID_MESH_CONVERGENCE_AND_GEQDSK_CONSISTENCY_SUPPORTED`
- Generated: `2026-06-10T20:48:09.570068+00:00`
- GEQDSK SHA-256: `1a5db6deb2494e9805f08c1dae5ee27fd2d6e87f8a73641df46b9fcbc087a51e`

## Source-equilibrium consistency

| Mesh | Dimensions | psi rel. RMSE | Br rel. RMSE | Bz rel. RMSE | Bt rel. RMSE | Connected pressure rel. RMSE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| coarse | 20 x 56 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 |
| base | 40 x 112 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 |
| fine | 60 x 168 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 |

The pressure comparison is restricted to the core/SOL-connected region.
Hypnotoad intentionally reflects pressure across flux in private-flux
divertor legs, so direct GEQDSK profile equality is not expected there.

## Resolution convergence

| Field | Coarse to base rel. RMSE | Base to fine rel. RMSE | Improves |
| --- | ---: | ---: | ---: |
| `Rxy` | 4.581287e-03 | 1.768339e-03 | True |
| `Zxy` | 1.284427e-02 | 5.571550e-03 | True |
| `psixy` | 5.885060e-03 | 2.016744e-03 | True |
| `Brxy` | 5.254352e-02 | 2.358932e-02 | True |
| `Bzxy` | 1.905266e-02 | 6.614690e-03 | True |
| `Bpxy` | 1.660979e-02 | 4.855603e-03 | True |
| `Btxy` | 4.689912e-03 | 1.918689e-03 | True |
| `Bxy` | 4.655423e-03 | 1.909050e-03 | True |
| `J` | 8.017167e-02 | 2.576153e-02 | True |
| `g11` | 2.293405e-02 | 6.274441e-03 | True |
| `g22` | 2.529901e-01 | 6.632015e-02 | True |
| `g33` | 3.031931e-01 | 1.707465e-01 | True |

- Improving fields: `12 / 12`
- All required mesh fields finite: `True`
- All source-equilibrium checks pass: `True`

## Claim boundary

This validates field-aligned mesh generation consistency and quantifies
resolution sensitivity for one DIII-D equilibrium. It does not establish
physics-solution convergence, exact-topology BOUT++ evolution, TCT control
performance, or agreement with experimental diagnostics.

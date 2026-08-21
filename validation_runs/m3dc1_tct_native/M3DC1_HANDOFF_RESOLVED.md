# M3D-C1 Handoff Resolved

Sources searched in `/home/ubuntu/work/openmc/sweep`: `validation_runs/bout_tct_dudson_resolution_highres/M3DC1_HANDOFF.json`, `validation_runs/bout_tct_dudson_resolution_default/M3DC1_HANDOFF.json`, `bout_tct_dudson_resolution_audit.py`, and current-sheet validation outputs.

Resolved high-resolution BOUT values used without tuning:

| value | source | resolved value |
|---|---|---:|
| peak current reduction fraction | highres `M3DC1_HANDOFF.json` | 0.14336391448782237 |
| actuator multiplier used in M3D-C1 | `1 - peak_current_reduction_fraction` | 0.8566360855121776 |
| integrated current reduction fraction | highres handoff | 0.6855924599716687 |
| controlled peak sheet FWHM | highres handoff | 24 cells |
| uncontrolled peak sheet FWHM | highres handoff | 24 cells |
| magnetic-energy final change | highres handoff | -0.9508571237402103 |

No dimensional current-sheet geometry was present in the handoff JSON; therefore the native mapping used the smallest available dimensionless native actuator multiplier rather than inventing geometry.

# C1ke Column Provenance

Writer: `/home/ubuntu/M3DC1-official/unstructured/output.f90`, lines 186-190 in commit `e17c0b7e`.

| column | variable | source routine | mathematical meaning | normalization/scaling | units | equilibrium vs perturbation | timing |
|---:|---|---|---|---|---|---|---|
| 1 | ntime | output | time-step index | none | index | not a physical field | after derived quantities, at output |
| 2 | time | output | simulation time | code time normalization | code units | state time | at output |
| 3 | ekin | diagnostics:derived_quantities | ekin = ekinp + ekint + ekin3 | integrals multiplied by twopi/tpifac | code energy | total kinetic | after initialization and derived quantities |
| 4 | gamma_gr | output/diagnostics | kinetic-energy growth rate | finite-difference ratio; zero at ntime=0 in current code | 1/code time | diagnostic | at output |
| 5 | ekinp | diagnostics:energy_kp | poloidal kinetic energy | twopi*energy_kp()/tpifac | code energy | kinetic | derived quantities |
| 6 | ekint | diagnostics:energy_kt | toroidal kinetic energy | twopi*energy_kt()/tpifac | code energy | kinetic | derived quantities |
| 7 | ekin3 | diagnostics:energy_k3 | third/parallel kinetic energy | twopi*energy_k3()/tpifac | code energy | kinetic | derived quantities |
| 8 | emagp | diagnostics:energy_mp | poloidal magnetic energy in plasma zone | twopi*energy_mp()/tpifac | code energy | magnetic equilibrium plus perturbation as represented by current fields | derived quantities |
| 9 | emagt | diagnostics:energy_mt | toroidal magnetic energy in plasma zone | twopi*energy_mt()/tpifac | code energy | magnetic equilibrium plus perturbation as represented by current fields | derived quantities |
| 10 | emag3 | diagnostics:energy_p | pressure/internal-energy scalar included in magnetic/energy block | twopi*energy_p()/tpifac | code energy | thermal/pressure state | derived quantities |
| 11 | etot | diagnostics:derived_quantities | etot = ekin + (emagp+emagt+emag3) - ptoto | code energy | code energy | total diagnostic; ignored by upstream compare.py | at output |

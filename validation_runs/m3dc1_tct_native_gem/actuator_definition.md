# Actuator Definition

Chosen actuator: native GEM magnetic-flux perturbation amplitude `eps` in `C1input`.

Upstream source path: `/home/ubuntu/M3DC1-official/unstructured/init_gem.f90`, `gem_reconnection_per`, where `eps*cos(akx*x)*cos(akz*z)` seeds the reconnecting flux perturbation.

Baseline: `eps = 1e-3`.

Controlled: `eps = 8.566360855e-4 = 1e-3 * (1 - 0.14336391448782237)`, directly using the frozen BOUT peak-current reduction fraction.

Sign-reversed falsification: `eps = -8.566360855e-4`.

No amplitude sweep was run. Mesh, timestep, transport, executable, MPI layout, and output cadence were unchanged across baseline/control/falsification.

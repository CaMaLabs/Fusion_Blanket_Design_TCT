# GEM Topology Geometry

Case: valid native GEM circle/source mesh configuration derived from the exploratory GEM rung.

Field files inspected: `C1.h5`, `equilibrium.h5`, and `time_000.h5` through `time_005.h5`. The available field datasets include `psi`, `jphi`, `I`, `phi`, `V`, `E_R`, `E_PHI`, `E_Z`, `E_par`, `eta_J`, and, when enabled, `cd_source`. Native topology scalars include `Reconnected_Flux`, `psi0`, `psi_lcfs`, `psimin`, `xmag`, `zmag`, `xnull`, and `znull`.

The extractor uses `/mesh/elements` columns 5 and 6 as physical R,Z element-center coordinates for this 2-D output and uses the first field coefficient as an element-center diagnostic value. Higher coefficients are retained only as QA extrema.

The native X-point scalar during the baseline is near `R=10`, `Z=1` for the active window. The actuator was therefore centered at `R_0cd=10.0`, `Z_0cd=1.0`. The highest element-center `jphi` is intermittent on this coarse mesh, so the X-point scalar, not the noisy max-J element, was used for placement.

Initial nearest element to the source center: `R=10.0157`, `Z=0.999877`, `jphi(t=0)=+0.00324238`.

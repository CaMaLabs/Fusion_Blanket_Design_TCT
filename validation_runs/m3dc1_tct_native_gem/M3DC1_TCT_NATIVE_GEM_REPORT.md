# Native M3D-C1 GEM TCT Exploratory Rung

Primary classification: `NATIVE_TCT_NO_EFFECT`

This continuation tested a native GEM reconnection initializer after the official `RMP_nonlin` path remained invalid on this host. The controlled case changed only `eps`, the upstream GEM magnetic-flux perturbation amplitude.

| metric | baseline | controlled | change |
|---|---:|---:|---:|
| peak current proxy | 0.29897373 | 0.29897503 | -0.000436688% reduction |
| integrated current proxy | 1.0892032 | 1.0892032 | -1.5901e-06% |
| final magnetic energy | 207.887 | 207.881 | -0.00288618% |
| final native Reconnected_Flux | 0.000349069 | 0.000277415 | -20.5272% |

Interpretation: the native topology scalar changes because the initial GEM perturbation amplitude was changed. It is not accompanied by a current-loading reduction, and the sign-reversed falsification confirms the response is dominated by perturbation-sign bookkeeping. This does not support the BOUT++ current-loading-reduction effect in this native GEM mapping.

Refinement was skipped because no same-physical-state finer circle mesh was available in the bundled artifacts.

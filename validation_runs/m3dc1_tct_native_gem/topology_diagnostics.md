# Topology Diagnostics

Primary native topology metric: `C1.h5:/scalars/Reconnected_Flux`, emitted by M3D-C1 diagnostics.

Supporting native topology/search scalars: `psi0`, `psi_lcfs`, `psimin`, `xmag`, `zmag`, `xnull`, and `znull`.

Result: reducing `eps` reduces the final native `Reconnected_Flux`, but this follows directly from reducing the initial GEM perturbation amplitude and does not reduce the current-loading proxy. The sign-reversed falsification flips the sign of `Reconnected_Flux` while leaving current nearly unchanged, supporting the interpretation that this rung measures seed-perturbation bookkeeping rather than a TCT current-loading effect.

Reliability warning: on this coarse circular mesh carrier, native magnetic-axis/X-point search is intermittent at some output times. The scalar trajectory is finite and repeatable, but this is not a strong topology-validation rung.

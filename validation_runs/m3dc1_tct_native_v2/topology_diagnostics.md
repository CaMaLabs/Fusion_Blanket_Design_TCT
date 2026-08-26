# Topology Diagnostics

Primary native topology metric: `C1.h5:/scalars/Reconnected_Flux`.

Supporting topology/search scalars: `psi0`, `psi_lcfs`, `psimin`, `xmag`, `zmag`, `xnull`, and `znull`.

Field-level diagnostics: element-center `psi` and `jphi`, high-|J| half-maximum loading, sheet centroid, sheet FWHM in R/Z, and finite-difference `d(Reconnected_Flux)/dt`.

Result: the localized current-drive source produced a very small high-|J| loading reduction without increasing peak or final native `Reconnected_Flux` and without increasing the finite-difference reconnection-rate proxy. The displaced same-amplitude source did not reproduce the current reduction and slightly increased peak `jphi`, supporting locality.

Caveat: this is a coarse, short GEM rung. The current-loading effect is weak, so it should be treated as a first local-coupling signal, not validation of a physical actuator.

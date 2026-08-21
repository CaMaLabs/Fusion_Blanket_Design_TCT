# Topology Diagnostics

This first native rung uses official `RMP`, a one-step linear-response case. Explicit island-width and X/O-point tracking are not emitted in the available scalar outputs. The least-assumptive topology-sensitive native quantities available are scalar flux and psi diagnostics: `toroidal_flux`, `psi0`, `psimin`, and `psi_lcfs`.

Derived reconnection/flux-transfer proxy: `abs(toroidal_flux(t) - toroidal_flux(0))`. It is labeled DERIVED and is not a formal reconnection rate.

Result: baseline, controlled, and sign-reversed control have identical C1ke/native scalar trajectories over the official one-step duration. Therefore there is no evidence in this rung that the actuator reduces current loading, changes sheet width, changes magnetic-energy release, delays topology change, or changes flux transfer.

Classification impact: lower peak J alone is not present; topology improvement is not present; primary state is `NATIVE_TCT_NO_EFFECT`.

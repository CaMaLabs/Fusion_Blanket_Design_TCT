# Native Case Selection

Selected baseline: official `unstructured/regtest/RMP` with the bundled single-part source mesh `diiid-0.02-2.5-4.0-4K0.smb`, `m3dc1_2d_complex`, one MPI rank, and unchanged physical inputs.

Why: it is the smallest non-KPRAD official case that exercises native RMP/current-response machinery and passes the hard initialization/reference gate on this runtime.

Rejected alternatives:

| case | reason rejected |
|---|---|
| `RMP_nonlin` checked-in 16-part mesh | t=0 magnetic energies ~1e24 and reference mismatch; initialization invalid |
| `RMP_nonlin` single-part source mesh | t=0 mismatch and nonlinear blow-up by timestep 3; initialization/reference invalid |
| `RMP` checked-in 16-part mesh | `Volume=0`/near-zero and t=0 energy mismatch |
| `adapt` | adaptation/t=0 oriented, not a clean paired current/topology test |
| `KPRAD_*` | explicitly excluded; not a TCT topology case |
| `NCSX` | larger stellarator case, no direct TCT/RMP actuator mapping needed for first rung |

This is a first native actuator-mapping falsification rung, not a nonlinear reconnection proof.

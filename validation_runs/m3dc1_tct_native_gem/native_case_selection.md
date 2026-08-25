# Native GEM Case Selection

Selected exploratory rung: native `itaylor = 3` GEM reconnection initializer on the official `RMP_nonlin` single-part circle mesh carrier, run with the real 2D executable.

Why: official `RMP_nonlin` 3D remains initialization-invalid on this host with the checked-in 16-part mesh, and the available splitter cannot regenerate the partition without an MPI launch. The GEM initializer is an upstream native reconnection path and emits the native `Reconnected_Flux` scalar.

Rejected alternatives:

| candidate | result |
|---|---|
| `RMP_nonlin` checked-in 16-part 3D | invalid t=0 energy scale and rank killed by signal 9 |
| regenerated `RMP_nonlin` 16-part mesh | local `split_smb` invocation aborted unless launched with enough MPI peers |
| rectilinear GEM deck | failed because this build expects SCOREC model/mesh files |
| bundled 2K circle mesh as refinement | rejected as same-physics refinement because its model changes wall/boundary geometry |

This is an exploratory native reconnection actuator-mapping rung, not an official regression result.

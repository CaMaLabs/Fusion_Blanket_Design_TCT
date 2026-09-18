# Quantum Surrogate Search Bridge

This branch already contains a FAIR-MAST-seeded reduced-order TCT forward
surrogate (`fair_mast_tct_forward_surrogate.py`) and a deterministic 320-scenario
sensitivity sweep (`fair_mast_tct_forward_sensitivity.py`).

`fair_mast_tct_quantum_search_export.py` exports that existing sensitivity
surface for a zero-QPU compiler/search experiment in
`CaMaLabs/RecycledQubitRegisters`.

## Search variables

The exported grid is the Cartesian product already used by the sensitivity
study:

- standing bias: 4 values
- boost reduction: 4 values
- false-trigger cost multiplier: 5 values
- event-rate multiplier: 4 values

Total: `4 * 4 * 5 * 4 = 320` parameter scenarios.

By default the scalar objective is the existing `mirnov_toroidal_loss`, and the
lowest-loss settings are marked for an unstructured-search benchmark. Ties at
the requested top-k boundary are included deterministically.

## Boundary

The export is not a new plasma model. It preserves the existing FAIR-MAST
reduced-order assumptions and claim boundaries. The JSON marking table is
classically precomputed; using it as a Grover oracle is a compiler workload and
idealized oracle-query experiment, not evidence of an end-to-end quantum
speedup.

A stronger follow-up would implement the simple expected-loss expression as
reversible fixed-point arithmetic and compare that coherent oracle's resource
cost with classical evaluation. That should only be attempted after the table
oracle establishes whether this workload maps favorably to the current quantum
compiler.

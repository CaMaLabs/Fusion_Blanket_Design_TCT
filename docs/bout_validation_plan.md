# BOUT++ Validation Plan

This is the project path for using BOUT++ as an independent plasma-side check.
BOUT++ should be treated as a validation filter for reduced edge, transport, and
stability claims. It does not validate blanket neutronics, p-B11 nuclear yield,
direct conversion, or material lifetime.

## Current harness

The first runner is:

```bash
source /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/bout-env.sh
cd /root/Fusion_Blanket_Design_TCT
python3 bout_validation_bridge.py --case-dir validation_runs/bout_conduction_default --nout 20
```

It maps the current default design into the BOUT++ 1D conduction example and
writes:

- `validation_runs/bout_conduction_default/BOUT.inp`
- `validation_runs/bout_conduction_default/BOUT.dmp.0.nc`
- `validation_runs/bout_conduction_default/summary.json`

This is Level 3 plumbing evidence only: the current fusion surrogate can drive an
independent BOUT++ executable and produce structured outputs. It is not yet
evidence that the TCT mechanism works in real edge plasma.

## Mapped quantities

The bridge currently maps:

- wall load to perturbation amplitude
- lithium wall modifier to perturbation width
- TCT control strength to effective diffusivity
- density, field, temperature, betaN, and qstar into the summary for traceability

The first completed run produced a decaying heat perturbation in the reduced
conduction case. That is a smoke-test pass for the workflow, not a physics proof.

## Validation ladder

1. **Conduction sanity check**
   Confirm BOUT++ can consume the project state, run deterministically, and
   produce heat-transport summaries.

2. **Parameter sensitivity**
   Sweep TCT control strength, wall load, and lithium wall modifier. The minimum
   useful result is a monotonic, explainable trend in peak heat perturbation or
   decay time.

3. **SOL / blob-like transport**
   Move from 1D conduction to a scrape-off-layer or blob transport example.
   Track intermittency, peak heat pulses, and target heat-load proxies.

4. **Reduced drift / edge turbulence**
   Use a BOUT++ reduced turbulence model such as Hasegawa-Wakatani-style or
   DALF-style physics if available in the local build. This is the first rung
   that can challenge the project claim that distributed dissipation is better
   than rare severe events.

5. **ELM / peeling-ballooning oriented setup**
   Build or import an equilibrium/grid and test whether pressure-gradient and
   current-sheet assumptions reduce crash severity in a mainstream edge-MHD
   framing.

6. **High-fidelity handoff**
   Use BOUT++ results to decide which cases deserve M3D-C1, JOREK, OpenMC, or
   materials follow-up. BOUT++ should narrow the cases before expensive tools are
   used.

## Falsification rules

Demote the TCT claim if a BOUT++ rung shows any of these outcomes under
reasonable parameter choices:

- the controlled case has higher peak heat load than the uncontrolled case
- event severity increases when the surrogate predicts lower severity
- trends reverse under modest grid, timestep, or boundary-condition changes
- only numerically fragile settings support the claimed direction

Promote the claim only if the same directional result survives resolution checks,
boundary-condition variants, and at least one model family beyond the toy
surrogate.

## Near-term next run

The next useful experiment is a small sweep around the default design:

- `tct_control_strength`: 0.0, 0.25, 0.5, 0.75, 1.0
- wall-load scale: 0.5x, 1.0x, 2.0x
- compare peak decay ratio and final peak perturbation

That sweep will say whether the current BOUT++ mapping supports the same
directional story as the internal reactor surrogate.

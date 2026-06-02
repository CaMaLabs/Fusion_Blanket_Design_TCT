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

The sweep runner is:

```bash
source /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/bout-env.sh
cd /root/Fusion_Blanket_Design_TCT
python3 bout_controlled_sweep.py --sweep-dir validation_runs/bout_controlled_sweep_default --nout 20
```

It writes per-case BOUT++ outputs plus:

- `validation_runs/bout_controlled_sweep_default/sweep_results.csv`
- `validation_runs/bout_controlled_sweep_default/sweep_summary.json`

## Controlled sweep result

The default 15-case sweep completed with monotonic final-peak reduction at every
wall-load scale:

| Wall-load scale | Final peak at TCT 0.0 | Final peak at TCT 1.0 | Reduction |
| --- | ---: | ---: | ---: |
| 0.5x | 0.2564165382 | 0.1358432422 | 47.02% |
| 1.0x | 0.5128330559 | 0.2716867520 | 47.02% |
| 2.0x | 1.0256662793 | 0.5433729445 | 47.02% |

Interpretation: the reduced conduction mapping supports the expected direction
for this specific transport proxy. It is still a first-rung BOUT++ result; the
claim must next survive a less-prescribed SOL, blob, or edge-turbulence model.

## Robustness and falsification checks

The next runner is:

```bash
source /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/bout-env.sh
cd /root/Fusion_Blanket_Design_TCT
python3 bout_robustness_sweep.py --run-dir validation_runs/bout_robustness_sweep_default --nout 20
```

It tests:

- mesh sensitivity at `ny = 50, 100, 200`
- boundary sensitivity across `dirichlet_o2`, `dirichlet_o4`, and `neumann`
- alternative control mappings where TCT changes amplitude or width instead of
  directly increasing effective diffusivity

The alternative mappings are deliberately stricter falsification checks. If they
do not support the same directional trend, the correct interpretation is not
that BOUT++ disproves TCT, but that the current conduction proxy only supports a
narrow transport-control formulation.

## Robustness sweep result

The default 27-case robustness sweep completed successfully:

| Check | Final peak at TCT 0.0 | Final peak at TCT 1.0 | Reduction | Decay-ratio trend |
| --- | ---: | ---: | ---: | --- |
| `ny = 50` | 0.5126658048 | 0.2716791184 | 47.01% | monotonic |
| `ny = 100` | 0.5128330559 | 0.2716867520 | 47.02% | monotonic |
| `ny = 200` | 0.5128737863 | 0.2716877042 | 47.03% | monotonic |
| `dirichlet_o2` | 0.5128330546 | 0.2716865876 | 47.02% | monotonic |
| `dirichlet_o4` | 0.5128330559 | 0.2716867520 | 47.02% | monotonic |
| `neumann` | 0.5128331076 | 0.2716871852 | 47.02% | monotonic |
| diffusivity mapping | 0.5128330559 | 0.2716867520 | 47.02% | monotonic |
| amplitude mapping | 0.5128330559 | 0.3076998554 | 40.00% | not monotonic |
| width mapping | 0.5128330559 | 0.4640341573 | 9.52% | not monotonic |

Interpretation: the main diffusivity-control trend is stable under the tested
mesh and boundary changes. The broader falsification checks are weaker: reducing
amplitude or broadening the perturbation still lowers absolute final peak, but
does not improve normalized decay ratio. That means the current positive result
should be framed as support for a transport/diffusivity-style TCT proxy, not as
general evidence that every plausible control mapping works.

## Blob / SOL source-shaping check

The next rung uses the BOUT++ `blob2d` model instead of the 1D conduction
example:

```bash
cmake --build /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/BOUT-dev/build --target blob2d -j2
source /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/bout-env.sh
cd /root/Fusion_Blanket_Design_TCT
python3 bout_blob_sol_sweep.py --run-dir validation_runs/bout_blob_sol_sweep_default --nout 12
```

This check does not prescribe higher diffusivity. It represents TCT-like control
as source shaping: the initial blob is broadened and lowered while approximately
conserving a Gaussian excess inventory proxy. The measured quantities are peak
density excess, time-integrated peak excess, high-percentile excess, and spatial
concentration.

## Blob / SOL source-shaping result

The default 9-case `blob2d` sweep completed successfully:

| Grid | Max peak at TCT 0.0 | Max peak at TCT 1.0 | Peak reduction | Integrated peak reduction | Concentration trend |
| --- | ---: | ---: | ---: | ---: | --- |
| coarse | 0.4957997816 | 0.1618995540 | 67.35% | 66.94% | monotonic |
| base | 0.5027107645 | 0.1621961389 | 67.74% | 67.15% | monotonic |
| fine | 0.5074445184 | 0.1626809705 | 67.94% | 67.30% | monotonic |

Interpretation: this is stronger than the conduction-only checks because the
positive trend is produced in a 2D blob/SOL model without directly increasing
diffusivity. It still does not prove the full TCT mechanism; the control is a
source-shaping proxy. The next hard test is to add source shaping or localized
damping to a reduced turbulence model where intermittent structures form from
the model dynamics rather than from a prescribed initial blob.

## Reduced turbulence check

The next rung uses the BOUT++ Hasegawa-Wakatani model:

```bash
cmake --build /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/BOUT-dev/build --target hasegawa-wakatani -j2
source /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/bout-env.sh
cd /root/Fusion_Blanket_Design_TCT
python3 bout_hw_turbulence_sweep.py --run-dir validation_runs/bout_hw_turbulence_sweep_default --nout 40
```

This check moves from a prescribed blob to a reduced drift-turbulence model. The
TCT-like proxy reduces gradient drive and initial vorticity perturbation without
directly changing diffusion. The primary metrics are max fluctuation energy,
time-integrated fluctuation energy, and high-percentile density/vorticity
fluctuations.

## Reduced turbulence result

The default 6-case Hasegawa-Wakatani sweep completed successfully:

| Grid | Max energy at TCT 0.0 | Max energy at TCT 1.0 | Max energy reduction | Integrated energy reduction | Density p95 trend |
| --- | ---: | ---: | ---: | ---: | --- |
| coarse | 0.0011033022 | 0.0006206075 | 43.75% | 55.33% | monotonic |
| base | 0.0012590790 | 0.0006088542 | 51.64% | 56.95% | monotonic |

Interpretation: this is a stronger plasma-side validation rung than the
conduction and prescribed-blob checks because it uses a reduced drift-turbulence
model. The control is still a reduced proxy, not a resolved actuator or current
sheet model, but the positive direction survived a second BOUT++ model family.

## Resolved TCT current-sheet check

The next rung adds a custom BOUT++ reduced-MHD current-sheet model:

```bash
source /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/bout-env.sh
cd /root/Fusion_Blanket_Design_TCT
python3 bout_tct_current_sheet_sweep.py --run-dir validation_runs/bout_tct_current_sheet_sweep_default --nout 20
```

The model evolves `psi` and `omega`, computes `J = -Delp2(psi)`, solves `phi`
from vorticity, and applies a spatially resolved TCT actuator mask near the
current sheet. This is the first validation rung where the actuator is a
localized term in the reduced-MHD equations rather than a global transport
coefficient or prescribed source-shaping-only input.

## Resolved TCT current-sheet result

The default 6-case current-sheet sweep completed successfully:

| Grid | Post-initial max J reduction | Integrated max J reduction | J p99 trend |
| --- | ---: | ---: | --- |
| coarse | 14.07% | 68.32% | monotonic |
| base | 14.16% | 68.07% | monotonic |

Interpretation: this is the strongest validation rung so far because the TCT
effect is represented as a resolved localized actuator/current-sheet term. It is
still a reduced-MHD slab model, so the next credibility step is actuator
placement/timing noise and a higher-resolution convergence pass.

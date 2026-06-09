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

## Resolved actuator robustness check

The robustness runner reuses the custom reduced-MHD current-sheet model, but now
varies actuator placement, mask width, start/end timing, strength, and one
higher-resolution grid:

```bash
source /root/Documents/Codex/2026-05-26/can-you-make-a-list-of/bout-env.sh
cd /root/Fusion_Blanket_Design_TCT
python3 bout_tct_actuator_robustness_sweep.py --run-dir validation_runs/bout_tct_actuator_robustness_default --nout 18
```

The model now accepts `[tct] start_time` and `end_time` so delayed and pulsed
actuation can be tested without changing the equation set between cases.

## Resolved actuator robustness result

The default 16-case robustness sweep completed. Of the 14 controlled cases, 12
reduced both post-initial peak current and time-integrated max current. All 14
reduced time-integrated max current.

| Check | Cases | Min post-initial max J reduction | Min integrated max J reduction | Result |
| --- | ---: | ---: | ---: | --- |
| nominal base actuator | 1 | 14.16% | 65.33% | pass |
| placement offsets `+/-0.04`, `+/-0.08` | 4 | 2.98% | 24.73% | pass, weak at large offsets |
| width scales `0.8x`, `1.2x`, `2.2x` | 3 | 12.76% | 45.65% | pass |
| strength `0.4`, `1.2` | 2 | 7.33% | 44.97% | pass |
| fine-grid nominal actuator | 1 | 14.05% | 65.08% | pass |
| delayed/pulsed timing | 3 | 0.00% | 44.81% | mixed |

Best case: `strength_1p2` reduced post-initial peak current by 20.41% and
integrated max current by 74.89%. The fine-grid nominal case reproduced the base
direction with 14.05% post-initial peak-current reduction and 65.08% integrated
max-current reduction.

Interpretation: the actuator survives width, moderate placement, strength, and
fine-grid checks. Timing is now the main falsification boundary: delayed
actuation still lowers integrated current, but it cannot reduce the peak-current
metric once the sheet has already formed. The next run should therefore focus on
closed-loop triggering or preemptive timing thresholds rather than only stronger
open-loop damping.

## M3D-C1 / BOUT++ cross-validation bridge

The next bridge ingests the public CaMaLabs M3D-C1 validation artifacts and the
BOUT++ actuator robustness summary:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 m3dc1_bout_cross_validation.py \
  --m3dc1-repo /root/CaMaLabs_M3DC1 \
  --run-dir validation_runs/m3dc1_bout_cross_validation_default
```

This check does not claim full M3D-C1 validation. It verifies that:

- the public M3D-C1 helical proxy `C1.h5` has the expected HDF5 fields and
  explicit proxy metadata,
- the M3D-C1 Candidate-0 proxy campaign passes its hard constraints,
- the open-source FreeGSNKE equilibrium verifier passed in the M3D-C1 repo,
- the BOUT++ resolved actuator reduces nominal and fine-grid current-sheet
  metrics,
- and the timing boundary is explicit rather than hidden.

The intended status is therefore `PASS_WITH_REDUCED_MODEL_BOUNDARIES`, not
`FULL_VALIDATION`.

## Machine equilibrium readiness check

The next bridge responds to the remaining validation gap around named machine
equilibria and EFIT/GEQDSK inputs:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 machine_equilibrium_readiness.py \
  --m3dc1-repo /root/CaMaLabs_M3DC1 \
  --input-dir validation_inputs/machine_equilibria \
  --run-dir validation_runs/machine_equilibrium_readiness_default
```

This check scans the public CaMaLabs/M3DC1 template package and copies only the
small, directly relevant machine-equilibrium inputs into this repo. It verifies
M3D-C1 support for:

- `idevice = 2` for NSTX-family templates,
- `idevice = 3` for ITER templates,
- `idevice = 4` for DIII-D templates,
- `iread_eqdsk = 1` for an EFIT g-file named `geqdsk`,
- profile reads through `iread_ne` and `iread_te`,
- scalar diagnostics through `icalc_scalars`.

Current result: the package is `PARTIAL_MACHINE_EQUILIBRIUM_READY`.

- DIII-D has a public EFIT-backed package with `g158103.03796`,
  `a158103.03796`, and `p158103.03796`.
- NSTX-U and ITER have M3D-C1 machine templates and coil/current material, but
  no public EFIT GEQDSK was found in the scanned public package.

Interpretation: this closes the “no GEQDSK at all” criticism for DIII-D, but it
does not close the full experimental-diagnostics gap. The correct next claim is
that the validation chain now has a DIII-D EFIT anchor and explicit NSTX-U/ITER
input holes, not that all three machines are experimentally validated.

## GEQDSK / EFIT baseline case

The concrete baseline case builder turns the DIII-D EFIT package into a
solver-facing case directory with a `geqdsk` filename, original `g/a/p`
provenance files, density-profile CSV, and filled M3D-C1 input deck:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 geqdsk_efit_baseline_case.py \
  --machine-input validation_inputs/machine_equilibria/diii_d \
  --case-dir validation_inputs/geqdsk_efit_baseline/diii_d_158103_03796 \
  --run-dir validation_runs/geqdsk_efit_baseline_default
```

Current baseline:

- Machine: DIII-D
- Shot/time: `158103 @ 3796 ms`
- GEQDSK source: `g158103.03796`
- M3D-C1 settings filled for the baseline deck:
  - `idevice = 4`
  - `iread_eqdsk = 1`
  - `iread_ne = 1`
  - `iread_te = 1`
  - `eqsubtract = 1`
  - `icalc_scalars = 1`

Interpretation: this is the first named-machine EFIT baseline input case in the
fusion validation repo. It is not yet a completed M3D-C1 run, and it still does
not include raw experimental diagnostic archives.

## M3D-C1 DIII-D GEQDSK smoke run

The next executable gate launches the local M3D-C1 MPICH build against the
imported DIII-D `geqdsk` while borrowing the existing first-linear DIII-D
SCOREC mesh/wall scaffold:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 m3dc1_geqdsk_smoke_run.py \
  --run-dir validation_runs/m3dc1_geqdsk_diiid_smoke_default \
  --timeout 180
```

Current result:

- Status: `M3DC1_STARTUP_SMOKE_PASSED`
- Imported equilibrium: DIII-D shot `158103 @ 3796 ms`
- GEQDSK grid: `129 x 129`
- Solver reached: normal exit after HDF5 output
- Emitted readable HDF5: `C1.h5`, `equilibrium.h5`, and `time_000.h5`
- Smoke flag: `M3DC1_SKIP_WALL_DIST_SOLVE=1`

Interpretation: this is stronger than an input-only EFIT harness because the
local M3D-C1 executable is now launched against the imported DIII-D GEQDSK
package, exits cleanly, and writes readable HDF5. It is still not a completed
M3D-C1 validation run. The smoke path uses a local M3D-C1 patch that
identity-regularizes the wall-distance matrix rows and, when
`M3DC1_SKIP_WALL_DIST_SOLVE=1` is set, keeps `wall_dist` as a neutral zero field
so the imported-equilibrium startup gate can proceed. The exact local M3D-C1
patch is archived with the run:

- `validation_runs/m3dc1_geqdsk_diiid_smoke_default/m3dc1_wall_dist_smoke_gate.patch`

## HW2D / BOUT++ reduced-turbulence cross-code check

With the M3D-C1 wall-distance path blocked by unavailable upstream tooling, the
next open-source validation rung is an independent reduced-turbulence
cross-check:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 hw2d_cross_validation.py \
  --bout-hw-dir validation_runs/bout_hw_turbulence_sweep_default \
  --run-dir validation_runs/hw2d_cross_validation_default
```

Current result:

- Status: `HW2D_BOUT_HW_CROSS_CODE_SUPPORTED`
- BOUT++ and the HW2D-style solver both show monotonic fixed-control
  fluctuation-energy reduction across the tested coarse and base grids.
- BOUT++ integrated-energy reduction from `tct000` to `tct100`:
  - base grid: 56.95%
  - coarse grid: 55.33%
- HW2D-style integrated-energy reduction from `tct000` to `tct100`:
  - base grid: 48.61%
  - coarse grid: 48.60%
- The HW2D timing check preserves the expected ordering that steady moderate
  early control beats late strong control on both grids.

Interpretation: this is the strongest fully open-source plasma-side rung after
the M3D-C1 startup/HDF5 gate. It cross-checks the reduced-gradient TCT proxy in
two independent Hasegawa-Wakatani implementations. It does not prove machine
geometry, experimental EFIT agreement, or a wall-distance M3D-C1 fix. It also
does not prove that moderate control is globally optimal: in this reduced HW2D
timing model, steady strong control has the lowest integrated energy, and
over-control remains an unresolved actuator-model question. The validated claim
is narrower and useful: early control beats late intervention in this
open-source reduced-turbulence check.

## Closed-loop threshold-control check

The next rung replaces prescribed actuator timing with a runtime observable:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 closed_loop_tct_validation.py \
  --run-dir validation_runs/closed_loop_tct_validation_default
```

The resolved BOUT++ current-sheet model now supports a latched global
max-vorticity threshold, deterministic sensor-noise injection, and actuator
delay. The campaign compares uncontrolled, fixed moderate, threshold
closed-loop, noisy/delayed closed-loop, and fixed strong strategies across
BOUT++ and HW2D-style coarse/base grids.

Current result: `CLOSED_LOOP_REDUCED_MODEL_MIXED`.

- Closed-loop control reduced integrated burden versus uncontrolled in every
  tested model/grid.
- The noisy/delayed closed-loop case also reduced integrated burden in every
  tested model/grid.
- BOUT++ closed-loop duty was 73.68% on the coarse grid and 84.21% on the base
  grid, below continuous fixed-strong actuation.
- BOUT++ threshold crossing occurred at approximately 4.96 coarse-grid time
  units and 2.40 base-grid time units.
- Closed loop did not reduce the reported peak metric because the threshold
  fired after the first peak.
- BOUT++ closed loop did not approach fixed-moderate integrated performance
  within the predefined 20% criterion.
- HW2D-style cases crossed the threshold at time zero from their initialized
  perturbation, so they do not validate precursor detection or lower effort.

Interpretation: this is a useful falsification boundary. A max-vorticity
threshold can reduce accumulated burden after triggering, including with the
tested noise and delay, but this observable triggers too late to reduce the
first peak in the current-sheet case. The next controller should use an earlier
precursor, such as vorticity growth rate, current-sheet thinning rate, or a
combined predictive threshold. The claim should not be promoted to successful
closed-loop peak suppression yet.

## Predictive growth-rate trigger check

The follow-up controller uses measured max-vorticity growth rate instead of
max-vorticity magnitude:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 predictive_tct_validation.py \
  --run-dir validation_runs/predictive_tct_validation_default
```

The BOUT++ model supports this through `feedback_mode = 1`, with a minimum
observation window of 0.25 time units to prevent the initial solver derivative
from counting as a precursor. The campaign compares uncontrolled, fixed
moderate, old magnitude threshold, predictive growth threshold, noisy/delayed
predictive threshold, and fixed strong control.

Current result: `PREDICTIVE_TRIGGER_BOUT_SUPPORTED_HW2D_LIMITED`.

- BOUT++ predictive trigger time:
  - base grid: 0.326 time units
  - coarse grid: 0.328 time units
- Old BOUT++ magnitude-trigger time:
  - base grid: 2.398 time units
  - coarse grid: 4.957 time units
- BOUT++ predictive control reduced post-initial peak current versus both
  uncontrolled and the old magnitude-threshold controller on both grids.
- BOUT++ predictive control reduced integrated current versus uncontrolled and
  remained within 20% of fixed moderate integrated performance on both grids.
- The noisy/delayed predictive case remained integrated-beneficial on both
  BOUT++ grids.
- BOUT++ predictive duty was output-sampled at 94.74%, below fixed strong
  continuous actuation, but sub-output delay timing should not be over-read
  from that duty metric.
- HW2D-style predictive cases reduced integrated fluctuation energy, but did not
  reduce the peak or trigger earlier than the magnitude threshold because the
  initialized-decay HW2D setup is not a clean precursor-growth test.

Interpretation: this repairs the falsification boundary found by the previous
closed-loop check for the resolved BOUT++ current-sheet model. A predictive
growth-rate trigger can fire before the first reported current peak and reduce
both peak and integrated current. The result is not yet a full cross-model
closed-loop validation because the current HW2D setup does not provide a
comparable growing precursor. The next open-source target is a HW2D initial
condition or drive configuration with a delayed growth phase, so the predictive
trigger can be tested against an independent model with a real precursor window.

## HW2D delayed-growth predictive check

The independent HW2D-style follow-up replaces the initialized-decay case with a
low-amplitude initial state and an explicit delayed density-gradient drive:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 hw2d_delayed_growth_validation.py \
  --run-dir validation_runs/hw2d_delayed_growth_validation_default
```

The density-gradient drive is held at a quiet value through time 2 and ramps to
the target value by time 4. Both coarse and base grids use the same initial
amplitude, drive schedule, controller sampling interval, filter, magnitude
threshold, growth-rate threshold, noise fraction, actuator delay, and control
strengths.

Current result: `HW2D_DELAYED_GROWTH_PREDICTIVE_SUPPORTED`.

- The predictive trigger fired at time 4.305 on the base grid and 4.400 on the
  coarse grid.
- The magnitude trigger fired at approximately time 8.0 on both grids.
- The uncontrolled peak occurred at time 12.0 on both grids.
- Predictive control reduced peak 95th-percentile absolute vorticity by 28.24%
  on the base grid and 27.84% on the coarse grid.
- Predictive control reduced integrated fluctuation energy by 29.65% on the
  base grid and 29.13% on the coarse grid.
- The noisy/delayed predictive case reduced both peak and integrated burden on
  both grids.
- Predictive control used less integrated actuation effort than continuously
  applied fixed moderate or fixed strong control.

Interpretation: together with the resolved BOUT++ current-sheet result, this
supports the predictive growth-rate trigger across two reduced-model
implementations with a genuine precursor window. It remains a synthetic
reduced-model validation: the delayed drive schedule is deliberately
constructed and is not an experimentally measured tokamak precursor. The next
step is to map the controller onto an EFIT-backed machine-equilibrium case and
anchor its observable, threshold, noise, and delay to diagnostic data.

## DIII-D EFIT-grid predictive check

The next rung maps the predictive controller onto the imported DIII-D shot
158103 at 3796 ms GEQDSK:

```bash
cd /root/Fusion_Blanket_Design_TCT
python3 efit_predictive_tct_validation.py \
  --run-dir validation_runs/efit_predictive_tct_validation_default
```

The campaign evolves a reduced perturbation-flux equation directly on the real
EFIT R-Z flux grid. The normalized-flux separatrix geometry defines the edge
perturbation and actuator masks. The native `129 x 129` GEQDSK grid and a
downsampled `65 x 65` grid use one controller configuration. The delayed
perturbation drive remains synthetic because raw diagnostic precursor timing is
not available in the repository.

Current result: `DIIID_EFIT_GRID_PREDICTIVE_REDUCED_SUPPORTED`.

- Predictive feedback triggered at time 2.5 on both grids.
- Magnitude feedback triggered at time 4.2 on the native grid and 4.3 on the
  coarse grid.
- The uncontrolled perturbation-current peak occurred at time 12.0.
- Predictive control reduced peak perturbation current by 45.90% on the native
  grid and 52.50% on the coarse grid.
- Predictive control reduced integrated perturbation current by 36.89% on the
  native grid and 42.64% on the coarse grid.
- The noisy/delayed predictive case reduced both peak and integrated
  perturbation current on both grids.
- Predictive integrated performance remained within 20% of fixed moderate
  control while using less effort than continuously applied fixed strong
  control.

Interpretation: the controller has now been applied to an actual DIII-D
EFIT-backed geometry, closing the input-only machine-equilibrium gap. This is
still a reduced R-Z perturbation-flux model, not a field-aligned BOUT++ run, a
nonlinear M3D-C1 control run, or validation against raw DIII-D diagnostics. No
Hypnotoad/BOUT++ machine mesh is available in the current open tooling. The next
rung requires generating that field-aligned mesh or obtaining a runnable
machine-geometry control model and anchoring the synthetic drive to diagnostic
precursor timing.

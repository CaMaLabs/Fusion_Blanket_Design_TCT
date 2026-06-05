# Validation Status

This repository is a public research workspace for fusion blanket optimization and thickness-controlled tokamak (TCT) concept exploration.

The current codebase should be read as a coupled screening and candidate-ranking workflow. It is not a completed reactor design, and it does not claim that TCT, liquid-lithium coupling, or any finalist blanket geometry has been experimentally validated.

## Current validation matrix

| Component | Current status | Evidence in repo | Next validation step |
|---|---|---|---|
| Plasma operating point | Proxy / analytic model plus partial machine-equilibrium package | `fusion_engine_v5/engine/plasma_model.py`, `validation_inputs/machine_equilibria/`, `validation_runs/machine_equilibrium_readiness_default/` | Run M3D-C1/BOUT++ follow-up against the DIII-D EFIT file; add NSTX-U and ITER EFIT/GEQDSK files when available. |
| TCT control response | Reduced-model BOUT++ plus HW2D-style cross-code support | `bout_tct_current_sheet_sweep.py`, `bout_tct_actuator_robustness_sweep.py`, `bout_hw_turbulence_sweep.py`, `hw2d_cross_validation.py`, `validation_runs/hw2d_cross_validation_default/` | Add closed-loop preemptive triggering and map it onto machine-equilibrium cases. |
| Current-sheet / plasmoid suppression | Reduced-MHD slab support for preemptive actuation | `validation_models/tct_current_sheet/`, `validation_runs/bout_tct_current_sheet_sweep_default/` | Test against EFIT-backed machine equilibria and nonlinear MHD tools; late plasmoid-stop claims remain unsupported. |
| Machine EFIT / GEQDSK inputs | Partial with DIII-D baseline case | DIII-D public EFIT `g/a/p` package copied from CaMaLabs/M3DC1; `validation_inputs/geqdsk_efit_baseline/diii_d_158103_03796/`; NSTX-U and ITER templates found but no public EFIT GEQDSK in the scanned package | Run M3D-C1/BOUT++ follow-up from the DIII-D GEQDSK baseline; add real NSTX-U and ITER equilibrium files; require experimental diagnostics before promoting beyond reduced-model status. |
| Liquid lithium wall moderation | Heuristic engineering proxy | `fusion_engine_v5/engine/lithium_wall.py`, lithium modifier in `reactor_simulation.py` | Add thermal-hydraulic and MHD drag validation, including flow stability and heat removal. |
| Blanket / TBR estimate | Dataset/proxy with OpenMC bridge | `fusion_engine_v5/blanket/`, `run_openmc_validation()` calls | Run explicit OpenMC finalist cases with documented geometry, materials, particles, and uncertainty. |
| Event severity / survivability | Monte Carlo proxy | `_monte_carlo_plasma()` and event-adjusted net power in `reactor_simulation.py` | Compare event rates and damage assumptions with ELM / disruption / reconnection literature or simulation outputs. |
| Plant power balance | Screening-level model | `fusion_engine_v5/engine/power_balance.py` | Separate physics validation from economic scoring; document assumptions. |
| Evolutionary candidate search | Implemented screening workflow | `run_evo_reactor_search.py`, `evo_reactor_runs/` outputs | Run reproducible sweeps, preserve seeds, compare Pareto fronts, and promote finalists to OpenMC/MHD validation. |
| Legacy standalone optimizer | Provenance only | `tct_full_reactor_optimizer.py` | Retained only to show development history; not the current model. |

## What can be claimed from this repo

The repository currently supports this claim:

> A reproducible proxy workflow has been implemented to screen fusion blanket / lithium-wall / TCT-coupled design candidates and identify cases worth higher-fidelity OpenMC and MHD validation.

## What should not be claimed yet

The repository does not yet prove that:

- TCT suppresses real tokamak plasmoids or ELMs.
- Lithium-current coupling stabilizes a real plasma edge.
- Any optimizer-selected blanket is experimentally validated.
- Any candidate is an engineering-ready reactor design.

## Current recommended workflow

1. Run the coupled evolutionary search:

```bash
python run_evo_reactor_search.py
```

2. Inspect:

```text
evo_reactor_runs/history.csv
evo_reactor_runs/pareto_front.json
evo_reactor_runs/best_overall.json
```

3. Promote only stable Pareto candidates to explicit validation.

4. Validate blanket candidates with OpenMC.

5. Validate TCT / edge-plasma behavior with M3D-C1, JOREK, or another suitable MHD workflow.

6. Keep speculative concept notes separate from validated outputs.

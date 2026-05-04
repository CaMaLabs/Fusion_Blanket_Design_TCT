# Uploaded artifact index — fusion/TCT work

This index records the relevant uploaded artifacts I found in the ChatGPT file library for the Fusion Blanket Design / TCT project. Raw binary PDFs/images from the ChatGPT file library were not directly exposed to the GitHub connector, so this commit captures a faithful manifest and extracted technical snapshot rather than the original binary bytes.

## Core uploaded artifacts found

### `dt_tct_simulation.py`
- Type: Python simulation script
- Created: 2026-03-21
- Purpose: DT fusion Monte Carlo + TCT controller simulation, API contract returning summaries/tails/dataframes.
- Key sections visible from extracted content:
  - DT fusion power scaling
  - radiated power model
  - net power calculation
  - burst precursor model
  - burst probability sampling
  - TCT trigger evaluation and controller action
  - Monte Carlo sample generation

### `manuscript.html`
- Type: HTML manuscript
- Created: 2026-03-23
- Title: *Plasmoid Suppression via Thickness-Controlled Resistivity in Inertial Reduced MHD*
- Core claim: enforcing current-sheet thickness above a threshold near alpha ≈ 10 suppresses plasmoid-mediated collapse in the reduced MHD model.
- Reported comparison:
  - alpha = 12: floor enforced, coherent/smooth sheet behavior
  - alpha = 5: floor violated, fragmented/plasmoid-like behavior

### `TCT_Reactor_Gen5_Full_With_Plots.pdf`
- Type: PDF summary paper with figures
- Created: 2026-03-23
- Scope: RMHD threshold work, DT/TCT checkpoint, modern AnyClaw control branch, and Ubuntu/OpenMC validation status.
- Key extracted values:
  - Pnet ≈ 2019.99 MW
  - Pfus ≈ 4033.47 MW
  - Q ≈ 2.003
  - betaN ≈ 2.091, below stated 2.5 cap
  - wall load ≈ 3.960 MW/m², near stated 4.0 cap
  - q* ≈ 2.590, above stated 2.4 minimum
  - best early trigger ≈ 0.55
  - current default promotion family near li_current ≈ 0.10–0.12
  - main unresolved bottleneck: blanket/OpenMC/TBR realization

### `TCT_Reactor_Gen5_Paper.pdf`
- Type: PDF paper
- Created: 2026-03-23
- Scope: consolidated Gen5 paper tying thickness-controlled reconnection to lithium-driven reactor stability.
- Noted limitation: preliminary OpenMC TBR values were low in the early model and likely affected by geometry/material mapping issues.

### OpenMC / thermal / TBR screenshot artifacts
Relevant screenshots found showing terminal outputs and intermediate verification states:
- `Screenshot_20260402-193626.png`: geometry debug and OpenMC-style run output; visible result includes `be_outer_kill TBR=2.20993`.
- `Screenshot_20260404-092903.png`: direct OpenMC verification output; visible result saved `candidate_verification_result.json`.
- `Screenshot_20260405-165929.png`: thermal sweep output including radius/wall-load/electric values.
- `Screenshot_20260405-164856.png`: `radius_thermal_sweep_results.json` saved, followed by KeyError.
- `Screenshot_20260405-172342.png`: syntax error while debugging `run_radius_head_to_head.py`.

## Recommended next repo action

1. Add the original raw files from local machine if available:
   - `dt_tct_simulation.py`
   - `manuscript.html`
   - `TCT_Reactor_Gen5_Full_With_Plots.pdf`
   - `TCT_Reactor_Gen5_Paper.pdf`
   - raw CSV/JSON outputs: `candidate_verification_result.json`, `radius_thermal_sweep_results.json`, `weight_sweep_results.csv`, etc.
2. Keep screenshots under `artifacts/screenshots/` only if raw CSV/JSON is not recoverable.
3. Promote extracted results into machine-readable `results/*.json` and `results/*.csv` files so they can be diffed and reproduced.

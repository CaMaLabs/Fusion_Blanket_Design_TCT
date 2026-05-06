from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
OUT = ROOT / "jorek_campaign_package"
OUT.mkdir(parents=True, exist_ok=True)

template_md = """# JOREK Case Input Template

## Purpose
Use this template to define a **minimal first JOREK edge / ELM validation case**
based on the frozen 55 cm reactor reference.

This is **not** the whole reactor.
It is the smallest serious case package needed to test whether the
flow + shear + stabilization story survives in a mainstream edge code path.

---

# 1. Reference design anchor

## Frozen engineering reference
- radius_cm = 55
- R = 0.55 m
- a = 0.55 m
- li_current = 0.10
- TCT supervisor = aggressive
- severity_scale = 0.6
- blanket topology = be_outer_kill
- blanket ordering = Be / Li2O / Li2O / W_Ti_B4C_60_30_10_wt / Be
- split = (0.15, 0.20, 0.40, 0.15, 0.10)
- blanket_thickness = 1.25
- axial_outer_cap_thickness = 0.6

## Why this is frozen
Blanket optimization has already converged to a stable basin.
The next uncertainty is plasma-side edge-event behavior, not blanket geometry.

---

# 2. JOREK case identity

## Case name
- Example: `case_A_baseline_low_control`

## Case purpose
- What specific comparison is this case testing?
- Example:
  - baseline edge behavior
  - high-flow case
  - stabilized surrogate case
  - combined high-flow + stabilized case

## Parent reference
- Which frozen reference is this derived from?

---

# 3. Geometry and equilibrium inputs

## Equilibrium source
Fill in:
- source type:
  - [ ] EFIT / reconstructed equilibrium
  - [ ] synthetic equilibrium
  - [ ] imported reference equilibrium
- file/path:
- shot / case ID:
- date/version:
- notes:

## Magnetic geometry
Fill in:
- major radius R0:
- minor radius a:
- elongation kappa:
- triangularity delta:
- X-point configuration:
  - [ ] lower single null
  - [ ] upper single null
  - [ ] double null
- separatrix / SOL treatment notes:

## q-profile / safety factor
Fill in:
- q95 target:
- q-axis or core q estimate:
- profile source:
- assumptions / smoothing notes:

---

# 4. Plasma profile inputs

## Density profile
Fill in:
- source:
- core density:
- pedestal density:
- edge density:
- profile functional form / fit:
- normalization notes:

## Temperature profile
Fill in:
- source:
- core temperature:
- pedestal temperature:
- edge temperature:
- electron / ion temperature handling:
- profile functional form / fit:

## Pressure profile
Fill in:
- derived from density/temperature:
- direct source if available:
- pedestal pressure:
- edge pressure gradient estimate:
- notes:

## Current profile
Fill in:
- source:
- bootstrap fraction assumption:
- edge current gradient estimate:
- smoothing / regularization notes:

---

# 5. Edge drive definition

## Reduced-model mapping
In the reduced model, `edge_drive` represented:
- pedestal pressure gradient
- edge current gradient / peeling-ballooning drive

## JOREK-side implementation
Fill in:
- which profile parameter(s) will be adjusted to represent edge drive?
- which cases use nominal drive?
- which cases use elevated drive?
- how is consistency maintained across cases?

## Record
- nominal drive case definition:
- elevated drive case definition:
- units / normalization:
- notes:

---

# 6. Flow and shear definition

## Toroidal flow
Reduced-model analog: `v_tor`

Fill in:
- toroidal flow source:
- imposed profile or derived quantity:
- baseline value/profile:
- high-flow case value/profile:
- units:
- notes:

## Poloidal flow
Reduced-model analog: `v_pol`

Fill in:
- poloidal flow source:
- imposed profile or derived quantity:
- baseline value/profile:
- moderate-flow case value/profile:
- units:
- notes:

## Edge shear
Reduced-model analog: derived from `v_tor` + `v_pol`

Fill in:
- how will edge shear be estimated in the JOREK case?
- direct diagnostic quantity:
- derived from flows:
- derived from electric field:
- expected low-shear case:
- expected high-shear case:

---

# 7. TCT surrogate definition

## Important
`TCT` is **not** a native JOREK knob.

So this section must define a **surrogate effect class**, not pretend that JOREK
has a direct TCT parameter.

## Allowed surrogate ideas
Choose one or more:
- [ ] profile shaping change
- [ ] transport modifier
- [ ] edge current-gradient adjustment
- [ ] flow/shear enhancement
- [ ] external stabilization scenario
- [ ] other

## Fill in
- surrogate name:
- physical interpretation:
- how it maps back to reduced-model `tct_gain`:
- low-surrogate case definition:
- high-surrogate case definition:
- justification:

---

# 8. Boundary and wall assumptions

## Boundary conditions
Fill in:
- core boundary condition assumptions:
- edge boundary condition assumptions:
- sheath model:
- divertor boundary notes:
- vacuum / wall coupling assumptions:

## Resistive wall / vessel
Fill in:
- wall model enabled?
- resistive wall parameters:
- conducting structures included?
- notes:

## SOL / divertor treatment
Fill in:
- SOL included?
- divertor plates represented?
- target boundary assumptions:
- heat-flux extraction method:

---

# 9. Physics model switches

Fill in which physics are enabled in this case:
- [ ] reduced MHD
- [ ] two-fluid terms
- [ ] diamagnetic effects
- [ ] neoclassical flow
- [ ] resistive wall
- [ ] sheath boundary conditions
- [ ] impurity / radiation model
- [ ] other

For each enabled item, note:
- why it is included
- whether it is required for the first campaign

---

# 10. Numerical setup

Fill in:
- mesh / grid resolution:
- toroidal harmonics:
- time step:
- total simulation time:
- convergence criteria:
- restart strategy:
- output cadence:
- known numerical risks:

---

# 11. Output extraction plan

## Metrics to record for every case
- ELM crash amplitude
- energy loss per ELM
- peak divertor heat flux
- wetted area
- ELM frequency
- stability threshold / stability window shift

## Optional but useful
- pedestal collapse depth
- filament / burst structure notes
- wall load asymmetry
- toroidal/poloidal localization
- post-crash recovery time

## Fill in extraction method
For each metric, define:
- variable / diagnostic name:
- extraction script or method:
- units:
- pass/fail threshold:

---

# 12. Case matrix

## Case A — baseline low control
- edge drive:
- toroidal flow:
- poloidal flow:
- shear level:
- stabilization surrogate:
- expected behavior:

## Case B — high flow
- edge drive:
- toroidal flow:
- poloidal flow:
- shear level:
- stabilization surrogate:
- expected behavior:

## Case C — stabilized surrogate
- edge drive:
- toroidal flow:
- poloidal flow:
- shear level:
- stabilization surrogate:
- expected behavior:

## Case D — combined
- edge drive:
- toroidal flow:
- poloidal flow:
- shear level:
- stabilization surrogate:
- expected behavior:

---

# 13. Decision rule

A successful first JOREK campaign should show some combination of:
- reduced ELM crash amplitude
- reduced peak divertor heat flux
- improved wetted area
- broader stability window
- improved behavior in the combined case relative to baseline

## Fill in
- primary success metric:
- secondary success metric:
- rejection condition:
- follow-up condition:

---

# 14. Notes / unresolved assumptions

Use this section to record:
- anything guessed
- anything not yet constrained by data
- which fields still need real equilibrium/profile inputs
- what must be verified before launch
"""

checklist_md = """# JOREK Case Build Checklist

## Before launch
- [ ] Frozen 55 cm reference confirmed
- [ ] Equilibrium source chosen
- [ ] Density profile defined
- [ ] Temperature profile defined
- [ ] Pressure profile defined
- [ ] Current profile defined
- [ ] Toroidal flow scenario defined
- [ ] Poloidal flow scenario defined
- [ ] Edge shear interpretation defined
- [ ] TCT surrogate explicitly defined
- [ ] Boundary conditions selected
- [ ] Physics model switches selected
- [ ] Numerical resolution selected
- [ ] Output extraction plan written
- [ ] 4-case matrix completed
- [ ] Success criteria written

## Before comparing results
- [ ] Same extraction method used across all 4 cases
- [ ] Same normalization conventions used across all 4 cases
- [ ] Baseline case archived
- [ ] Combined case archived
- [ ] Failures logged separately from physics conclusions
"""

example_md = """# Example JOREK Case Skeleton

## Case name
case_A_baseline_low_control

## Purpose
Baseline edge / ELM reference case for comparison against flow-enhanced and stabilization-surrogate cases.

## Geometry / equilibrium
- equilibrium source: TODO
- X-point configuration: TODO
- q95: TODO

## Profiles
- density profile: TODO
- temperature profile: TODO
- pressure profile: TODO
- current profile: TODO

## Flow
- toroidal flow: low
- poloidal flow: low
- edge shear: derived low-shear case

## TCT surrogate
- surrogate type: profile/current-gradient stabilization surrogate
- level: low

## Outputs to record
- ELM crash amplitude
- energy loss per event
- peak divertor heat flux
- wetted area
- ELM frequency
- stability window shift
"""

(OUT / "jorek_case_input_template.md").write_text(template_md, encoding="utf-8")
(OUT / "jorek_case_build_checklist.md").write_text(checklist_md, encoding="utf-8")
(OUT / "jorek_case_example_skeleton.md").write_text(example_md, encoding="utf-8")

print("Wrote:")
print(OUT / "jorek_case_input_template.md")
print(OUT / "jorek_case_build_checklist.md")
print(OUT / "jorek_case_example_skeleton.md")	

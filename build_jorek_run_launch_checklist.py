from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
OUT = ROOT / "jorek_campaign_package"
OUT.mkdir(parents=True, exist_ok=True)

checklist_md = """# JOREK Run-Launch Checklist

## Purpose
This checklist answers one question:

**Are we actually ready to construct and launch a first JOREK case, or are we still only at synthetic planning stage?**

Use it before attempting any serious JOREK setup.

---

# 1. Frozen reference confirmation

These must already be locked:

- [ ] radius_cm = 55 confirmed
- [ ] li_current = 0.10 confirmed
- [ ] TCT supervisor = aggressive confirmed
- [ ] severity_scale = 0.6 confirmed
- [ ] blanket topology = be_outer_kill confirmed
- [ ] blanket ordering = Be / Li2O / Li2O / W_Ti_B4C_60_30_10_wt / Be confirmed
- [ ] blanket split = (0.15, 0.20, 0.40, 0.15, 0.10) confirmed
- [ ] blanket_thickness = 1.25 confirmed
- [ ] axial_outer_cap_thickness = 0.6 confirmed

If any of these are still moving, stop. Do not proceed to JOREK launch prep.

---

# 2. Campaign structure confirmation

These should already exist:

- [ ] jorek_case_matrix.csv exists
- [ ] jorek_case_workbook_merged.csv exists
- [ ] jorek_synthetic_equilibrium_assumptions.json exists
- [ ] jorek_synthetic_profiles.json exists
- [ ] jorek_synthetic_flows.json exists

If these do not exist, stop and build the campaign package first.

---

# 3. Hard blockers: must be real before launch

These are the actual blockers.

## Equilibrium
- [ ] real equilibrium source selected
- [ ] real equilibrium file identified
- [ ] shot/case or synthetic-equilibrium provenance recorded
- [ ] q95 target chosen from equilibrium
- [ ] X-point configuration explicitly chosen
- [ ] geometry assumptions checked for consistency

## Profiles
- [ ] density profile source is real or consciously synthetic for a test case
- [ ] temperature profile source is real or consciously synthetic for a test case
- [ ] pressure profile is defined
- [ ] current profile is defined
- [ ] edge current-gradient assumption is explicit
- [ ] pedestal pressure-gradient assumption is explicit

## Flows / shear
- [ ] toroidal flow scenario explicitly defined
- [ ] poloidal flow scenario explicitly defined
- [ ] edge shear definition explicitly derived from flow choice
- [ ] case A/B/C/D differences are physically stated, not just named

## TCT surrogate
- [ ] TCT surrogate is defined as an effect class
- [ ] low surrogate case is explicitly defined
- [ ] high surrogate case is explicitly defined
- [ ] surrogate maps back to reduced-model interpretation

If any of the above are blank, you are not ready to launch.

---

# 4. Physics-model decisions

These must be chosen explicitly:

- [ ] reduced MHD enabled/disabled decision recorded
- [ ] two-fluid enabled/disabled decision recorded
- [ ] diamagnetic effects enabled/disabled decision recorded
- [ ] neoclassical flow enabled/disabled decision recorded
- [ ] resistive wall enabled/disabled decision recorded
- [ ] sheath boundary conditions enabled/disabled decision recorded
- [ ] SOL/divertor treatment chosen
- [ ] any omitted physics justified in writing

If these are unresolved, you are still in design mode, not launch mode.

---

# 5. Boundary / wall assumptions

These must be specified:

- [ ] boundary condition strategy chosen
- [ ] wall / vessel assumptions chosen
- [ ] resistive wall parameters defined if wall is enabled
- [ ] divertor / target handling chosen
- [ ] heat-flux extraction location defined
- [ ] output diagnostics for divertor heat flux chosen

---

# 6. Numerical setup

These do not need to be final-production values, but they must exist:

- [ ] mesh / grid plan chosen
- [ ] toroidal harmonics chosen
- [ ] time step chosen
- [ ] total simulation time chosen
- [ ] output cadence chosen
- [ ] restart strategy chosen
- [ ] convergence / failure criteria written
- [ ] compute environment identified

If you have no numerical plan, you do not have a launchable case.

---

# 7. Output extraction plan

These must be defined before launch:

- [ ] ELM crash amplitude extraction method defined
- [ ] ELM energy loss per event extraction method defined
- [ ] peak divertor heat flux extraction method defined
- [ ] wetted area extraction method defined
- [ ] ELM frequency extraction method defined
- [ ] stability window / threshold shift extraction method defined
- [ ] same extraction method will be used across A/B/C/D

---

# 8. Minimum acceptable first campaign

Before first launch, all of these should be true:

- [ ] case_A_baseline_low_control fully defined
- [ ] case_B_high_flow fully defined
- [ ] case_C_stabilized_surrogate fully defined
- [ ] case_D_combined fully defined
- [ ] all four cases differ only where intended
- [ ] comparison outputs are the same across all four cases
- [ ] success criteria are written

---

# 9. Launch decision rule

## Ready for first synthetic launch if:
- hard blockers are filled
- physics-model choices are explicit
- numerical setup exists
- output extraction plan exists
- all 4 cases are internally coherent

## Not ready if:
- equilibrium is missing
- profiles are missing
- TCT surrogate is undefined
- flow cases are just labels without profile meaning
- output extraction is unspecified

---

# 10. Current project-state interpretation

At the current project state, the likely status is:

- frozen engineering reference: **ready**
- first JOREK campaign structure: **ready**
- synthetic starter package: **ready**
- real equilibrium/profile source: **not ready**
- physics-model switch decisions: **not ready**
- numerical launch plan: **not ready**
- extraction plan: **not ready**

So the project is currently at:

**JOREK case-construction stage, not JOREK launch stage.**
"""

next_steps_md = """# JOREK Immediate Next Steps

## We are here
We now have:
- frozen engineering reference
- case matrix
- workbook
- synthetic starter pack

## We do NOT yet have
- real equilibrium/profile source
- actual JOREK physics-switch choices
- numerical launch settings
- output extraction method

## Therefore the next real move is:
1. choose the first-pass physics switch set
2. choose the first-pass boundary/divertor assumptions
3. choose the first-pass numerical setup
4. define output extraction for ELM and heat-flux metrics

## Best immediate follow-up artifact
Build a **JOREK first-pass physics/numerics config sheet**.

That should include:
- reduced MHD vs two-fluid
- diamagnetic on/off
- neoclassical flow on/off
- resistive wall on/off
- sheath BC on/off
- SOL/divertor treatment
- mesh plan
- harmonics
- timestep
- total runtime
"""

(OUT / "jorek_run_launch_checklist.md").write_text(checklist_md, encoding="utf-8")
(OUT / "jorek_immediate_next_steps.md").write_text(next_steps_md, encoding="utf-8")

print("Wrote:")
print(" -", OUT / "jorek_run_launch_checklist.md")
print(" -", OUT / "jorek_immediate_next_steps.md")

import csv
import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
OUT = ROOT / "jorek_campaign_package"
OUT.mkdir(parents=True, exist_ok=True)

cases = [
    {
        "case_name": "case_A_baseline_low_control",
        "purpose": "Baseline edge / ELM reference case.",
        "edge_drive_level": "nominal_high",
        "toroidal_flow_level": "low",
        "poloidal_flow_level": "low",
        "edge_shear_level": "low",
        "tct_surrogate_level": "low",
    },
    {
        "case_name": "case_B_high_flow",
        "purpose": "Higher toroidal flow plus moderate poloidal flow.",
        "edge_drive_level": "same_as_A",
        "toroidal_flow_level": "high",
        "poloidal_flow_level": "moderate",
        "edge_shear_level": "high",
        "tct_surrogate_level": "low",
    },
    {
        "case_name": "case_C_stabilized_surrogate",
        "purpose": "Baseline flow with stronger stabilization surrogate.",
        "edge_drive_level": "same_as_A",
        "toroidal_flow_level": "low",
        "poloidal_flow_level": "low",
        "edge_shear_level": "low",
        "tct_surrogate_level": "high",
    },
    {
        "case_name": "case_D_combined",
        "purpose": "High flow plus strong stabilization surrogate.",
        "edge_drive_level": "same_as_A",
        "toroidal_flow_level": "high",
        "poloidal_flow_level": "moderate",
        "edge_shear_level": "high",
        "tct_surrogate_level": "high",
    },
]

workbook_rows = []
for c in cases:
    workbook_rows.append({
        "case_name": c["case_name"],
        "purpose": c["purpose"],

        # Equilibrium / geometry
        "equilibrium_source": "",
        "equilibrium_file": "",
        "shot_or_case_id": "",
        "R0_m": "0.55",
        "a_m": "0.55",
        "kappa": "",
        "delta": "",
        "xpoint_config": "",
        "q95_target": "",

        # Profiles
        "density_profile_source": "",
        "density_profile_notes": "",
        "temperature_profile_source": "",
        "temperature_profile_notes": "",
        "pressure_profile_source": "",
        "pressure_profile_notes": "",
        "current_profile_source": "",
        "current_profile_notes": "",

        # Drive / flow / shear
        "edge_drive_level": c["edge_drive_level"],
        "pedestal_pressure_gradient_setting": "",
        "edge_current_gradient_setting": "",
        "toroidal_flow_level": c["toroidal_flow_level"],
        "toroidal_flow_profile": "",
        "poloidal_flow_level": c["poloidal_flow_level"],
        "poloidal_flow_profile": "",
        "edge_shear_level": c["edge_shear_level"],
        "edge_shear_definition": "",

        # TCT surrogate
        "tct_surrogate_level": c["tct_surrogate_level"],
        "tct_surrogate_type": "",
        "tct_surrogate_definition": "",

        # Boundary / physics
        "sol_included": "",
        "divertor_model": "",
        "sheath_bc": "",
        "resistive_wall_enabled": "",
        "two_fluid_enabled": "",
        "diamagnetic_enabled": "",
        "neoclassical_flow_enabled": "",
        "other_physics_notes": "",

        # Numerics
        "mesh_notes": "",
        "toroidal_harmonics": "",
        "time_step": "",
        "total_sim_time": "",
        "output_cadence": "",

        # Extraction plan
        "extract_elm_crash_amplitude": "yes",
        "extract_elm_energy_loss": "yes",
        "extract_peak_divertor_heat_flux": "yes",
        "extract_wetted_area": "yes",
        "extract_elm_frequency": "yes",
        "extract_stability_window_shift": "yes",
        "extraction_script_or_method": "",

        # Run status
        "status": "not_started",
        "notes": "",
    })

csv_path = OUT / "jorek_case_workbook.csv"
with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=workbook_rows[0].keys())
    writer.writeheader()
    writer.writerows(workbook_rows)

json_path = OUT / "jorek_case_workbook.json"
json_path.write_text(json.dumps(workbook_rows, indent=2), encoding="utf-8")

readme = """# JOREK Case Workbook

This workbook is the per-case completion sheet for the first JOREK campaign.

Fill in, for each case:
- equilibrium source
- geometry / q-profile info
- density / temperature / pressure / current profiles
- toroidal and poloidal flow assumptions
- edge shear interpretation
- TCT surrogate definition
- boundary / wall / SOL / divertor settings
- enabled physics switches
- numerical setup
- output extraction method

Cases:
- case_A_baseline_low_control
- case_B_high_flow
- case_C_stabilized_surrogate
- case_D_combined

Rule:
Do not launch any case until the required fields are populated enough to explain
what is physically different between A/B/C/D.
"""
(OUT / "jorek_case_workbook_README.md").write_text(readme, encoding="utf-8")

print("Wrote:")
print(" -", csv_path)
print(" -", json_path)
print(" -", OUT / "jorek_case_workbook_README.md")

import csv
import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
OUT = ROOT / "jorek_campaign_package"
OUT.mkdir(parents=True, exist_ok=True)

reference = {
    "reference_name": "55cm_be_outer_kill_mainline",
    "radius_cm": 55.0,
    "R_m": 0.55,
    "a_m": 0.55,
    "li_current": 0.10,
    "tct_supervisor": "aggressive",
    "severity_scale": 0.6,
    "blanket_topology": "be_outer_kill",
    "blanket_ordering": [
        "Be",
        "Li2O",
        "Li2O",
        "W_Ti_B4C_60_30_10_wt",
        "Be",
    ],
    "blanket_split": [0.15, 0.20, 0.40, 0.15, 0.10],
    "blanket_thickness": 1.25,
    "axial_outer_cap_thickness": 0.6,
    "lithium_thickness": 0.003,
}

cases = [
    {
        "case_name": "case_A_baseline_low_control",
        "purpose": "Baseline edge / ELM reference case.",
        "edge_drive_level": "nominal_high",
        "pedestal_pressure_gradient": "baseline",
        "edge_current_gradient": "baseline",
        "toroidal_flow_level": "low",
        "poloidal_flow_level": "low",
        "edge_shear_level": "low",
        "tct_surrogate_level": "low",
        "tct_surrogate_type": "profile_or_transport_surrogate",
        "expected_result": "Highest event severity of the 4 cases.",
    },
    {
        "case_name": "case_B_high_flow",
        "purpose": "Test effect of stronger toroidal flow and moderate poloidal flow.",
        "edge_drive_level": "same_as_A",
        "pedestal_pressure_gradient": "baseline",
        "edge_current_gradient": "baseline",
        "toroidal_flow_level": "high",
        "poloidal_flow_level": "moderate",
        "edge_shear_level": "high",
        "tct_surrogate_level": "low",
        "tct_surrogate_type": "profile_or_transport_surrogate",
        "expected_result": "Lower crash amplitude / heat load than baseline if flow-shear effect is real.",
    },
    {
        "case_name": "case_C_stabilized_surrogate",
        "purpose": "Test TCT-like stabilization surrogate without adding strong flow.",
        "edge_drive_level": "same_as_A",
        "pedestal_pressure_gradient": "baseline_or_shaped",
        "edge_current_gradient": "baseline_or_shaped",
        "toroidal_flow_level": "low",
        "poloidal_flow_level": "low",
        "edge_shear_level": "low",
        "tct_surrogate_level": "high",
        "tct_surrogate_type": "profile_or_transport_surrogate",
        "expected_result": "Lower severity than baseline if stabilization surrogate is effective.",
    },
    {
        "case_name": "case_D_combined",
        "purpose": "Test strongest combined scenario: high flow plus high stabilization surrogate.",
        "edge_drive_level": "same_as_A",
        "pedestal_pressure_gradient": "baseline_or_shaped",
        "edge_current_gradient": "baseline_or_shaped",
        "toroidal_flow_level": "high",
        "poloidal_flow_level": "moderate",
        "edge_shear_level": "high",
        "tct_surrogate_level": "high",
        "tct_surrogate_type": "profile_or_transport_surrogate",
        "expected_result": "Best stability / lowest event severity if the full concept survives translation.",
    },
]

outputs = [
    "elm_crash_amplitude",
    "elm_energy_loss_per_event",
    "peak_divertor_heat_flux",
    "wetted_area",
    "elm_frequency",
    "stability_window_shift",
]

success_criteria = [
    "case_D better than case_A on elm_crash_amplitude",
    "case_D better than case_A on peak_divertor_heat_flux",
    "case_D better than case_A on stability_window_shift",
    "case_B and/or case_C improve at least one severity metric vs case_A",
]

# CSV matrix
csv_path = OUT / "jorek_case_matrix.csv"
fieldnames = list(cases[0].keys())

with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cases)

# JSON bundle
bundle = {
    "reference": reference,
    "cases": cases,
    "outputs_to_compare": outputs,
    "success_criteria": success_criteria,
}

json_path = OUT / "jorek_case_matrix.json"
json_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

# Markdown summary
md = f"""# JOREK Case Matrix

## Frozen reference
- radius_cm = {reference["radius_cm"]}
- R = {reference["R_m"]} m
- a = {reference["a_m"]} m
- li_current = {reference["li_current"]}
- TCT supervisor = {reference["tct_supervisor"]}
- severity_scale = {reference["severity_scale"]}
- blanket topology = {reference["blanket_topology"]}
- blanket thickness = {reference["blanket_thickness"]}
- axial outer cap thickness = {reference["axial_outer_cap_thickness"]}

## Case table
| Case | Purpose | Edge drive | Toroidal flow | Poloidal flow | Edge shear | TCT surrogate |
|---|---|---|---|---|---|---|
"""

for c in cases:
    md += (
        f'| {c["case_name"]} | {c["purpose"]} | {c["edge_drive_level"]} | '
        f'{c["toroidal_flow_level"]} | {c["poloidal_flow_level"]} | '
        f'{c["edge_shear_level"]} | {c["tct_surrogate_level"]} |\n'
    )

md += "\n## Outputs to compare\n"
for o in outputs:
    md += f"- {o}\n"

md += "\n## Success criteria\n"
for s in success_criteria:
    md += f"- {s}\n"

md_path = OUT / "jorek_case_matrix.md"
md_path.write_text(md, encoding="utf-8")

print("Wrote:")
print(f" - {csv_path}")
print(f" - {json_path}")
print(f" - {md_path}")

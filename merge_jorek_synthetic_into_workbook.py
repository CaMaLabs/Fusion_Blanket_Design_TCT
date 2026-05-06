import csv
import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

workbook_csv = PKG / "jorek_case_workbook.csv"
synthetic_csv = PKG / "jorek_synthetic_case_seed.csv"
equilibrium_json = PKG / "jorek_synthetic_equilibrium_assumptions.json"
profiles_json = PKG / "jorek_synthetic_profiles.json"
flows_json = PKG / "jorek_synthetic_flows.json"

out_csv = PKG / "jorek_case_workbook_merged.csv"
out_json = PKG / "jorek_case_workbook_merged.json"

required = [
    workbook_csv,
    synthetic_csv,
    equilibrium_json,
    profiles_json,
    flows_json,
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit(
        "Missing required files:\\n" + "\\n".join(missing)
    )

with equilibrium_json.open("r", encoding="utf-8") as f:
    equilibrium = json.load(f)

with profiles_json.open("r", encoding="utf-8") as f:
    profiles = json.load(f)

with flows_json.open("r", encoding="utf-8") as f:
    flows = json.load(f)

# Load workbook
with workbook_csv.open("r", encoding="utf-8", newline="") as f:
    workbook_reader = csv.DictReader(f)
    workbook_fields = workbook_reader.fieldnames
    workbook_rows = list(workbook_reader)

if not workbook_fields:
    raise SystemExit("Workbook has no header row")

# Load synthetic seed keyed by case_name
with synthetic_csv.open("r", encoding="utf-8", newline="") as f:
    synthetic_reader = csv.DictReader(f)
    synthetic_rows = {row["case_name"]: row for row in synthetic_reader}

def fill_if_blank(row: dict, key: str, value):
    if key not in row:
        return
    if row[key] is None or str(row[key]).strip() == "":
        row[key] = str(value)

merged_rows = []

for row in workbook_rows:
    case_name = row["case_name"]
    seed = synthetic_rows.get(case_name, {})

    # First: merge seed columns directly where workbook is blank
    for k, v in seed.items():
        if k in row and (row[k] is None or str(row[k]).strip() == ""):
            row[k] = v

    # Then: fill from synthetic equilibrium/profile/flow package where helpful
    geom = equilibrium.get("geometry", {})
    mag = equilibrium.get("magnetic", {})

    fill_if_blank(row, "equilibrium_source", "synthetic_first_pass")
    fill_if_blank(row, "equilibrium_file", equilibrium_json.name)
    fill_if_blank(row, "shot_or_case_id", "synthetic_55cm_reference")
    fill_if_blank(row, "R0_m", geom.get("R0_m", "0.55"))
    fill_if_blank(row, "a_m", geom.get("a_m", "0.55"))
    fill_if_blank(row, "kappa", geom.get("kappa", "1.70"))
    fill_if_blank(row, "delta", geom.get("delta", "0.30"))
    fill_if_blank(row, "xpoint_config", geom.get("xpoint_config", "lower_single_null"))
    fill_if_blank(row, "q95_target", mag.get("q95_target", "3.5"))

    fill_if_blank(row, "density_profile_source", f"{profiles_json.name}:density_profile")
    fill_if_blank(row, "temperature_profile_source", f"{profiles_json.name}:temperature_profile")
    fill_if_blank(row, "pressure_profile_source", f"{profiles_json.name}:pressure_profile")
    fill_if_blank(row, "current_profile_source", f"{profiles_json.name}:current_profile")

    # Helpful notes
    if "density_profile_notes" in row and not str(row["density_profile_notes"]).strip():
        row["density_profile_notes"] = "Synthetic first-pass density profile: core-flat pedestal-drop."
    if "temperature_profile_notes" in row and not str(row["temperature_profile_notes"]).strip():
        row["temperature_profile_notes"] = "Synthetic first-pass temperature profile: hot core / steep pedestal / cool edge."
    if "pressure_profile_notes" in row and not str(row["pressure_profile_notes"]).strip():
        row["pressure_profile_notes"] = "Synthetic first-pass pressure profile consistent with nominal edge-drive assumptions."
    if "current_profile_notes" in row and not str(row["current_profile_notes"]).strip():
        row["current_profile_notes"] = "Synthetic first-pass current profile with edge-current shoulder."

    # Flow defaults from synthetic flow package
    tor_levels = flows.get("levels", {}).get("toroidal_flow", {})
    pol_levels = flows.get("levels", {}).get("poloidal_flow", {})
    shear_levels = flows.get("levels", {}).get("edge_shear", {})
    tct_levels = flows.get("tct_surrogate", {})

    tor_level = row.get("toroidal_flow_profile", "").strip()
    pol_level = row.get("poloidal_flow_profile", "").strip()
    shear_level = row.get("edge_shear_level", "").strip()
    tct_level = row.get("tct_surrogate_level", "").strip()

    if "toroidal_flow_profile" in row and tor_level in tor_levels:
        row["toroidal_flow_profile"] = (
            f"{tor_level} "
            f"(normalized_peak={tor_levels[tor_level].get('normalized_peak')}; "
            f"{tor_levels[tor_level].get('description')})"
        )

    if "poloidal_flow_profile" in row and pol_level in pol_levels:
        row["poloidal_flow_profile"] = (
            f"{pol_level} "
            f"(normalized_peak={pol_levels[pol_level].get('normalized_peak')}; "
            f"{pol_levels[pol_level].get('description')})"
        )

    if "edge_shear_definition" in row and shear_level in shear_levels:
        if not str(row["edge_shear_definition"]).strip():
            row["edge_shear_definition"] = shear_levels[shear_level].get("description", shear_level)

    if "tct_surrogate_type" in row and tct_level in tct_levels:
        fill_if_blank(row, "tct_surrogate_type", tct_levels[tct_level].get("type", "profile_or_transport_surrogate"))

    if "tct_surrogate_definition" in row and tct_level in tct_levels:
        if not str(row["tct_surrogate_definition"]).strip():
            row["tct_surrogate_definition"] = tct_levels[tct_level].get("definition", "")

    # Mark status
    if "status" in row:
        row["status"] = "merged_with_synthetic_seed"

    # Notes
    existing_notes = str(row.get("notes", "")).strip()
    merge_note = (
        "Merged with synthetic starter package. "
        "Still replace synthetic equilibrium/profile assumptions with real data when available."
    )
    row["notes"] = f"{existing_notes} | {merge_note}" if existing_notes else merge_note

    merged_rows.append(row)

# Write merged CSV
with out_csv.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=workbook_fields)
    writer.writeheader()
    writer.writerows(merged_rows)

# Write merged JSON
with out_json.open("w", encoding="utf-8") as f:
    json.dump(merged_rows, f, indent=2)

print("Wrote:")
print(" -", out_csv)
print(" -", out_json)

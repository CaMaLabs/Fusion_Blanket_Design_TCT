#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source_path = ROOT / "validation_models/tct_current_sheet/tct_current_sheet.cxx"
out_dir = ROOT / "validation_runs/tct_segmented_electrode_bout_handoff_audit"
out_dir.mkdir(parents=True, exist_ok=True)
text = source_path.read_text(encoding="utf-8")

checks = {
    "evolves_vorticity": "SOLVE_FOR(psi, omega)" in text,
    "solves_electrostatic_potential_from_vorticity": "phi_solver->solve(omega, phi)" in text,
    "spatial_actuator_mask_present": "tct_mask *" in text,
    "phi_output_present": 'state["phi"]' in text,
    "current_density_proxy_present": 'state["J"]' in text,
    "existing_actuator_is_psi_damping": "tct_strength * tct_mask * psi" in text,
    "existing_actuator_is_omega_damping": "omega_tct_strength * tct_mask * omega" in text,
    "segmented_electrode_potential_forcing_present": any(k in text for k in ("electrode_phi", "electrode_potential", "segmented_electrode")),
}
base_spatial_model_ready = all(checks[k] for k in (
    "evolves_vorticity", "solves_electrostatic_potential_from_vorticity",
    "spatial_actuator_mask_present", "phi_output_present"))
electrode_handoff_ready = base_spatial_model_ready and checks["segmented_electrode_potential_forcing_present"]
classification = (
    "TCT_SEGMENTED_ELECTRODE_BOUT_HANDOFF_READY"
    if electrode_handoff_ready else
    "TCT_SEGMENTED_ELECTRODE_BOUT_HANDOFF_NOT_YET_IMPLEMENTED"
)
summary = {
    "classification": classification,
    "formal_m3dc1_classification": None,
    "pipeline_failure": False,
    "claim_boundary": "BOUT++ source-capability/handoff audit only. No native M3D-C1 electrode efficacy, BOUT++ segmented-electrode efficacy, experimental, reactor-scale, precursor, species-separation, or spatial-segmentation efficacy claim.",
    "frozen_gates": {"width_gain_pct_gt": 0.020, "Jpk_change_pct_le": 0.10},
    "zero_equivalence_required_for_future_forcing": True,
    "handoff_equivalence_required_for_future_forcing": True,
    "checks": checks,
    "base_spatial_model_ready": base_spatial_model_ready,
    "electrode_handoff_ready": electrode_handoff_ready,
    "interpretation": (
        "The existing BOUT++ current-sheet model already evolves vorticity, solves phi spatially, and supports a resolved actuator mask, but its present actuator terms are localized psi/omega damping rather than segmented electrode-potential forcing. A future implementation must add a physically explicit electrode-to-potential/vorticity coupling and prove zero-equivalence plus handoff-equivalence before any efficacy comparison."
        if not electrode_handoff_ready else
        "A segmented-electrode forcing path is present in the spatial BOUT++ model; it still requires zero-equivalence and handoff-equivalence before efficacy claims."
    ),
}
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))

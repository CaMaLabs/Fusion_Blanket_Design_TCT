#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "validation_models/tct_current_sheet/tct_current_sheet.cxx"
OUT = ROOT / "validation_runs/tct_segmented_electrode_coupling_audit"
OUT.mkdir(parents=True, exist_ok=True)
text = SRC.read_text(encoding="utf-8")

checks = {
    "signed_spatial_profile_present": 'initial_profile("electrode_profile", electrode_profile)' in text,
    "electrode_amplitude_option_present": 'options["electrode_strength"]' in text,
    "plasma_phi_kept_separate": "phi_plasma = phi_solver->solve(omega, phi_plasma);" in text,
    "electrode_phi_explicit": "electrode_phi = actuator_gate * electrode_strength * electrode_profile;" in text,
    "electrode_enters_total_phi": "phi = phi_plasma + electrode_phi;" in text,
    "total_phi_drives_psi_bracket": "-bracket(phi, psi, bracket_method)" in text,
    "total_phi_drives_omega_bracket": "-bracket(phi, omega, bracket_method)" in text,
    "legacy_psi_actuator_preserved": "- actuator_gate * tct_strength * tct_mask * psi" in text,
    "legacy_omega_actuator_preserved": "- actuator_gate * omega_tct_strength * tct_mask * omega" in text,
    "electrode_phi_output_present": 'state["electrode_phi"]' in text,
    "electrode_profile_output_present": 'state["electrode_profile"]' in text,
}
implemented = all(checks.values())
classification = (
    "TCT_SEGMENTED_ELECTRODE_BOUT_COUPLING_IMPLEMENTED_RUNTIME_EQUIVALENCE_REQUIRED"
    if implemented else
    "TCT_SEGMENTED_ELECTRODE_BOUT_COUPLING_IMPLEMENTATION_INCOMPLETE"
)
summary = {
    "classification": classification,
    "formal_m3dc1_classification": None,
    "pipeline_failure": False,
    "claim_boundary": "BOUT++ coupling implementation audit only. No BOUT++ segmented-electrode efficacy, native M3D-C1 electrode efficacy, experimental, reactor-scale, precursor, species-separation, or spatial-segmentation efficacy claim.",
    "frozen_gates": {"width_gain_pct_gt": 0.020, "Jpk_change_pct_le": 0.10},
    "zero_equivalence_required": True,
    "handoff_equivalence_required": True,
    "runtime_equivalence_proven": False,
    "efficacy_testing_permitted": False,
    "checks": checks,
    "interpretation": (
        "A signed spatial electrode potential is now explicitly coupled into the BOUT++ electrostatic potential used by the E x B Poisson brackets while the legacy psi/omega actuator terms remain unchanged. This source-level audit does not prove numerical zero-equivalence or handoff-equivalence; both must pass in compiled BOUT++ before any efficacy comparison."
        if implemented else
        "The explicit BOUT++ segmented-electrode coupling is incomplete; do not proceed to runtime or efficacy testing."
    ),
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
raise SystemExit(0 if implemented else 2)

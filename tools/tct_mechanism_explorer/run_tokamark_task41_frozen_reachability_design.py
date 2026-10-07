#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

OUT=Path("validation_runs/tokamark_task41_frozen_reachability_design")
OUT.mkdir(parents=True, exist_ok=True)

design={
 "schema_version":1,
 "created_utc":datetime.now(timezone.utc).isoformat(),
 "classification":"TOKAMARK_MAST_TASK41_FROZEN_REACHABILITY_DESIGN",
 "machine":"MAST",
 "fuel_track":"fuel_agnostic_control",
 "evidence_class":"prospective_observational_design",
 "pipeline_failure":False,
 "parent_result_job_id":"20261006-092-tokamark-group4-task41-metadata-audit",
 "task_id":"4-1",
 "timing":{"input_length_ms":150.0,"forecast_length_ms":100.0,"forecast_delta_ms":0.0,"stride_ms":1.0},
 "diagnostics":{
   "inputs":[
    ["magnetics","flux_loop_flux"],["magnetics","b_field_pol_probe_ccbv_field"],
    ["magnetics","b_field_pol_probe_obr_field"],["magnetics","b_field_pol_probe_obv_field"],
    ["magnetics","b_field_tor_probe_saddle_voltage"],["pf_active","coil_current"],
    ["pf_active","solenoid_current"],["summary","ip"],["interferometer","n_e_line"],
    ["spectrometer_visible","filter_spectrometer_dalpha_voltage"],
    ["soft_x_rays","horizontal_cam_lower"],["soft_x_rays","horizontal_cam_upper"],
    ["magnetics","b_field_tor_probe_cc_field"],["magnetics","b_field_pol_probe_omv_voltage"]
   ],
   "actuators":[["pulse_schedule","i_plasma"],["pulse_schedule","n_e_line"],["summary","power_nbi"],["gas_injection","total_injected"]],
   "outputs":[["soft_x_rays","horizontal_cam_lower"],["soft_x_rays","horizontal_cam_upper"]]
 },
 "canonical_split":{"path":"src/tokamark/metadata/TokaMark_data_splits.csv","columns":["shot_id","train","val","test","fold_1_train","fold_1_val","fold_2_train","fold_2_val","fold_3_train","fold_3_val","fold_4_train","fold_4_val","fold_5_train","fold_5_val","train_ip_negative","val_ip_negative","test_ip_negative"]},
 "reachability_budgets_ms":{"prebiased_fast":2.75,"prebiased_nominal":5.25},
 "frozen_nulls":["circular_shift","shuffled_event"],
 "retuning_permitted":False,
 "m3dc1_gates_not_mapped":True,
 "frozen_reference_gates_only":{"width_gain_pct_gt":0.02,"Jpk_change_pct_le":0.1},
 "prospective_analysis_contract":[
   "Use canonical train/val/test membership without reshuffling.",
   "Calibrate diagnostic timing before precursor lead-time inference.",
   "Estimate precursor lead distributions without per-shot threshold retuning.",
   "Report fractions exceeding 2.75 ms and 5.25 ms separately.",
   "Run circular-shift and shuffled-event nulls under the same detector.",
   "Preserve shot IDs and diagnostic provenance in all outputs."
 ],
 "claim_boundary":"Prospective observational MAST/TokaMark reachability design only. It can test whether native diagnostic precursors precede task outputs by enough time for TCT actuator budgets; it cannot establish causal TCT, segmented-electrode efficacy, M3D-C1 equivalence, or p-B11 validation.",
 "next_gate":"Execute frozen shot-level observational precursor reachability only after required TokaMark shot data are locally available through the existing pipeline."
}
(OUT/"design.json").write_text(json.dumps(design,indent=2)+"\n")
print(json.dumps(design,indent=2))

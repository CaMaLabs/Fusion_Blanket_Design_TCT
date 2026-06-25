#!/usr/bin/env python3
"""Emit a machine-readable claim status for the FAIR-MAST/TCT validation chain."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = REPO / "validation_runs" / "fair_mast_claim_gate_default"

REQUIRED = {
    "machine_labels": REPO / "validation_runs/fair_mast_machine_reviewed_labels_default/fair_mast_machine_reviewed_label_summary.json",
    "strict_nulls": REPO / "validation_runs/fair_mast_precursor_strict_null_suite_default/fair_mast_precursor_strict_null_suite_summary.json",
    "actuator_budget": REPO / "validation_runs/fair_mast_biased_actuator_response_budget_default/fair_mast_biased_actuator_response_budget_summary.json",
    "sxr_tradeoff": REPO / "validation_runs/fair_mast_sxr_precursor_tradeoff_default/fair_mast_sxr_precursor_tradeoff_summary.json",
    "morphology_gate": REPO / "validation_runs/fair_mast_sxr_morphology_gate_default/fair_mast_sxr_morphology_gate_summary.json",
    "other_trigger_screen": REPO / "validation_runs/fair_mast_other_trigger_screen_default/fair_mast_other_trigger_screen_summary.json",
    "omv_followup": REPO / "validation_runs/fair_mast_omv_followup_default/fair_mast_omv_followup_summary.json",
    "omv_fresh_split": REPO / "validation_runs/fair_mast_omv_fresh_split_default/fair_mast_omv_fresh_split_summary.json",
    "fresh_trigger_search": REPO / "validation_runs/fair_mast_fresh_trigger_search_default/fair_mast_fresh_trigger_search_summary.json",
    "mirnov8_omv4_validation": REPO / "validation_runs/fair_mast_mirnov8_omv4_validation_default/fair_mast_mirnov8_omv4_validation_summary.json",
    "rolling_fresh_trigger_search": REPO / "validation_runs/fair_mast_fresh_trigger_search_skip20_small_default/fair_mast_fresh_trigger_search_summary.json",
    "forward_surrogate": REPO / "validation_runs/fair_mast_tct_forward_surrogate_default/fair_mast_tct_forward_surrogate_summary.json",
    "forward_sensitivity": REPO / "validation_runs/fair_mast_tct_forward_sensitivity_default/fair_mast_tct_forward_sensitivity_summary.json",
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def gate_status(artifacts: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    missing = [name for name, data in artifacts.items() if data is None]
    flags: list[str] = []
    blockers: list[str] = []

    if missing:
        flags.append("MISSING_REQUIRED_ARTIFACTS")
        blockers.extend(f"missing:{name}" for name in missing)

    machine = artifacts.get("machine_labels") or {}
    reviewed_metrics = machine.get("reviewed_metrics", {})
    accepted = int(
        reviewed_metrics.get("accepted_true_elm_count", 0)
        or machine.get("accepted_true_elm_count", 0)
        or machine.get("label_counts", {}).get("true_elm", 0)
        or 0
    )
    if accepted < 50:
        flags.append("WEAK_EVENT_LABEL_SET")
        blockers.append("accepted_true_elm_count_below_50")
    else:
        flags.append("HELD_OUT_EVENT_LABELS_PRESENT")

    nulls = artifacts.get("strict_nulls") or {}
    null_status = str(nulls.get("status", ""))
    if "COMPLETED" in null_status:
        flags.append("STRICT_NULLS_COMPLETED")
    else:
        flags.append("STRICT_NULLS_NOT_CONFIRMED")
        blockers.append("strict_null_suite_not_completed")

    actuator = artifacts.get("actuator_budget") or {}
    passing_budget = any(
        row.get("verdict") == "passes_for_bounded_boost"
        for row in actuator.get("scenario_rows", [])
    )
    if passing_budget:
        flags.append("FAST_BIASED_RESPONSE_BUDGET_COMPATIBLE")
    else:
        flags.append("NO_PASSING_RESPONSE_BUDGET")
        blockers.append("no_biased_response_budget_pass")

    morphology = artifacts.get("morphology_gate") or {}
    if str(morphology.get("status", "")).startswith("BLOCKED"):
        flags.append("MISSING_MORPHOLOGY_GATE_RUN")
        blockers.append("sxr_morphology_gate_blocked")
    elif morphology.get("status") == "MAST_SXR_MORPHOLOGY_GATE_COMPLETED":
        selected = morphology.get("selected_gate_reviewed_labels", {})
        reference = morphology.get("mirnov_toroidal_reviewed_labels", {})
        if (
            selected.get("false_trigger_count", 10**9) <= reference.get("false_trigger_count", -1)
            and selected.get("detected_event_count", -1) >= reference.get("detected_event_count", 10**9)
        ):
            flags.append("SXR_MORPHOLOGY_GATE_IMPROVES_TRIGGER")
        else:
            flags.append("SXR_MORPHOLOGY_GATE_COMPLETED_NO_OPERATIONAL_IMPROVEMENT")

    other_trigger = artifacts.get("other_trigger_screen") or {}
    if other_trigger.get("status") == "MAST_OTHER_TRIGGER_SCREEN_COMPLETED":
        selected = other_trigger.get("selected_reviewed_labels", {})
        baseline = other_trigger.get("baseline_reviewed_labels", {})
        exploratory = other_trigger.get("best_exploratory_reviewed_labels", {})
        selected_improves = (
            selected.get("false_trigger_count", 10**9) <= baseline.get("false_trigger_count", -1)
            and selected.get("detected_event_count", -1) > baseline.get("detected_event_count", 10**9)
        )
        exploratory_improves = (
            exploratory.get("detected_event_count", -1) > baseline.get("detected_event_count", 10**9)
            and exploratory.get("false_trigger_count", 10**9) <= baseline.get("false_trigger_count", 10**9) + 1
        )
        if selected_improves:
            flags.append("OTHER_TRIGGER_SCREEN_IMPROVES_TRIGGER")
        elif exploratory_improves:
            flags.append("OTHER_TRIGGER_SCREEN_EXPLORATORY_OMV_LEAD_ONLY")
        else:
            flags.append("OTHER_TRIGGER_SCREEN_COMPLETED_NO_OPERATIONAL_IMPROVEMENT")

    omv_followup = artifacts.get("omv_followup") or {}
    if omv_followup.get("status") == "MAST_OMV_FOLLOWUP_COMPLETED":
        verdict = omv_followup.get("robustness_verdict")
        detected_delta = int(omv_followup.get("detected_delta_omv6_vs_baseline", 0) or 0)
        false_delta = int(omv_followup.get("false_trigger_delta_omv6_vs_baseline", 0) or 0)
        if verdict in {"broad_exploratory_gain", "mostly_stable_exploratory_gain"} and detected_delta > 0:
            if false_delta <= 1:
                flags.append("OMV_FOLLOWUP_SHOT_LOCALIZED_EXPLORATORY_LEAD")
            else:
                flags.append("OMV_FOLLOWUP_GAIN_WITH_FALSE_TRIGGER_COST")
        else:
            flags.append("OMV_FOLLOWUP_NO_ROBUST_GAIN")

    omv_fresh_split = artifacts.get("omv_fresh_split") or {}
    if omv_fresh_split.get("status") == "MAST_OMV_FRESH_SPLIT_COMPLETED":
        verdict = str(omv_fresh_split.get("fresh_split_verdict", ""))
        if verdict == "fresh_split_supports_omv6_candidate":
            flags.append("OMV_FRESH_SPLIT_SUPPORTS_FIXED_CANDIDATE")
        elif verdict == "fresh_split_mixed_gain_with_noise_cost":
            flags.append("OMV_FRESH_SPLIT_MIXED_GAIN_WITH_NOISE_COST")
        else:
            flags.append("OMV_FRESH_SPLIT_DOES_NOT_SUPPORT_FIXED_CANDIDATE")

    fresh_search = artifacts.get("fresh_trigger_search") or {}
    if fresh_search.get("status") == "MAST_FRESH_TRIGGER_SEARCH_COMPLETED":
        verdict = str(fresh_search.get("search_verdict", ""))
        if verdict == "train_selected_trigger_improves_fresh_test_score":
            flags.append("FRESH_TRIGGER_SEARCH_TRAIN_SELECTED_IMPROVES")
        else:
            flags.append("FRESH_TRIGGER_SEARCH_NO_TRAIN_SELECTED_IMPROVEMENT")

    mirnov8_omv4 = artifacts.get("mirnov8_omv4_validation") or {}
    if mirnov8_omv4.get("status") == "MAST_MIRNOV8_OMV4_VALIDATION_COMPLETED":
        verdict = str(mirnov8_omv4.get("validation_verdict", ""))
        if verdict == "validated_candidate_improves_score":
            flags.append("MIRNOV8_OMV4_VALIDATES")
        elif verdict == "mixed_candidate_gain_with_noise_cost":
            flags.append("MIRNOV8_OMV4_RECALL_GAIN_WITH_FALSE_TRIGGER_COST")
        else:
            flags.append("MIRNOV8_OMV4_DOES_NOT_GENERALIZE")

    rolling_search = artifacts.get("rolling_fresh_trigger_search") or {}
    if rolling_search.get("status") == "MAST_FRESH_TRIGGER_SEARCH_COMPLETED":
        score_delta = float(rolling_search.get("test_selected_score_delta_vs_baseline", 0.0) or 0.0)
        false_delta = int(rolling_search.get("test_selected_false_trigger_delta_vs_baseline", 0) or 0)
        detected_delta = int(rolling_search.get("test_selected_detected_delta_vs_baseline", 0) or 0)
        if score_delta > 0.1 and false_delta <= 0:
            flags.append("ROLLING_FRESH_SEARCH_CLEAN_IMPROVEMENT")
        elif score_delta > 0.0 and detected_delta > 0:
            flags.append("ROLLING_FRESH_SEARCH_MARGINAL_RECALL_NOISE_TRADEOFF")
        else:
            flags.append("ROLLING_FRESH_SEARCH_NO_IMPROVEMENT")

    sensitivity = artifacts.get("forward_sensitivity") or {}
    if sensitivity.get("falsifier_count") == 0:
        flags.append("FORWARD_PROXY_NO_SWEPT_FALSIFIERS")
    else:
        flags.append("FORWARD_PROXY_HAS_FALSIFIERS")
        blockers.append("forward_sensitivity_falsifiers_present")

    flags.extend(
        [
            "SUPPORTED_PROXY_ONLY",
            "NOT_CAUSAL_VALIDATION",
            "MISSING_EXPERT_LABELS",
            "MISSING_MEASURED_TCT_ACTUATOR",
            "MISSING_REACTOR_PHYSICS_VALIDATION",
        ]
    )

    if blockers:
        top_status = "SUPPORTED_PROXY_WITH_BLOCKERS"
    else:
        top_status = "SUPPORTED_PROXY_ONLY"

    return {
        "status": top_status,
        "flags": sorted(set(flags)),
        "blockers": blockers,
        "claim_supported": "FAIR-MAST reduced-order timing/control-policy prerequisite",
        "claim_not_supported": [
            "causal TCT actuator suppression",
            "sustained fusion",
            "reactor burn physics",
            "expert-reviewed final ELM labels",
            "measured TCT actuator transfer function",
        ],
    }


def write_report(run_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# FAIR-MAST Claim Gate",
        "",
        f"- Status: `{result['status']}`",
        f"- Generated: `{result['generated_at']}`",
        "",
        "## Supported Claim",
        "",
        result["claim_supported"],
        "",
        "## Not Supported",
        "",
    ]
    lines.extend(f"- {item}" for item in result["claim_not_supported"])
    lines += [
        "",
        "## Flags",
        "",
    ]
    lines.extend(f"- `{flag}`" for flag in result["flags"])
    lines += [
        "",
        "## Blockers",
        "",
    ]
    if result["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in result["blockers"])
    else:
        lines.append("- none")
    lines += [
        "",
        "## Interpretation",
        "",
        "The current validation state supports only a reduced-order FAIR-MAST",
        "timing/control-policy prerequisite. It should not be presented as causal",
        "TCT validation or sustained-fusion validation.",
        "",
    ]
    (run_dir / "fair_mast_claim_gate_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()

    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    artifacts = {name: load_json(path) for name, path in REQUIRED.items()}
    result = gate_status(artifacts)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["artifact_paths"] = {name: str(path.relative_to(REPO)) for name, path in REQUIRED.items()}

    (args.run_dir / "fair_mast_claim_gate_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.run_dir, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

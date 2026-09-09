#!/usr/bin/env python3
"""Repair wrapper for the timed TCT feedback audit.

This wrapper preserves the native single-window transient authority result while
repairing restart chaining for segmented schedules and feedback.  The original
audit remains the physics/metric implementation; this layer changes only how
restart state is transferred and how restart validity is audited.

Key safeguards:
  * copy only actual restart state, never C1ke/time_*.h5 diagnostics;
  * hash each seed/final C1.h5 and require every restart to advance state;
  * require each restarted segment to reach its requested stop time;
  * preserve and re-check the previously observed native transient gate points;
  * never let an invalid feedback chain outrank valid native timed evidence.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import timed_feedback_switching_audit as audit

REFERENCE = Path(__file__).with_name("timed_transient_authority_reference.json")
MANIFEST = "restart_seed_manifest.json"
REFERENCE_ABS_TOL = 1e-9
TIME_TOL = 1e-8


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: object) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def restart_auxiliary(item: Path) -> bool:
    """Allow only files explicitly identifiable as restart payloads.

    C1.h5 is the primary M3D-C1 restart state.  Some checkouts can emit
    auxiliary restart files/directories; keep only names that explicitly say
    restart.  Diagnostic histories such as C1ke and time_*.h5 are deliberately
    excluded so a new segment cannot inherit stale measurements.
    """
    name = item.name.lower()
    return "restart" in name and item.name != MANIFEST


def clean_copy_restart_state(previous: Path, current: Path) -> None:
    source = previous / "C1.h5"
    if not source.exists():
        raise RuntimeError(f"restart source missing C1.h5: {previous}")

    copied: list[str] = []
    target = current / "C1.h5"
    shutil.copy2(source, target)
    copied.append("C1.h5")

    for item in previous.iterdir():
        if item.name == "C1.h5" or not restart_auxiliary(item):
            continue
        destination = current / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        elif item.is_file():
            shutil.copy2(item, destination)
        copied.append(item.name)

    stale_diagnostics = [
        p.name for p in current.iterdir()
        if p.name == "C1ke" or p.name.startswith("time_")
    ]
    if stale_diagnostics:
        raise RuntimeError(
            "restart target already contains diagnostic history before execution: "
            + ", ".join(sorted(stale_diagnostics))
        )

    write_json(
        current / MANIFEST,
        {
            "source_directory": str(previous),
            "source_C1_sha256": sha256_file(source),
            "seed_C1_sha256": sha256_file(target),
            "copied_restart_payload": sorted(copied),
            "diagnostics_copied": [],
            "policy": "C1.h5 plus explicitly named restart auxiliaries only",
        },
    )


def case_by_name(report: dict, name: str) -> dict | None:
    for case in report.get("case_summaries", []):
        if case.get("case") == name:
            return case
    return None


def sample_at(case: dict, time_value: float) -> dict | None:
    samples = case.get("samples", [])
    if not samples:
        return None
    row = min(samples, key=lambda r: abs(float(r.get("time", 0.0)) - time_value))
    if abs(float(row.get("time", 0.0)) - time_value) > TIME_TOL:
        return None
    return row


def protect_native_transients(report: dict) -> dict:
    reference = json.loads(REFERENCE.read_text())
    gates = reference["frozen_gates"]
    rows: list[dict] = []
    all_safe = True

    for expected in reference["points"]:
        case = case_by_name(report, expected["case"])
        current = sample_at(case, float(expected["time"])) if case else None
        if current is None:
            rows.append({
                **expected,
                "present": False,
                "safe_gate_pass": False,
                "reference_match": False,
            })
            all_safe = False
            continue

        width = float(current["width_gain_pct"])
        jpk = float(current["Jpk_change_pct"])
        safe = (
            width > float(gates["width_gain_threshold_pct"])
            and jpk <= float(gates["Jpk_change_max_pct"])
        )
        reference_match = (
            abs(width - float(expected["width_gain_pct"])) <= REFERENCE_ABS_TOL
            and abs(jpk - float(expected["Jpk_change_pct"])) <= REFERENCE_ABS_TOL
        )
        rows.append({
            "case": expected["case"],
            "time": expected["time"],
            "present": True,
            "width_gain_pct": width,
            "Jpk_change_pct": jpk,
            "safe_gate_pass": safe,
            "reference_width_gain_pct": expected["width_gain_pct"],
            "reference_Jpk_change_pct": expected["Jpk_change_pct"],
            "reference_match": reference_match,
            "width_delta_from_reference_pct": width - float(expected["width_gain_pct"]),
            "Jpk_delta_from_reference_pct": jpk - float(expected["Jpk_change_pct"]),
        })
        all_safe = all_safe and safe

    return {
        "pass": all_safe,
        "reference_file": str(REFERENCE),
        "reference_abs_tolerance": REFERENCE_ABS_TOL,
        "frozen_gates": gates,
        "points": rows,
        "interpretation": (
            "PASS means the previously observed native single-window transient "
            "authority still clears the unchanged width/Jpk gates. Exact reference "
            "matching is reported but is not the physics acceptance criterion."
        ),
    }


def annotate_gate_semantics(report: dict) -> None:
    """Make the legacy width_gate_pass_any field unambiguous."""
    for case in report.get("case_summaries", []):
        samples = case.get("samples", [])
        width_only = any(bool(row.get("width_gate_pass")) for row in samples)
        safe_any = any(
            bool(row.get("width_gate_pass")) and bool(row.get("current_gate_pass"))
            for row in samples
        )
        case["width_only_gate_pass_any"] = width_only
        case["safe_gate_pass_any"] = safe_any
        case["legacy_width_gate_pass_any_semantics"] = "width_and_current_gate"
        if bool(case.get("width_gate_pass_any")) != safe_any:
            raise RuntimeError(
                f"summary gate aggregation mismatch for {case.get('case')}: "
                f"legacy={case.get('width_gate_pass_any')} recomputed_safe={safe_any}"
            )


def validate_feedback_chain(report: dict) -> dict:
    feedback = report.get("feedback_case") or {}
    history = feedback.get("command_history") or []
    checks: list[dict] = []
    chain_ok = True

    for index, entry in enumerate(history):
        directory = Path(entry["directory"])
        final_h5 = directory / "C1.h5"
        row = {
            "step": entry.get("step", index),
            "directory": str(directory),
            "requested_start": entry.get("start"),
            "requested_stop": entry.get("stop"),
            "state": entry.get("state"),
        }

        if not final_h5.exists():
            row.update({"pass": False, "error": "missing final C1.h5"})
            checks.append(row)
            chain_ok = False
            continue

        final_hash = sha256_file(final_h5)
        row["final_C1_sha256"] = final_hash

        try:
            extracted = audit.nfc.safe_extract(directory)
            last_time = max(float(r["time"]) for r in extracted)
            row["last_extracted_time"] = last_time
            row["time_advanced_to_stop"] = abs(
                last_time - float(entry["stop"])
            ) <= TIME_TOL
        except Exception as exc:
            row.update({
                "pass": False,
                "error": f"cannot re-extract restart segment: {exc}",
            })
            checks.append(row)
            chain_ok = False
            continue

        if index == 0:
            row["restart"] = False
            row["seed_matches_previous_final"] = True
            row["state_hash_advanced"] = True
            row["pass"] = bool(row["time_advanced_to_stop"])
            chain_ok = chain_ok and bool(row["pass"])
            checks.append(row)
            continue

        manifest_path = directory / MANIFEST
        if not manifest_path.exists():
            row.update({"pass": False, "error": f"missing {MANIFEST}"})
            checks.append(row)
            chain_ok = False
            continue

        manifest = json.loads(manifest_path.read_text())
        previous_directory = Path(history[index - 1]["directory"])
        previous_final = previous_directory / "C1.h5"
        previous_hash = sha256_file(previous_final)
        seed_hash = str(manifest.get("seed_C1_sha256", ""))
        source_hash = str(manifest.get("source_C1_sha256", ""))

        seed_matches_previous = (
            seed_hash == previous_hash and source_hash == previous_hash
        )
        state_advanced = final_hash != seed_hash
        diagnostics_clean = not bool(manifest.get("diagnostics_copied"))
        row.update({
            "restart": True,
            "seed_C1_sha256": seed_hash,
            "previous_final_C1_sha256": previous_hash,
            "seed_matches_previous_final": seed_matches_previous,
            "state_hash_advanced": state_advanced,
            "diagnostics_clean": diagnostics_clean,
            "copied_restart_payload": manifest.get("copied_restart_payload", []),
        })
        row["pass"] = all((
            seed_matches_previous,
            state_advanced,
            diagnostics_clean,
            bool(row["time_advanced_to_stop"]),
        ))
        chain_ok = chain_ok and bool(row["pass"])
        checks.append(row)

    return {
        "pass": chain_ok and bool(history),
        "segments_checked": len(checks),
        "restart_segments_checked": max(0, len(checks) - 1),
        "seed_policy": "C1.h5 plus explicitly named restart auxiliaries; no C1ke/time_*.h5",
        "checks": checks,
    }


def best_native_case(report: dict) -> dict | None:
    native = [
        case for case in report.get("case_summaries", [])
        if case.get("kind") != "state_switched_feedback"
    ]
    if not native:
        return None
    return sorted(
        native,
        key=lambda s: (
            bool(s.get("final_safe_authority")),
            bool(s.get("sustained_positive_from_t0p10")),
            float(s.get("final_width_gain_pct", float("-inf"))),
            float(s.get("peak_width_gain_pct", float("-inf"))),
        ),
        reverse=True,
    )[0]


def postprocess_report() -> tuple[dict, int]:
    summary_path = audit.OUT / "timed_feedback_summary.json"
    report = json.loads(summary_path.read_text())

    annotate_gate_semantics(report)
    protected = protect_native_transients(report)
    chain = validate_feedback_chain(report)
    report["protected_native_transient_authority"] = protected
    report["feedback_restart_chain_validation"] = chain
    report.setdefault("audit", {})["restart_seed_policy"] = (
        "C1.h5 plus explicitly named restart auxiliaries only; diagnostic histories are not copied"
    )

    feedback = report.get("feedback_case") or {}
    feedback["restart_chain_validated"] = bool(chain["pass"])
    report["feedback_case"] = feedback

    if not chain["pass"]:
        report["best_case"] = best_native_case(report)
        if protected["pass"]:
            report["classification"] = (
                "M3DC1_TCT_TIMED_WINDOW_TRANSIENT_SAFE_AUTHORITY_FEEDBACK_CHAIN_INVALID"
            )
        else:
            report["classification"] = (
                "M3DC1_TCT_PROTECTED_NATIVE_TRANSIENT_REGRESSION_AND_FEEDBACK_CHAIN_INVALID"
            )
    elif not protected["pass"]:
        report["classification"] = "M3DC1_TCT_PROTECTED_NATIVE_TRANSIENT_REGRESSION"

    write_json(summary_path, report)
    write_json(audit.OUT / "feedback_restart_chain_validation.json", chain)
    write_json(audit.OUT / "protected_native_transient_authority.json", protected)

    if not protected["pass"]:
        return report, 3
    if not chain["pass"]:
        return report, 4
    return report, 0


def main() -> int:
    # Patch only restart transport.  Physics, actuator settings, metric extraction,
    # frozen gates, and native timed-window cases remain in the original audit.
    audit.nfc.copy_restart_state = clean_copy_restart_state
    rc = audit.main()
    report, validation_rc = postprocess_report()
    print("\n===== REPAIRED RESTART VALIDATION =====")
    print(json.dumps({
        "classification": report.get("classification"),
        "protected_native_transient_authority": report.get("protected_native_transient_authority"),
        "feedback_restart_chain_validation": {
            "pass": report.get("feedback_restart_chain_validation", {}).get("pass"),
            "segments_checked": report.get("feedback_restart_chain_validation", {}).get("segments_checked"),
            "restart_segments_checked": report.get("feedback_restart_chain_validation", {}).get("restart_segments_checked"),
        },
    }, indent=2, sort_keys=True))
    return rc if rc else validation_rc


if __name__ == "__main__":
    raise SystemExit(main())

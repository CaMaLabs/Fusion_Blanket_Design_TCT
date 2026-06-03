#!/usr/bin/env python3
"""Cross-check BOUT++ actuator results against the public CaMaLabs M3DC1 artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py


REPO = Path(__file__).resolve().parent
DEFAULT_M3DC1_REPO = Path("/root/CaMaLabs_M3DC1")
DEFAULT_BOUT_SUMMARY = (
    REPO
    / "validation_runs"
    / "bout_tct_actuator_robustness_default"
    / "tct_actuator_robustness_summary.json"
)
REQUIRED_M3DC1_FIELDS = ("psi", "phi", "P", "den", "ne", "te", "ti")


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _h5_string(value: Any) -> str:
    if hasattr(value, "asstr"):
        return str(value.asstr()[()])
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _inspect_hdf5(path: Path) -> dict[str, Any]:
    with h5py.File(path, "r") as h5:
        root_attrs = {key: _jsonable(value) for key, value in h5.attrs.items()}
        time_group = "time_000" if "time_000" in h5 else "equilibrium"
        field_path = f"{time_group}/fields"
        fields = sorted(h5[field_path].keys()) if field_path in h5 else []
        metadata: dict[str, Any] = {}
        if "proxy_metadata" in h5:
            for key, item in h5["proxy_metadata"].items():
                raw = item[()]
                if getattr(raw, "shape", None) == ():
                    raw = raw.item()
                if isinstance(raw, bytes):
                    metadata[key] = raw.decode("utf-8")
                elif hasattr(raw, "tolist"):
                    metadata[key] = raw.tolist()
                else:
                    metadata[key] = raw

    missing = [field for field in REQUIRED_M3DC1_FIELDS if field not in fields]
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size,
        "root_attrs": root_attrs,
        "proxy_metadata": metadata,
        "time_group_used": time_group,
        "field_count": len(fields),
        "required_fields": list(REQUIRED_M3DC1_FIELDS),
        "missing_required_fields": missing,
        "has_required_fields": not missing,
        "helical_proxy_flag": int(root_attrs.get("helical_proxy", 0)),
    }


def _summarize_m3dc1(m3dc1_repo: Path) -> dict[str, Any]:
    c1_path = m3dc1_repo / "validation" / "generated" / "helical_benchmark_proxy" / "C1.h5"
    candidate_results = m3dc1_repo / "validation" / "generated" / "candidate0_physics_results.csv"
    real_report = m3dc1_repo / "validation" / "real_c1_h5_report.md"
    helical_note = m3dc1_repo / "validation" / "helical_benchmark_note.md"
    verifier_summary = m3dc1_repo / "validation" / "results" / "freegsnke_verifier_summary.json"

    hdf5 = _inspect_hdf5(c1_path)
    rows = _read_csv(candidate_results)
    controlled = [row for row in rows if row.get("case_name") != "baseline"]
    passed_rows = [row for row in rows if row.get("status") == "ok" and row.get("passed_hard_constraints") == "True"]
    tbr_values = [_as_float(row.get("TBR")) for row in rows]
    severity_values = [_as_float(row.get("event_severity_mean")) for row in rows]
    score_values = [_as_float(row.get("score")) for row in rows]

    verifier = {}
    if verifier_summary.exists():
        verifier = json.loads(verifier_summary.read_text(encoding="utf-8"))

    return {
        "repo": str(m3dc1_repo),
        "hdf5": hdf5,
        "candidate_results": {
            "path": str(candidate_results),
            "rows": len(rows),
            "controlled_rows": len(controlled),
            "passed_hard_constraints_rows": len(passed_rows),
            "all_rows_pass_hard_constraints": len(passed_rows) == len(rows),
            "min_TBR": min(tbr_values) if tbr_values else None,
            "max_TBR": max(tbr_values) if tbr_values else None,
            "baseline_event_severity_mean": severity_values[0] if severity_values else None,
            "best_score": max(score_values) if score_values else None,
            "best_case": max(rows, key=lambda row: _as_float(row.get("score"))).get("case_name") if rows else None,
        },
        "reports": {
            "real_c1_h5_report": str(real_report),
            "helical_benchmark_note": str(helical_note),
        },
        "freegsnke_verifier": {
            "path": str(verifier_summary),
            "returncode": verifier.get("returncode"),
            "stdout": verifier.get("stdout"),
            "tests": verifier.get("tests"),
        },
    }


def _summarize_bout(path: Path) -> dict[str, Any]:
    summary = json.loads(path.read_text(encoding="utf-8"))
    trend = summary["trend_summary"]
    family = trend["family_summary"]
    return {
        "path": str(path),
        "interpretation": trend["interpretation"],
        "controlled_cases": trend["controlled_cases"],
        "robust_cases": trend["robust_cases"],
        "all_controlled_reduce_integrated_J": all(
            item["all_reduce_integrated_J"] for item in family.values()
        ),
        "nominal_peak_reduction": family["baseline"]["min_post_initial_peak_J_reduction_fraction"],
        "nominal_integrated_reduction": family["baseline"]["min_integrated_J_reduction_fraction"],
        "fine_peak_reduction": family["resolution"]["min_post_initial_peak_J_reduction_fraction"],
        "fine_integrated_reduction": family["resolution"]["min_integrated_J_reduction_fraction"],
        "timing_min_peak_reduction": family["timing"]["min_post_initial_peak_J_reduction_fraction"],
        "timing_min_integrated_reduction": family["timing"]["min_integrated_J_reduction_fraction"],
        "placement_min_peak_reduction": family["placement"]["min_post_initial_peak_J_reduction_fraction"],
        "placement_min_integrated_reduction": family["placement"]["min_integrated_J_reduction_fraction"],
        "top_cases": trend["top_cases"],
        "weakest_cases": trend["weakest_cases"],
    }


def _gates(m3dc1: dict[str, Any], bout: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "gate": "m3dc1_helical_proxy_hdf5_schema",
            "passed": bool(m3dc1["hdf5"]["has_required_fields"] and m3dc1["hdf5"]["helical_proxy_flag"] == 1),
            "evidence": {
                "missing_required_fields": m3dc1["hdf5"]["missing_required_fields"],
                "field_count": m3dc1["hdf5"]["field_count"],
                "helical_proxy_flag": m3dc1["hdf5"]["helical_proxy_flag"],
            },
        },
        {
            "gate": "m3dc1_candidate_proxy_constraints",
            "passed": bool(m3dc1["candidate_results"]["all_rows_pass_hard_constraints"]),
            "evidence": {
                "rows": m3dc1["candidate_results"]["rows"],
                "min_TBR": m3dc1["candidate_results"]["min_TBR"],
                "best_case": m3dc1["candidate_results"]["best_case"],
            },
        },
        {
            "gate": "open_source_equilibrium_verifier",
            "passed": m3dc1["freegsnke_verifier"]["returncode"] == 0,
            "evidence": {
                "returncode": m3dc1["freegsnke_verifier"]["returncode"],
                "stdout": m3dc1["freegsnke_verifier"]["stdout"],
            },
        },
        {
            "gate": "bout_preemptive_actuator_supported",
            "passed": bool(bout["nominal_peak_reduction"] > 0.0 and bout["nominal_integrated_reduction"] > 0.0),
            "evidence": {
                "nominal_peak_reduction": bout["nominal_peak_reduction"],
                "nominal_integrated_reduction": bout["nominal_integrated_reduction"],
            },
        },
        {
            "gate": "bout_fine_grid_direction_preserved",
            "passed": bool(bout["fine_peak_reduction"] > 0.0 and bout["fine_integrated_reduction"] > 0.0),
            "evidence": {
                "fine_peak_reduction": bout["fine_peak_reduction"],
                "fine_integrated_reduction": bout["fine_integrated_reduction"],
            },
        },
        {
            "gate": "timing_boundary_detected",
            "passed": bool(bout["timing_min_peak_reduction"] == 0.0 and bout["timing_min_integrated_reduction"] > 0.0),
            "evidence": {
                "timing_min_peak_reduction": bout["timing_min_peak_reduction"],
                "timing_min_integrated_reduction": bout["timing_min_integrated_reduction"],
            },
        },
    ]


def _write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    gates = summary["gates"]
    passed = sum(1 for gate in gates if gate["passed"])
    lines = [
        "# M3D-C1 / BOUT++ Cross-Validation Status",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        f"Overall status: **{summary['overall_status']}**",
        "",
        "## Gate Summary",
        "",
        "| Gate | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for gate in gates:
        status = "pass" if gate["passed"] else "fail"
        evidence = json.dumps(gate["evidence"], sort_keys=True)
        lines.append(f"| `{gate['gate']}` | {status} | `{evidence}` |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The combined evidence supports TCT as a preemptive edge/current-sheet conditioning concept in reduced plasma-side checks.",
            "It does not yet establish full tokamak-grade validation because the M3D-C1 helical artifact is a source-inspired proxy and the BOUT++ actuator is a reduced-MHD slab model.",
            "The falsification boundary is explicit: delayed actuation still lowers integrated current but does not prevent peak current after the sheet has formed.",
            "",
            "## Next Step",
            "",
            "Build a closed-loop trigger that turns on the resolved actuator before the current-sheet peak, then export the same trigger schedule as an M3D-C1-compatible backend diagnostic contract.",
            "",
            f"Passed gates: `{passed}/{len(gates)}`",
            "",
        ]
    )
    (run_dir / "cross_validation_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m3dc1-repo", type=Path, default=DEFAULT_M3DC1_REPO)
    parser.add_argument("--bout-summary", type=Path, default=DEFAULT_BOUT_SUMMARY)
    parser.add_argument("--run-dir", type=Path, default=REPO / "validation_runs" / "m3dc1_bout_cross_validation_default")
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)
    m3dc1 = _summarize_m3dc1(args.m3dc1_repo)
    bout = _summarize_bout(args.bout_summary)
    gates = _gates(m3dc1, bout)
    passed = sum(1 for gate in gates if gate["passed"])
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": "PASS_WITH_REDUCED_MODEL_BOUNDARIES" if passed == len(gates) else "CHECK_REQUIRED",
        "m3dc1": m3dc1,
        "bout": bout,
        "gates": gates,
    }
    summary = _jsonable(summary)

    (args.run_dir / "cross_validation_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    with (args.run_dir / "cross_validation_gates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["gate", "passed", "evidence"])
        writer.writeheader()
        for gate in gates:
            writer.writerow(
                {"gate": gate["gate"], "passed": gate["passed"], "evidence": json.dumps(gate["evidence"], sort_keys=True)}
            )
    _write_report(args.run_dir, summary)
    print(json.dumps({"run_dir": str(args.run_dir), "overall_status": summary["overall_status"], "passed_gates": passed, "total_gates": len(gates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

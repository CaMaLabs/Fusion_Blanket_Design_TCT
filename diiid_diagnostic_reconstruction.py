#!/usr/bin/env python3
"""Build a reviewer-facing reconstructed diagnostic package for DIII-D shot 158103."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from machine_equilibrium_readiness import _parse_geqdsk


REPO = Path(__file__).resolve().parent
CASE_DIR = REPO / "validation_inputs" / "geqdsk_efit_baseline" / "diii_d_158103_03796"
DEFAULT_GEQDSK = CASE_DIR / "geqdsk"
DEFAULT_AEQDSK = CASE_DIR / "efit" / "a158103.03796"
DEFAULT_PROFILE = CASE_DIR / "efit" / "p158103.03796"
DEFAULT_RUN_DIR = REPO / "validation_runs" / "diiid_diagnostic_reconstruction_default"
SHOT = 158103
REFERENCE_TIME_MS = 3796.325
PROFILE_HEADER = re.compile(r"^(\d+)\s+psinorm\s+(\S+)\s+(\S+)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_profiles(path: Path) -> dict[str, dict[str, Any]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    profiles: dict[str, dict[str, Any]] = {}
    index = 0
    while index < len(lines):
        match = PROFILE_HEADER.match(lines[index].strip())
        if not match:
            index += 1
            continue
        count = int(match.group(1))
        value_label = match.group(2)
        derivative_label = match.group(3)
        rows = []
        for line in lines[index + 1 : index + 1 + count]:
            parts = line.split()
            if len(parts) >= 3:
                rows.append(tuple(float(value) for value in parts[:3]))
        if len(rows) == count:
            name = value_label.split("(")[0].lower()
            data = np.asarray(rows, dtype=float)
            profiles[name] = {
                "value_label": value_label,
                "derivative_label": derivative_label,
                "psinorm": data[:, 0],
                "value": data[:, 1],
                "derivative": data[:, 2],
            }
        index += count + 1
    return profiles


def interpolate(profile: dict[str, Any], psinorm: float, field: str = "value") -> float:
    return float(np.interp(psinorm, profile["psinorm"], profile[field]))


def profile_summary(profiles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for name, profile in profiles.items():
        rows.append(
            {
                "profile": name,
                "value_label": profile["value_label"],
                "rows": len(profile["value"]),
                "axis_value": interpolate(profile, 0.0),
                "pedestal_value_psin_0p95": interpolate(profile, 0.95),
                "edge_value_psin_0p99": interpolate(profile, 0.99),
                "pedestal_gradient_psin_0p95": interpolate(profile, 0.95, "derivative"),
            }
        )
    return rows


def reconstructed_baselines(profiles: dict[str, dict[str, Any]], geqdsk: dict[str, Any]) -> dict[str, Any]:
    required = ("ne", "te", "ni", "ti", "ptot", "er", "vtor1", "vpol1")
    missing = [name for name in required if name not in profiles]
    if missing:
        raise ValueError(f"missing required fitted profiles: {missing}")
    return {
        "ip_a": geqdsk["current_a"],
        "btor_t": geqdsk["bcentr_t"],
        "edge_ne_1e20_m3": interpolate(profiles["ne"], 0.95),
        "edge_te_kev": interpolate(profiles["te"], 0.95),
        "edge_ni_1e20_m3": interpolate(profiles["ni"], 0.95),
        "edge_ti_kev": interpolate(profiles["ti"], 0.95),
        "edge_ptot_kpa": interpolate(profiles["ptot"], 0.95),
        "edge_er_kv_m": interpolate(profiles["er"], 0.95),
        "edge_vtor1_km_s": interpolate(profiles["vtor1"], 0.95),
        "edge_vpol1_km_s": interpolate(profiles["vpol1"], 0.95),
        "edge_pressure_gradient_kpa_per_psin": interpolate(profiles["ptot"], 0.95, "derivative"),
        "edge_er_gradient_kv_m_per_psin": interpolate(profiles["er"], 0.95, "derivative"),
    }


def logistic(times: np.ndarray, center: float, width: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(times - center) / width))


def make_trace(baselines: dict[str, Any], scenario: dict[str, float]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    times = np.arange(REFERENCE_TIME_MS - 40.0, REFERENCE_TIME_MS + 10.0001, 0.25)
    onset = REFERENCE_TIME_MS - scenario["precursor_lead_ms"]
    ramp = logistic(times, onset, scenario["rise_width_ms"])
    event = np.exp(-0.5 * ((times - REFERENCE_TIME_MS) / 0.8) ** 2)
    phase = np.sin(0.73 * (times - REFERENCE_TIME_MS) + scenario["phase"])
    noise = scenario["noise_fraction"] * phase
    mirnov = scenario["mirnov_amplitude"] * ramp * (1.0 + noise) + 0.35 * event
    ece = baselines["edge_te_kev"] * (1.0 - scenario["ece_drop_fraction"] * ramp - 0.12 * event)
    density = baselines["edge_ne_1e20_m3"] * (1.0 + scenario["density_rise_fraction"] * ramp - 0.08 * event)
    er = baselines["edge_er_kv_m"] * (1.0 - scenario["er_relax_fraction"] * ramp)
    dalpha = 0.05 * ramp + event
    derivative = np.gradient(mirnov, times)
    precursor_only = (times >= onset) & (times <= REFERENCE_TIME_MS - 2.5)
    threshold = 0.35 * float(np.max(derivative[precursor_only]))
    valid = np.flatnonzero(precursor_only & (derivative >= threshold))
    trigger_time = float(times[valid[0]]) if len(valid) else -1.0
    lead = REFERENCE_TIME_MS - trigger_time if trigger_time >= 0.0 else -1.0
    rows = [
        {
            "shot": SHOT,
            "scenario": scenario["name"],
            "time_ms": float(time),
            "reconstructed_mirnov_proxy": float(mirnov[i]),
            "reconstructed_mirnov_growth_per_ms": float(derivative[i]),
            "reconstructed_edge_ece_te_kev": float(ece[i]),
            "reconstructed_edge_density_1e20_m3": float(density[i]),
            "reconstructed_edge_er_kv_m": float(er[i]),
            "reconstructed_dalpha_proxy": float(dalpha[i]),
        }
        for i, time in enumerate(times)
    ]
    latency_checks = {}
    for latency in (3.0, 5.0, 8.0, 12.0):
        latency_checks[f"{latency:g}_ms"] = bool(lead >= latency)
    return rows, {
        "scenario": scenario["name"],
        "assumed_precursor_lead_ms": scenario["precursor_lead_ms"],
        "growth_threshold": threshold,
        "threshold_definition": "35% of maximum reconstructed derivative between hypothesized precursor onset and reference_time_minus_2.5_ms; excludes event-marker contamination",
        "trigger_time_ms": trigger_time,
        "available_lead_ms": lead,
        "latency_feasibility": latency_checks,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def diagnostic_contract() -> dict[str, Any]:
    return {
        "shot": SHOT,
        "window_ms": [REFERENCE_TIME_MS - 40.0, REFERENCE_TIME_MS + 10.0],
        "reference_time_ms": REFERENCE_TIME_MS,
        "minimum_time_resolution_ms": 0.25,
        "requested_observables": [
            {
                "standard_name": "plasma_current",
                "priority": "required",
                "candidate_source": "PTDATA ip or MDSplus efit01 \\\\ipmhd",
                "replacement_column": "ip_a",
            },
            {
                "standard_name": "edge_electron_temperature",
                "priority": "required",
                "candidate_source": "IMAS ece.channel.t_e.data or mapped ECE channels",
                "replacement_column": "edge_ece_te_kev",
            },
            {
                "standard_name": "magnetic_fluctuation_precursor",
                "priority": "required",
                "candidate_source": "appropriate Mirnov/magnetic probe channels selected by DIII-D reviewer",
                "replacement_column": "mirnov_proxy",
            },
            {
                "standard_name": "line_or_edge_density",
                "priority": "required",
                "candidate_source": "PTDATA dssdenest and/or available interferometer/profile channel",
                "replacement_column": "density",
            },
            {
                "standard_name": "event_timing",
                "priority": "required",
                "candidate_source": "D-alpha/divertor light or established ELM/event marker",
                "replacement_column": "event_marker",
            },
            {
                "standard_name": "actuator_command_and_response",
                "priority": "preferred",
                "candidate_source": "PCS/RMP/coil command and measured response channels applicable to shot",
                "replacement_column": "actuator",
            },
            {
                "standard_name": "efit_time_evolution",
                "priority": "preferred",
                "candidate_source": "FDP efit01 tree around requested window",
                "replacement_column": "equilibrium",
            },
        ],
        "acceptance_tests": {
            "precursor_exists": "A reproducible pre-event growth signal exceeds its noise-derived threshold before the event marker.",
            "lead_time": "Trigger lead exceeds measured processing plus candidate actuator latency.",
            "cross_channel": "Magnetic precursor timing is corroborated by at least one independent edge channel.",
            "falsification": "No robust precursor, insufficient lead time, or inconsistent timing across channels falsifies the diagnostic-trigger claim for this event.",
        },
    }


def write_report(run_dir: Path, summary: dict[str, Any]) -> None:
    base = summary["reconstructed_baselines"]
    lines = [
        "# DIII-D Shot 158103 Diagnostic Reconstruction Package",
        "",
        f"- Status: `{summary['status']}`",
        f"- Reference: shot `{SHOT}` at `{REFERENCE_TIME_MS:.3f} ms`",
        "- Input basis: public EFIT `g/a/p` snapshot",
        "- Raw time-series diagnostics: `not present`",
        "",
        "## Experiment-referenced baseline",
        "",
        f"- Plasma current: `{base['ip_a']:.6e} A`",
        f"- Toroidal field: `{base['btor_t']:.6g} T`",
        f"- Edge ne at psiN=0.95: `{base['edge_ne_1e20_m3']:.6g} 1e20/m^3`",
        f"- Edge Te at psiN=0.95: `{base['edge_te_kev']:.6g} keV`",
        f"- Edge total pressure at psiN=0.95: `{base['edge_ptot_kpa']:.6g} kPa`",
        f"- Edge Er at psiN=0.95: `{base['edge_er_kv_m']:.6g} kV/m`",
        "",
        "## Falsifiable timing hypotheses",
        "",
        "| Scenario | Assumed precursor lead | Reconstructed trigger lead | 3 ms feasible | 5 ms feasible | 8 ms feasible | 12 ms feasible |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["timing_hypotheses"]:
        checks = row["latency_feasibility"]
        lines.append(
            f"| `{row['scenario']}` | {row['assumed_precursor_lead_ms']:.1f} ms | "
            f"{row['available_lead_ms']:.2f} ms | {checks['3_ms']} | {checks['5_ms']} | "
            f"{checks['8_ms']} | {checks['12_ms']} |"
        )
    lines += [
        "",
        "These traces are reconstructed hypotheses, not measurements. They define the",
        "signals, time window, thresholds, and pass/fail tests that raw DIII-D data can",
        "directly replace.",
        "",
        "## Requested access",
        "",
        "The narrow request is read-only access to the listed channels for shot 158103",
        "over 3756.325-3806.325 ms. The test asks whether a robust magnetic precursor",
        "exists, whether ECE/density corroborate it, and whether measured lead time is",
        "longer than plausible sensing and actuator latency.",
        "",
        "## Claim boundary",
        "",
        "This package demonstrates preparation for an experimental diagnostic test. It",
        "does not demonstrate that the reconstructed precursor occurred, that the event",
        "at the reference time is an ELM, or that a real actuator could respond in time.",
        "",
    ]
    (run_dir / "diiid_diagnostic_reconstruction_report.md").write_text("\n".join(lines), encoding="utf-8")


def write_access_request(run_dir: Path) -> None:
    text = f"""# Limited DIII-D Diagnostic Data Access Request

We reconstructed the public EFIT equilibrium and fitted profiles for DIII-D
shot `{SHOT}` at `{REFERENCE_TIME_MS:.3f} ms` and prepared a directly falsifiable
precursor-timing test.

## Requested scope

- Read-only data for shot `{SHOT}`
- Time window: `{REFERENCE_TIME_MS - 40.0:.3f}` to `{REFERENCE_TIME_MS + 10.0:.3f} ms`
- Required quantities: magnetic fluctuation/precursor signal, edge ECE,
  density, established event marker, and plasma current
- Preferred additions: applicable actuator command/response and EFIT time evolution

## Question

Does a reproducible magnetic-growth precursor occur before the event marker,
is it corroborated by an independent edge channel, and is its measured lead
time longer than the sensing plus actuator latency?

## Precommitted outcomes

- No robust precursor: diagnostic-trigger claim fails for this event.
- Precursor but insufficient lead: real-time preemptive control is unsupported
  for the tested latency.
- Robust precursor with sufficient lead: proceed to a supported actuator-model
  study; this alone does not validate TCT control.

The repository contains the reconstruction script, standardized replacement
contract, synthetic traces, and pass/fail criteria so authorized users can
replace the reconstructed columns with raw data without redesigning the test.
"""
    (run_dir / "DIIID_LIMITED_DATA_ACCESS_REQUEST.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geqdsk", type=Path, default=DEFAULT_GEQDSK)
    parser.add_argument("--aeqdsk", type=Path, default=DEFAULT_AEQDSK)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    if args.run_dir.exists():
        shutil.rmtree(args.run_dir)
    args.run_dir.mkdir(parents=True)

    geqdsk = _parse_geqdsk(args.geqdsk)
    profiles = parse_profiles(args.profile)
    profile_rows = profile_summary(profiles)
    baselines = reconstructed_baselines(profiles, geqdsk)
    scenarios = (
        {"name": "late_weak", "precursor_lead_ms": 6.0, "rise_width_ms": 2.0, "noise_fraction": 0.20, "mirnov_amplitude": 0.45, "ece_drop_fraction": 0.03, "density_rise_fraction": 0.02, "er_relax_fraction": 0.05, "phase": 0.2},
        {"name": "nominal", "precursor_lead_ms": 15.0, "rise_width_ms": 3.0, "noise_fraction": 0.10, "mirnov_amplitude": 0.75, "ece_drop_fraction": 0.06, "density_rise_fraction": 0.04, "er_relax_fraction": 0.10, "phase": 1.1},
        {"name": "early_strong", "precursor_lead_ms": 25.0, "rise_width_ms": 4.0, "noise_fraction": 0.05, "mirnov_amplitude": 1.00, "ece_drop_fraction": 0.10, "density_rise_fraction": 0.06, "er_relax_fraction": 0.16, "phase": 2.0},
    )
    traces: list[dict[str, Any]] = []
    hypotheses = []
    for scenario in scenarios:
        rows, hypothesis = make_trace(baselines, scenario)
        traces.extend(rows)
        hypotheses.append(hypothesis)

    contract = diagnostic_contract()
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "DIIID_DIAGNOSTIC_RECONSTRUCTION_READY_FOR_AUTHORIZED_REPLACEMENT",
        "shot": SHOT,
        "reference_time_ms": REFERENCE_TIME_MS,
        "source_files": {
            "geqdsk": {"path": str(args.geqdsk), "sha256": sha256(args.geqdsk)},
            "aeqdsk": {"path": str(args.aeqdsk), "sha256": sha256(args.aeqdsk)},
            "profile": {"path": str(args.profile), "sha256": sha256(args.profile)},
        },
        "profile_group_count": len(profiles),
        "reconstructed_baselines": baselines,
        "timing_hypotheses": hypotheses,
        "raw_diagnostics_present": False,
        "claim_boundary": "Experiment-referenced reconstruction and precommitted test only; not raw diagnostic validation.",
    }
    write_csv(args.run_dir / "reconstructed_diagnostic_traces.csv", traces)
    write_csv(args.run_dir / "fitted_profile_summary.csv", profile_rows)
    (args.run_dir / "diagnostic_replacement_contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.run_dir / "diiid_diagnostic_reconstruction_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(args.run_dir, summary)
    write_access_request(args.run_dir)
    print(json.dumps({"status": summary["status"], "profile_group_count": len(profiles)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

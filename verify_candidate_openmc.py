#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from fusion_engine_v5.engine.reactor_simulation import simulate_reactor


ROOT = Path.cwd()
REACTOR_GLOB = "reactor_*.json"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def candidate_target(packet: Dict[str, Any]) -> Dict[str, float]:
    geom = packet.get("geometry", {})
    return {
        "lithium_thickness_mm": safe_float(geom.get("lithium_thickness_mm")),
        "blanket_thickness_cm": safe_float(geom.get("blanket_thickness_cm")),
        "layer_count": safe_float(geom.get("layer_count")),
        "blanket_attenuation": blanket_attenuation,
    "TBR": TBR,
    "gradient": gradient if "gradient" in locals() else 0.0,
}


def reactor_distance(target: Dict[str, float], reactor: Dict[str, Any]) -> float:
    rx_lith_mm = safe_float(
        reactor.get("lithium_thickness_mm", reactor.get("lithium_layer_thickness_mm", 0.0))
    )
    rx_blanket_cm = safe_float(
        reactor.get("blanket_thickness_cm", reactor.get("blanket_thickness", 0.0))
    )
    rx_layers = safe_float(
        reactor.get("layer_count", reactor.get("layers", 0.0))
    )

    return (
        (rx_lith_mm - target["lithium_thickness_mm"]) ** 2
        + (rx_blanket_cm - target["blanket_thickness_cm"]) ** 2
        + (rx_layers - target["layer_count"]) ** 2
    )


def find_best_reactor(packet: Dict[str, Any]) -> Tuple[Path, Dict[str, Any]]:
    target = candidate_target(packet)
    reactor_paths = sorted(ROOT.glob(REACTOR_GLOB))
    if not reactor_paths:
        raise FileNotFoundError(f"No {REACTOR_GLOB} files found in {ROOT}")

    best_path = None
    best_data = None
    best_dist = float("inf")

    for rp in reactor_paths:
        data = load_json(rp)
        dist = reactor_distance(target, data)
        if dist < best_dist:
            best_dist = dist
            best_path = rp
            best_data = data

    assert best_path is not None and best_data is not None
    return best_path, best_data


def apply_candidate_overlay(reactor: Dict[str, Any], packet: Dict[str, Any]) -> Dict[str, Any]:
    design = dict(reactor)
    geom = packet.get("geometry", {})
    ctrl = packet.get("control", {})

    # Geometry overlay
    if "wall_type" in geom:
        design["wall_type"] = geom["wall_type"]
    if "lithium_thickness_mm" in geom:
        # keep both names if different branches use different keys
        design["lithium_thickness_mm"] = geom["lithium_thickness_mm"]
        design["lithium_thickness"] = geom["lithium_thickness_mm"]
    if "blanket_thickness_cm" in geom:
        design["blanket_thickness_cm"] = geom["blanket_thickness_cm"]
        design["blanket_thickness"] = geom["blanket_thickness_cm"]
    if "layer_count" in geom:
        design["layer_count"] = geom["layer_count"]
        design["layers"] = geom["layer_count"]
    if "layer_stack_label" in geom:
        design["layer_stack_label"] = geom["layer_stack_label"]

    # Control overlay metadata
    if "li_current" in ctrl:
        design["li_current"] = ctrl["li_current"]
    if "severity_scale" in ctrl:
        design["severity_scale"] = ctrl["severity_scale"]
    if "supervisor_enabled" in ctrl:
        design["supervisor_enabled"] = ctrl["supervisor_enabled"]
    if "supervisor_level" in ctrl:
        design["supervisor_level"] = ctrl["supervisor_level"]

    # Map supervisor label to gains
    level = str(ctrl.get("supervisor_level", "")).lower()
    if level == "weak":
        design["supervisor_gain_down"] = 0.025
        design["supervisor_gain_up"] = 0.012
    elif level == "medium":
        design["supervisor_gain_down"] = 0.035
        design["supervisor_gain_up"] = 0.018
    elif level == "slightly_stronger":
        design["supervisor_gain_down"] = 0.045
        design["supervisor_gain_up"] = 0.023

    # Reasonable defaults used in newer branch
    if design.get("supervisor_enabled", False):
        design.setdefault("supervisor_risk_high", 0.9)
        design.setdefault("supervisor_risk_low", 0.5)
        design.setdefault("supervisor_li_ceiling_min", 0.05)
        design.setdefault("supervisor_li_ceiling_max", 1.0)

    return design


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run real Ubuntu/OpenMC verification for a candidate packet.")
    parser.add_argument("candidate_packet", type=Path)
    parser.add_argument("--out", type=Path, default=Path("verification_summary.json"))
    args = parser.parse_args()

    packet = load_json(args.candidate_packet)
    reactor_path, reactor = find_best_reactor(packet)
    design = apply_candidate_overlay(reactor, packet)

    print(f"[+] Matched reactor: {reactor_path}")
    print("[+] Running simulate_reactor(..., blanket_validate=True)")

    result = simulate_reactor(design, blanket_validate=True)

    blanket_model = result.get("blanket_model", result.get("blanket", {}).get("model"))
    tbr = safe_float(result.get("TBR", result.get("blanket", {}).get("TBR", 0.0)))
    wall_load = safe_float(result.get("wall_load", result.get("blanket", {}).get("wall_load", 0.0)))
    wall_temp = safe_float(result.get("wall_temp", result.get("blanket", {}).get("wall_temp", 0.0)))
    net_electric = safe_float(result.get("net_electric", result.get("net_electric_MW", 0.0)))
    fail_rate = safe_float(result.get("fail_rate", 0.0))

    summary = {
        "schema_version": "1.0",
        "candidate_id": packet.get("candidate_id"),
        "verifier_branch": "ubuntu_fusion_engine_v5_openmc_real",
        "matched_reactor_file": str(reactor_path),
        "input_echo": {
            "reactor_family": packet.get("reactor_family"),
            "blanket_family": packet.get("blanket_family"),
            "li_current": packet.get("control", {}).get("li_current"),
            "supervisor_level": packet.get("control", {}).get("supervisor_level"),
            "severity_scale": packet.get("control", {}).get("severity_scale"),
        },
        "neutronics": {
            "blanket_model": blanket_model,
            "TBR": tbr,
            "wall_load_MW_m2": wall_load,
            "wall_temp_C": wall_temp,
            "net_electric_MW": net_electric,
            "fail_rate": fail_rate,
        },
        "full_result": result,
    }

    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[+] Wrote {args.out}")

    if __name__ == "__main__":
        main()

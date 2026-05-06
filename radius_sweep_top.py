#!/usr/bin/env python3
import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

BASELINE_RADIUS_CM = 60.0
RADIUS_VALUES_CM = [60.0, 70.0, 80.0, 90.0, 100.0]

ATTENUATION_SOFT_CAP = 0.995
ATTENUATION_PENALTY_SCALE = 50.0
WALL_LOAD_SCREEN_MW_M2 = 10.0
FRONT_HEAT_SCREEN = 0.05
ATTENUATION_HARD_CAP = 0.995
FRONT_HEAT_PENALTY_SCALE = 4000.0

DEFAULT_INPUTS = [
    "radius_heat_top.json",
    "verification_top_rows_20260324_164708_L20_WTi_B4C_60_30_10_blanket_form.json",
    "verification_runs_20260324_164708_L20_WTi_B4C_60_30_10_blanket_form.json",
    "best_candidates.json",
    "top_candidates.json",
]


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def area_scale_from_radius(radius_cm: float, baseline_radius_cm: float = BASELINE_RADIUS_CM) -> float:
    if radius_cm <= 0.0 or baseline_radius_cm <= 0.0:
        return 1.0
    return (radius_cm / baseline_radius_cm) ** 2


def corrected_wall_load(raw_wall_load: float, radius_cm: float) -> float:
    return raw_wall_load / area_scale_from_radius(radius_cm)


def scaled_front_heating(front_heat: float, radius_cm: float) -> float:
    return front_heat / area_scale_from_radius(radius_cm)


def attenuation_penalty(attn: float) -> float:
    excess = max(0.0, attn - ATTENUATION_SOFT_CAP)
    return excess * ATTENUATION_PENALTY_SCALE


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_input_file(user_path: str = None) -> str:
    if user_path:
        if not os.path.exists(user_path):
            raise FileNotFoundError(f"Input file not found: {user_path}")
        return user_path

    for p in DEFAULT_INPUTS:
        if os.path.exists(p):
            return p

    raise FileNotFoundError(
        "No input JSON found. Tried:\n  " + "\n  ".join(DEFAULT_INPUTS)
    )


def extract_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if isinstance(payload, dict):
        for key in ("results", "rows", "data", "top_rows", "candidates"):
            v = payload.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        return [payload]

    raise ValueError("Unsupported JSON structure")


def get_metric(row, *keys, default=0.0):
    if not isinstance(row, dict):
        return default

    # 1. direct keys
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]

    # 2. try neutronics block
    n = row.get("neutronics")
    if isinstance(n, dict):
        for k in keys:
            if k in n and n[k] is not None:
                return n[k]

    # 3. fallback: suffix match (_openmc, etc)
    for k in keys:
        for rk in row.keys():
            if rk.lower().startswith(k.lower()):
                v = row.get(rk)
                if v is not None:
                    return v

    return default

    return default


def choose_base_radius(row: Dict[str, Any]) -> float:
    for name in ("radius_cm", "r_cm", "major_radius_cm"):
        if name in row:
            return safe_float(row.get(name), BASELINE_RADIUS_CM)
    return BASELINE_RADIUS_CM


def expand_row_for_radius(base_row: Dict[str, Any], radius_cm: float) -> Dict[str, Any]:
    out = dict(base_row)

    base_radius_cm = choose_base_radius(base_row)

    attn = get_metric(
        base_row,
        "attenuation",
        "ATTN",
        "ATTN_openmc",
        "blanket_attenuation",
        default=0.0,
    )

    # reject rows with missing physics (attenuation == 0 is invalid)
    if attn <= 0.0:
        out["rejected_reason"] = "missing_physics"
        out["score"] = -1e18

    grad = get_metric(
        base_row,
        "gradient",
        "GRAD",
        "GRAD_openmc",
        default=0.0,
    )
    tbr = get_metric(
        base_row,
        "tbr",
        "TBR",
        "TBR_openmc",
        default=0.0,
    )

    net_electric = get_metric(
        base_row,
        "net_electric",
        "net_electric_MW",
        "net_MW",
        "net",
        default=0.0,
    )

    front_heat_raw = get_metric(
        base_row,
        "front_heating_raw",
        "front_heat_raw",
        "front_heat",
        "blanket_front_heat_frac",
        default=0.0,
    )

    front_heat_corrected_existing = get_metric(
        base_row,
        "front_heating_corrected",
        "front_heat_corrected",
        default=front_heat_raw,
    )

    wall_load_raw = get_metric(
        base_row,
        "wall_load_raw",
        "wall_load",
        "wall_load_MW_m2",
        default=0.0,
    )

    wall_load_corrected_existing = get_metric(
        base_row,
        "wall_load_corrected",
        default=wall_load_raw,
    )

    wall_temp_raw = get_metric(
        base_row,
        "wall_temp_raw",
        "wall_temp",
        "wall_temp_C",
        default=0.0,
    )

    wall_temp_corrected = get_metric(
        base_row,
        "wall_temp_corrected",
        default=wall_temp_raw,
    )

    fail_rate = get_metric(base_row, "fail_rate", default=0.0)
    plasmoid_rate = get_metric(base_row, "plasmoid_rate", default=0.0)
    burst_rate = get_metric(base_row, "burst_rate", default=0.0)
    meltdown_rate = get_metric(base_row, "meltdown_rate", default=fail_rate)
    spread_credit = get_metric(base_row, "spread_credit", default=0.0)
    healing_credit = get_metric(base_row, "healing_credit", default=0.0)

    # Undo prior baseline correction if present and reapply at new radius
    baseline_area_scale = area_scale_from_radius(base_radius_cm)
    wall_load_unscaled = wall_load_corrected_existing * baseline_area_scale if wall_load_corrected_existing > 0 else wall_load_raw
    front_heat_unscaled = front_heat_corrected_existing * baseline_area_scale if front_heat_corrected_existing > 0 else front_heat_raw

    # --- PHYSICS-BASED HEAT TRANSPORT MODEL ---
    # Approximate spreading/removal from flowing liquid lithium plus conduction.
    # This is still a reduced-order model, but it is grounded in material properties
    # instead of an arbitrary flat spread factor.

    # liquid lithium properties near fusion-relevant operating temperatures
    LI_DENSITY = 510.0   # kg/m^3
    LI_CP = 3580.0       # J/kg-K
    LI_K = 85.0          # W/m-K

    # characteristic transport length scale
    L_char = max(0.01, radius_cm / 100.0)   # meters

    # grounded but still conservative default flow assumption
    flow_velocity = 0.5  # m/s
    res_time = L_char / max(flow_velocity, 1e-9)

    # conductive smoothing
    thermal_diffusivity = LI_K / (LI_DENSITY * LI_CP)
    eta_cond = thermal_diffusivity * res_time / max(L_char ** 2, 1e-12)

    # advective transport / moving-wall spreading
    eta_flow = (flow_velocity * res_time) / max(L_char, 1e-12)

    # total reduction factor
    heat_transport_factor = 1.0 + eta_flow + eta_cond

    wall_load_corrected_new = corrected_wall_load(wall_load_unscaled, radius_cm) / heat_transport_factor
    front_heat_corrected_new = scaled_front_heating(front_heat_unscaled, radius_cm) / heat_transport_factor

    # Temperature scaling remains conservative, but now also benefits from transport
    temp_scale = math.sqrt(max(1e-12, BASELINE_RADIUS_CM / radius_cm)) / math.sqrt(max(heat_transport_factor, 1e-12))
    wall_temp_corrected_new = wall_temp_corrected * temp_scale if wall_temp_corrected > 0 else wall_temp_raw * temp_scale

    attn_pen = attenuation_penalty(attn)

    # Hard reject over-trapping regimes that dump too much energy near the wall
    if attn > ATTENUATION_HARD_CAP:
        out["rejected_reason"] = "attenuation_hard_cap"
        out["attenuation_penalty"] = attn_pen
        out["score"] = -1e18
        return out

    meltdown_penalty = 1000.0 * meltdown_rate
    plasmoid_penalty = 100.0 * plasmoid_rate
    burst_penalty = 50.0 * burst_rate

    front_heat_penalty = FRONT_HEAT_PENALTY_SCALE * max(0.0, front_heat_corrected_new)

    score = (
        net_electric
        - meltdown_penalty
        - plasmoid_penalty
        - burst_penalty
        - attn_pen
        - front_heat_penalty
    )

    out["source_radius_cm"] = base_radius_cm
    out["radius_cm"] = radius_cm
    out["tbr"] = tbr
    out["attenuation"] = attn
    out["gradient"] = grad
    out["net_electric"] = net_electric

    out["front_heating_raw"] = front_heat_raw
    out["front_heating_corrected"] = front_heat_corrected_new

    out["wall_load_raw"] = wall_load_raw
    out["wall_load_corrected"] = wall_load_corrected_new

    out["wall_temp_raw"] = wall_temp_raw
    out["wall_temp_corrected"] = wall_temp_corrected_new

    out["fail_rate"] = fail_rate
    out["plasmoid_rate"] = plasmoid_rate
    out["burst_rate"] = burst_rate
    out["meltdown_rate"] = meltdown_rate
    out["spread_credit"] = spread_credit
    out["healing_credit"] = healing_credit
    out["attenuation_penalty"] = attn_pen
    out["front_heat_penalty"] = front_heat_penalty
    out["heat_transport_factor"] = heat_transport_factor
    out["eta_flow"] = eta_flow
    out["eta_cond"] = eta_cond
    out["score"] = score

    return out


def row_survives(row: Dict[str, Any], keep_unscreened: bool) -> bool:
    if keep_unscreened:
        return True
    attn = safe_float(row.get("attenuation"))

    # enforce optimal attenuation window
    if attn > 0.995:
        return False
    if attn < 0.95:
        return False

    if row.get("rejected_reason") in ("attenuation_hard_cap", "missing_physics"):
        return False
    if safe_float(row.get("wall_load_corrected"), 1e18) > WALL_LOAD_SCREEN_MW_M2:
        return False
    if safe_float(row.get("front_heating_corrected"), 1e18) > FRONT_HEAT_SCREEN:
        return False
    return True


def fmt(row: Dict[str, Any]) -> str:
    return (
        f"radius_cm={safe_float(row.get('radius_cm')):.1f} "
        f"TBR={safe_float(row.get('tbr')):.6f} "
        f"ATTN={safe_float(row.get('attenuation')):.12f} "
        f"GRAD={safe_float(row.get('gradient')):.12f} "
        f"front_heat_raw={safe_float(row.get('front_heating_raw')):.6f} "
        f"front_heat_corrected={safe_float(row.get('front_heating_corrected')):.6f} "
        f"wall_load_raw={safe_float(row.get('wall_load_raw')):.6f} "
        f"wall_load_corrected={safe_float(row.get('wall_load_corrected')):.6f} "
        f"wall_temp_raw={safe_float(row.get('wall_temp_raw')):.6f} "
        f"wall_temp_corrected={safe_float(row.get('wall_temp_corrected')):.6f} "
        f"fail_rate={safe_float(row.get('fail_rate')):.12f} "
        f"net_electric={safe_float(row.get('net_electric')):.6f} "
        f"front_heat_penalty={safe_float(row.get('front_heat_penalty'), 0.0):.6f} "
        f"heat_transport_factor={safe_float(row.get('heat_transport_factor'), 1.0):.6f} "
        f"eta_flow={safe_float(row.get('eta_flow'), 0.0):.6f} "
        f"eta_cond={safe_float(row.get('eta_cond'), 0.0):.6f} "
        f"score={safe_float(row.get('score')):.6f}"
    )


def write_json(path: str, rows: List[Dict[str, Any]], input_file: str) -> None:
    payload = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "input_file": input_file,
        "baseline_radius_cm": BASELINE_RADIUS_CM,
        "radius_values_cm": RADIUS_VALUES_CM,
        "attenuation_soft_cap": ATTENUATION_SOFT_CAP,
        "attenuation_penalty_scale": ATTENUATION_PENALTY_SCALE,
        "wall_load_screen_mw_m2": WALL_LOAD_SCREEN_MW_M2,
        "results": rows,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    fields = [
        "source_radius_cm",
        "radius_cm",
        "tbr",
        "attenuation",
        "gradient",
        "front_heating_raw",
        "front_heating_corrected",
        "wall_load_raw",
        "wall_load_corrected",
        "wall_temp_raw",
        "wall_temp_corrected",
        "fail_rate",
        "plasmoid_rate",
        "burst_rate",
        "meltdown_rate",
        "spread_credit",
        "healing_credit",
        "net_electric",
        "attenuation_penalty",
        "front_heat_penalty",
        "heat_transport_factor",
        "eta_flow",
        "eta_cond",
        "score",
        "first_wall",
        "li_current",
        "blanket_model",
        "blanket_form",
        "cap_material",
        "cap_be",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-process top reactor rows across larger radii with thermal/load correction.")
    parser.add_argument("--infile", default=None, help="Input JSON file. If omitted, first known default is used.")
    parser.add_argument("--top", type=int, default=20, help="How many ranked rows to print.")
    parser.add_argument("--keep-unscreened", action="store_true", help="Keep thermally bad rows in exports.")
    parser.add_argument("--json-out", default="radius_thermal_sweep_results.json")
    parser.add_argument("--csv-out", default="radius_thermal_sweep_results.csv")
    args = parser.parse_args()

    input_file = pick_input_file(args.infile)
    payload = load_json(input_file)
    base_rows = extract_rows(payload)

    # normalize OpenMC-specific field names into the generic names used below
    aliased_rows = []
    for r in base_rows:
        if isinstance(r, dict):
            rr = dict(r)

            if "ATTN_openmc" in rr and "attenuation" not in rr:
                rr["attenuation"] = rr["ATTN_openmc"]
            if "GRAD_openmc" in rr and "gradient" not in rr:
                rr["gradient"] = rr["GRAD_openmc"]
            if "TBR_openmc" in rr and "tbr" not in rr:
                rr["tbr"] = rr["TBR_openmc"]

            # keep uppercase aliases too, in case later code expects them
            if "attenuation" in rr and "ATTN" not in rr:
                rr["ATTN"] = rr["attenuation"]
            if "gradient" in rr and "GRAD" not in rr:
                rr["GRAD"] = rr["gradient"]
            if "tbr" in rr and "TBR" not in rr:
                rr["TBR"] = rr["tbr"]

            aliased_rows.append(rr)
        else:
            aliased_rows.append(r)
    base_rows = aliased_rows


    # 🔥 force unwrap nested result layer
    new_rows = []
    for r in base_rows:
        if isinstance(r, dict) and "result" in r and isinstance(r["result"], dict):
            new_rows.append(r["result"])
        else:
            new_rows.append(r)
    base_rows = new_rows


    print(f"[INFO] Input file: {input_file}")
    print(f"[INFO] Loaded rows: {len(base_rows)}")
    print(f"[INFO] Radius sweep: {RADIUS_VALUES_CM}")

    expanded_rows: List[Dict[str, Any]] = []

    for idx, base_row in enumerate(base_rows, start=1):
        print(f"[INFO] Expanding base row {idx}/{len(base_rows)}")
        for radius_cm in RADIUS_VALUES_CM:
            row = expand_row_for_radius(base_row, radius_cm)
            if not row_survives(row, args.keep_unscreened):
                print(
                    f"[SCREENED] radius_cm={radius_cm:.1f} "
                    f"wall_load_raw={safe_float(row.get('wall_load_raw')):.6f} "
                    f"wall_load_corrected={safe_float(row.get('wall_load_corrected')):.6f}"
                )
                continue
            expanded_rows.append(row)
            print(fmt(row))

    expanded_rows.sort(key=lambda x: safe_float(x.get("score"), -1e18), reverse=True)

    write_json(args.json_out, expanded_rows, input_file)
    write_csv(args.csv_out, expanded_rows)

    print("\n=== RANKED SUMMARY ===")
    for row in expanded_rows[:args.top]:
        print(fmt(row))

    print(f"\n[INFO] Saved JSON -> {args.json_out}")
    print(f"[INFO] Saved CSV  -> {args.csv_out}")
    print(f"[INFO] Successful rows: {len(expanded_rows)}")

    if not expanded_rows:
        print("[INFO] No rows survived screening. Re-run with --keep-unscreened to inspect thermally bad cases.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

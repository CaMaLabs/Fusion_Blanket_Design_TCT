#!/usr/bin/env python3
import argparse
import csv
import importlib
import inspect
import json
import math
import os
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

BASELINE_RADIUS_CM = 60.0
RADIUS_VALUES_CM = [60.0, 70.0, 80.0, 90.0, 100.0]

ATTENUATION_SOFT_CAP = 0.995
ATTENUATION_PENALTY_SCALE = 50.0
WALL_LOAD_SCREEN_MW_M2 = 10.0

DEFAULT_CANDIDATES = [
    {
        "blanket_thickness_cm": 60.0,
        "lithium_thickness_cm": 0.3,
        "axial_caps_cm": [80.0, 60.0],
        "split": [0.19047619047619047, 0.19047619047619047, 0.38095238095238093, 0.14285714285714285, 0.09523809523809523],
        "materials": ["Be", "Li2O", "Li2O", "W_Ti_B4C_60_30_10_wt_Be"],
        "axial_materials": ["Be", "Be"],
        "cell_names": [
            "plasma",
            "liquid_wall",
            "l1_inner_breeder",
            "l2_multiplier",
            "l3_main_breeder",
            "l4_outer_shape",
            "l5_outer_breeder",
            "top_cap_inner",
            "bot_cap_inner",
            "top_cap_outer",
            "bot_cap_outer",
        ],
    }
]

CANDIDATE_FILES = [
    "radius_adjust.json",
    "best_candidates.json",
    "top_candidates.json",
    "candidates.json",
]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def area_scale_from_radius(radius_cm: float, baseline_radius_cm: float = BASELINE_RADIUS_CM) -> float:
    if radius_cm <= 0 or baseline_radius_cm <= 0:
        return 1.0
    return (radius_cm / baseline_radius_cm) ** 2


def corrected_wall_load(wall_load_raw_mw_m2: float, radius_cm: float) -> float:
    return wall_load_raw_mw_m2 / area_scale_from_radius(radius_cm)


def attenuation_penalty(attenuation: float,
                        soft_cap: float = ATTENUATION_SOFT_CAP,
                        scale: float = ATTENUATION_PENALTY_SCALE) -> float:
    excess = max(0.0, attenuation - soft_cap)
    return excess * scale


def find_existing_candidate_file() -> Optional[str]:
    for path in CANDIDATE_FILES:
        if os.path.exists(path):
            return path
    return None


def load_candidates(path: Optional[str]) -> List[Dict[str, Any]]:
    if path is None:
        found = find_existing_candidate_file()
        if found is None:
            eprint("[INFO] No candidate JSON found. Using built-in default candidate.")
            return DEFAULT_CANDIDATES
        path = found

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            raw = data["results"]
        elif "candidates" in data and isinstance(data["candidates"], list):
            raw = data["candidates"]
        else:
            raw = [data]
    elif isinstance(data, list):
        raw = data
    else:
        raise ValueError(f"Unsupported candidate file format: {path}")

    candidates: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        candidates.append(item)

    if not candidates:
        raise ValueError(f"No usable candidates found in {path}")

    return candidates


def extract_metric(d: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in d and d[key] is not None:
            return safe_float(d[key], default)
    return default


def normalize_result(result: Dict[str, Any], radius_cm: float, cfg: Dict[str, Any]) -> Dict[str, Any]:
    attenuation = extract_metric(result, "attenuation", "ATTN", default=0.0)
    gradient = extract_metric(result, "gradient", "GRAD", default=0.0)
    tbr = extract_metric(result, "tbr", "TBR", default=0.0)

    front_heating_raw = extract_metric(result, "front_heating_raw", "front_heat_raw", default=0.0)
    front_heating_corrected = extract_metric(result, "front_heating_corrected", "front_heat_corrected", default=front_heating_raw)

    wall_load_raw = extract_metric(result, "wall_load_raw", "wall_load", default=0.0)
    wall_temp_raw = extract_metric(result, "wall_temp_raw", "wall_temp", default=0.0)
    wall_temp_corrected = extract_metric(result, "wall_temp_corrected", default=wall_temp_raw)

    fail_rate = extract_metric(result, "fail_rate", default=0.0)
    spread_credit = extract_metric(result, "spread_credit", default=0.0)
    healing_credit = extract_metric(result, "healing_credit", default=0.0)
    net_electric = extract_metric(result, "net_electric", "pnet", default=0.0)

    plasmoid_rate = extract_metric(result, "plasmoid_rate", default=0.0)
    burst_rate = extract_metric(result, "burst_rate", default=0.0)
    meltdown_rate = extract_metric(result, "meltdown_rate", default=fail_rate)

    wall_load_corr = corrected_wall_load(wall_load_raw, radius_cm)
    atten_pen = attenuation_penalty(attenuation)

    meltdown_penalty = 1000.0 * meltdown_rate
    plasmoid_penalty = 100.0 * plasmoid_rate
    burst_penalty = 50.0 * burst_rate

    score = (
        net_electric
        - meltdown_penalty
        - plasmoid_penalty
        - burst_penalty
        - atten_pen
    )

    out = dict(result)
    out["radius_cm"] = radius_cm
    out["tbr"] = tbr
    out["attenuation"] = attenuation
    out["gradient"] = gradient
    out["front_heating_raw"] = front_heating_raw
    out["front_heating_corrected"] = front_heating_corrected
    out["wall_load_raw"] = wall_load_raw
    out["wall_load_corrected"] = wall_load_corr
    out["wall_temp_raw"] = wall_temp_raw
    out["wall_temp_corrected"] = wall_temp_corrected
    out["fail_rate"] = fail_rate
    out["spread_credit"] = spread_credit
    out["healing_credit"] = healing_credit
    out["net_electric"] = net_electric
    out["plasmoid_rate"] = plasmoid_rate
    out["burst_rate"] = burst_rate
    out["meltdown_rate"] = meltdown_rate
    out["attenuation_penalty"] = atten_pen
    out["score"] = score

    out["blanket_thickness_cm"] = safe_float(cfg["blanket_thickness_cm"])
    out["lithium_thickness_cm"] = safe_float(cfg.get("lithium_thickness_cm", 0.3))
    out["axial_caps_cm"] = cfg.get("axial_caps_cm", [80.0, 60.0])
    out["split"] = cfg.get("split")
    out["materials"] = cfg.get("materials")
    out["axial_materials"] = cfg.get("axial_materials")
    out["cell_names"] = cfg.get("cell_names")

    return out


def pick_runner() -> Tuple[Any, str]:
    candidates = [
        ("openmc_recovery", "run_openmc_case"),
        ("openmc_recovery", "run_case"),
        ("run_openmc_recovery", "run_openmc_case"),
        ("run_openmc_recovery", "run_case"),
        ("reactor_sweep", "run_case"),
        ("reactor_sweep", "evaluate_candidate"),
        ("reactor_sweep", "simulate_case"),
        ("sim_reactor", "run_case"),
        ("sim_reactor", "simulate_case"),
        ("tct_openmc_top3_eval", "run_case"),
        ("tct_openmc_top3_eval", "evaluate_candidate"),
    ]

    last_err = None
    for module_name, func_name in candidates:
        try:
            mod = importlib.import_module(module_name)
            fn = getattr(mod, func_name, None)
            if callable(fn):
                return fn, f"{module_name}.{func_name}"
        except Exception as exc:
            last_err = exc

    raise RuntimeError(
        "Could not find a usable reactor runner.\n"
        "Tried common module/function names and failed.\n"
        "Expected one of:\n"
        "  openmc_recovery.run_openmc_case\n"
        "  openmc_recovery.run_case\n"
        "  run_openmc_recovery.run_openmc_case\n"
        "  run_openmc_recovery.run_case\n"
        "  reactor_sweep.run_case\n"
        "  reactor_sweep.evaluate_candidate\n"
        "  reactor_sweep.simulate_case\n"
        "  sim_reactor.run_case\n"
        "  sim_reactor.simulate_case\n"
        "  tct_openmc_top3_eval.run_case\n"
        "  tct_openmc_top3_eval.evaluate_candidate\n"
        f"Last import error: {last_err}"
    )


def call_runner(fn: Any, radius_cm: float, cfg: Dict[str, Any]) -> Dict[str, Any]:
    sig = inspect.signature(fn)
    kwargs = {}

    passthrough = dict(cfg)
    passthrough["radius_cm"] = radius_cm

    for name, param in sig.parameters.items():
        if name in passthrough:
            kwargs[name] = passthrough[name]
            continue

        lname = name.lower()

        if lname in ("radius_cm", "r_cm"):
            kwargs[name] = radius_cm
        elif lname in ("outer_radius_cm",):
            kwargs[name] = radius_cm * (185.3 / 60.0)
        elif lname in ("blanket_thickness_cm",):
            kwargs[name] = cfg["blanket_thickness_cm"]
        elif lname in ("lithium_thickness_cm",):
            kwargs[name] = cfg.get("lithium_thickness_cm", 0.3)
        elif lname in ("axial_caps_cm",):
            kwargs[name] = cfg.get("axial_caps_cm", [80.0, 60.0])
        elif lname in ("split",):
            kwargs[name] = cfg.get("split")
        elif lname in ("materials",):
            kwargs[name] = cfg.get("materials")
        elif lname in ("axial_materials",):
            kwargs[name] = cfg.get("axial_materials")
        elif lname in ("cell_names",):
            kwargs[name] = cfg.get("cell_names")
        elif param.default is not inspect._empty:
            continue

    result = fn(**kwargs)

    if result is None:
        return {}

    if isinstance(result, dict):
        return result

    if hasattr(result, "__dict__"):
        return dict(result.__dict__)

    raise TypeError(f"Runner returned unsupported type: {type(result)}")


def screen_result(result: Dict[str, Any]) -> bool:
    return safe_float(result.get("wall_load_corrected"), 1e18) <= WALL_LOAD_SCREEN_MW_M2


def format_summary_line(row: Dict[str, Any]) -> str:
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
        f"score={safe_float(row.get('score')):.6f}"
    )


def write_json(path: str, rows: List[Dict[str, Any]]) -> None:
    payload = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
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
        "spread_credit",
        "healing_credit",
        "net_electric",
        "plasmoid_rate",
        "burst_rate",
        "meltdown_rate",
        "attenuation_penalty",
        "score",
        "blanket_thickness_cm",
        "lithium_thickness_cm",
        "axial_caps_cm",
        "split",
        "materials",
        "axial_materials",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            cooked = dict(row)
            for k in ("axial_caps_cm", "split", "materials", "axial_materials"):
                if k in cooked and isinstance(cooked[k], (list, dict)):
                    cooked[k] = json.dumps(cooked[k])
            writer.writerow(cooked)


def main() -> int:
    parser = argparse.ArgumentParser(description="Radius-expanded thermal-aware OpenMC/TCT sweep driver.")
    parser.add_argument("--candidates", default=None, help="Path to candidate JSON. Defaults to radius_adjust.json / best_candidates.json if found.")
    parser.add_argument("--top", type=int, default=20, help="How many ranked rows to print.")
    parser.add_argument("--keep-unscreened", action="store_true", help="Keep thermally bad rows in exports.")
    parser.add_argument("--json-out", default="radius_thermal_sweep_results.json")
    parser.add_argument("--csv-out", default="radius_thermal_sweep_results.csv")
    args = parser.parse_args()

    try:
        candidates = load_candidates(args.candidates)
        runner, runner_name = pick_runner()
    except Exception as exc:
        eprint(str(exc))
        return 1

    print(f"[INFO] Loaded {len(candidates)} candidate(s)")
    print(f"[INFO] Using runner: {runner_name}")
    print(f"[INFO] Radius sweep: {RADIUS_VALUES_CM}")

    all_rows: List[Dict[str, Any]] = []
    failed_runs = 0

    for idx, cfg in enumerate(candidates, start=1):
        print(f"[INFO] Candidate {idx}/{len(candidates)}")
        for radius_cm in RADIUS_VALUES_CM:
            print(f"[RUN] radius_cm={radius_cm}")
            try:
                raw = call_runner(runner, radius_cm, cfg)
                if not raw:
                    print(f"[WARN] Empty result for candidate={idx} radius_cm={radius_cm}")
                    continue

                row = normalize_result(raw, radius_cm, cfg)

                if not args.keep_unscreened and not screen_result(row):
                    print(
                        f"[SCREENED] radius_cm={radius_cm:.1f} "
                        f"wall_load_raw={row['wall_load_raw']:.6f} "
                        f"wall_load_corrected={row['wall_load_corrected']:.6f}"
                    )
                    continue

                all_rows.append(row)

                print(format_summary_line(row))

            except KeyboardInterrupt:
                raise
            except Exception as exc:
                failed_runs += 1
                print(f"[ERROR] candidate={idx} radius_cm={radius_cm}: {exc}")
                traceback.print_exc()

    all_rows.sort(key=lambda x: safe_float(x.get("score"), -1e18), reverse=True)

    write_json(args.json_out, all_rows)
    write_csv(args.csv_out, all_rows)

    print("\n=== RANKED SUMMARY ===")
    for row in all_rows[:args.top]:
        print(format_summary_line(row))

    print(f"\n[INFO] Saved JSON -> {args.json_out}")
    print(f"[INFO] Saved CSV  -> {args.csv_out}")
    print(f"[INFO] Successful rows: {len(all_rows)}")
    print(f"[INFO] Failed runs: {failed_runs}")

    if not all_rows:
        print("[INFO] No rows survived screening. Re-run with --keep-unscreened to inspect thermally bad cases.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

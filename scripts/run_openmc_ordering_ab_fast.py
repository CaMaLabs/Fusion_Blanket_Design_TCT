import csv
import json
from copy import deepcopy
from pathlib import Path

from fusion_engine_v5.engine.reactor_simulation import simulate_reactor

ROOT = Path(".")
with open(ROOT / "reactor_1.json", "r", encoding="utf-8") as f:
    rx = json.load(f)

BASE = deepcopy(rx["design"])
BASE["li_current"] = 0.10
BASE["severity_scale"] = 0.6
BASE["supervisor_enabled"] = True
BASE["supervisor_level"] = "aggressive"


def f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return float(d)


def score_result(res):
    tbr = f(res.get("TBR", res.get("tbr", 0.0)))
    attn = f(res.get("attenuation", res.get("blanket_attenuation", 0.0)))
    grad = f(res.get("gradient", 0.0))
    front_heat = f(res.get("front_heating_frac", res.get("blanket_front_heating_frac", 1.0)))
    pnet = f(res.get("net_electric", res.get("pnet", 0.0)))
    fail_rate = f(res.get("fail_rate", 0.0))
    raw_wall = f(res.get("raw_wall_load", res.get("wall_load", 0.0)))

    s = 0.0
    s += 40.0 * tbr
    s += 15.0 * attn
    s += 14.0 * grad
    s -= 2.0 * front_heat
    s -= 4.0 * fail_rate
    s -= 0.5 * max(0.0, raw_wall - 5.0)
    s += 0.0002 * pnet

    if tbr < 1.0:
        s -= (1.0 - tbr) * 12.0

    return s


def make_design(case_name, mats, bt_m, azo_m):
    d = deepcopy(BASE)

    d["blanket_family"] = "Li2O_W_Be_Li2O"
    d["l1"] = mats["l1"]
    d["l2"] = mats["l2"]
    d["l3"] = mats["l3"]
    d["l4"] = mats["l4"]
    d["l5"] = mats["l5"]

    d["plasma_radius_cm"] = 50.0
    d["R"] = 0.50
    d["a"] = 0.50

    d["blanket_thickness"] = bt_m
    d["lithium_thickness"] = 0.003

    d["axial_inner_material"] = mats["l1"]
    d["axial_outer_material"] = mats["l5"]
    d["axial_inner_cap_thickness"] = 0.8
    d["axial_outer_cap_thickness"] = azo_m

    d["split"] = (0.15, 0.25, 0.35, 0.15, 0.10)

    d["liquid_wall_li6_enrich"] = 0.95
    d["l1_li6"] = 0.90 if "Li2O" not in mats["l1"] else 0.95
    d["l2_li6"] = 0.95 if "Li2O" in mats["l2"] else 0.90
    d["l3_li6"] = 0.98 if "Li2O" in mats["l3"] else 0.90
    d["l4_li6"] = 0.95 if "Li2O" in mats["l4"] else 0.90
    d["l5_li6"] = 0.90 if "Li2O" not in mats["l5"] else 0.95

    d["l1_pack"] = 1.0
    d["l2_pack"] = 1.0
    d["l3_pack"] = 1.25
    d["l4_pack"] = 1.0
    d["l5_pack"] = 1.0

    d["_case"] = case_name
    return d


CASES = {
    "be_sandwich": {
        "l1": "Be",
        "l2": "Li2O",
        "l3": "Li2O",
        "l4": "Be",
        "l5": "W_Ti_B4C_60_30_10_wt",
    },
    "be_outer_kill": {
        "l1": "Be",
        "l2": "Li2O",
        "l3": "Li2O",
        "l4": "W_Ti_B4C_60_30_10_wt",
        "l5": "Be",
    },
    "center_kill": {
        "l1": "Be",
        "l2": "Li2O",
        "l3": "W_Ti_B4C_60_30_10_wt",
        "l4": "Li2O",
        "l5": "Be",
    },
    "ti_sandwich": {
        "l1": "Be12Ti",
        "l2": "Li2O",
        "l3": "Li2O",
        "l4": "Be12Ti",
        "l5": "W_Ti_B4C_60_30_10_wt",
    },
    "pbli_front_breeder_tail": {
        "l1": "PbLi",
        "l2": "Li2O",
        "l3": "W_Ti_B4C_60_30_10_wt",
        "l4": "Li2O",
        "l5": "Be",
    },
    "pbli_front_double_breeder": {
        "l1": "PbLi",
        "l2": "Li2O",
        "l3": "Li2O",
        "l4": "W_Ti_B4C_60_30_10_wt",
        "l5": "Be",
    },
    "liquid_pbli_breeder_tail": {
        "l1": "PbLi",
        "l2": "Li2O",
        "l3": "Li2O",
        "l4": "Be",
        "l5": "W_Ti_B4C_60_30_10_wt",
    },
}

BT = [0.50, 0.75, 1.00]
AZO = [0.4, 0.6]

rows = []

for case_name, mats in CASES.items():
    print(f"\n=== CASE {case_name} ===")
    for bt in BT:
        for azo in AZO:
            d = make_design(case_name, mats, bt, azo)
            try:
                res = simulate_reactor(d, blanket_validate=True)
            except Exception as e:
                print(f"[FAIL] {case_name} bt={bt} azo={azo} err={e!r}")
                continue

            row = {
                "case": case_name,
                "bt_m": bt,
                "azo_m": azo,
                "score": score_result(res),
                "TBR": f(res.get("TBR", res.get("tbr", 0.0))),
                "ATTN": f(res.get("attenuation", res.get("blanket_attenuation", 0.0))),
                "GRAD": f(res.get("gradient", 0.0)),
                "front_heat": f(res.get("front_heating_frac", res.get("blanket_front_heating_frac", 1.0))),
                "wall": f(res.get("raw_wall_load", res.get("wall_load", 0.0))),
                "pnet": f(res.get("net_electric", res.get("pnet", 0.0))),
            }
            rows.append(row)

            print(
                f"[OK] {case_name} "
                f"TBR={row['TBR']:.6f} "
                f"ATTN={row['ATTN']:.6f} "
                f"GRAD={row['GRAD']:.6f} "
                f"score={row['score']:.4f} "
                f"bt={bt} azo={azo}"
            )

rows.sort(key=lambda x: x["score"], reverse=True)

with open("ordering_ab_fast_results.csv", "w", newline="", encoding="utf-8") as fobj:
    writer = csv.DictWriter(
        fobj,
        fieldnames=["case", "bt_m", "azo_m", "score", "TBR", "ATTN", "GRAD", "front_heat", "wall", "pnet"],
    )
    writer.writeheader()
    writer.writerows(rows)

print("\n=== RANKED RESULTS ===")
for r in rows:
    print(
        f"{r['case']:>24} "
        f"TBR={r['TBR']:.6f} "
        f"ATTN={r['ATTN']:.6f} "
        f"GRAD={r['GRAD']:.6f} "
        f"score={r['score']:.4f} "
        f"bt={r['bt_m']} azo={r['azo_m']}"
    )

print("\nWrote ordering_ab_fast_results.csv")

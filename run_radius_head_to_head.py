import json
from copy import deepcopy
from pathlib import Path

from fusion_engine_v5.engine.reactor_simulation import simulate_reactor
from fusion_engine_v5.blanket.openmc_runner import run_openmc_validation

ROOT = Path(".")
with open(ROOT / "reactor_1.json", "r", encoding="utf-8") as f:
    rx = json.load(f)

BASE = deepcopy(rx["design"])


def f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return float(d)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def build_candidate(radius_cm):
    d = deepcopy(BASE)

    d["li_current"] = 0.10
    d["severity_scale"] = 0.6
    d["supervisor_enabled"] = True
    d["supervisor_level"] = "aggressive"

    d["blanket_family"] = "Li2O_W_Be_Li2O"

    d["l1"] = "Be"
    d["l2"] = "Li2O"
    d["l3"] = "Li2O"
    d["l4"] = "W_Ti_B4C_60_30_10_wt"
    d["l5"] = "Be"

    d["plasma_radius_cm"] = radius_cm
    d["R"] = radius_cm / 100.0
    d["a"] = radius_cm / 100.0

    d["blanket_thickness"] = 1.25
    d["lithium_thickness"] = 0.003

    d["axial_inner_material"] = "Be"
    d["axial_outer_material"] = "Be"
    d["axial_inner_cap_thickness"] = 0.8
    d["axial_outer_cap_thickness"] = 0.6

    d["split"] = (0.15, 0.20, 0.40, 0.15, 0.10)

    d["liquid_wall_li6_enrich"] = 0.95
    d["l1_li6"] = 0.90
    d["l2_li6"] = 0.95
    d["l3_li6"] = 0.98
    d["l4_li6"] = 0.90
    d["l5_li6"] = 0.90

    d["l1_pack"] = 1.0
    d["l2_pack"] = 1.0
    d["l3_pack"] = 1.25
    d["l4_pack"] = 1.0
    d["l5_pack"] = 1.0
    return d


def liquid_wall_proxy(reactor_res, openmc_res, design):
    li_current = f(design.get("li_current", 0.0))
    li_thick = f(design.get("lithium_thickness", 0.0))
    front_heat = f(openmc_res.get("front_heating_frac", 0.0))
    attn = f(openmc_res.get("attenuation", openmc_res.get("ATTN", 0.0)))
    grad = f(openmc_res.get("gradient", openmc_res.get("GRAD", 0.0)))

    wall_load_raw = f(reactor_res.get("raw_wall_load", reactor_res.get("wall_load", 0.0)))
    wall_temp_raw = f(reactor_res.get("wall_temp", 0.0))
    fail_rate_raw = f(reactor_res.get("fail_rate", 0.0))
    event_severity_raw = f(reactor_res.get("event_severity", 0.0))

    thickness_factor = clamp(li_thick / 0.003, 0.5, 2.0)
    flow_factor = clamp(li_current / 0.1, 0.0, 2.0)
    hotspot_factor = clamp(0.5 + 1.5 * front_heat, 0.5, 1.2)
    shape_factor = clamp(0.5 * attn + 0.5 * grad, 0.0, 1.0)

    spread_credit = clamp(
        0.10 + 0.10 * flow_factor + 0.08 * thickness_factor + 0.07 * hotspot_factor + 0.05 * shape_factor,
        0.0, 0.35
    )
    healing_credit = clamp(
        0.08 + 0.12 * flow_factor + 0.08 * thickness_factor,
        0.0, 0.32
    )

    return {
        "spread_credit": spread_credit,
        "healing_credit": healing_credit,
        "corrected_wall_load": wall_load_raw * (1.0 - 0.55 * spread_credit),
        "corrected_wall_temp": wall_temp_raw * (1.0 - 0.75 * spread_credit),
        "corrected_front_heating_frac": front_heat * (1.0 - 0.45 * spread_credit),
        "corrected_fail_rate": fail_rate_raw * (1.0 - healing_credit),
        "corrected_event_severity": event_severity_raw * (1.0 - healing_credit),
    }


RADII = [55.0, 60.0]
rows = []

for radius_cm in RADII:
    d = build_candidate(radius_cm)
    print(f"\n=== radius_cm={radius_cm} ===")

    try:
        reactor_res = simulate_reactor(d, blanket_validate=True)
    except Exception as e:
        print("REACTOR ERROR:", e)
        continue

    plasma = {"pfus_mw": float(reactor_res.get("fusion_power", reactor_res.get("pfus_mw", 1000.0)))}
    openmc_res, openmc_err = run_openmc_validation(d, plasma)
    if openmc_res is None:
        print("OPENMC ERROR:", openmc_err)
        openmc_res = {}

    proxy = liquid_wall_proxy(reactor_res, openmc_res, d)

    row = {
        "radius_cm": radius_cm,
        "TBR_openmc": f(openmc_res.get("TBR", openmc_res.get("tbr", 0.0))),
        "ATTN_openmc": f(openmc_res.get("attenuation", openmc_res.get("ATTN", 0.0))),
        "GRAD_openmc": f(openmc_res.get("gradient", openmc_res.get("GRAD", 0.0))),
        "front_heating_raw": f(openmc_res.get("front_heating_frac", 0.0)),
        "front_heating_corrected": f(proxy.get("corrected_front_heating_frac", 0.0)),
        "wall_load_raw": f(reactor_res.get("raw_wall_load", reactor_res.get("wall_load", 0.0))),
        "wall_load_corrected": f(proxy.get("corrected_wall_load", 0.0)),
        "wall_temp_raw": f(reactor_res.get("wall_temp", 0.0)),
        "wall_temp_corrected": f(proxy.get("corrected_wall_temp", 0.0)),
        "fail_rate_raw": f(reactor_res.get("fail_rate", 0.0)),
        "fail_rate_corrected": f(proxy.get("corrected_fail_rate", 0.0)),
        "spread_credit": f(proxy.get("spread_credit", 0.0)),
        "healing_credit": f(proxy.get("healing_credit", 0.0)),
        "net_electric": f(reactor_res.get("net_electric", reactor_res.get("pnet", 0.0))),
    }
    rows.append(row)

    for k, v in row.items():
        print(f"{k}: {v}")

# simple engineering-first ranking with neutronics guardrail
ranked = sorted(
    rows,
    key=lambda r: (
        -r["TBR_openmc"],                  # keep breeding high
        -r["ATTN_openmc"],
        -r["GRAD_openmc"],
        -r["net_electric"],
        r["front_heating_corrected"],      # lower is better
        r["wall_load_corrected"],
        r["wall_temp_corrected"],
        r["fail_rate_corrected"],
    )
)

print("\n=== RANKED SUMMARY ===")
for r in ranked:
    print(
        "radius_cm=", r["radius_cm"],
        "TBR=", r["TBR_openmc"],
        "ATTN=", r["ATTN_openmc"],
        "GRAD=", r["GRAD_openmc"],
        "front_heat_raw=", r["front_heating_raw"],
        "front_heat_corr=", r["front_heating_corrected"],
        "wall_load_raw=", r["wall_load_raw"],
        "wall_load_corr=", r["wall_load_corrected"],
        "wall_temp_raw=", r["wall_temp_raw"],
        "wall_temp_corr=", r["wall_temp_corrected"],
        "fail_raw=", r["fail_rate_raw"],
        "fail_corr=", r["fail_rate_corrected"],
        "net_electric=", r["net_electric"],
    )

out = ROOT / "radius_head_to_head_result.json"
out.write_text(json.dumps({"rows": rows, "ranked": ranked}, indent=2), encoding="utf-8")
print("\nSaved radius_head_to_head_result.json")

import csv
import json
import math
from copy import deepcopy
from pathlib import Path

ROOT = Path(".")
with open(ROOT / "reactor_1.json", "r", encoding="utf-8") as f:
    rx = json.load(f)

BASE = deepcopy(rx["design"])

# Frozen 55 cm engineering reference candidate
BASE["li_current"] = 0.10
BASE["severity_scale"] = 0.6
BASE["supervisor_enabled"] = True
BASE["supervisor_level"] = "aggressive"

BASE["blanket_family"] = "Li2O_W_Be_Li2O"
BASE["l1"] = "Be"
BASE["l2"] = "Li2O"
BASE["l3"] = "Li2O"
BASE["l4"] = "W_Ti_B4C_60_30_10_wt"
BASE["l5"] = "Be"

BASE["plasma_radius_cm"] = 55.0
BASE["R"] = 0.55
BASE["a"] = 0.55

BASE["blanket_thickness"] = 1.25
BASE["lithium_thickness"] = 0.003
BASE["axial_inner_material"] = "Be"
BASE["axial_outer_material"] = "Be"
BASE["axial_inner_cap_thickness"] = 0.8
BASE["axial_outer_cap_thickness"] = 0.6
BASE["split"] = (0.15, 0.20, 0.40, 0.15, 0.10)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def shear_profile(v_tor, v_pol, edge_width=0.08, pol_weight=0.65):
    """
    Reduced edge shear proxy.
    Units are normalized/arbitrary, but consistent across the sweep.
    """
    v_edge = v_tor + pol_weight * v_pol
    shear = v_edge / max(edge_width, 1e-6)
    return shear


def edge_event_model(edge_drive, v_tor, v_pol, tct_gain):
    """
    Reduced edge-event model with explicit toroidal/poloidal velocity
    and derived edge shear.
    """
    shear = shear_profile(v_tor, v_pol)

    # Stabilization channels
    toroidal_stab = 0.18 * math.tanh(1.8 * v_tor)
    poloidal_stab = 0.12 * math.tanh(2.2 * v_pol)
    shear_stab = 0.22 * math.tanh(0.22 * shear)
    tct_stab = 0.45 * math.tanh(1.8 * tct_gain)

    total_stab = toroidal_stab + poloidal_stab + shear_stab + tct_stab
    residual_instability = edge_drive - total_stab

    # Stability margin: positive is better
    stability_margin = total_stab - edge_drive

    # Event amplitude
    event_amplitude = clamp(0.10 + 1.85 * max(0.0, residual_instability), 0.0, 3.5)

    # Event frequency:
    # moderate shear/TCT can increase small-event pacing while lowering amplitude
    pacing_term = 0.20 * tct_gain + 0.10 * math.tanh(0.18 * shear)
    event_frequency = clamp(
        0.35 + 0.85 * edge_drive - 0.10 * v_tor - 0.08 * v_pol - 0.12 * tct_gain + pacing_term,
        0.05,
        3.5,
    )

    # Heat pulse severity
    heat_pulse_severity = clamp(
        event_amplitude * (0.72 + 0.28 * event_frequency),
        0.0,
        8.0,
    )

    # Wetted fraction increases with pacing/shear, decreases with big crashes
    wetted_fraction = clamp(
        0.22 + 0.16 * math.tanh(0.14 * shear) + 0.10 * tct_gain - 0.07 * event_amplitude,
        0.05,
        0.95,
    )

    # Peak heat flux falls when wetted fraction increases, rises with severity
    peak_heat_flux = clamp(
        heat_pulse_severity / max(wetted_fraction, 1e-6),
        0.0,
        20.0,
    )

    # Divertor load proxy
    divertor_load_proxy = clamp(
        0.65 * peak_heat_flux + 0.35 * heat_pulse_severity,
        0.0,
        20.0,
    )

    # Stability window shift: how much control widened the safe operating region
    stability_window_shift = clamp(
        0.35 * tct_gain + 0.10 * math.tanh(0.18 * shear) + 0.08 * math.tanh(1.8 * v_tor),
        -1.0,
        1.0,
    )

    # Frequency-severity product
    freq_severity_product = event_frequency * heat_pulse_severity

    # Overall damage index
    damage_index = clamp(
        0.40 * heat_pulse_severity
        + 0.30 * peak_heat_flux
        + 0.15 * event_frequency
        + 0.15 * max(0.0, -stability_margin),
        0.0,
        20.0,
    )

    return {
        "edge_shear": shear,
        "residual_instability": residual_instability,
        "stability_margin": stability_margin,
        "stability_window_shift": stability_window_shift,
        "event_amplitude": event_amplitude,
        "event_frequency": event_frequency,
        "heat_pulse_severity": heat_pulse_severity,
        "wetted_fraction": wetted_fraction,
        "peak_heat_flux": peak_heat_flux,
        "divertor_load_proxy": divertor_load_proxy,
        "freq_severity_product": freq_severity_product,
        "damage_index": damage_index,
    }


EDGE_DRIVE = [0.70, 0.85, 1.00, 1.15]
V_TOR = [0.00, 0.20, 0.40, 0.60]
V_POL = [0.00, 0.10, 0.20, 0.30]
TCT_GAIN = [0.00, 0.20, 0.40, 0.60]

rows = []

print("=== EDGE VELOCITY/SHEAR SWEEP ===")
print("Frozen engineering reference:")
print(json.dumps({
    "radius_cm": BASE["plasma_radius_cm"],
    "li_current": BASE["li_current"],
    "supervisor_level": BASE["supervisor_level"],
    "severity_scale": BASE["severity_scale"],
    "blanket_thickness": BASE["blanket_thickness"],
    "axial_outer_cap_thickness": BASE["axial_outer_cap_thickness"],
    "split": BASE["split"],
}, indent=2))

for edge_drive in EDGE_DRIVE:
    for v_tor in V_TOR:
        for v_pol in V_POL:
            for tct_gain in TCT_GAIN:
                res = edge_event_model(edge_drive, v_tor, v_pol, tct_gain)
                row = {
                    "edge_drive": edge_drive,
                    "v_tor": v_tor,
                    "v_pol": v_pol,
                    "tct_gain": tct_gain,
                    **res,
                }
                rows.append(row)
                print(
                    f"[OK] edge_drive={edge_drive:.2f} v_tor={v_tor:.2f} v_pol={v_pol:.2f} "
                    f"tct_gain={tct_gain:.2f} shear={res['edge_shear']:.4f} "
                    f"margin={res['stability_margin']:.4f} amp={res['event_amplitude']:.4f} "
                    f"freq={res['event_frequency']:.4f} heat={res['heat_pulse_severity']:.4f} "
                    f"peak_q={res['peak_heat_flux']:.4f} wet={res['wetted_fraction']:.4f} "
                    f"div={res['divertor_load_proxy']:.4f} shift={res['stability_window_shift']:.4f} "
                    f"damage={res['damage_index']:.4f}"
                )

# Best = lowest damage, then best margin, then lower peak heat
rows_sorted = sorted(
    rows,
    key=lambda r: (
        r["damage_index"],
        -r["stability_margin"],
        r["peak_heat_flux"],
        r["freq_severity_product"],
    ),
)

with open("edge_velocity_shear_sweep_results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows_sorted[0].keys())
    writer.writeheader()
    writer.writerows(rows_sorted)

summary = {
    "frozen_reference": {
        "radius_cm": BASE["plasma_radius_cm"],
        "li_current": BASE["li_current"],
        "supervisor_level": BASE["supervisor_level"],
        "severity_scale": BASE["severity_scale"],
        "blanket_thickness": BASE["blanket_thickness"],
        "axial_outer_cap_thickness": BASE["axial_outer_cap_thickness"],
        "split": list(BASE["split"]),
    },
    "best_20": rows_sorted[:20],
    "worst_20": rows_sorted[-20:],
}

(ROOT / "edge_velocity_shear_sweep_summary.json").write_text(
    json.dumps(summary, indent=2),
    encoding="utf-8",
)

print("\\n=== BEST 20 ===")
for r in rows_sorted[:20]:
    print(r)

print("\\nSaved edge_velocity_shear_sweep_results.csv")
print("Saved edge_velocity_shear_sweep_summary.json")

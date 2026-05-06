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


def reduced_edge_event_model(edge_drive, spin, tct_gain):
    """
    Reduced mainstream-ish edge-event model.
    This is not first-principles nonlinear MHD.
    It is a structured reduced model meant to test whether the
    severity-reduction story survives outside the blanket scoring stack.

    edge_drive:
        pedestal / edge pressure drive proxy
    spin:
        rotation / shear stabilization proxy
    tct_gain:
        TCT-linked stabilizing control strength
    """

    # baseline instability tendency
    raw_instability = edge_drive

    # rotation/shear helps, but saturates
    spin_stabilization = 0.35 * math.tanh(1.4 * spin)

    # TCT-linked stabilization
    tct_stabilization = 0.45 * math.tanh(1.8 * tct_gain)

    # residual instability after control
    residual = raw_instability - spin_stabilization - tct_stabilization

    # amplitude: larger when residual drive is positive
    event_amplitude = clamp(0.15 + 1.8 * max(0.0, residual), 0.0, 3.0)

    # frequency: moderate residual drive can increase frequency even as amplitude falls
    event_frequency = clamp(0.4 + 0.9 * edge_drive - 0.25 * tct_gain - 0.15 * spin, 0.05, 3.0)

    # heat pulse severity depends more on amplitude than frequency
    heat_pulse_severity = clamp(event_amplitude * (0.7 + 0.3 * event_frequency), 0.0, 6.0)

    # target heat flux proxy
    target_heat_flux_proxy = clamp(0.8 * heat_pulse_severity + 0.2 * event_amplitude**2, 0.0, 10.0)

    # overall damage index
    damage_index = clamp(
        0.55 * heat_pulse_severity
        + 0.30 * target_heat_flux_proxy
        + 0.15 * event_frequency,
        0.0, 10.0
    )

    return {
        "residual_instability": residual,
        "event_amplitude": event_amplitude,
        "event_frequency": event_frequency,
        "heat_pulse_severity": heat_pulse_severity,
        "target_heat_flux_proxy": target_heat_flux_proxy,
        "damage_index": damage_index,
    }


EDGE_DRIVE = [0.70, 0.85, 1.00, 1.15]
SPIN = [0.00, 0.15, 0.30, 0.45]
TCT_GAIN = [0.00, 0.20, 0.40, 0.60]

rows = []

print("=== REDUCED EDGE EVENT SWEEP ===")
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
    for spin in SPIN:
        for tct_gain in TCT_GAIN:
            res = reduced_edge_event_model(edge_drive, spin, tct_gain)
            row = {
                "edge_drive": edge_drive,
                "spin": spin,
                "tct_gain": tct_gain,
                **res,
            }
            rows.append(row)
            print(
                f"[OK] edge_drive={edge_drive:.2f} spin={spin:.2f} tct_gain={tct_gain:.2f} "
                f"amp={res['event_amplitude']:.4f} freq={res['event_frequency']:.4f} "
                f"heat={res['heat_pulse_severity']:.4f} flux={res['target_heat_flux_proxy']:.4f} "
                f"damage={res['damage_index']:.4f}"
            )

rows.sort(key=lambda r: r["damage_index"])

with open("reduced_edge_event_sweep_results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

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
    "best_10": rows[:10],
    "worst_10": rows[-10:],
}

(ROOT / "reduced_edge_event_sweep_summary.json").write_text(
    json.dumps(summary, indent=2),
    encoding="utf-8",
)

print("\n=== BEST 10 ===")
for r in rows[:10]:
    print(r)

print("\nSaved reduced_edge_event_sweep_results.csv")
print("Saved reduced_edge_event_sweep_summary.json")

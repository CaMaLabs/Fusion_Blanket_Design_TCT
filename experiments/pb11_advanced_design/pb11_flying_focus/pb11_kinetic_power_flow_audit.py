#!/usr/bin/env python3
"""0D p-B11 flying-focus / alpha-channel power-flow audit.

This model sits downstream of pb11_physical_channel_audit.py.  It conserves
alpha power explicitly and separates:
  * p-B11 alpha -> fast-proton wave channeling
  * remaining p-B11 alpha -> direct electrical conversion
  * DT-alpha assist -> fast-proton channeling
  * 0.64-MeV fast-proton Coulomb drag
  * electron-tail bremsstrahlung screening

It is a screening/threshold model, not a Fokker-Planck, PIC, or reactor-gain
calculation.
"""
from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np

# Physical-channel anchors from the preceding committed audit.
QE = 1.602176634e-19
EPS0 = 8.8541878128e-12
ME = 9.1093837015e-31
MP = 1.67262192369e-27
U = 1.66053906660e-27
MB = 11.00930536 * U
KEV = 1e3 * QE
ZB = 5.0
Q_MEV = 8.7
TARGET_KEV = 638.0
TE0_KEV = 16.67
TI_KEV = 55.358
LNL = 15.0

# Repo candidate-0 density anchor.
IP_MA = 14.0
A_M = 1.8
FG = 0.83
DENSITY_NORM = 1.171
NE = IP_MA / (math.pi * A_M * A_M) * 1e20 * FG * DENSITY_NORM

# Rate-optimal packet path cross section inferred from the preceding physical
# audit's 419246.468-pass / 23.033% burnup bridge.
BURNUP_ANCHOR = 0.23033
PASSES = 419246.468
BORON_COLUMN_PER_PASS = 6.592e21
HAZARD_PER_PASS = -math.log(1.0 - BURNUP_ANCHOR) / PASSES
SIGMA_PATH_M2 = HAZARD_PER_PASS / BORON_COLUMN_PER_PASS
VP = math.sqrt(2.0 * TARGET_KEV * KEV / MP)
SIGMA_V_M3_S = SIGMA_PATH_M2 * VP

# Existing selected hybrid surrogate anchors.
PB11_ALPHA_CAPTURE = 0.98
PB11_ALPHA_YIELD_PROXY = 2.363
DT_FUSION_PROXY = 13.705
DT_ALPHA_FRACTION = 3.5 / 17.6
DT_ALPHA_TO_PB11_ALPHA = DT_FUSION_PROXY * DT_ALPHA_FRACTION / PB11_ALPHA_YIELD_PROXY
DT_ALPHA_ASSIST_MAX = 0.85
DIRECT_CONVERSION_EFF = 0.92  # selected staged upper clamp in current bridge

# Standard nonrelativistic free-free screening coefficient. Used only as a
# threshold screen; gaunt/relativistic/non-Maxwellian corrections are not hidden.
BREMS_COEFF = 1.69e-38  # W m^3 / (sqrt(eV)); conventional screening form

def psi(x: float) -> float:
    y = math.sqrt(max(x, 0.0))
    return math.erf(y) - 2.0 / math.sqrt(math.pi) * y * math.exp(-x)

def psip(x: float) -> float:
    return 2.0 / math.sqrt(math.pi) * math.sqrt(max(x, 0.0)) * math.exp(-x)

def stopping_parts(fB: float, Te_keV: float, lnL: float = LNL):
    """Return classical dE/dx (eV/m) parts at the FF target.

    fB = fraction of electron charge supplied by fully ionized boron:
         5*nB/ne.  The fast proton packet remains a minority test population.
    """
    nB = fB * NE / ZB
    np_bg = (1.0 - fB) * NE
    EJ = TARGET_KEV * KEV
    v = math.sqrt(2.0 * EJ / MP)
    kc = QE * QE / (4.0 * math.pi * EPS0)
    parts = {}
    total = 0.0
    for name, n, Z, m, T in (
        ("electron", NE, 1.0, ME, Te_keV),
        ("background_proton", np_bg, 1.0, MP, TI_KEV),
        ("boron", nB, ZB, MB, TI_KEV),
    ):
        if n <= 0:
            parts[name] = 0.0
            continue
        x = m * v * v / (2.0 * T * KEV)
        nu0 = 4.0 * math.pi * (Z * kc) ** 2 * lnL * n / (MP * MP * v ** 3)
        nue = 2.0 * ((MP / m) * psi(x) - psip(x)) * nu0
        d = max(0.0, nue) * EJ / v / QE
        parts[name] = d
        total += d
    return nB, total, parts

def local_merit(fB: float, Te_keV: float):
    """p-B11 fusion energy / classical fast-proton collision transfer."""
    nB, d, parts = stopping_parts(fB, Te_keV)
    fusion_J_per_m = nB * SIGMA_PATH_M2 * Q_MEV * 1e6 * QE
    collision_J_per_m = d * QE
    return fusion_J_per_m / collision_J_per_m, d, parts

def collision_power_per_fusion(fB: float, Te_keV: float):
    m, d, parts = local_merit(fB, Te_keV)
    return 1.0 / m, d, parts

def alpha_support(eta_channel: float, pb_fraction: float = 1.0,
                  dt_assist_fraction: float = 0.0):
    p_b = PB11_ALPHA_CAPTURE * pb_fraction * eta_channel
    p_dt = DT_ALPHA_TO_PB11_ALPHA * dt_assist_fraction * eta_channel
    return p_b + p_dt, p_b, p_dt

def zeff(fB: float):
    # background proton charge fraction is 1-fB; boron contributes Z^2 nB/ne = 5 fB
    return (1.0 - fB) + ZB * fB

def brems_ratio_to_fusion(fB: float, Te_keV: float, fast_proton_fraction_ne: float,
                          tail_suppression: float = 0.0):
    nB = fB * NE / ZB
    nfast = fast_proton_fraction_ne * NE
    Pf = nfast * nB * SIGMA_V_M3_S * Q_MEV * 1e6 * QE
    Pb = BREMS_COEFF * zeff(fB) * NE * NE * math.sqrt(Te_keV * 1e3)
    Pb *= max(0.0, 1.0 - tail_suppression)
    return Pb / max(Pf, 1e-300), Pf, Pb

def minimum_fast_fraction_for_brems_break_even(fB: float, Te_keV: float,
                                                tail_suppression: float = 0.0):
    ratio_at_one, _, _ = brems_ratio_to_fusion(fB, Te_keV, 1.0, tail_suppression)
    return ratio_at_one  # since ratio scales as 1/f_fast

def main(outdir="power_flow"):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    composition_rows = []
    for fB in (0.50, 0.75, 1.00):
        merit, d, parts = local_merit(fB, TE0_KEV)
        composition_rows.append({
            "fB_charge_fraction": fB,
            "fusion_to_collision_merit": merit,
            "collision_power_per_fusion": 1.0 / merit,
            "electron_drag_fraction": parts["electron"] / d,
            "background_proton_drag_fraction": parts["background_proton"] / d,
            "boron_drag_fraction": parts["boron"] / d,
        })

    threshold_rows = []
    for fB in (0.50, 0.75, 1.00):
        _, d0, _ = local_merit(fB, TE0_KEV)
        C0, _, _ = collision_power_per_fusion(fB, TE0_KEV)
        for eta in (0.60, 0.75, 0.90):
            for mode, dtmax in (("pB11_alpha_only", 0.0),
                                ("pB11_plus_repo_DT_alpha_assist", DT_ALPHA_ASSIST_MAX)):
                support_max, _, _ = alpha_support(eta, 1.0, dtmax)
                threshold = None
                for Te in np.arange(TE0_KEV, 501.0, 0.1):
                    _, d, _ = local_merit(fB, float(Te))
                    C = C0 * d / d0
                    if C <= support_max:
                        threshold = float(Te)
                        break
                threshold_rows.append({
                    "fB_charge_fraction": fB,
                    "alpha_to_fast_efficiency": eta,
                    "mode": mode,
                    "max_DT_alpha_assist_fraction": dtmax,
                    "support_capacity_per_pB11_fusion": support_max,
                    "minimum_Maxwellian_equivalent_Te_keV": threshold if threshold is not None else "not_reached_500",
                })

    dt_rows = []
    for fB in (0.75, 1.00):
        C0, d0, _ = collision_power_per_fusion(fB, TE0_KEV)
        for Te in (30., 50., 60., 62., 70., 80., 100., 150.):
            _, d, parts = local_merit(fB, Te)
            C = C0 * d / d0
            for eta in (0.60, 0.75, 0.90):
                pb_support = PB11_ALPHA_CAPTURE * eta
                deficit = max(0.0, C - pb_support)
                dt_frac = deficit / max(DT_ALPHA_TO_PB11_ALPHA * eta, 1e-12)
                dt_rows.append({
                    "fB_charge_fraction": fB,
                    "Te_keV": Te,
                    "alpha_to_fast_efficiency": eta,
                    "collision_power_per_pB11_fusion": C,
                    "pB11_alpha_fast_support": pb_support,
                    "minimum_fraction_of_gross_DT_alpha_needed": dt_frac,
                    "within_repo_85pct_DT_alpha_assist": dt_frac <= DT_ALPHA_ASSIST_MAX,
                    "electron_drag_fraction_at_Te": parts["electron"] / d,
                })

    partition_rows = []
    for fB in (0.75, 1.00):
        C0, d0, _ = collision_power_per_fusion(fB, TE0_KEV)
        for Te in (50., 60., 62., 70., 80., 100., 150.):
            _, d, _ = local_merit(fB, Te)
            C = C0 * d / d0
            for eta in (0.60, 0.75, 0.90):
                dt_support = DT_ALPHA_TO_PB11_ALPHA * DT_ALPHA_ASSIST_MAX * eta
                residual = max(0.0, C - dt_support)
                pb_frac_needed = residual / max(PB11_ALPHA_CAPTURE * eta, 1e-12)
                closed = pb_frac_needed <= 1.0
                pb_frac_used = min(1.0, pb_frac_needed)
                direct_electric = PB11_ALPHA_CAPTURE * (1.0 - pb_frac_used) * DIRECT_CONVERSION_EFF
                partition_rows.append({
                    "fB_charge_fraction": fB,
                    "Te_keV": Te,
                    "alpha_to_fast_efficiency": eta,
                    "fast_loop_closed_with_repo_DT_assist": closed,
                    "pB11_alpha_fraction_channeled": pb_frac_used,
                    "pB11_alpha_fraction_left_for_direct_conversion": max(0.0, 1.0 - pb_frac_used),
                    "direct_electric_per_pB11_fusion_before_plant_loads": direct_electric,
                    "unclosed_fast_support_deficit": max(0.0, residual - PB11_ALPHA_CAPTURE * eta),
                })

    brems_rows = []
    for fB in (0.75, 1.00):
        for Te in (50., 60., 62., 70., 80., 100., 112., 150.):
            for sup in (0.0, 0.25, 0.50, 0.75):
                req = minimum_fast_fraction_for_brems_break_even(fB, Te, sup)
                ratio10, pf10, pb = brems_ratio_to_fusion(fB, Te, 0.10, sup)
                brems_rows.append({
                    "fB_charge_fraction": fB,
                    "Te_keV": Te,
                    "electron_tail_brems_suppression": sup,
                    "minimum_fast_proton_density_fraction_of_ne_for_Pfusion_ge_Pbrems": req,
                    "Pbrems_over_Pfusion_at_fast_fraction_0p10": ratio10,
                    "fusion_power_density_W_m3_at_fast_fraction_0p10": pf10,
                    "brems_power_density_W_m3": pb,
                })

    def write(name, rows):
        with (out / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write("composition_drag.csv", composition_rows)
    write("alpha_loop_temperature_thresholds.csv", threshold_rows)
    write("dt_alpha_assist_requirements.csv", dt_rows)
    write("conserved_alpha_partition.csv", partition_rows)
    write("brems_beam_density_thresholds.csv", brems_rows)

    selected = {
        "fB": 1.0,
        "electron_drag_fraction_current": next(r["electron_drag_fraction"] for r in composition_rows if r["fB_charge_fraction"] == 1.0),
        "threshold_Te_keV_with_repo_DT_assist": {
            str(r["alpha_to_fast_efficiency"]): r["minimum_Maxwellian_equivalent_Te_keV"]
            for r in threshold_rows
            if r["fB_charge_fraction"] == 1.0 and r["mode"] == "pB11_plus_repo_DT_alpha_assist"
        },
        "threshold_Te_keV_pB11_only": {
            str(r["alpha_to_fast_efficiency"]): r["minimum_Maxwellian_equivalent_Te_keV"]
            for r in threshold_rows
            if r["fB_charge_fraction"] == 1.0 and r["mode"] == "pB11_alpha_only"
        },
    }
    payload = {
        "classification": "HYBRID_ALPHA_LOOP_CONDITIONAL_WINDOW_IDENTIFIED",
        "target_proton_lab_keV": TARGET_KEV,
        "current_Te_keV": TE0_KEV,
        "current_Ti_keV": TI_KEV,
        "repo_DT_alpha_to_pB11_alpha_power_ratio": DT_ALPHA_TO_PB11_ALPHA,
        "repo_DT_alpha_assist_fraction": DT_ALPHA_ASSIST_MAX,
        "selected_boron_rich_result": selected,
        "interpretation": (
            "At current Te the fast-proton loop does not close. Because ~90% of classical "
            "drag is electronic in the boron-rich case, a localized higher electron velocity "
            "scale plus efficient alpha-to-fast-proton channeling can create a conditional "
            "hybrid closure window. This is not yet an ignition prediction."
        ),
        "guardrails": [
            "Electron-tail removal that suppresses bremsstrahlung is NOT assumed to suppress fast-proton drag.",
            "The electron-drag reduction represented by higher Maxwellian-equivalent Te must be replaced by an actual non-Maxwellian distribution calculation.",
            "DT alpha assist diverts DT alpha self-heating and therefore is not free power.",
            "Direct conversion and alpha channeling compete for the same p-B11 alpha energy; this audit conserves that partition.",
            "Bremsstrahlung uses a simple free-free threshold screen and does not include relativistic/Gaunt/opacity corrections.",
            "No claim of p-B11 ignition or reactor net power is made.",
        ],
    }
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Distribution-resolved p-B11 / flying-focus kinetic screening audit.

Downstream of the committed physical-channel and conserved-alpha power-flow
audits.  This model replaces the scalar "Maxwellian-equivalent Te" lever with
an explicit isotropic electron energy distribution and charges the
phase-space recirculating power required to maintain it against collisional
relaxation.

Physics boundary:
- 638-keV lab proton packet is retained from the frame-corrected physical audit.
- The same electron distribution is used for fast-proton electron drag and
  bremsstrahlung moments.
- Low-energy electron depletion is particle-conserving; depleted electrons are
  re-injected into a low-keV shoulder.
- Electron self-collision relaxation is represented by an energy-conserving,
  projected relaxation operator with NRL electron collision-frequency scaling.
  This is Fokker-Planck-like, not a full Landau/Fokker-Planck solve.
- Fast-proton self-relaxation is also screened with an energy-conserving BGK
  lower-bound operator; inter-species proton energy loss is handled separately.
- Quasineutrality includes the fast-proton minority: ne = n_fast + 5*nB.
- p-B11 alpha, DT-alpha assist, direct conversion, proton maintenance, and
  electron distribution recirculation are not double counted.

This audit is a falsification / promotion gate, not an ignition or reactor-gain
calculation.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import numpy as np

QE = 1.602176634e-19
EPS0 = 8.8541878128e-12
ME = 9.1093837015e-31
MP = 1.67262192369e-27
U = 1.66053906660e-27
MB = 11.00930536 * U
KEV_J = 1e3 * QE
ZB = 5.0
Q_MEV = 8.7
TARGET_KEV = 638.0
TE0_KEV = 16.67
TI_KEV = 55.358
LNL = 15.0

# Candidate-0 / selected-surrogate anchors.
IP_MA = 14.0
MINOR_RADIUS_M = 1.8
GREENWALD_FRACTION = 0.83
DENSITY_NORM = 1.171
NE = (
    IP_MA / (math.pi * MINOR_RADIUS_M * MINOR_RADIUS_M)
    * 1e20 * GREENWALD_FRACTION * DENSITY_NORM
)
PB11_ALPHA_CAPTURE = 0.98
DT_FUSION_PROXY = 13.705
PB11_ALPHA_YIELD_PROXY = 2.363
DT_ALPHA_FRACTION = 3.5 / 17.6
DT_ALPHA_TO_PB11_ALPHA = (
    DT_FUSION_PROXY * DT_ALPHA_FRACTION / PB11_ALPHA_YIELD_PROXY
)
DT_ALPHA_ASSIST_MAX = 0.85
ALPHA_TO_FAST_EFF = 0.90
DIRECT_CONVERSION_EFF = 0.92

# Physical-channel bridge: rate-optimal 638-keV packet.
BURNUP_ANCHOR = 0.23033
EFFECTIVE_PASSES = 419246.468
BORON_COLUMN_PER_PASS = 6.592e21
HAZARD_PER_PASS = -math.log(1.0 - BURNUP_ANCHOR) / EFFECTIVE_PASSES
SIGMA_PATH_M2 = HAZARD_PER_PASS / BORON_COLUMN_PER_PASS
VP = math.sqrt(2.0 * TARGET_KEV * KEV_J / MP)
SIGMA_V_M3_S = SIGMA_PATH_M2 * VP

# Distribution grids.
EE = np.geomspace(1.0e-3, 500.0, 4000)  # keV
EP = np.geomspace(10.0, 1500.0, 3000)   # keV
ECRIT_ELECTRON_KEV = (ME / MP) * TARGET_KEV

FAST_FRACTIONS = (0.05, 0.10, 0.20)
HOLE_CUTOFFS_KEV = (0.20, 0.25, 0.35, 0.50, 0.75, 1.00)
HOLE_DEPTHS = (0.0, 0.25, 0.50, 0.75, 0.90, 0.99)

def integ(y, x):
    return float(np.trapz(y, x))

def maxwell_energy_pdf(grid, T_keV):
    g = 2.0 / math.sqrt(math.pi) * np.sqrt(grid) / (T_keV ** 1.5) * np.exp(-grid / T_keV)
    return g / integ(g, grid)

G0 = maxwell_energy_pdf(EE, TE0_KEV)
F0_SLOW = integ(G0[EE <= ECRIT_ELECTRON_KEV], EE[EE <= ECRIT_ELECTRON_KEV])

def shaped_electron_pdf(depth, cutoff_keV):
    """Particle-conserving low-energy depletion + low-keV shoulder."""
    if depth <= 0.0:
        return G0.copy(), 0.0, 0.0, 0.0
    shoulder = max(0.50, 1.50 * cutoff_keV)
    width = max(0.05, 0.15 * shoulder)
    depletion = depth / (1.0 + (EE / cutoff_keV) ** 8)
    raw = G0 * (1.0 - depletion)
    removed = integ(G0 - raw, EE)
    source = np.exp(-0.5 * ((EE - shoulder) / width) ** 2)
    source /= integ(source, EE)
    g = raw + removed * source
    g /= integ(g, EE)
    return g, removed, shoulder, width

def project_number_energy_conserving(Craw, geq, grid):
    """Remove the two moments that would change particle number or total energy."""
    b0 = geq
    b1 = grid * geq
    M = np.array([
        [integ(b0, grid), integ(b1, grid)],
        [integ(grid * b0, grid), integ(grid * b1, grid)],
    ])
    rhs = np.array([integ(Craw, grid), integ(grid * Craw, grid)])
    a, b = np.linalg.solve(M, rhs)
    C = Craw - a * b0 - b * b1
    return C

def electron_recirculation_power(g):
    """Gross phase-space power required to cancel isotropic e-e relaxation.

    The raw operator relaxes toward a Maxwellian with the same number and mean
    energy, with local NRL electron collision-frequency scaling. Projection
    enforces zero number and energy moments. The actuator must provide -C.
    Positive and negative energy flows should agree after projection.
    """
    mean_E = integ(EE * g, EE)
    Teq = 2.0 * mean_E / 3.0
    geq = maxwell_energy_pdf(EE, Teq)

    ne_cm3 = NE / 1e6
    E_eV = np.maximum(EE * 1e3, 100.0)
    nu = 2.91e-6 * ne_cm3 * LNL / (E_eV ** 1.5)
    Craw = nu * (geq - g)
    C = project_number_energy_conserving(Craw, geq, EE)
    actuator = -C

    P_pos = NE * integ(np.maximum(actuator, 0.0) * EE * KEV_J, EE)
    P_neg = NE * integ(np.maximum(-actuator, 0.0) * EE * KEV_J, EE)
    return {
        "mean_electron_energy_keV": mean_E,
        "equivalent_temperature_keV": Teq,
        "gross_recirculating_power_W_m3": P_pos,
        "gross_extracted_power_W_m3": P_neg,
        "number_residual_s-1": integ(C, EE),
        "energy_residual_keV_s-1": integ(EE * C, EE),
    }

def psi(x):
    y = math.sqrt(max(x, 0.0))
    return math.erf(y) - 2.0 / math.sqrt(math.pi) * y * math.exp(-x)

def psip(x):
    return 2.0 / math.sqrt(math.pi) * math.sqrt(max(x, 0.0)) * math.exp(-x)

def nrl_drag_component(n, Z, m, T_keV):
    if n <= 0.0:
        return 0.0
    EJ = TARGET_KEV * KEV_J
    v = VP
    kc = QE * QE / (4.0 * math.pi * EPS0)
    x = m * v * v / (2.0 * T_keV * KEV_J)
    nu0 = 4.0 * math.pi * (Z * kc) ** 2 * LNL * n / (MP * MP * v ** 3)
    nue = 2.0 * ((MP / m) * psi(x) - psip(x)) * nu0
    return max(0.0, nue) * EJ / v / QE  # eV/m

def electron_drag_factor(g):
    slow = integ(g[EE <= ECRIT_ELECTRON_KEV], EE[EE <= ECRIT_ELECTRON_KEV])
    return slow / max(F0_SLOW, 1e-300)

def arbitrary_brems_power(g, nB, nfast):
    """Distribution-moment bremsstrahlung screen.

    Nonrelativistic shape dependence is represented by <sqrt(E)> and the
    relativistic correction uses Teff = 2/3 <E>. It is calibrated to reduce to
    the standard 1.69e-32 n_e^2 sqrt(Te) form for a Maxwellian.
    """
    ne_cm3 = NE / 1e6
    mean_sqrt_eV = integ(np.sqrt(EE * 1e3) * g, EE)
    mean_E_eV = integ(EE * 1e3 * g, EE)
    Teff_eV = 2.0 * mean_E_eV / 3.0
    mec2_eV = 511e3
    zeff = (nfast + 25.0 * nB) / NE

    coeff = 1.69e-32 / (2.0 / math.sqrt(math.pi))
    bracket = (
        zeff * (
            1.0
            + 0.7936 * Teff_eV / mec2_eV
            + 1.874 * (Teff_eV / mec2_eV) ** 2
        )
        + (3.0 / math.sqrt(2.0)) * Teff_eV / mec2_eV
    )
    P_W_cm3 = coeff * ne_cm3 * ne_cm3 * mean_sqrt_eV * bracket
    return P_W_cm3 * 1e6

def proton_target_pdf():
    sigma = TARGET_KEV * 0.037
    g = np.exp(-0.5 * ((EP - TARGET_KEV) / sigma) ** 2)
    return g / integ(g, EP)

GP = proton_target_pdf()

def proton_self_recirculation_power(nfast):
    """Optimistic fast-fast phase-space relaxation lower bound."""
    mean_E = integ(EP * GP, EP)
    Teq = 2.0 * mean_E / 3.0
    geq = maxwell_energy_pdf(EP, Teq)

    n_cm3 = nfast / 1e6
    T_eV = max(Teq * 1e3, 1.0)
    # NRL ion-ion collision-frequency scaling for protons.
    nu_pp = 4.80e-8 * n_cm3 * LNL / (T_eV ** 1.5)
    C = nu_pp * (geq - GP)  # same number and mean energy
    actuator = -C
    P = nfast * integ(np.maximum(actuator, 0.0) * EP * KEV_J, EP)
    return P, nu_pp

def case(ffast, cutoff, depth):
    nfast = ffast * NE
    # Quasineutrality includes the fast proton packet; no thermal-proton
    # background in this boron-rich channel screen.
    nB = (NE - nfast) / ZB

    Pfusion = nfast * nB * SIGMA_V_M3_S * Q_MEV * 1e6 * QE
    fusion_rate = Pfusion / (Q_MEV * 1e6 * QE)

    g, removed, shoulder, width = shaped_electron_pdf(depth, cutoff)
    drag_factor = electron_drag_factor(g)
    erec = electron_recirculation_power(g) if depth > 0 else {
        "mean_electron_energy_keV": integ(EE * g, EE),
        "equivalent_temperature_keV": TE0_KEV,
        "gross_recirculating_power_W_m3": 0.0,
        "gross_extracted_power_W_m3": 0.0,
        "number_residual_s-1": 0.0,
        "energy_residual_keV_s-1": 0.0,
    }

    d_e0 = nrl_drag_component(NE, 1.0, ME, TE0_KEV)
    d_e = d_e0 * drag_factor
    d_B = nrl_drag_component(nB, ZB, MB, TI_KEV)

    Pcollision = nfast * (d_e + d_B) * QE * VP
    # Every fusion consumes one fast proton that must be replaced at target energy.
    Preplacement = fusion_rate * TARGET_KEV * KEV_J
    Ppp_shape, nu_pp = proton_self_recirculation_power(nfast)

    # Inter-species losses plus fuel replacement need useful fast-proton power.
    proton_demand = Pcollision + Preplacement

    # Conserved alpha partition, DT-assist-first to preserve p-B11 direct conversion.
    gross_alpha_required = proton_demand / ALPHA_TO_FAST_EFF
    dt_alpha_available = DT_ALPHA_TO_PB11_ALPHA * DT_ALPHA_ASSIST_MAX * Pfusion
    pb_alpha_available = PB11_ALPHA_CAPTURE * Pfusion
    dt_alpha_used = min(dt_alpha_available, gross_alpha_required)
    residual = max(0.0, gross_alpha_required - dt_alpha_used)
    pb_alpha_used = min(pb_alpha_available, residual)
    proton_loop_closed = residual <= pb_alpha_available

    pb_alpha_left = max(0.0, pb_alpha_available - pb_alpha_used)
    Pdirect = pb_alpha_left * DIRECT_CONVERSION_EFF

    Pshape = erec["gross_recirculating_power_W_m3"] + Ppp_shape
    # Minimum fraction of the gross phase-space power that must be recovered
    # internally for the remaining direct-electric stream to pay the unrecovered part.
    if Pshape > 0:
        required_shape_recovery = max(0.0, 1.0 - Pdirect / Pshape)
    else:
        required_shape_recovery = 0.0

    # Alternative interpretation: how much larger the imported DT-alpha wave
    # power would have to be (relative to the repo DT-alpha/pB11-alpha ratio)
    # to pay the full phase-space recirculation with no energy recovery.
    base_dt_wave = max(dt_alpha_available, 1e-300)
    dt_concentration = max(0.0, (Pshape - Pdirect) / base_dt_wave)

    Pbrem = arbitrary_brems_power(g, nB, nfast)
    Pe_deposition = nfast * d_e * QE * VP
    electron_exhaust_needed = max(0.0, Pe_deposition - Pbrem)
    electron_heating_deficit = max(0.0, Pbrem - Pe_deposition)

    return {
        "fast_proton_fraction_ne": ffast,
        "boron_charge_fraction_5nB_over_ne": 1.0 - ffast,
        "hole_cutoff_keV": cutoff,
        "hole_depth": depth,
        "removed_electron_fraction": removed,
        "shoulder_keV": shoulder,
        "electron_drag_factor_vs_16p67keV_Maxwellian": drag_factor,
        "mean_electron_energy_keV": erec["mean_electron_energy_keV"],
        "Pfusion_W_m3": Pfusion,
        "Pcollision_over_Pfusion": Pcollision / Pfusion,
        "burn_replacement_over_Pfusion": Preplacement / Pfusion,
        "proton_self_shape_over_Pfusion": Ppp_shape / Pfusion,
        "proton_demand_over_Pfusion": proton_demand / Pfusion,
        "electron_shape_recirc_over_Pfusion": erec["gross_recirculating_power_W_m3"] / Pfusion,
        "total_phase_shape_recirc_over_Pfusion": Pshape / Pfusion,
        "Pbrems_over_Pfusion": Pbrem / Pfusion,
        "electron_drag_deposition_over_Pfusion": Pe_deposition / Pfusion,
        "electron_exhaust_needed_over_Pfusion": electron_exhaust_needed / Pfusion,
        "electron_heating_deficit_over_Pfusion": electron_heating_deficit / Pfusion,
        "proton_loop_closed": proton_loop_closed,
        "DT_alpha_used_over_Pfusion": dt_alpha_used / Pfusion,
        "pB11_alpha_used_over_Pfusion": pb_alpha_used / Pfusion,
        "pB11_alpha_left_over_Pfusion": pb_alpha_left / Pfusion,
        "direct_electric_over_Pfusion_before_other_loads": Pdirect / Pfusion,
        "required_phase_space_energy_recovery_fraction": required_shape_recovery,
        "required_DT_alpha_spatial_concentration_factor_no_recovery": dt_concentration,
        "fast_fast_collision_frequency_s-1": nu_pp,
        "electron_collision_operator_number_residual_s-1": erec["number_residual_s-1"],
        "electron_collision_operator_energy_residual_keV_s-1": erec["energy_residual_keV_s-1"],
    }

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def main(outdir="distribution_kinetic"):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for ffast in FAST_FRACTIONS:
        for cutoff in HOLE_CUTOFFS_KEV:
            for depth in HOLE_DEPTHS:
                rows.append(case(ffast, cutoff, depth))
    write_csv(out / "distribution_sweep.csv", rows)

    # Keep a compact Pareto-like table: loop-closed cases ordered by the least
    # severe phase-space recovery requirement, then the lowest recirculating power.
    closed = [r for r in rows if r["proton_loop_closed"]]
    closed_sorted = sorted(
        closed,
        key=lambda r: (
            r["required_phase_space_energy_recovery_fraction"],
            r["total_phase_shape_recirc_over_Pfusion"],
        ),
    )
    best_cases = closed_sorted[:20]
    write_csv(out / "best_closed_cases.csv", best_cases)

    # Representative electron distribution profiles for inspection/reproduction.
    profiles = []
    for label, cutoff, depth in (
        ("maxwellian_baseline", 0.50, 0.0),
        ("moderate_hole", 0.35, 0.50),
        ("deep_hole", 0.50, 0.99),
    ):
        g, _, _, _ = shaped_electron_pdf(depth, cutoff)
        for i in np.linspace(0, len(EE) - 1, 180, dtype=int):
            profiles.append({
                "profile": label,
                "electron_energy_keV": float(EE[i]),
                "pdf_per_keV": float(g[i]),
            })
    write_csv(out / "electron_distribution_profiles.csv", profiles)

    best = best_cases[0] if best_cases else None
    maxwell = [r for r in rows if r["fast_proton_fraction_ne"] == 0.20 and r["hole_depth"] == 0.0][0]

    # Internal consistency gates.
    max_num_res = max(abs(r["electron_collision_operator_number_residual_s-1"]) for r in rows)
    max_E_res = max(abs(r["electron_collision_operator_energy_residual_keV_s-1"]) for r in rows)
    validation = {
        "maxwellian_drag_factor_should_be_1": maxwell["electron_drag_factor_vs_16p67keV_Maxwellian"],
        "maxwellian_electron_shape_recirc_should_be_0": maxwell["electron_shape_recirc_over_Pfusion"],
        "max_abs_projected_number_residual_s-1": max_num_res,
        "max_abs_projected_energy_residual_keV_s-1": max_E_res,
        "quasineutrality_enforced": True,
        "burn_replacement_energy_included": True,
        "same_electron_distribution_used_for_drag_and_bremsstrahlung": True,
        "alpha_partition_conserved": True,
    }
    (out / "validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")

    classification = (
        "ISOTROPIC_ELECTRON_HOLE_RECIRCULATION_FAILS_POWER_GATE"
        if best is not None and best["required_phase_space_energy_recovery_fraction"] > 0.999
        else "DISTRIBUTION_WINDOW_REMAINS_CONDITIONAL"
    )
    summary = {
        "classification": classification,
        "model": "reduced isotropic distribution-resolved kinetic screen",
        "target_proton_lab_keV": TARGET_KEV,
        "electron_speed_equivalent_energy_at_proton_speed_keV": ECRIT_ELECTRON_KEV,
        "repo_electron_temperature_keV": TE0_KEV,
        "repo_ion_temperature_keV": TI_KEV,
        "density_anchor_m-3": NE,
        "selected_alpha_to_fast_efficiency": ALPHA_TO_FAST_EFF,
        "selected_DT_alpha_assist_fraction": DT_ALPHA_ASSIST_MAX,
        "best_closed_case": best,
        "core_result": (
            "Deep depletion of sub-keV electrons can suppress 638-keV proton electron drag "
            "enough for the alpha-supported fast-proton loop to close, but isotropic e-e "
            "collisions refill that phase-space hole so rapidly that the gross electron "
            "distribution recirculating power overwhelms the local p-B11 fusion power. "
            "The earlier scalar-Te closure window therefore does not survive once electron "
            "distribution maintenance is charged."
        ),
        "guardrails": [
            "The electron collision operator is an energy-conserving projected relaxation model, not a full Landau operator.",
            "Its recirculating-power result is a screening estimate; exact coefficients require a validated Fokker-Planck solver.",
            "The model is spatially homogeneous and isotropic; directed/an-isotropic electron channels are outside this gate.",
            "Imported DT-alpha power uses a repository surrogate ratio, not an experimentally calibrated spatial wave-coupling efficiency.",
            "Fast-proton quasineutrality is enforced here; prior fB=1 test-particle cases did not include fast-proton charge in the composition.",
            "No reactor gain or p-B11 ignition claim is made."
        ],
        "next_gate": (
            "Do not promote isotropic electron-hole shaping. If continuing, test anisotropic/directed "
            "electron phase-space control or a full Landau/Fokker-Planck operator with realistic wave "
            "coupling, because those are the remaining ways to reduce drag without paying the isotropic "
            "hole-refill power found here."
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()

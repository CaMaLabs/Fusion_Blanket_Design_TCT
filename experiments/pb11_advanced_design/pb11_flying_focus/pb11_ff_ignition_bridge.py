#!/usr/bin/env python3
"""p-B11 flying-focus ignition bridge for the advanced TCT architecture.

This audit is deliberately separate from the reactor surrogate. It asks whether
flying-focus (FF) rephasing can improve the nonthermal p-11B reaction rate and
whether the incremental rephasing energy can plausibly fit inside the extra
fusion-energy budget.

Important boundaries:
- be_outer_kill / be_outer_killer OpenMC results are credited as neutron/photon
  blanket and wall-load evidence only; OpenMC does not transport protons.
- Liquid-lithium/current/TCT results remain wall/confinement/control proxies and
  are not used as a multiplier on proton Coulomb stopping.
- The p-11B cross-section uses the 2026 Wang et al. analytic parameterization.
- The conversion from relative sigma-v exposure to burnup is a screening bridge,
  not a validated burn solver.
"""
from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np

SEED = 6750411
Q_MEV = 8.7
BASE_BURNUP = 0.23033  # selected p-B11 surrogate handoff
CYCLES = 32
N = 160_000
LOSSES_KEV = (1., 2., 5., 10., 20., 35., 50.)
PHASE_RECOVERY = (0.0, 0.5, 0.8, 1.0)
COLLISION_BURDEN = (1.0, 2.0, 3.0)
USABLE_FUSION = (0.25, 0.50, 0.75, 0.85, 1.00)

# Wang et al. 2026 arXiv:2601.00241, Table 1 / Eqs. 1-5.
EG_MEV = 22.589
C0, C1, C2 = 197.0, 0.240, 2.31e-4
AL, EL_KEV, DEL_KEV = 1.82e4, 148.0, 2.35
D0, D1, D2, D5 = 330.2, 102.436, -58.481, 0.0933
B = 0.209689
A = np.array([2.0235e6, 4.0102e6, 1.3220e6, 4.9451e6, 4.3430e5])
ER = np.array([0.6222, 1.3884, 2.4924, 3.5286, 4.7036])
DR = np.array([0.0996, 0.4499, 0.2386, 0.3985, 0.1525])

ARCHITECTURE = {
    "topology": "be_outer_kill / be_outer_killer",
    "li_current": 0.1,
    "openmc_55cm_attenuation": 0.99971,
    "openmc_55cm_tbr": 2.2155,
    "wall_load_raw": 619.97,
    "wall_load_liquid_wall_corrected": 507.63,
    "wall_temp_raw": 22141.89,
    "wall_temp_liquid_wall_corrected": 16329.64,
    "front_heat_raw": 0.2226,
    "front_heat_liquid_wall_corrected": 0.1857,
    "fair_mast_best_proxy_loss_reduction": 0.515,
    "notes": [
        "OpenMC attenuation is neutron/photon blanket evidence, not proton stopping.",
        "Liquid-wall correction is an explicit engineering proxy, not OpenMC proton transport.",
        "FAIR-MAST loss reduction is a reduced-order TCT control proxy, not an experimental actuator efficiency.",
    ],
}


def sigma_barn(E_keV: np.ndarray) -> np.ndarray:
    E = np.asarray(E_keV, dtype=float) / 1000.0
    S = np.zeros_like(E)
    m1 = E <= 0.4
    if np.any(m1):
        ek = E[m1] * 1000.0
        S[m1] = C0 + C1*ek + C2*ek**2 + AL / ((ek-EL_KEV)**2 + DEL_KEV**2)
    m2 = (E > 0.4) & (E <= 0.7)
    if np.any(m2):
        x = (E[m2] - 0.4) / 0.1
        S[m2] = D0 + D1*x + D2*x**2 + D5*x**5
    m3 = E > 0.7
    if np.any(m3):
        em = E[m3]
        terms = np.zeros_like(em)
        for a, er, dr in zip(A, ER, DR):
            dx_keV = (em-er)*1000.0
            d_keV = dr*1000.0
            terms += a / (dx_keV**2 + d_keV**2)
        S[m3] = B + terms
    out = np.zeros_like(E)
    good = E > 1e-9
    out[good] = (S[good] / E[good]) * np.exp(-np.sqrt(EG_MEV/E[good]))
    return np.clip(out, 0.0, None)


def sigmav_proxy(E_keV: np.ndarray) -> np.ndarray:
    return sigma_barn(E_keV) * np.sqrt(np.clip(E_keV, 0.0, None))


def reset_packet(rng, E, mask, target=600., spread_pct=3.7, jitter_keV=10.):
    if not np.any(mask):
        return 0., 0.
    shot = target + (rng.normal(0., jitter_keV) if jitter_keV else 0.)
    sigma = abs(shot)*spread_pct/100.
    before = E[mask].copy()
    after = np.clip(rng.normal(shot, sigma, int(mask.sum())), 1., None)
    delta = after-before
    up = float(np.maximum(delta,0.).sum())
    down = float(np.maximum(-delta,0.).sum())
    E[mask] = after
    return up, down


def run_case(loss_keV, ff=False, seed=0):
    rng = np.random.default_rng(SEED+seed)
    spread = 3.7 if ff else 8.0
    E = np.clip(rng.normal(600., 600.*spread/100., N), 1., None)
    exposure = 0.
    gross_up = 0.
    gross_down = 0.
    window = []
    for _ in range(CYCLES):
        vals = sigmav_proxy(E)
        exposure += float(vals.mean())
        window.append(float(np.mean((E>=500.)&(E<=700.))))
        strag = max(0.2, 0.2*loss_keV)
        E = np.clip(E - np.maximum(rng.normal(loss_keV, strag, N),0.), 1., None)
        if ff:
            trapped = rng.random(N) < 0.85
            up, down = reset_packet(rng, E, trapped)
            gross_up += up
            gross_down += down
    return {
        "exposure": exposure,
        "mean_window_fraction": float(np.mean(window)),
        "gross_up_keV_per_proton": gross_up/N,
        "gross_down_keV_per_proton": gross_down/N,
        "final_mean_keV": float(E.mean()),
    }


def burnup_from_exposure_multiplier(mult):
    lam0 = -math.log(max(1e-12, 1.0-BASE_BURNUP))
    return 1.0-math.exp(-lam0*mult)


def main(outdir="pb11_ff_ignition_bridge_results"):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    scan_rng = np.random.default_rng(SEED+999)
    target_rows=[]
    for target in np.arange(500.0, 701.0, 2.0):
        packet=np.clip(scan_rng.normal(target, target*0.037, 60000),1.0,None)
        target_rows.append({"target_keV":float(target),"mean_sigma_v_proxy":float(sigmav_proxy(packet).mean()),"mean_sigma_barn":float(sigma_barn(packet).mean())})
    best_target=max(target_rows,key=lambda r:r["mean_sigma_v_proxy"])
    loss_rows=[]; balance_rows=[]
    for i, loss in enumerate(LOSSES_KEV):
        conv = run_case(loss, ff=False, seed=100+i)
        ff = run_case(loss, ff=True, seed=200+i)
        mult = ff["exposure"] / conv["exposure"]
        ff_burn = burnup_from_exposure_multiplier(mult)
        delta_burn = ff_burn - BASE_BURNUP
        hazard_extra_mev = delta_burn*Q_MEV
        literature_extra_mev = BASE_BURNUP*0.25*Q_MEV
        row = {
            "loss_keV_per_encounter": loss,
            "relative_sigma_v_exposure": mult,
            "ff_mean_window_fraction": ff["mean_window_fraction"],
            "hazard_bridge_burnup": ff_burn,
            "baseline_burnup": BASE_BURNUP,
            "hazard_bridge_extra_fusion_MeV_per_initial_proton": hazard_extra_mev,
            "literature_25pct_extra_fusion_MeV_per_initial_proton": literature_extra_mev,
            "gross_rephase_up_keV_per_proton": ff["gross_up_keV_per_proton"],
            "recoverable_rephase_down_keV_per_proton": ff["gross_down_keV_per_proton"],
        }
        loss_rows.append(row)
        for pr in PHASE_RECOVERY:
            net_rephase_mev = max(0., ff["gross_up_keV_per_proton"] - pr*ff["gross_down_keV_per_proton"])/1000.
            for burden in COLLISION_BURDEN:
                for usable in USABLE_FUSION:
                    for mode, extra in (("hazard_bridge", hazard_extra_mev), ("literature_25pct", literature_extra_mev)):
                        denom = extra*usable
                        eta_req = (net_rephase_mev*burden/denom) if denom>0 else math.inf
                        balance_rows.append({
                            "loss_keV_per_encounter": loss,
                            "phase_energy_recovery_fraction": pr,
                            "all_species_collision_burden_multiplier": burden,
                            "usable_incremental_fusion_fraction": usable,
                            "fusion_gain_mode": mode,
                            "net_rephase_MeV_per_proton_before_burden": net_rephase_mev,
                            "required_ff_useful_coupling_efficiency": eta_req,
                            "energetically_possible_eta_le_1": eta_req <= 1.0,
                            "passes_eta_50pct": eta_req <= 0.5,
                            "passes_eta_30pct": eta_req <= 0.3,
                        })

    def write_csv(name, rows):
        with (out/name).open("w", newline="", encoding="utf-8") as f:
            w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    write_csv("target_scan.csv", target_rows)
    write_csv("loss_sweep.csv", loss_rows)
    write_csv("energy_balance_sweep.csv", balance_rows)

    wall_relief = 1.0-ARCHITECTURE["wall_load_liquid_wall_corrected"]/ARCHITECTURE["wall_load_raw"]
    wall_temp_relief = 1.0-ARCHITECTURE["wall_temp_liquid_wall_corrected"]/ARCHITECTURE["wall_temp_raw"]
    front_heat_relief = 1.0-ARCHITECTURE["front_heat_liquid_wall_corrected"]/ARCHITECTURE["front_heat_raw"]
    lit_rows=[r for r in balance_rows if r["fusion_gain_mode"]=="literature_25pct" and r["usable_incremental_fusion_fraction"]==0.85]
    feasible_50=[r for r in lit_rows if r["phase_energy_recovery_fraction"]>=0.8 and r["passes_eta_50pct"]]
    feasible_30=[r for r in lit_rows if r["phase_energy_recovery_fraction"]>=0.8 and r["passes_eta_30pct"]]
    payload={
        "classification": "CONDITIONAL_IGNITION_ASSISTANCE_CANDIDATE",
        "main_result": "FF can raise p-B11 sigma-v exposure. Ignition benefit depends primarily on actual per-encounter energy loss, phase-energy recovery, all-species collisional recirculation burden, and useful FF coupling efficiency.",
        "optimized_ff_target": best_target,
        "architecture": ARCHITECTURE,
        "architecture_derived": {
            "liquid_wall_load_relief_fraction": wall_relief,
            "liquid_wall_temperature_relief_fraction": wall_temp_relief,
            "liquid_wall_front_heat_relief_fraction": front_heat_relief,
            "openmc_attenuation_not_applied_to_proton_stopping": True,
            "tct_proxy_loss_reduction_not_multiplied_into_ff_energy_balance": True,
        },
        "literature_benchmarks": {
            "wang_2026_cross_section": "arXiv:2601.00241 analytic p-11B cross-section fit used directly",
            "liu_2026_nmpd": {
                "optimistic_fusion_power_enhancement_fraction_at_Ti_300keV": 0.25,
                "optimistic_required_tauE_ignition_reduction_factor": 10.0,
                "all_species_recirculating_power_vs_pp_only": "2-3x",
            },
        },
        "loss_sweep": loss_rows,
        "peer_reviewed_25pct_bound": {
            "eta_50pct_feasible_cases_with_phase_recovery_ge_0p8": len(feasible_50),
            "eta_30pct_feasible_cases_with_phase_recovery_ge_0p8": len(feasible_30),
        },
        "guardrails": [
            "The existing 23.033% burnup is a repository surrogate anchor, not a measured burn fraction.",
            "Hazard-scaled burnup is a screening inference from relative sigma-v exposure and must not be treated as validated.",
            "The 25% fusion-power and ~10x ignition-confinement benchmarks come from a 0D Fokker-Planck study under optimistic assumptions; FF has not been demonstrated to realize that distribution at reactor scale.",
            "No blanket attenuation factor is used to reduce proton collisional stopping.",
            "The missing physical input is an actual areal density / stopping and straggling calculation for the magnetized boron reaction region.",
        ],
    }
    (out/"summary.json").write_text(json.dumps(payload, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()

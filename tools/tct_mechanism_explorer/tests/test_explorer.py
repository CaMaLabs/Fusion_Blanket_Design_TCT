from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from tct_explorer.config import DEFAULT_CONFIG, load_config, write_default
from tct_explorer.mechanisms import FORBIDDEN_PHYSICS_KEYS, REGISTRY, candidate_updates, random_candidate, staged_times, validate_updates, zero_candidate
from tct_explorer.models import Candidate, Evaluation
from tct_explorer.extract import compare_series
from tct_explorer.gates import authority_gate, reachability_gate, sustained_gate
from tct_explorer.objectives import make_objectives, pareto_front

class ExplorerTests(unittest.TestCase):
    def test_all_mechanisms_emit_only_safe_keys(self):
        rng=random.Random(8776)
        for name in REGISTRY:
            candidate=random_candidate(name,rng);updates=candidate_updates(candidate,"impulse",DEFAULT_CONFIG);validate_updates(updates);self.assertFalse(set(updates)&FORBIDDEN_PHYSICS_KEYS)

    def test_zero_candidates_disable_actuation(self):
        rng=random.Random(1)
        for name in REGISTRY:
            candidate=zero_candidate(name,rng);updates=candidate_updates(candidate,"impulse",DEFAULT_CONFIG)
            self.assertEqual(float(updates.get("mag_ctrl_amp",0.0)),0.0)
            self.assertEqual(float(updates.get("mag_ctrl_bias_amp",0.0)),0.0)
            self.assertEqual(float(updates.get("mag_ctrl_early_amp",0.0)),0.0)
            self.assertEqual(float(updates.get("mag_ctrl_aggressive_amp",0.0)),0.0)
            self.assertEqual(float(updates.get("mag_ctrl_hold_amp",0.0)),0.0)
            self.assertEqual(float(updates.get("J_0cd",0.0)),0.0)
            self.assertEqual(float(updates.get("aforce",0.0)),0.0)

    def test_native_momentum_families_present(self):
        self.assertIn("poloidal_momentum_bias",REGISTRY)
        self.assertIn("hybrid_mag_momentum",REGISTRY)
        self.assertIn("hybrid_mag_momentum_redistribution",REGISTRY)
        c=Candidate("poloidal_momentum_bias",{"amp":0.005,"force_width":0.12,"force_x":0.5,"force_n":0})
        u=candidate_updates(c,"impulse",DEFAULT_CONFIG)
        self.assertEqual(u["ipforce"],1)
        self.assertAlmostEqual(float(u["aforce"]),0.005)
        self.assertEqual(u["imag_control"],0)

    def test_staged_family_has_ordered_transitions(self):
        p={
            "bias_amp":-0.002,"early_amp":-0.006,"aggressive_amp":-0.012,"hold_amp":-0.003,
            "early_start":0.025,"early_duration":0.05,"aggressive_duration":0.05,"hold_duration":0.08,
            "ramp":0.0,"r0":10.0,"z0":1.0,"mag_wr":0.5,"mag_wz":0.5,
            "momentum_amp":-0.005,"force_width":0.12,"force_x":0.5,"force_n":0,
        }
        t0,t1,t2,t3=staged_times(p)
        self.assertTrue(t0<t1<t2<t3)
        c=Candidate("staged_mag_momentum",p)
        u=candidate_updates(c,"sustained",DEFAULT_CONFIG)
        self.assertEqual(u["imag_control_staged"],1)
        self.assertEqual(u["ipforce"],1)
        self.assertAlmostEqual(u["mag_ctrl_t_early"],t0)
        self.assertAlmostEqual(u["mag_ctrl_t_aggressive"],t1)
        self.assertAlmostEqual(u["mag_ctrl_t_hold"],t2)
        self.assertAlmostEqual(u["mag_ctrl_t_off"],t3)

    def test_forbidden_physics_key_rejected(self):
        with self.assertRaises(ValueError):validate_updates({"eta":1e-3})

    def test_candidate_id_is_stable(self):
        a=Candidate("magnetic_pulse",{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.1,"duration":0.05,"ramp":0.0});b=Candidate("magnetic_pulse",dict(reversed(list(a.params.items()))));self.assertEqual(a.candidate_id,b.candidate_id)

    def test_pareto_prefers_feasible(self):
        a=Evaluation(Candidate("magnetic_pulse",{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.1,"duration":0.05,"ramp":0.0}),feasible=True);b=Evaluation(Candidate("magnetic_pulse",{"amp":0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.1,"duration":0.05,"ramp":0.0}),feasible=False);a.objectives={k:0.0 for k in make_objectives(a)};b.objectives={k:100.0 for k in make_objectives(b)};front=pareto_front([a,b]);self.assertEqual([x.candidate.candidate_id for x in front],[a.candidate.candidate_id])

    def test_default_config_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"explorer.json";write_default(path);loaded=json.loads(path.read_text());self.assertIn("hybrid_mag_momentum",loaded["search"]["enabled_mechanisms"])
            resolved=load_config(path);self.assertNotIn("${REPO_ROOT}",resolved["paths"]["repo_root"])

    def test_kinetic_reachability_counts_for_momentum(self):
        cfg=load_config(None)
        self.assertTrue(reachability_gate({"final_psi_span_delta":0.0,"final_bz_proxy_delta":0.0,"final_kinetic_energy_delta":1e-6},cfg))

    def test_nonredistribution_authority_does_not_require_shape_ratio(self):
        cfg=load_config(None)
        metrics={
            "peak_favorable_width_gain_pct":1.0,
            "peak_favorable_jpk_change_pct":-0.02,
            "peak_favorable_high_j_change_pct":-0.2,
            "peak_favorable_center_to_shoulder_change_pct":0.08,
        }
        self.assertTrue(authority_gate(metrics,cfg,"hybrid_mag_momentum"))
        self.assertTrue(authority_gate(metrics,cfg))

    def test_redistribution_authority_keeps_shape_requirement(self):
        cfg=load_config(None)
        metrics={
            "peak_favorable_width_gain_pct":1.0,
            "peak_favorable_jpk_change_pct":-0.02,
            "peak_favorable_high_j_change_pct":-0.2,
            "peak_favorable_center_to_shoulder_change_pct":0.08,
        }
        self.assertFalse(authority_gate(metrics,cfg,"current_redistribution"))
        metrics["peak_favorable_center_to_shoulder_change_pct"]=-0.08
        self.assertTrue(authority_gate(metrics,cfg,"current_redistribution"))

    def test_post_turnoff_peak_can_pass_impulse_gate(self):
        def row(t, w, j, ratio):
            return {"time":t,"W_sheet":w,"Jpk":j,"Jint_high":1.0,
                "center_to_shoulder_ratio":ratio,"magnetic_energy":10.0,"kinetic_energy":2.0,
                "toroidal_current":1.0,"Reconnected_Flux":1.0,
                "roi_psi_span":1.0,"roi_Bz_proxy_dpsi_dZ":1.0}
        base=[row(0,1,1,1),row(.05,1,1,1),row(.10,1,1,1)]
        controlled=[row(0,1,1,1),row(.05,.99,1.01,1.01),row(.10,1.01,.99,.99)]
        metrics=compare_series(base,controlled,0,.05,response_horizon=.05)
        self.assertAlmostEqual(metrics["peak_favorable_width_gain_pct"],1.0)
        self.assertAlmostEqual(metrics["peak_favorable_jpk_change_pct"],-1.0)
        self.assertAlmostEqual(metrics["response_latency"],.10)
        self.assertTrue(authority_gate(metrics,load_config(None)))

    def test_onset_boundary_is_excluded(self):
        def row(t, w):
            return {"time":t,"W_sheet":w,"Jpk":1.0,"Jint_high":1.0,
                "center_to_shoulder_ratio":1.0,"magnetic_energy":10.0,"kinetic_energy":2.0,
                "toroidal_current":1.0,"Reconnected_Flux":1.0,
                "roi_psi_span":1.0,"roi_Bz_proxy_dpsi_dZ":1.0}
        metrics=compare_series([row(.05,1),row(.10,1)],[row(.05,2),row(.10,1.01)],.05,.10,0)
        self.assertEqual(metrics["impulse_sample_count"],1)
        self.assertAlmostEqual(metrics["immediate_width_gain_pct"],1.0)

    def test_sustained_gate_rejects_transient_with_adverse_jpk(self):
        cfg=load_config(None)
        metrics={"mean_active_width_gain_pct":0.4,"integrated_width_gain_pct_time":0.02,
            "positive_width_sample_fraction":0.8,"max_active_peak_j_change_pct":0.8}
        self.assertFalse(sustained_gate(metrics,cfg))
        metrics["max_active_peak_j_change_pct"]=0.2
        self.assertTrue(sustained_gate(metrics,cfg))

    def test_stage_horizons_are_distinct(self):
        c=Candidate("magnetic_pulse",{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.05,"duration":0.05,"ramp":0.0})
        impulse=candidate_updates(c,"impulse",DEFAULT_CONFIG)
        sustained=candidate_updates(c,"sustained",DEFAULT_CONFIG)
        full=candidate_updates(c,"full",DEFAULT_CONFIG)
        self.assertLess(impulse["ntimemax"],sustained["ntimemax"])
        self.assertLess(sustained["ntimemax"],full["ntimemax"])

if __name__=="__main__":unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from tct_explorer.config import DEFAULT_CONFIG, write_default
from tct_explorer.mechanisms import FORBIDDEN_PHYSICS_KEYS, REGISTRY, candidate_updates, random_candidate, validate_updates, zero_candidate
from tct_explorer.models import Candidate, Evaluation
from tct_explorer.objectives import make_objectives, pareto_front

class ExplorerTests(unittest.TestCase):
    def test_all_mechanisms_emit_only_safe_keys(self):
        rng=random.Random(8776)
        for name in REGISTRY:
            candidate=random_candidate(name,rng);updates=candidate_updates(candidate,"impulse",DEFAULT_CONFIG);validate_updates(updates);self.assertFalse(set(updates)&FORBIDDEN_PHYSICS_KEYS)
    def test_zero_candidates_disable_actuation(self):
        rng=random.Random(1)
        for name in REGISTRY:
            candidate=zero_candidate(name,rng);updates=candidate_updates(candidate,"impulse",DEFAULT_CONFIG);self.assertEqual(float(updates.get("mag_ctrl_amp",0.0)),0.0);self.assertEqual(float(updates.get("J_0cd",0.0)),0.0)
    def test_forbidden_physics_key_rejected(self):
        with self.assertRaises(ValueError):validate_updates({"eta":1e-3})
    def test_candidate_id_is_stable(self):
        a=Candidate("magnetic_pulse",{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.1,"duration":0.05,"ramp":0.0});b=Candidate("magnetic_pulse",dict(reversed(list(a.params.items()))));self.assertEqual(a.candidate_id,b.candidate_id)
    def test_pareto_prefers_feasible(self):
        a=Evaluation(Candidate("magnetic_pulse",{"amp":-0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.1,"duration":0.05,"ramp":0.0}),feasible=True);b=Evaluation(Candidate("magnetic_pulse",{"amp":0.01,"r0":10.0,"z0":1.0,"wr":0.5,"wz":0.5,"t_on":0.1,"duration":0.05,"ramp":0.0}),feasible=False);a.objectives={k:0.0 for k in make_objectives(a)};b.objectives={k:100.0 for k in make_objectives(b)};front=pareto_front([a,b]);self.assertEqual([x.candidate.candidate_id for x in front],[a.candidate.candidate_id])
    def test_default_config_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"explorer.json";write_default(path);loaded=json.loads(path.read_text());self.assertIn("magnetic_pulse",loaded["search"]["enabled_mechanisms"])

if __name__=="__main__":unittest.main()

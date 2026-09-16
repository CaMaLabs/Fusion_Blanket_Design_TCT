#!/usr/bin/env python3
import unittest

from tct_predictive_supervisor import Actuator, Prediction, PredictiveSupervisor


def actuator_set():
    return [
        Actuator("prebiased_current_sheet_fast", 2.75, True, "passes_for_bounded_boost"),
        Actuator("prebiased_current_sheet_nominal", 5.25, True, "passes_for_bounded_boost"),
        Actuator("prebiased_current_sheet_slow", 8.25, False, "fails_event_specific_boost"),
    ]


class SupervisorTests(unittest.TestCase):
    def test_mirnov_with_margin_fires_fast_path(self):
        s = PredictiveSupervisor(actuator_set())
        d = s.decide(Prediction("median", 8.376, 0.9, 1.0, ("mirnov",)))
        self.assertEqual(d.command, "BOUNDED_BOOST")
        self.assertEqual(d.actuator, "prebiased_current_sheet_fast")
        self.assertAlmostEqual(d.margin_ms, 5.626, places=6)

    def test_late_prediction_is_no_action(self):
        s = PredictiveSupervisor(actuator_set())
        d = s.decide(Prediction("late", 2.7, 1.0, 1.0, ("mirnov_toroidal",)))
        self.assertEqual(d.command, "NO_ACTION")
        self.assertEqual(d.reason, "insufficient_lead_for_passing_actuator_plus_guard")

    def test_sxr_only_blocked_by_default(self):
        s = PredictiveSupervisor(actuator_set())
        d = s.decide(Prediction("sxr", 12.0, 1.0, 1.0, ("sxr",)))
        self.assertEqual(d.command, "NO_ACTION")
        self.assertEqual(d.reason, "sxr_only_blocked_by_false_trigger_tradeoff")

    def test_bridge_requires_explicit_enable(self):
        p = Prediction("bridge", 12.0, 1.0, 1.0, ("j_djdt",))
        self.assertEqual(PredictiveSupervisor(actuator_set()).decide(p).command, "NO_ACTION")
        self.assertEqual(
            PredictiveSupervisor(actuator_set(), allow_bridge_trigger=True).decide(p).command,
            "BOUNDED_BOOST",
        )

    def test_low_risk_is_no_action(self):
        s = PredictiveSupervisor(actuator_set(), min_risk=0.5)
        d = s.decide(Prediction("low", 12.0, 0.49, 1.0, ("mirnov",)))
        self.assertEqual(d.reason, "risk_below_threshold")

    def test_failed_actuator_is_not_eligible(self):
        s = PredictiveSupervisor([Actuator("failed", 1.0, False, "failed")])
        d = s.decide(Prediction("x", 20.0, 1.0, 1.0, ("mirnov",)))
        self.assertEqual(d.command, "NO_ACTION")


if __name__ == "__main__":
    unittest.main()

import datetime
import unittest
from unittest.mock import patch
from core.coach_simulator import _action, _phase, simulate_pb_build

class CoachSimulatorTests(unittest.TestCase):
    def test_phase_moves_toward_race(self):
        self.assertEqual(_phase(8.0),"Build")
        self.assertEqual(_phase(3.0),"Specific")
        self.assertEqual(_phase(0.5),"Taper")

    def test_race_substitutes_for_quality(self):
        action,accepted,_=_action(
            "threshold",
            {"family":"race","execution":None},
            [],
        )
        self.assertTrue(accepted)
        self.assertEqual(action,"recover")

    def test_weak_execution_does_not_progress(self):
        action,accepted,_=_action(
            "threshold",
            {"family":"threshold","execution":70.0},
            [88.0,90.0],
        )
        self.assertTrue(accepted)
        self.assertEqual(action,"reduce")

    @patch("core.coach_simulator._prior_execution", return_value=[])
    @patch("core.coach_simulator._actual_on_date", return_value=None)
    def test_simulator_keeps_sensible_quality_spacing(self, actual, prior):
        sim=simulate_pb_build(
            1,target_date=datetime.date(2026,5,5),
            target_label="Test PB",weeks=2,
        )
        self.assertGreater(sim.coaching_decision_count,0)
        self.assertEqual(sim.review_decision_count,0)

if __name__=="__main__":
    unittest.main()

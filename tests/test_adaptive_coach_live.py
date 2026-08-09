import unittest
from unittest.mock import patch

from core.adaptive_coach_live import build_live_coach_decision


class Legacy:
    session_family = "Easy Recovery Run"
    earliest_timing = "Today"
    timing_detail = "Easy first"
    next_key_session_family = "Threshold Development"
    next_key_session_timing = "Wednesday"
    confidence = 0.80
    confidence_label = "Good"
    headline = "Recover"
    why = ("legacy",)
    readiness_required = True


class Arbitration:
    ready_for_live = True
    selected_family = "vo2"
    selected_prescription = "8 × 500m"
    selected_day = "Wednesday"
    confidence = 0.88
    confidence_label = "High"
    headline = "Use VO₂ now"
    evidence = ("Threshold is preserved for Saturday.",)
    safety_notes = ()


class LiveCoachTests(unittest.TestCase):
    @patch("core.adaptive_coach_live.build_coaching_arbitration", return_value=Arbitration())
    @patch("core.adaptive_coach_live.build_next_run_recommendation", return_value=Legacy())
    def test_arbitration_becomes_authoritative_key_session(self, legacy, arbitration):
        result = build_live_coach_decision(1)
        self.assertEqual(result.key_family, "vo2")
        self.assertEqual(result.key_prescription, "8 × 500m")
        self.assertEqual(result.source, "Adaptive Coach + Arbitration")


if __name__ == "__main__":
    unittest.main()

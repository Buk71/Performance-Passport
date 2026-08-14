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


class OperationalNext:
    session_type = "Long run"
    timing = "Sunday"
    detail = "11.0 mi comfortable continuous running"
    family = "long"
    planned_type = "Long run"
    day = "Sunday"
    adapted = False
    reason = "This is the next incomplete runnable day in the saved week."


class Operational:
    state = "Active"
    week_number = 3
    status = "On track"
    headline = "22.0 of 40.0 reliable miles complete"
    summary = "4 of 6 planned running days have activity evidence."
    suggestions = ()
    next_run = OperationalNext()
    completed_miles = 22.0
    planned_miles = 40.0
    source = "Saved Training Block + real activities"


class UpcomingOperational(Operational):
    state = "Upcoming"
    status = "Ready to start"


class LiveCoachTests(unittest.TestCase):
    @patch("core.adaptive_coach_live.build_operational_block_week", return_value=None)
    @patch("core.adaptive_coach_live.build_coaching_arbitration", return_value=Arbitration())
    @patch("core.adaptive_coach_live.build_next_run_recommendation", return_value=Legacy())
    def test_arbitration_becomes_authoritative_key_session(self, legacy, arbitration, operational):
        result = build_live_coach_decision(1)
        self.assertEqual(result.key_family, "vo2")
        self.assertEqual(result.key_prescription, "8 × 500m")
        self.assertEqual(result.source, "Adaptive Coach + Arbitration")

    @patch("core.adaptive_coach_live.build_operational_block_week", return_value=Operational())
    @patch("core.adaptive_coach_live.build_coaching_arbitration", return_value=Arbitration())
    @patch("core.adaptive_coach_live.build_next_run_recommendation", return_value=Legacy())
    def test_saved_week_becomes_immediate_authority_without_losing_coach_evidence(
        self, legacy, arbitration, operational
    ):
        result = build_live_coach_decision(1)

        self.assertEqual(result.immediate_label, "Long run")
        self.assertEqual(result.immediate_timing, "Sunday")
        self.assertEqual(result.key_family, "long")
        self.assertEqual(result.operational_week_number, 3)
        self.assertIn("Saved Training Block", result.source)
        self.assertIn("4 of 6", result.why[0])

    @patch("core.adaptive_coach_live.build_operational_block_week", return_value=UpcomingOperational())
    @patch("core.adaptive_coach_live.build_coaching_arbitration", return_value=Arbitration())
    @patch("core.adaptive_coach_live.build_next_run_recommendation", return_value=Legacy())
    def test_upcoming_saved_week_does_not_replace_current_coaching(
        self, legacy, arbitration, operational
    ):
        result = build_live_coach_decision(1)

        self.assertNotEqual(result.immediate_label, "Long run")
        self.assertEqual(result.source, "Adaptive Coach + Arbitration")
        self.assertEqual(result.operational_status, "Ready to start")


if __name__ == "__main__":
    unittest.main()

import datetime
import unittest

from core.next_run import _recommend_from_context


class FakeEntry:
    athlete_id = 1
    activity_date = "2026-08-08"
    activity_title = "Easy Run"
    category = "Easy"
    todays_win = "Top 10% Easy"
    next_opportunity = "Threshold is the clearest next opportunity"
    next_focus = "Threshold Development"
    evidence_confidence = 0.82


class FakeBlock:
    name = "Autumn 10K Block"
    current_phase = "Build"
    primary_focus = "Threshold"


class FakeQualityEntry(FakeEntry):
    activity_title = "Threshold Session"
    category = "Threshold Development"


class FakeRecoveryBlock(FakeBlock):
    current_phase = "Recovery"
    primary_focus = "Recovery"


class NextRunTests(unittest.TestCase):
    def test_easy_run_can_lead_to_threshold_focus(self):
        result = _recommend_from_context(
            FakeEntry(),
            FakeBlock(),
            today=datetime.date(2026, 8, 8),
        )
        self.assertEqual(result.session_family, "Threshold Development")
        self.assertEqual(result.earliest_timing, "Tomorrow")
        self.assertTrue(result.readiness_required)

    def test_quality_run_is_not_followed_by_quality(self):
        result = _recommend_from_context(
            FakeQualityEntry(),
            FakeBlock(),
            today=datetime.date(2026, 8, 8),
        )
        self.assertEqual(result.session_family, "Easy Recovery Run")
        self.assertFalse(result.readiness_required)

    def test_recovery_phase_overrides_threshold_focus(self):
        result = _recommend_from_context(
            FakeEntry(),
            FakeRecoveryBlock(),
            today=datetime.date(2026, 8, 8),
        )
        self.assertEqual(result.session_family, "Recovery Run")
        self.assertFalse(result.readiness_required)


if __name__ == "__main__":
    unittest.main()

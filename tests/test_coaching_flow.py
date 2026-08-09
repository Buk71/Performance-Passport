import datetime
import unittest

from core.next_run import _recommend_from_context
from core.session_designer import _session_family_from_label


class FakeEntry:
    athlete_id = 1
    activity_date = "2026-08-08"
    activity_title = "Easy Run"
    category = "Easy"
    todays_win = "Top 10% Easy"
    next_opportunity = "Threshold is the clearest next opportunity"
    next_focus = "Threshold Development"
    evidence_confidence = 0.82


class FakeQualityEntry(FakeEntry):
    activity_title = "Threshold Session"
    category = "Threshold Development"


class FakeBlock:
    name = "Autumn 10K Block"
    current_phase = "Build"
    primary_focus = "Threshold"


class CoachingFlowTests(unittest.TestCase):
    def test_quality_after_easy_is_both_immediate_and_key(self):
        result = _recommend_from_context(
            FakeEntry(),
            FakeBlock(),
            today=datetime.date(2026, 8, 8),
        )
        self.assertEqual(result.session_family, "Threshold Development")
        self.assertEqual(
            result.next_key_session_family,
            "Threshold Development",
        )

    def test_quality_after_quality_preserves_key_direction(self):
        result = _recommend_from_context(
            FakeQualityEntry(),
            FakeBlock(),
            today=datetime.date(2026, 8, 8),
        )
        self.assertEqual(result.session_family, "Easy Recovery Run")
        self.assertEqual(
            result.next_key_session_family,
            "Threshold Development",
        )
        self.assertEqual(result.next_key_session_timing, "In 2 days")

    def test_session_designer_maps_key_label(self):
        self.assertEqual(
            _session_family_from_label("Threshold Development"),
            "threshold",
        )


if __name__ == "__main__":
    unittest.main()

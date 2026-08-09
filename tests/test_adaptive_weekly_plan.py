import datetime
import unittest
from unittest.mock import patch

from core.adaptive_training_block import AdaptiveBlockPreview, AdaptivePhase
from core.adaptive_weekly_plan import (
    _humanise_signature,
    _progress_interval_session,
    _progress_threshold_session,
    build_adaptive_weekly_plan,
)
from core.performance_backtracking import PerformanceBacktrackingProfile


BLOCK = AdaptiveBlockPreview(
    athlete_id=1,
    available=True,
    goal_name="Autumn 10K",
    distance_label="10K",
    target_date="2026-10-04",
    weeks_remaining=4,
    current_phase="Specific",
    phases=(
        AdaptivePhase(
            "Specific",1,3,"Race Specific","10K-specific development",
            "Convert fitness into race demands.",(),
        ),
        AdaptivePhase(
            "Taper / Race",4,4,"Freshness","Sharpen and freshen",
            "Arrive fresh.",(),
        ),
    ),
    learned_signals=(),
    headline="Preview",
    summary="Preview",
    limitations=(),
)

EMPTY_HISTORY = PerformanceBacktrackingProfile(
    athlete_id=1,
    anchor_count=0,
    pb_count=0,
    performances=(),
    recurring_42d_signatures=(),
    normal_42d_block_count=0,
    preparation_contrasts=(),
    signature_lifts=(),
    summary="",
    limitations=(),
)


class AdaptiveWeeklyPlanTests(unittest.TestCase):
    def test_odd_historical_distances_become_coach_friendly(self):
        self.assertEqual(
            _humanise_signature("threshold_7x775m"),
            "7 × 800m threshold",
        )
        self.assertEqual(
            _humanise_signature("short_intervals_8x525m"),
            "8 × 500m controlled intervals",
        )

    def test_build_sessions_progress_week_to_week(self):
        week1=_progress_interval_session(
            "8 × 500m controlled intervals",
            1,
        )
        week4=_progress_interval_session(
            "8 × 500m controlled intervals",
            4,
        )
        self.assertNotEqual(week1,week4)

        threshold1=_progress_threshold_session(
            "7 × 800m threshold",
            1,
        )
        threshold5=_progress_threshold_session(
            "7 × 800m threshold",
            5,
        )
        self.assertNotEqual(threshold1,threshold5)
        self.assertIn("min threshold",threshold5)

    @patch("core.adaptive_weekly_plan.build_performance_backtracking_profile", return_value=EMPTY_HISTORY)
    @patch("core.adaptive_weekly_plan._target_text", return_value="Target")
    @patch("core.adaptive_weekly_plan._training_rhythm", return_value=(("Wednesday","Saturday"),"Sunday","Friday"))
    @patch("core.adaptive_weekly_plan.build_adaptive_block_preview", return_value=BLOCK)
    def test_builds_full_week_calendar(self, block, rhythm, targets, history):
        plan=build_adaptive_weekly_plan(1,today=datetime.date(2026,8,9))
        self.assertTrue(plan.available)
        self.assertEqual(len(plan.weeks),4)
        self.assertEqual(len(plan.weeks[0].days),7)
        wed=next(x for x in plan.weeks[0].days if x.day_name=="Wednesday")
        sat=next(x for x in plan.weeks[0].days if x.day_name=="Saturday")
        self.assertIn(wed.session_family,{"race_pace","vo2"})
        self.assertEqual(sat.session_family,"threshold")

    @patch("core.adaptive_weekly_plan.build_adaptive_block_preview")
    def test_unavailable_block_gives_no_plan(self, block):
        block.return_value=AdaptiveBlockPreview(
            1,False,None,None,None,None,None,(),(),"No goal","No goal",()
        )
        plan=build_adaptive_weekly_plan(1)
        self.assertFalse(plan.available)
        self.assertEqual(plan.weeks,())


if __name__=="__main__":
    unittest.main()

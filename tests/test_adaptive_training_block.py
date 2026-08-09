import datetime
import unittest
from unittest.mock import patch

from core.adaptive_training_block import build_adaptive_block_preview
from core.performance_backtracking import PerformanceBacktrackingProfile

EMPTY_PROFILE = PerformanceBacktrackingProfile(
    athlete_id=1, anchor_count=0, pb_count=0, performances=(),
    recurring_42d_signatures=(), normal_42d_block_count=0,
    preparation_contrasts=(), signature_lifts=(), summary="",
    limitations=(),
)

class AdaptiveBlockTests(unittest.TestCase):
    @patch("core.adaptive_training_block.build_performance_backtracking_profile")
    @patch("core.adaptive_training_block.get_active_goal")
    def test_10k_goal_builds_progressive_preview(self, goal, history):
        goal.return_value={
            "goal_name":"Autumn 10K","goal_type":"10K","distance_m":10000,
            "target_date":"2026-10-04",
        }
        history.return_value=EMPTY_PROFILE
        preview=build_adaptive_block_preview(
            1,today=datetime.date(2026,8,9)
        )
        self.assertTrue(preview.available)
        self.assertEqual(preview.distance_label,"10K")
        self.assertEqual(preview.phases[-1].name,"Taper / Race")
        self.assertGreaterEqual(len(preview.phases),3)

    @patch("core.adaptive_training_block.get_active_goal")
    def test_no_goal_does_not_generate_plan(self, goal):
        goal.return_value=None
        preview=build_adaptive_block_preview(1)
        self.assertFalse(preview.available)

if __name__=="__main__":
    unittest.main()

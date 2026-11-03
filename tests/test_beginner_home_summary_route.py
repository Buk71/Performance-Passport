import datetime
from unittest.mock import patch

from core.home_summary import build_home_summary
from core.runner_journey import RunnerJourney


def _journey():
    return RunnerJourney(
        id=1,
        athlete_id=99,
        journey_type="couch_to_5k",
        status="Active",
        goal_id=5,
        entry_stage="run_walk_short",
        current_stage="run_walk_short",
        sessions_per_week=3,
        started_at="2026-09-04",
        completed_at=None,
        baseline={},
        preferences={"current_week": 2, "plan_length_weeks": 12},
        created_at=None,
        updated_at=None,
    )


def test_public_home_summary_routes_active_beginner_before_old_plan_engines():
    goal = {
        "goal_name": "Complete my first 5K",
        "goal_type": "5K",
        "target_time_s": None,
        "target_date": None,
    }
    with (
        patch("core.home_summary.get_active_goal", return_value=goal),
        patch("core.home_summary.get_active_runner_journey", return_value=_journey()),
        patch("core.home_summary.build_adaptive_weekly_plan") as adaptive,
        patch("core.home_summary.get_active_training_block") as old_block,
        patch("core.home_summary.build_operational_block_week") as operational,
    ):
        summary = build_home_summary(
            99,
            today=datetime.date(2026, 9, 4),
        )

    assert summary.block_name == "Couch → 5K"
    assert "Level 2 of 12" in summary.block_context
    adaptive.assert_not_called()
    old_block.assert_not_called()
    operational.assert_not_called()

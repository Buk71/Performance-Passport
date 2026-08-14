import datetime
from types import SimpleNamespace
from unittest.mock import patch

from core.home_summary import build_home_summary
from core.operational_block import OperationalActivity, compose_operational_week
from core.training_blocks import block_progress, get_active_training_block


TEST_DATE = datetime.date(2026, 8, 11)


@patch("core.home_summary.build_operational_block_week", return_value=None)
def test_richard_home_uses_goal_and_honest_adaptive_preview(_operational):
    summary = build_home_summary(1, today=TEST_DATE)

    assert summary.goal_name == "Sub 39:00"
    assert summary.target_time_s == 2340
    assert summary.block_is_saved is False
    assert "adaptive" in summary.block_name.lower()
    assert len(summary.week_days) == 7
    assert summary.week_days[1].is_today is True


@patch("core.home_summary.build_operational_block_week", return_value=None)
def test_jo_home_uses_her_saved_active_block(_operational):
    summary = build_home_summary(3, today=TEST_DATE)
    active = get_active_training_block(3)
    assert active is not None
    progress = block_progress(active, today=TEST_DATE)

    assert summary.goal_name == "Sub 45"
    assert summary.target_time_s == 2700
    assert summary.block_is_saved is True
    assert summary.block_name == active.name
    expected_progress = (
        "Upcoming"
        if progress.week_number == 0
        else f"Week {progress.week_number} of {progress.total_weeks}"
    )
    assert expected_progress in summary.block_context
    assert len(summary.week_days) == 7


@patch("core.home_summary.build_operational_block_week", return_value=None)
def test_home_summaries_do_not_cross_athletes(_operational):
    richard = build_home_summary(1, today=TEST_DATE)
    jo = build_home_summary(3, today=TEST_DATE)

    assert richard.goal_name != jo.goal_name
    assert richard.target_time_s != jo.target_time_s
    assert richard.athlete_id == 1
    assert jo.athlete_id == 3


def test_active_operational_week_drives_home_schedule_and_next_run():
    plan = {
        "weeks": [{
            "week_number": 2, "start_date": "2026-08-10", "end_date": "2026-08-16",
            "target_miles": 30.0, "phase": "Build", "emphasis": "Threshold rhythm",
            "days": [
                {"day": "Monday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Tuesday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Wednesday", "session_type": "Threshold", "detail": "6 mi total", "is_hard": True},
                {"day": "Thursday", "session_type": "Recovery", "detail": "4 mi easy", "is_hard": False},
                {"day": "Friday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Saturday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Sunday", "session_type": "Long run", "detail": "10 mi", "is_hard": False},
            ],
        }, {"week_number": 3, "start_date": "2026-08-17", "end_date": "2026-08-23", "target_miles": 32.0, "phase": "Build", "emphasis": "Continue", "days": []}],
    }
    activity = OperationalActivity(
        activity_id=1, activity_date="2026-08-11", title="Easy five",
        family="easy", family_label="Easy / aerobic", distance_miles=5.0,
        moving_time_s=2400.0, confidence=.9, distance_reliable=True,
    )
    operational = compose_operational_week(
        athlete_id=1, training_block_id=7, block_name="Sub 39 block",
        plan=plan, activities=(activity,), today=TEST_DATE,
    )
    goal = {
        "goal_name": "Sub 39:00", "target_time_s": 2340,
        "target_date": "2026-11-29", "race_name": "Leeds Abbey Dash",
    }
    with (
        patch("core.home_summary.get_active_goal", return_value=goal),
        patch("core.home_summary.build_adaptive_weekly_plan", return_value=SimpleNamespace(available=False, summary="Fallback")),
        patch("core.home_summary.get_active_training_block", return_value=SimpleNamespace(name="Sub 39 block", current_phase="Build")),
        patch("core.home_summary.block_progress", return_value=SimpleNamespace(week_number=2, total_weeks=3)),
        patch("core.home_summary.build_operational_block_week", return_value=operational),
    ):
        summary = build_home_summary(1, today=TEST_DATE)

    assert summary.week_days[1].session_family == "completed"
    assert summary.week_days[1].is_today is True
    assert summary.next_label == "Threshold"
    assert summary.next_source == "Saved Training Block + real activities"
    assert "On track" in summary.block_context

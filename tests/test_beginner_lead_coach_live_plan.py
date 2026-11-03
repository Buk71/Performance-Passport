import datetime
from core.home_summary import (
    _beginner_home_days,
    _beginner_next,
    _build_beginner_home_summary,
)
from core.runner_journey import RunnerJourney


def _journey(stage="run_walk_short", week=2, sessions=3):
    return RunnerJourney(
        id=1,
        athlete_id=99,
        journey_type="couch_to_5k",
        status="Active",
        goal_id=5,
        entry_stage=stage,
        current_stage=stage,
        sessions_per_week=sessions,
        started_at="2026-09-04",
        completed_at=None,
        baseline={},
        preferences={"current_week": week, "plan_length_weeks": 12},
        created_at=None,
        updated_at=None,
    )


def test_beginner_home_has_full_seven_day_strip():
    days = _beginner_home_days(
        journey=_journey(),
        today=datetime.date(2026, 9, 4),
    )
    assert len(days) == 7
    assert [d.day_name for d in days] == [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]


def test_three_day_beginner_week_places_three_journey_sessions():
    days = _beginner_home_days(
        journey=_journey(sessions=3),
        today=datetime.date(2026, 9, 4),
    )
    planned = [d for d in days if d.session_family != "rest"]
    assert [d.day_name for d in planned] == ["Tuesday", "Thursday", "Sunday"]
    assert all(d.target == "Counts for progression" for d in planned)


def test_beginner_next_uses_next_planned_day():
    days = _beginner_home_days(
        journey=_journey(),
        today=datetime.date(2026, 9, 4),
    )
    label, timing, detail, source = _beginner_next(
        days, datetime.date(2026, 9, 4)
    )
    assert timing == "Sunday"
    assert label
    assert detail
    assert source == "Couch → 5K Runner Journey"


def test_beginner_home_summary_reports_live_plan_level():
    summary = _build_beginner_home_summary(
        99,
        {
            "goal_name": "Complete my first 5K",
            "goal_type": "5K",
            "target_time_s": None,
            "target_date": None,
        },
        _journey(stage="run_blocks_5", week=4),
        today=datetime.date(2026, 9, 4),
    )
    assert summary.block_name == "Couch → 5K"
    assert summary.block_is_saved is True
    assert "Level 4 of 12" in summary.block_context
    assert summary.week_theme.startswith("Level 4:")
    assert summary.next_source == "Couch → 5K Runner Journey"


def test_four_day_beginner_week_marks_support_day_separately():
    days = _beginner_home_days(
        journey=_journey(sessions=4),
        today=datetime.date(2026, 9, 4),
    )
    sunday = next(day for day in days if day.day_name == "Sunday")
    assert sunday.session_family == "recovery"
    assert sunday.target == "Support session"

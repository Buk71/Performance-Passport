from core.beginner_training_plan import (
    PLAN_LENGTH,
    build_couch_to_5k_plan,
    entry_week_for_stage,
    stage_for_week,
)


def test_full_plan_has_12_levels():
    plan = build_couch_to_5k_plan(
        athlete_id=1, sessions_per_week=3, entry_stage="run_walk_short"
    )
    assert PLAN_LENGTH == 12
    assert len(plan.weeks) == 12
    assert plan.current_week == 2


def test_full_plan_is_visible_before_and_after_entry_point():
    plan = build_couch_to_5k_plan(
        athlete_id=1, sessions_per_week=3, entry_stage="run_blocks_5"
    )
    assert plan.weeks[0].status == "Skipped by entry assessment"
    assert plan.weeks[3].status == "Current"
    assert plan.weeks[-1].status == "Ahead"


def test_three_day_plan_has_three_progression_sessions():
    plan = build_couch_to_5k_plan(
        athlete_id=1, sessions_per_week=3, entry_stage="run_walk_short"
    )
    week = plan.weeks[1]
    assert len(week.sessions) == 3
    assert all(day.counts_for_progression for day in week.sessions)


def test_four_day_plan_has_three_progression_plus_support_day():
    plan = build_couch_to_5k_plan(
        athlete_id=1, sessions_per_week=4, entry_stage="run_walk_short"
    )
    week = plan.weeks[1]
    assert len(week.sessions) == 4
    assert sum(day.counts_for_progression for day in week.sessions) == 3
    assert week.sessions[-1].role == "Support day"


def test_two_day_plan_is_supported():
    plan = build_couch_to_5k_plan(
        athlete_id=1, sessions_per_week=2, entry_stage="continuous_20"
    )
    assert len(plan.weeks[7].sessions) == 2


def test_week_11_consolidates_before_5k():
    assert stage_for_week(10) == "continuous_30"
    assert stage_for_week(11) == "continuous_30"
    assert stage_for_week(12) == "5k_ready"


def test_entry_mapping_can_skip_early_levels():
    assert entry_week_for_stage("run_blocks_8") == 5
    assert entry_week_for_stage("continuous_25") == 9


def test_projected_dates_are_advisory_from_current_level():
    plan = build_couch_to_5k_plan(
        athlete_id=1,
        sessions_per_week=3,
        entry_stage="run_walk_short",
        current_week=4,
    )
    assert plan.weeks[2].projected_start_date is None
    assert plan.weeks[3].projected_start_date is not None
    assert "not fixed calendar weeks" in plan.timeline_note.lower()

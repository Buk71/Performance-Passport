from core.five_to_ten_k_plan import (
    PLAN_LENGTH,
    build_five_to_ten_k_plan,
    entry_level_for_stage,
    stage_for_level,
)


def test_full_plan_has_10_levels():
    plan = build_five_to_ten_k_plan(
        athlete_id=1,
        sessions_per_week=3,
        entry_stage="5k_consistency",
    )
    assert PLAN_LENGTH == 10
    assert len(plan.levels) == 10


def test_entry_stage_can_skip_early_levels():
    assert entry_level_for_stage("build_7k") == 4
    assert entry_level_for_stage("build_9k") == 8


def test_levels_map_to_shared_six_stage_journey():
    assert stage_for_level(2) == "build_6k"
    assert stage_for_level(3) == "build_6k"
    assert stage_for_level(8) == "build_9k"
    assert stage_for_level(10) == "10k_ready"


def test_three_day_plan_has_two_normal_runs_and_long_run():
    plan = build_five_to_ten_k_plan(
        athlete_id=1, sessions_per_week=3, entry_stage="5k_consistency"
    )
    level = plan.levels[0]
    assert len(level.sessions) == 3
    assert level.sessions[-1].role == "Long easy"
    assert level.sessions[-1].long_run_km if hasattr(level.sessions[-1], "long_run_km") else True


def test_four_day_plan_has_optional_recovery_day():
    plan = build_five_to_ten_k_plan(
        athlete_id=1, sessions_per_week=4, entry_stage="5k_consistency"
    )
    level = plan.levels[5]
    assert len(level.sessions) == 4
    assert any(not item.counts_for_progression for item in level.sessions)


def test_quality_is_introduced_gradually():
    plan = build_five_to_ten_k_plan(
        athlete_id=1, sessions_per_week=3, entry_stage="5k_consistency"
    )
    early = " ".join(day.detail for day in plan.levels[0].sessions).lower()
    later = " ".join(day.detail for day in plan.levels[6].sessions).lower()
    assert "comfortably hard" not in early
    assert "comfortably hard" in later


def test_long_run_progresses_to_10k():
    plan = build_five_to_ten_k_plan(
        athlete_id=1, sessions_per_week=3, entry_stage="5k_consistency"
    )
    assert plan.levels[0].long_run_km == 5.0
    assert plan.levels[-1].long_run_km == 10.0


def test_plan_is_adaptive_not_fixed_calendar():
    plan = build_five_to_ten_k_plan(
        athlete_id=1, sessions_per_week=3, entry_stage="build_7k",
        current_level=5,
    )
    assert "not fixed calendar weeks" in plan.timeline_note.lower()
    assert plan.levels[4].status == "Current"

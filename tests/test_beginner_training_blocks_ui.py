from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "ui" / "training_blocks.py").read_text(encoding="utf-8")


def test_training_blocks_detects_active_couch_to_5k_before_history_requirements():
    journey_pos = SOURCE.index("journey = get_active_runner_journey(athlete_id)")
    hierarchy_pos = SOURCE.index("history, hierarchy = _cached_foundation(")
    assert journey_pos < hierarchy_pos
    assert "_show_beginner_training_plan(athlete_id, journey)" in SOURCE


def test_beginner_plan_renders_all_12_levels():
    assert "All 12 progression levels" in SOURCE
    assert "build_beginner_week_timeline_html" in SOURCE
    assert "plan.weeks[selected - 1]" in SOURCE


def test_beginner_current_level_is_highlighted():
    assert "is-current" in SOURCE
    assert "CURRENT LEVEL" in SOURCE


def test_beginner_has_progress_repeat_and_step_back_controls():
    assert "Step back one level" in SOURCE
    assert "Repeat this level" in SOURCE
    assert "Progress to next level" in SOURCE


def test_beginner_level_controls_are_audited_through_runner_journey():
    assert "set_active_journey_week(" in SOURCE
    assert 'decision="step_back"' in SOURCE
    assert 'decision="repeat"' in SOURCE
    assert 'decision="progress_early"' in SOURCE


def test_beginner_plan_does_not_require_target_date_or_running_history():
    beginner_branch = SOURCE[
        SOURCE.index("journey = get_active_runner_journey(athlete_id)"):
        SOURCE.index("data_version = get_athlete_cache_version(athlete_id)")
    ]
    assert "target_date" not in beginner_branch
    assert "_cached_foundation" not in beginner_branch


def test_existing_history_led_training_block_path_remains_present():
    assert "design_training_block(" in SOURCE
    assert "build_training_block_overview_html" in SOURCE
    assert "_save_design(" in SOURCE


def test_training_block_cache_schema_bumped():
    assert "TRAINING_BLOCK_CACHE_SCHEMA = 2" in SOURCE

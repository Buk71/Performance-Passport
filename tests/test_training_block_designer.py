import datetime
from functools import lru_cache

import pytest

from core.goals import build_goal_hierarchy, build_goal_hierarchy_from_records
from core.training_block_designer import (
    TrainingBlockPreferences,
    build_training_history_profile,
    design_training_block,
    preferences_from_dict,
    preferences_to_dict,
    recommend_preferences,
    validate_preferences,
)


REFERENCE_DATE = datetime.date(2026, 8, 14)


@lru_cache(maxsize=2)
def _foundation(athlete_id):
    history = build_training_history_profile(athlete_id)
    hierarchy = build_goal_hierarchy(athlete_id, reference_date=REFERENCE_DATE)
    return history, hierarchy


def test_richard_defaults_come_from_real_sustainable_history():
    history, _ = _foundation(1)
    preferences = recommend_preferences(history)

    assert history.athlete_name == "Richard Burke"
    assert history.recent_days_per_week == 5.8
    assert history.recent_miles_per_week == 39.7
    assert history.typical_long_run_miles == 11.5
    assert history.supported_sessions_per_week == 2
    assert history.inferred_long_run_day == "Sunday"
    assert len(preferences.running_days) == 6
    assert len(preferences.session_days) == 2
    assert preferences.max_weekly_miles == 43


def test_richard_block_progresses_then_tapers_into_primary_goal():
    history, hierarchy = _foundation(1)
    design = design_training_block(
        history=history,
        hierarchy=hierarchy,
        preferences=recommend_preferences(history),
        reference_date=REFERENCE_DATE,
    )

    assert design.block_type == "10K"
    assert design.start_date == "2026-08-17"
    assert design.end_date == "2026-11-29"
    assert len(design.weeks) == 15
    assert design.weeks[-1].phase == "Race"
    assert design.weeks[-2].phase == "Taper"
    assert design.weeks[-1].target_miles < design.peak_miles
    assert any(week.is_cutback for week in design.weeks)
    assert design.peak_miles <= 43
    assert any(day.session_type == "Primary race" for day in design.weeks[-1].days)


def test_jo_keeps_her_own_frequency_volume_and_goal():
    history, hierarchy = _foundation(3)
    design = design_training_block(
        history=history,
        hierarchy=hierarchy,
        preferences=recommend_preferences(history),
        reference_date=REFERENCE_DATE,
    )

    assert history.athlete_name == "Joanne Burke"
    assert history.recent_days_per_week == 4.8
    assert history.recent_miles_per_week == 27.5
    assert history.supported_sessions_per_week == 1
    assert design.primary_goal_name == "Sub 45"
    assert design.end_date == "2026-10-11"
    assert len(design.weeks) == 8
    assert design.peak_miles < 30


def test_custom_preferences_surface_spacing_and_load_warnings():
    history, _ = _foundation(1)
    preferences = TrainingBlockPreferences(
        running_days=("Monday", "Tuesday", "Saturday", "Sunday"),
        long_run_day="Sunday",
        session_days=("Monday", "Tuesday", "Saturday"),
        strength_days=("Saturday",),
        max_weekly_miles=52,
        recovery_note="Protect calf",
    )
    warnings = validate_preferences(preferences, history)

    assert any("back to back" in warning for warning in warnings)
    assert any("above the recent history-supported rhythm" in warning for warning in warnings)
    assert any("more than 20%" in warning for warning in warnings)
    assert any("Strength overlaps" in warning for warning in warnings)


def test_secondary_race_is_placed_and_replaces_normal_quality():
    history, _ = _foundation(1)
    goals = [
        {
            "id": 10, "athlete_id": 1, "goal_name": "Main 10K",
            "goal_type": "Race time", "distance_m": 10000,
            "target_time_s": 2340, "target_date": "2026-11-29",
            "race_name": "Main 10K", "priority": "Primary",
            "status": "Active", "motivation": None, "training_block_id": None,
        },
        {
            "id": 11, "athlete_id": 1, "goal_name": "Tune-up 5K",
            "goal_type": "Race time", "distance_m": 5000,
            "target_time_s": 1140, "target_date": "2026-09-12",
            "race_name": "Tune-up 5K", "priority": "Secondary",
            "status": "Active", "motivation": None, "training_block_id": None,
        },
    ]
    hierarchy = build_goal_hierarchy_from_records(
        1, goals, reference_date=REFERENCE_DATE,
    )
    design = design_training_block(
        history=history,
        hierarchy=hierarchy,
        preferences=recommend_preferences(history),
        reference_date=REFERENCE_DATE,
    )
    event_week = next(week for week in design.weeks if week.event_name)

    assert design.secondary_goal_ids == (11,)
    assert event_week.event_name == "Tune-up 5K"
    assert any(day.session_type == "Secondary race" for day in event_week.days)
    assert event_week.session_count == 1


def test_preferences_round_trip_without_losing_weekdays():
    history, _ = _foundation(1)
    expected = recommend_preferences(history)
    assert preferences_from_dict(preferences_to_dict(expected)) == expected


def test_a_primary_goal_is_required():
    history, _ = _foundation(1)
    hierarchy = build_goal_hierarchy_from_records(
        1, [], reference_date=REFERENCE_DATE,
    )
    with pytest.raises(ValueError, match="Active Primary"):
        design_training_block(
            history=history,
            hierarchy=hierarchy,
            preferences=recommend_preferences(history),
            reference_date=REFERENCE_DATE,
        )

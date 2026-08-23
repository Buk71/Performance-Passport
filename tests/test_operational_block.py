import datetime
from functools import lru_cache

from core.operational_block import (
    OperationalActivity,
    _has_trustworthy_recorded_intervals,
    _load_operational_activities,
    compose_operational_week,
)
from tests.test_classification_integration import _real_activity_facts
from core.session_intelligence import classify_session


def _plan():
    return {
        "weeks": [{
            "week_number": 1,
            "start_date": "2026-08-10",
            "end_date": "2026-08-16",
            "target_miles": 30.0,
            "phase": "Build",
            "emphasis": "Threshold rhythm",
            "days": [
                {"day": "Monday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Tuesday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Wednesday", "session_type": "Threshold", "detail": "6 mi total", "is_hard": True},
                {"day": "Thursday", "session_type": "Recovery", "detail": "4 mi easy", "is_hard": False},
                {"day": "Friday", "session_type": "Threshold", "detail": "5 mi total", "is_hard": True},
                {"day": "Saturday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Sunday", "session_type": "Long run", "detail": "10 mi", "is_hard": False},
            ],
        }]
    }


def _activity(activity_id, date, family, miles, title=None, reliable=True):
    labels = {
        "easy": "Easy / aerobic", "recovery": "Recovery",
        "quality": "Structured workout", "threshold": "Threshold",
        "long": "Long run", "race": "Race",
    }
    return OperationalActivity(
        activity_id=activity_id, activity_date=date,
        title=title or labels[family], family=family,
        family_label=labels[family], distance_miles=miles if reliable else None,
        moving_time_s=2400.0, confidence=.9, distance_reliable=reliable,
    )


def test_saved_week_matches_purpose_distance_and_commitments():
    activities = (
        _activity(1, "2026-08-11", "easy", 5.0),
        _activity(2, "2026-08-12", "threshold", 6.0),
        _activity(3, "2026-08-13", "recovery", 4.0),
        _activity(4, "2026-08-16", "long", 10.0),
    )
    week = compose_operational_week(
        athlete_id=1, training_block_id=9, block_name="Test block",
        plan=_plan(), activities=activities, today=datetime.date(2026, 8, 16),
    )

    assert week.completed_miles == 25.0
    assert week.completed_run_days == 4
    assert week.completed_quality_sessions == 1
    assert week.planned_quality_sessions == 2
    assert week.long_run_completed is True
    assert week.next_run.session_type == "Week complete"
    assert any(item.title == "Do not chase missed quality" for item in week.suggestions)


def test_completed_run_today_is_not_recommended_twice():
    week = compose_operational_week(
        athlete_id=1, training_block_id=9, block_name="Test block",
        plan=_plan(), activities=(_activity(1, "2026-08-12", "threshold", 6.0),),
        today=datetime.date(2026, 8, 12),
    )

    assert week.next_run.day == "Thursday"
    assert week.next_run.family == "recovery"


def test_unreliable_distance_completes_day_without_inventing_miles():
    week = compose_operational_week(
        athlete_id=1, training_block_id=9, block_name="Test block",
        plan=_plan(),
        activities=(_activity(1, "2026-08-11", "easy", 5.0, reliable=False),),
        today=datetime.date(2026, 8, 11),
    )

    assert week.days[1].status == "Complete"
    assert week.completed_miles == 0.0
    assert week.unreliable_distance_count == 1
    assert "count by time" in week.summary


@lru_cache(maxsize=1)
def _richard_august_ninth():
    return _load_operational_activities(
        1, datetime.date(2026, 8, 9), datetime.date(2026, 8, 9)
    )


def test_real_recognition_identifies_richards_long_run():
    activities = _richard_august_ninth()
    slr = next(activity for activity in activities if "SLR 12" in activity.title)

    assert slr.family == "long"
    assert slr.distance_miles is not None


def test_jo_real_unnamed_interval_workout_uses_recorded_reps_not_easy_average():
    activities = _load_operational_activities(
        3, datetime.date(2025, 9, 2), datetime.date(2025, 9, 2)
    )
    workout = next(activity for activity in activities if activity.activity_id == 5119)

    assert workout.family == "quality"
    assert workout.family_label == "5 × 1 km workout"
    assert workout.title == "5 × 1 km workout"
    assert workout.distance_miles == 4.41


def test_long_run_auto_laps_cannot_pass_active_week_interval_verification():
    facts = _real_activity_facts(3737)
    session = classify_session(facts)

    assert _has_trustworthy_recorded_intervals(session, facts.raw_json_text) is False

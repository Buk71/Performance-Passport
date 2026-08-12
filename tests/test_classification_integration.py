from __future__ import annotations

import sqlite3

from core.database import get_effective_athlete_thresholds
from core.home_latest_run import _load_runs
from core.performance_recognition import (
    build_recognition_index,
    recognition_key,
)
from core.session import SessionPurpose, SessionType
from core.session_intelligence import ActivityFacts, classify_session
from core.workout_title_intent import parse_workout_title


SCREENSHOT_TITLE = (
    "Progressive warm up, drills, 6 x 100m strides: "
    "1,2,3,4,5,4,3,2,1 at 5k pace off 60 seconds. 32c today"
)


def _real_activity_facts(activity_id: int) -> ActivityFacts:
    connection = sqlite3.connect("database/performance_passport.db")
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM activities WHERE id = ?",
        (activity_id,),
    ).fetchone()
    connection.close()

    assert row is not None
    distance = float(row["distance_m"] or 0.0)
    distance_km = distance / 1000.0 if distance > 250 else distance
    thresholds = get_effective_athlete_thresholds(int(row["athlete_id"]))

    return ActivityFacts(
        activity_id=int(row["id"]),
        athlete_id=int(row["athlete_id"]),
        activity_date=row["activity_date"],
        title=row["title"],
        sport_id=str(row["sport_id"]),
        distance_km=distance_km,
        moving_time_s=row["moving_time_s"],
        elapsed_time_s=row["elapsed_time_s"],
        avg_hr=row["avg_hr"],
        max_hr=row["max_hr"],
        elevation_up_m=row["elevation_up_m"],
        temperature_c=row["temperature_c"],
        humidity=row["humidity"],
        wind_speed=row["wind_speed"],
        route_name=row["route_name"],
        raw_json_text=row["raw_json"],
        athlete_lt2_hr=thresholds.get("lt2_hr"),
        athlete_max_hr=thresholds.get("athlete_max_hr"),
    )


def test_real_august_ladder_uses_splits_before_summary_averages():
    session = classify_session(_real_activity_facts(3177))

    assert session.session_type == SessionType.STRUCTURED_WORKOUT
    assert session.confidence == 0.98
    assert session.metadata["classification_scores"] == {
        "continuous_run": 37.0,
        "structured_workout": 100.0,
        "race": 24.5,
    }
    split_evidence = session.metadata["split_classification"]
    assert split_evidence["split_count"] == 35
    assert split_evidence["recovery_count"] == 6
    assert split_evidence["unknown_recovery_count"] == 8


def test_full_strava_title_is_structured_even_without_splits():
    intent = parse_workout_title(SCREENSHOT_TITLE)
    assert intent is not None
    assert intent.total_reps == 6
    assert intent.recovery_s == 60

    session = classify_session(
        ActivityFacts(
            activity_id=999999,
            athlete_id=1,
            activity_date="2025-08-13",
            title=SCREENSHOT_TITLE,
            sport_id="965611",
            distance_km=8.92,
            moving_time_s=2148.0,
            elapsed_time_s=3531.0,
            avg_hr=146.0,
            max_hr=166.0,
            elevation_up_m=18.9,
            temperature_c=32.0,
            humidity=None,
            wind_speed=None,
            route_name=None,
            raw_json_text=None,
            athlete_lt2_hr=162.0,
            athlete_max_hr=170.0,
        )
    )

    assert session.session_type == SessionType.STRUCTURED_WORKOUT
    assert session.purpose == SessionPurpose.VO2
    assert (
        session.metadata["classification_scores"]["structured_workout"]
        > session.metadata["classification_scores"]["continuous_run"]
    )


def test_recognition_uses_shared_split_aware_classification():
    runs = _load_runs(1)
    index = build_recognition_index(runs, athlete_id=1)
    target = next(
        run
        for run in runs
        if run.activity_date == "2025-08-13"
        and abs(float(run.distance_km or 0.0) - 8.92) < 0.001
    )

    recognition = index[recognition_key(target)]
    assert recognition.category_key == "workout"
    assert recognition.category_label == "Structured Workout"
    assert recognition.provisional is True

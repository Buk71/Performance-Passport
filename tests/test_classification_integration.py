from __future__ import annotations

from dataclasses import replace
import json
import sqlite3

from core.database import get_effective_athlete_thresholds
from core.home_latest_run import _load_runs
from core.performance_recognition import (
    build_recognition_index,
    recognition_key,
)
from core.session import SessionPurpose, SessionType
from core.session_intelligence import (
    ActivityFacts,
    RELIABLE_SESSION_CONFIDENCE,
    classify_session,
)
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


def test_jo_unnamed_six_by_one_k_retains_real_work_and_recovery_evidence():
    historical_facts = _real_activity_facts(5119)
    tuesday_splits = (
        "U0.400|2:27-U1.000|4:27-U0.165|2:00-U1.000|4:21-"
        "U0.163|2:00-U1.000|4:17-U0.165|2:00-U1.000|4:20-"
        "U0.174|2:00-U1.000|4:23-U0.177|2:00-U1.000|4:31-"
        "U0.149|2:00-U1.150|6:39"
    )
    session = classify_session(
        replace(
            historical_facts,
            activity_id=990052,
            activity_date="2026-08-18",
            title="",
            distance_km=8.54,
            moving_time_s=2844.0,
            elapsed_time_s=2844.0,
            avg_hr=155.0,
            max_hr=180.0,
            raw_json_text=json.dumps({"splits": tuesday_splits}),
        )
    )

    assert session.session_type == SessionType.STRUCTURED_WORKOUT
    assert session.confidence < RELIABLE_SESSION_CONFIDENCE
    assert session.metadata["split_classification"]["recovery_count"] == 5
    assert session.metadata["classification_scores"]["structured_workout"] == 66.0
    assert any(
        "5 recorded recovery segment" in reason
        for reason in session.metadata["classification_reasons"]["structured_workout"]
    )


def test_richard_historical_trail_auto_laps_do_not_rewrite_long_run_history():
    session = classify_session(_real_activity_facts(3737))

    assert session.confidence < RELIABLE_SESSION_CONFIDENCE


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

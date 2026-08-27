"""Real-athlete regressions from the first independent coaching review."""

from __future__ import annotations

from functools import lru_cache
import sqlite3

from core.coach_brain import CoachBrain
from core.database import get_connection, get_effective_athlete_thresholds
from core.progress import build_progress_summary
from core.session import SessionPurpose, SessionType
from core.session_intelligence import ActivityFacts, classify_session


def _paul_activity_facts(activity_id: int) -> ActivityFacts:
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM activities WHERE id = ? AND athlete_id = 4",
        (activity_id,),
    ).fetchone()
    connection.close()

    assert row is not None, f"Paul's regression activity {activity_id} is missing"
    thresholds = get_effective_athlete_thresholds(4)
    distance = float(row["distance_m"] or 0.0)

    return ActivityFacts(
        activity_id=int(row["id"]),
        athlete_id=4,
        activity_date=row["activity_date"],
        title=row["title"] or "",
        sport_id=str(row["sport_id"]),
        distance_km=distance / 1000.0 if distance > 250 else distance,
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


@lru_cache(maxsize=1)
def _paul_coaching_evidence():
    brain = CoachBrain(4)
    return {item.key: item for item in brain.build_evidence().items}


def test_easy_running_with_finishing_strides_is_not_a_workout():
    session = classify_session(_paul_activity_facts(10599))

    assert session.session_type == SessionType.CONTINUOUS_RUN
    assert session.purpose == SessionPurpose.EASY
    assert session.metadata["activity_intent"] == "easy_with_strides"
    assert session.metadata["stride_details"]["stride_count"] == 10


def test_genuine_ten_kilometre_race_beats_ordinary_auto_laps():
    session = classify_session(_paul_activity_facts(9772))

    assert session.session_type == SessionType.RACE
    assert session.purpose == SessionPurpose.RACE


def test_specialist_coaches_select_evidence_for_their_actual_role():
    evidence = _paul_coaching_evidence()

    assert evidence["workout"].metadata["activity_id"] != 10599
    assert evidence["recent_race"].metadata["activity_id"] != 10599
    assert evidence["recent_race"].metadata["activity_date"] >= "2026-02-01"
    assert evidence["recent_race"].metadata["projection_distance_km"] in {
        5.0, 10.0,
    }
    assert evidence["threshold"].metadata["selected_activity_id"] == 9945


def test_threshold_coach_does_not_claim_five_k_race_pace_is_threshold():
    threshold = _paul_coaching_evidence()["threshold"].metadata

    floor = threshold["recent_five_k_threshold_floor_seconds_per_km"]
    assert floor is not None
    assert threshold["threshold_pace_seconds_per_km"] >= floor - 0.1
    assert floor >= 240.0


def test_passport_uses_real_threshold_work_instead_of_slow_easy_running():
    progress = build_progress_summary(4)

    assert progress is not None
    assert progress.threshold.available is True
    assert 230.0 <= progress.threshold.current_pace_s_per_km <= 250.0
    assert progress.threshold.total_sample_size >= 4
    assert progress.threshold.current_conditions

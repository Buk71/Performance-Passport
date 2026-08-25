"""Verified Richard, Jo, and Paul sessions drive the shared live classifier."""

from __future__ import annotations

import pytest

from core.database import clear_activity_override, save_activity_override
from core.recognition_audit import audit_activity
from core.session import CoachRoute, SessionPurpose, SessionType
from core.session_intelligence import RELIABLE_SESSION_CONFIDENCE, classify_session
from tests.test_classification_integration import _real_activity_facts


@pytest.mark.parametrize(
    "athlete_id, activity_id",
    (
        (1, 3742),  # Repetitions with stopped-watch recovery.
        (1, 3559),  # 3 x 3 km off 90 seconds.
        (1, 3493),  # 3 x 3.2 km off 90 seconds.
        (3, 5119),  # Unnamed 5 x 1 km.
        (3, 5474),  # Repeated sustained work and recovery.
        (3, 5399),  # 7 x 800 m off 1 minute.
        (3, 5391),  # 7 x 800 m off 1 minute.
        (3, 5351),  # Sustained grass intervals.
        (3, 5312),  # 800 m repetitions.
        (4, 9879),  # Paul's genuine Blizard pyramid.
    ),
)
def test_confirmed_real_workouts_now_reach_the_live_coaching_confidence_floor(
    athlete_id,
    activity_id,
):
    session = classify_session(_real_activity_facts(activity_id))
    audit = audit_activity(athlete_id, activity_id)

    assert session.session_type == SessionType.STRUCTURED_WORKOUT
    assert session.confidence >= RELIABLE_SESSION_CONFIDENCE
    assert session.metadata["verified_session_evidence"]["trustworthy_intervals"]
    assert CoachRoute.WORKOUT in session.suitable_coaches
    assert audit.audit_status == "verified"


@pytest.mark.parametrize("activity_id", (5559, 5299))
def test_jos_alternating_sessions_are_real_workouts_not_easy_auto_laps(activity_id):
    session = classify_session(_real_activity_facts(activity_id))

    assert session.session_type == SessionType.STRUCTURED_WORKOUT
    assert session.purpose == SessionPurpose.FARTLEK
    assert session.metadata["activity_intent"] == "alternating_workout"
    assert session.confidence >= RELIABLE_SESSION_CONFIDENCE


@pytest.mark.parametrize("activity_id", (3573, 3496))
def test_richards_short_pickups_stay_out_of_race_prediction_workouts(activity_id):
    session = classify_session(_real_activity_facts(activity_id))

    assert session.session_type == SessionType.CONTINUOUS_RUN
    assert session.purpose == SessionPurpose.EASY
    assert session.metadata["activity_intent"] == "easy_with_pickups"
    assert session.metadata["verified_session_evidence"]["pickup_count"] >= 5
    assert CoachRoute.WORKOUT not in session.suitable_coaches


@pytest.mark.parametrize(
    "activity_id",
    (9360, 3737, 3590, 5453, 5447, 5403, 9876, 10443),
)
def test_verified_easy_long_and_interrupted_auto_laps_remain_continuous(activity_id):
    session = classify_session(_real_activity_facts(activity_id))

    assert session.session_type == SessionType.CONTINUOUS_RUN
    assert CoachRoute.WORKOUT not in session.suitable_coaches


def test_pauls_race_keeps_race_coach_ownership():
    session = classify_session(_real_activity_facts(9772))

    assert session.session_type == SessionType.RACE
    assert session.purpose == SessionPurpose.RACE
    assert CoachRoute.RACE in session.suitable_coaches
    assert CoachRoute.WORKOUT not in session.suitable_coaches


def test_explicit_workout_override_beats_automatic_pickup_protection():
    try:
        save_activity_override(1, 3573, session_intent="workout")
        session = classify_session(_real_activity_facts(3573))

        assert session.session_type == SessionType.STRUCTURED_WORKOUT
        assert session.metadata["manual_override"] == "workout"
        assert "activity_intent" not in session.metadata
        assert CoachRoute.WORKOUT in session.suitable_coaches
    finally:
        clear_activity_override(1, 3573)


def test_explicit_easy_override_beats_verified_interval_structure():
    try:
        save_activity_override(3, 5399, session_intent="easy")
        session = classify_session(_real_activity_facts(5399))

        assert session.session_type == SessionType.CONTINUOUS_RUN
        assert session.metadata["manual_override"] == "easy"
        assert session.metadata["activity_intent"] == "easy"
        assert CoachRoute.WORKOUT not in session.suitable_coaches
    finally:
        clear_activity_override(3, 5399)

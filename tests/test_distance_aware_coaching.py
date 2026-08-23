"""Keep strong endurance workouts from being overridden by short race history."""

from __future__ import annotations

import datetime
from functools import lru_cache
import json

from core.coach_brain import CoachBrain
from core.evidence_providers.base import EvidenceContext
from core.evidence_providers.workout import (
    WorkoutEvidenceProvider,
    _endurance_workout_rank,
)
from core.workout_dna import build_workout_dna
from core.workout_similarity import (
    SimilarityResult,
    SimilarWorkoutMatch,
    predict_from_similarity,
)
from core.workout_title_intent import build_title_intent_evidence


RICHARD_MIXED_SESSION_TITLE = (
    "4 x strides, 6 x 1200 off 90, 4 x 200 off 30"
)
RICHARD_MIXED_SESSION_SPLITS = (
    "I0.095|0:20||0-I0.013|0:03||0-"
    "I0.095|0:18||0-I0.013|0:04||0-"
    "I0.093|0:17||0-I0.016|0:04||0-"
    "I0.098|0:17||0-I0.012|0:05||0-"
    "I1.199|4:32||0-I0.011|0:05||0-"
    "I1.194|4:35||0-I0.013|0:04||0-"
    "I1.202|4:33||0-I0.011|0:03||0-"
    "I1.196|4:30||0-I0.010|0:04||0-"
    "I1.197|4:36||0-I0.013|0:04||0-"
    "I1.205|4:28||0-I0.013|0:04||0-"
    "I0.193|0:37||0-I0.017|0:04||0-"
    "I0.194|0:37||0-I0.013|0:05||0-"
    "I0.202|0:37||0-I0.013|0:04||0-"
    "I0.193|0:36||0-I0.013|0:03||0"
)


@lru_cache(maxsize=1)
def _richard_latest_session_evidence():
    return build_title_intent_evidence(
        RICHARD_MIXED_SESSION_TITLE,
        json.dumps({"splits": RICHARD_MIXED_SESSION_SPLITS}),
    )


@lru_cache(maxsize=1)
def _richard_half_marathon_workout():
    goal = {
        "id": None,
        "athlete_id": 1,
        "goal_name": "Half-marathon evidence check",
        "goal_type": "Half Marathon",
        "distance_m": 21097.5,
        "target_time_s": 5400,
        "target_date": "2026-11-29",
        "priority": "Primary",
        "status": "Active",
    }
    return WorkoutEvidenceProvider().build(
        EvidenceContext(athlete_id=1, goal=goal)
    )


def test_half_marathon_uses_relevant_work_instead_of_linked_short_races():
    item = _richard_half_marathon_workout()
    distance_prediction = item.metadata["distance_relevant_prediction"]
    historical_prediction = item.metadata["similarity_prediction"]

    assert item.metadata["prediction_source"] == "distance_relevant_workout"
    assert 5200 <= item.predicted_seconds <= 5500
    assert historical_prediction["central_seconds"] > 5000
    assert all(
        outcome["race_age_days"] <= 180
        and outcome["race_distance_km"] >= 21.0975 * 0.45
        and "trail" not in outcome["race_title"].lower()
        for outcome in historical_prediction["outcomes"]
    )
    assert distance_prediction["representative_race_count"] < 2
    assert distance_prediction["historical_outcome_count"] == len(
        historical_prediction["outcomes"]
    )


def test_endurance_prediction_stays_auditable_and_uses_actual_half_pb():
    item = _richard_half_marathon_workout()
    prediction = item.metadata["distance_relevant_prediction"]

    assert prediction["pb_anchor_seconds"] == 5360.0
    assert any(
        estimate["activity_id"] == 9358
        and estimate["relevant_work_distance_km"] >= 3.7
        for estimate in prediction["estimates"]
    )
    assert "Distance-specific workout prediction: 1:" in item.summary


def test_existing_ten_kilometre_workout_prediction_remains_unchanged():
    evidence = CoachBrain(1).build_evidence()
    workout = next(item for item in evidence.items if item.key == "workout")

    assert workout.metadata["prediction_source"] == "pb_shape"
    assert workout.predicted_seconds == 2350.3


def test_introductory_strides_do_not_hide_the_real_six_by_twelve_hundred():
    result = _richard_latest_session_evidence()

    assert result is not None
    assert result["metadata"]["match_ratio"] == 1.0
    assert [component["rep_count"] for component in result["components"]] == [6, 4]
    long_work, short_work = result["components"]
    assert round(long_work["total_work_distance_km"], 3) == 7.193
    assert round(long_work["average_pace_s_per_km"], 1) == 227.2
    assert long_work["component_type"] == "long_intervals"
    assert long_work["recovery_duration_s"] == 90.0
    assert short_work["recovery_duration_s"] == 30.0


def test_real_mixed_workout_has_quality_dna_not_empty_aerobic_support():
    result = _richard_latest_session_evidence()
    dna = build_workout_dna(
        phases=result["metadata"]["phases"],
        activity_id=10616,
        athlete_id=1,
        execution_score=88.5,
        recognition_confidence=0.80,
        phase_confidence=result["metadata"]["confidence"],
        source=result["metadata"]["source"],
    )

    assert dna.primary_system in {"threshold", "speed"}
    assert dna.quality_phase_count == 2
    assert round(dna.total_quality_distance_km, 3) == 7.975
    assert "aerobic" in dna.secondary_systems


def test_half_marathon_rank_favours_recent_real_endurance_work():
    reference = datetime.date(2026, 8, 16)
    latest = {
        "trust_score": 94.8,
        "activity_date": datetime.date(2026, 8, 15),
        "phase_components": _richard_latest_session_evidence()["components"],
    }
    older = {
        "trust_score": 100.0,
        "activity_date": datetime.date(2026, 8, 5),
        "phase_components": [
            {
                "component_type": "threshold",
                "total_work_distance_km": 7.836,
                "average_pace_s_per_km": 230.0,
                "confidence": 0.96,
            }
        ],
    }

    assert _endurance_workout_rank(latest, 21.0975, reference) > (
        _endurance_workout_rank(older, 21.0975, reference)
    )


def test_endurance_history_excludes_old_short_and_trail_races():
    def linked_race(activity_id, *, race_date, race_distance, title):
        return SimilarWorkoutMatch(
            workout_activity_id=activity_id + 100,
            workout_date=race_date,
            workout_signature="threshold_6x1200m",
            similarity=0.85,
            race_activity_id=activity_id,
            race_date=race_date,
            race_title=title,
            race_distance_km=race_distance,
            race_time_s=2400.0 if race_distance < 11 else 5400.0,
            days_after=10,
            link_confidence=0.90,
            reasons=(),
            differences=(),
            feature_scores={},
        )

    matches = (
        linked_race(1, race_date="2023-12-16", race_distance=10.0, title="Old race"),
        linked_race(2, race_date="2026-08-02", race_distance=5.0, title="Short race"),
        linked_race(3, race_date="2026-07-12", race_distance=21.1, title="Trail Running"),
        linked_race(4, race_date="2026-07-24", race_distance=10.0, title="Road 10K"),
    )
    result = SimilarityResult(
        athlete_id=1,
        current_activity_id=10616,
        match_count=len(matches),
        linked_history_count=len(matches),
        distinct_workout_count=len(matches),
        distinct_race_count=len(matches),
        confidence=0.85,
        matches=matches,
        limitations=(),
    )

    prediction = predict_from_similarity(
        result,
        goal_distance_km=21.0975,
        reference_date=datetime.date(2026, 8, 16),
        road_goal=True,
    )

    assert prediction is not None
    assert prediction["distinct_race_count"] == 1
    assert prediction["outcomes"][0]["race_activity_id"] == 4

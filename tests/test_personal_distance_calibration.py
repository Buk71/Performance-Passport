"""Personal distance calibration stays cautious, auditable and athlete-led."""

from __future__ import annotations

import datetime
from functools import lru_cache

from core.coach_brain import CoachBrain
from core.distance_calibration import (
    build_personal_pb_shape_bridge,
    personal_pb_ratio_projection,
)
from core.evidence_providers.base import EvidenceContext
from core.evidence_providers.race import RaceEvidenceProvider
from core.evidence_providers.workout import WorkoutEvidenceProvider
from core.home_prediction_matrix import build_home_prediction_matrix
from core.home_predictions import build_home_predictions
from core.prediction import PredictionEngine


HALF_GOAL = {
    "id": None,
    "goal_name": "Half-marathon calibration",
    "goal_type": "Half Marathon",
    "distance_m": 21097.5,
    "target_time_s": None,
    "race_name": "",
}


@lru_cache(maxsize=3)
def _half_evidence(athlete_id: int):
    return CoachBrain(athlete_id).build_evidence(HALF_GOAL)


def test_personal_bridge_carries_shape_percentage_not_generic_riegel():
    result = build_personal_pb_shape_bridge(
        source_distance_km=10.0,
        target_distance_km=21.0975,
        source_pb_seconds=2400.0,
        source_current_seconds=2448.0,
        source_confidence=0.70,
        target_pb_seconds=5400.0,
        target_pb_date="2026-03-15",
        reference_date=datetime.date(2026, 8, 16),
    )

    assert result is not None
    assert result.shape_ratio == 1.02
    assert result.central_seconds == 5508.0
    assert 0.35 <= result.confidence < 0.70
    assert result.low_seconds < result.central_seconds < result.high_seconds


def test_personal_bridge_withholds_stale_or_non_comparable_evidence():
    common = dict(
        source_distance_km=10.0,
        target_distance_km=21.0975,
        source_pb_seconds=2400.0,
        source_confidence=0.70,
        target_pb_seconds=5400.0,
        reference_date=datetime.date(2026, 8, 16),
    )

    assert build_personal_pb_shape_bridge(
        **common,
        source_current_seconds=2448.0,
        target_pb_date="2023-01-01",
    ) is None
    assert build_personal_pb_shape_bridge(
        **common,
        source_current_seconds=3000.0,
        target_pb_date="2026-03-15",
    ) is None


def test_personal_pb_ratio_projects_current_ten_k_through_own_endurance():
    result = personal_pb_ratio_projection(
        source_distance_km=10.0,
        target_distance_km=21.0975,
        source_pb_seconds=2408.0,
        source_current_seconds=2401.0,
        target_pb_seconds=5591.0,
    )

    assert result is not None
    assert result["current_to_pb_ratio"] == 0.9971
    assert result["predicted_seconds"] == 5574.7


def test_paul_half_race_coach_uses_recent_actual_half_not_a_slower_five_k():
    item = RaceEvidenceProvider().build(
        EvidenceContext(athlete_id=4, goal=HALF_GOAL)
    )

    assert item.metadata["activity_id"] == 10156
    assert item.metadata["selection_basis"] == "recent_direct_goal_distance"
    assert item.metadata["distance_km"] == 21.1
    assert 5520 <= item.predicted_seconds <= 5580


def test_paul_half_workout_uses_personal_pb_bridge_not_formula_outlier():
    item = WorkoutEvidenceProvider().build(
        EvidenceContext(athlete_id=4, goal=HALF_GOAL)
    )
    bridge = item.metadata["cross_distance_pb_shape_prediction"]

    assert item.metadata["prediction_source"] == "cross_distance_pb_shape"
    assert item.metadata["best_evidence"]["date"] == "2026-07-29"
    assert bridge["source_distance_km"] == 10.0
    assert bridge["source_pb_seconds"] == 2408.0
    assert bridge["target_pb_seconds"] == 5591.0
    assert 5670 <= item.predicted_seconds <= 5710
    assert item.weight < 0.55


def test_paul_threshold_uses_recent_personal_distance_relationship():
    threshold = next(
        item for item in _half_evidence(4).items if item.key == "threshold"
    )
    calibration = threshold.metadata["personal_distance_calibration"]

    assert calibration is not None
    assert calibration["source_pb_seconds"] == 2408.0
    assert calibration["target_pb_seconds"] == 5591.0
    assert 5560 <= threshold.predicted_seconds <= 5590


def test_paul_half_is_plausibly_slower_than_richard_without_forcing_a_match():
    richard_bundle = _half_evidence(1)
    paul_bundle = _half_evidence(4)
    engine = PredictionEngine()
    richard = engine.predict_goal(1, HALF_GOAL, richard_bundle)
    paul = engine.predict_goal(4, HALF_GOAL, paul_bundle)

    assert richard.available and paul.available
    # This is a relationship regression, not a five-second golden value.
    # Both predictions may move as verified evidence develops, but Paul must
    # remain independently plausible rather than being forced to Richard's
    # result or allowed to drift implausibly far away.
    assert 5040 <= richard.predicted_seconds <= 5400
    assert 5400 <= paul.predicted_seconds <= 5760
    assert 120 <= paul.predicted_seconds - richard.predicted_seconds <= 480


def test_richard_and_jo_keep_their_distance_specific_half_workout_routes():
    for athlete_id in (1, 3):
        workout = next(
            item
            for item in _half_evidence(athlete_id).items
            if item.key == "workout"
        )

        assert workout.metadata["prediction_source"] == (
            "distance_relevant_workout"
        )
        assert workout.metadata["cross_distance_pb_shape_prediction"] is None


def test_paul_home_matrix_uses_personal_half_relationship_not_fixed_riegel():
    matrix = build_home_prediction_matrix(
        build_home_predictions(4),
        personal_bests={
            "5k": 1185.0,
            "10k": 2408.0,
            "half_marathon": 5591.0,
        },
    )
    ten_k = next(row for row in matrix.rows if row.key == "10k")
    half = next(row for row in matrix.rows if row.key == "half_marathon")
    ten_k_ideal = next(cell.seconds for cell in ten_k.cells if cell.key == "ideal")
    half_ideal = next(cell.seconds for cell in half.cells if cell.key == "ideal")

    assert ten_k.is_active_distance is True
    assert half_ideal == ten_k_ideal * 5591.0 / 2408.0
    assert 5550 <= half_ideal <= 5600
    assert "verified PB relationship" in matrix.explanation

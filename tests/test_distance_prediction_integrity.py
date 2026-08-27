"""Distance predictions remain direct, conservative and explainable."""

from types import SimpleNamespace

from core.distance_prediction_outlook import (
    DistancePredictionAnchor,
    DistancePredictionOutlook,
)
from core.evidence import EvidenceBundle, EvidenceItem, EvidenceStatus
from core.evidence_providers.race import (
    CandidateScore,
    RaceCandidate,
    _projection_distance_km,
    _wind_adjustment_seconds,
)
from core.home_prediction_matrix import build_home_prediction_matrix
from core.prediction import PredictionEngine


def _candidate(*, distance_km=4.96, wind_speed=10.0):
    import datetime

    return RaceCandidate(
        activity_id=1,
        activity_date=datetime.date(2026, 8, 22),
        title="Flat 5K",
        distance_km=distance_km,
        elapsed_time_s=1157.0,
        moving_time_s=1157.0,
        avg_hr=166.0,
        max_hr=184.0,
        athlete_lt2_hr=170.0,
        athlete_max_hr=190.0,
        elevation_up_m=4.0,
        elevation_down_m=6.0,
        temperature_c=14.0,
        humidity=77.0,
        wind_speed=wind_speed,
        route_name="Flat route",
        official_race_name=None,
        official_distance_m=None,
        official_time_s=None,
        officially_measured=False,
        raw_json={},
    )


def test_gps_short_race_quality_effort_uses_matched_standard_distance():
    selected = CandidateScore(
        candidate=_candidate(),
        total=88.0,
        recency=0.98,
        distance=1.0,
        continuity=1.0,
        effort=0.88,
        official=0.0,
        title=0.0,
        training_penalty=0.0,
        matched_distance_km=5.0,
        age_days=4,
        moving_ratio=1.0,
    )

    distance, normalised = _projection_distance_km(selected)

    assert distance == 5.0
    assert normalised is True


def test_wind_allowance_matches_existing_mixed_exposure_model():
    seconds, details = _wind_adjustment_seconds(
        _candidate(distance_km=21.1, wind_speed=29.0)
    )

    assert 39 <= seconds <= 41
    assert details["wind_adjustment_applied"] is True
    assert details["wind_exposure_assumption"] == "mixed"
    assert details["wind_adjustment_confidence"] == 0.45


def test_recent_direct_race_sets_capability_anchor_without_inflating_confidence():
    items = (
        EvidenceItem(
            key="activity_history",
            title="History",
            summary="Current history",
            status=EvidenceStatus.AVAILABLE,
            confidence=0.9,
            sample_size=100,
            metadata={"latest_activity_date": "2026-08-26"},
        ),
        EvidenceItem(
            key="recent_race",
            title="Race Coach",
            summary="Direct 5K",
            status=EvidenceStatus.AVAILABLE,
            confidence=0.85,
            sample_size=4,
            predicted_seconds=1155.0,
            weight=1.0,
            metadata={
                "activity_date": "2026-08-22",
                "projection_distance_km": 5.0,
                "direct_goal_distance": True,
            },
        ),
        EvidenceItem(
            key="workout",
            title="Workout Coach",
            summary="Cautious workout",
            status=EvidenceStatus.AVAILABLE,
            confidence=0.75,
            sample_size=3,
            predicted_seconds=1200.0,
            weight=0.65,
        ),
        EvidenceItem(
            key="threshold",
            title="Threshold Coach",
            summary="Threshold",
            status=EvidenceStatus.AVAILABLE,
            confidence=0.85,
            sample_size=5,
            predicted_seconds=1185.0,
            weight=0.9,
        ),
    )
    evidence = EvidenceBundle(
        athlete_id=4,
        purpose="goal_prediction",
        items=items,
    )

    result = PredictionEngine().predict_goal(
        4,
        {"id": None, "distance_m": 5000, "target_time_s": None},
        evidence,
    )

    assert result.predicted_seconds == 1155.0
    assert result.confidence <= 0.85
    assert "direct goal-distance" in result.explanation


def test_matrix_prefers_independent_distance_anchors_over_pb_translation():
    predictions = SimpleNamespace(
        athlete_id=4,
        available=True,
        distance_label="10K",
        central_seconds=2405.0,
        confidence=0.85,
        scenarios=(
            SimpleNamespace(key="typical", central_seconds=2420.0),
            SimpleNamespace(key="warm", central_seconds=2445.0),
            SimpleNamespace(key="hilly", central_seconds=2490.0),
            SimpleNamespace(key="windy", central_seconds=2460.0),
        ),
        environment_responses=(),
    )
    values = {
        "5k": ("5K", 5.0, 1155.0, 0.89),
        "10k": ("10K", 10.0, 2405.0, 0.85),
        "half_marathon": ("Half marathon", 21.0975, 5510.0, 0.77),
        "marathon": ("Marathon", 42.195, 12330.0, 0.70),
    }
    outlook = DistancePredictionOutlook(
        athlete_id=4,
        anchors=tuple(
            DistancePredictionAnchor(
                key=key,
                label=label,
                distance_km=distance,
                available=True,
                central_seconds=seconds,
                confidence=confidence,
                evidence_source_count=3,
                source="distance_specific_coaches",
                explanation="Three real coaches",
            )
            for key, (label, distance, seconds, confidence) in values.items()
        ),
    )

    matrix = build_home_prediction_matrix(
        predictions,
        personal_bests={
            "5k": 1185.0,
            "10k": 2408.0,
            "half_marathon": 5591.0,
        },
        distance_outlook=outlook,
    )
    ideal = {
        row.key: next(cell.seconds for cell in row.cells if cell.key == "ideal")
        for row in matrix.rows
    }

    assert ideal == {
        "5k": 1155.0,
        "10k": 2405.0,
        "half_marathon": 5510.0,
        "marathon": 12330.0,
    }
    assert [round(row.confidence, 2) for row in matrix.rows] == [
        0.89, 0.85, 0.77, 0.70,
    ]
    assert [row.readiness_label for row in matrix.rows] == ["", "", "", ""]
    assert "uses its own Race, Workout and Threshold Coach evidence" in (
        matrix.explanation
    )

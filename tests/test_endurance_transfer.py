"""Endurance transfer is bounded, athlete-specific and explainable."""

import datetime

from core.distance_prediction_outlook import DistancePredictionAnchor
from core.endurance_transfer import (
    EnduranceProfile,
    assess_endurance,
    calibrate_endurance_anchors,
)


def _anchor(key, label, distance_km, seconds, confidence):
    return DistancePredictionAnchor(
        key=key,
        label=label,
        distance_km=distance_km,
        available=True,
        central_seconds=seconds,
        confidence=confidence,
        evidence_source_count=3,
        source="distance_specific_coaches",
        explanation="Three specialist opinions.",
    )


def _profile(**overrides):
    values = {
        "athlete_id": 4,
        "reference_date": datetime.date(2026, 8, 26),
        "reliable_run_count_84d": 83,
        "weekly_km_42d": 51.2,
        "weekly_km_56d": 51.3,
        "longest_run_km_56d": 23.9,
        "longest_run_km_84d": 23.9,
        "half_long_run_count_56d": 5,
        "marathon_long_run_count_84d": 1,
        "half_completion_count_365d": 16,
        "marathon_completion_count_730d": 1,
    }
    values.update(overrides)
    return EnduranceProfile(**values)


def test_paul_like_endurance_supports_bounded_half_and_marathon_transfer():
    anchors = (
        _anchor("5k", "5K", 5.0, 1155.2, 0.89),
        _anchor("10k", "10K", 10.0, 2405.1, 0.85),
        _anchor("half_marathon", "Half marathon", 21.0975, 5510.4, 0.77),
        _anchor("marathon", "Marathon", 42.195, 12330.0, 0.77),
    )

    calibrated = calibrate_endurance_anchors(anchors, _profile())
    half = calibrated[2]
    marathon = calibrated[3]

    assert 5420 <= half.central_seconds <= 5430
    assert half.raw_central_seconds == 5510.4
    assert half.transfer_fraction == 0.42
    assert half.readiness_label == "Strong endurance"
    assert 11980 <= marathon.central_seconds <= 12010
    assert 0.31 <= marathon.transfer_fraction <= 0.35
    assert marathon.readiness_label == "Supported endurance"
    assert marathon.confidence < half.confidence
    assert "51 km/week" in marathon.endurance_summary


def test_shorter_distance_speed_does_not_transfer_without_endurance_support():
    anchors = (
        _anchor("10k", "10K", 10.0, 2400.0, 0.85),
        _anchor("half_marathon", "Half marathon", 21.0975, 5700.0, 0.70),
    )
    limited = _profile(
        weekly_km_42d=12.0,
        weekly_km_56d=12.0,
        longest_run_km_56d=8.0,
        longest_run_km_84d=8.0,
        half_long_run_count_56d=0,
        marathon_long_run_count_84d=0,
        half_completion_count_365d=0,
        marathon_completion_count_730d=0,
    )

    calibrated = calibrate_endurance_anchors(anchors, limited)
    half = calibrated[1]

    assert half.central_seconds == 5700.0
    assert half.transfer_fraction == 0.0
    assert half.readiness_label == "Limited endurance"


def test_endurance_assessment_keeps_capability_and_readiness_separate():
    half = assess_endurance(_profile(), "half_marathon")
    marathon = assess_endurance(_profile(), "marathon")

    assert half is not None and marathon is not None
    assert half.score > marathon.score
    assert half.label == "Strong endurance"
    assert marathon.label == "Supported endurance"
    assert "longest run 23.9 km" in marathon.summary


def test_five_and_ten_k_capability_are_never_changed_by_endurance_transfer():
    anchors = (
        _anchor("5k", "5K", 5.0, 1155.2, 0.89),
        _anchor("10k", "10K", 10.0, 2405.1, 0.85),
    )

    calibrated = calibrate_endurance_anchors(anchors, _profile())

    assert calibrated == anchors

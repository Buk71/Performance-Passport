"""Transparent personal calibration between race distances.

The helpers in this module do not infer fitness from population averages.
They carry a current workout-shape change from one distance to another using
the athlete's own verified PB relationship. This is deliberately a fallback:
direct goal-distance races and genuinely distance-relevant workouts remain
stronger evidence.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonalPBShapeBridge:
    source_distance_km: float
    target_distance_km: float
    source_pb_seconds: float
    source_current_seconds: float
    target_pb_seconds: float
    target_pb_date: str
    shape_ratio: float
    central_seconds: float
    low_seconds: float
    high_seconds: float
    confidence: float
    target_pb_age_days: int


def _as_date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def build_personal_pb_shape_bridge(
    *,
    source_distance_km: float,
    target_distance_km: float,
    source_pb_seconds: float,
    source_current_seconds: float,
    source_confidence: float,
    target_pb_seconds: float,
    target_pb_date: str | None,
    reference_date: datetime.date,
) -> PersonalPBShapeBridge | None:
    """Transfer a current PB-shape ratio to a longer target distance.

    For example, if current 10K workout shape is 2% behind the athlete's
    verified 10K PB, their verified half-marathon PB is also moved 2% slower.
    This is more personal than a generic conversion while remaining cautious:
    short-distance fitness does not by itself prove endurance readiness.
    """
    values = (
        source_distance_km,
        target_distance_km,
        source_pb_seconds,
        source_current_seconds,
        target_pb_seconds,
    )
    if any(value <= 0 for value in values):
        return None
    if target_distance_km <= source_distance_km:
        return None
    if not 0.0 < source_confidence <= 1.0:
        return None

    pb_date = _as_date(target_pb_date)
    if pb_date is None:
        return None
    age_days = (reference_date - pb_date).days
    if age_days < 0 or age_days > 730:
        return None

    shape_ratio = source_current_seconds / source_pb_seconds
    # A large change probably means the source workout is not comparable to
    # its PB-window evidence. Withhold rather than manufacture a prediction.
    if not 0.88 <= shape_ratio <= 1.15:
        return None

    central = target_pb_seconds * shape_ratio
    if age_days <= 180:
        recency_factor = 1.0
    elif age_days <= 365:
        recency_factor = 0.88
    else:
        recency_factor = 0.72

    distance_factor = max(
        0.62,
        1.0 - (target_distance_km / source_distance_km - 1.0) * 0.18,
    )
    confidence = min(
        0.78,
        source_confidence * recency_factor * distance_factor * 0.92,
    )
    if confidence < 0.35:
        return None

    uncertainty_fraction = 0.025 + (1.0 - confidence) * 0.05
    half_range = max(central * uncertainty_fraction, 30.0)

    return PersonalPBShapeBridge(
        source_distance_km=round(source_distance_km, 4),
        target_distance_km=round(target_distance_km, 4),
        source_pb_seconds=round(source_pb_seconds, 1),
        source_current_seconds=round(source_current_seconds, 1),
        target_pb_seconds=round(target_pb_seconds, 1),
        target_pb_date=pb_date.isoformat(),
        shape_ratio=round(shape_ratio, 4),
        central_seconds=round(central, 1),
        low_seconds=round(max(central - half_range, 1.0), 1),
        high_seconds=round(central + half_range, 1),
        confidence=round(confidence, 4),
        target_pb_age_days=age_days,
    )


def personal_pb_shape_bridge_to_dict(
    result: PersonalPBShapeBridge,
) -> dict:
    return {
        "central_seconds": result.central_seconds,
        "low_seconds": result.low_seconds,
        "high_seconds": result.high_seconds,
        "confidence": result.confidence,
        "source_distance_km": result.source_distance_km,
        "target_distance_km": result.target_distance_km,
        "source_pb_seconds": result.source_pb_seconds,
        "source_current_seconds": result.source_current_seconds,
        "target_pb_seconds": result.target_pb_seconds,
        "target_pb_date": result.target_pb_date,
        "target_pb_age_days": result.target_pb_age_days,
        "shape_ratio": result.shape_ratio,
        "conditions": "Ideal, flat conditions",
        "method": (
            "Current shorter-distance PB Shape carried through the athlete's "
            "own verified cross-distance PB relationship."
        ),
        "model_version": 1,
    }


def personal_pb_ratio_projection(
    *,
    source_distance_km: float,
    target_distance_km: float,
    source_pb_seconds: float,
    source_current_seconds: float,
    target_pb_seconds: float,
) -> dict | None:
    """Project current capability through an athlete's own PB relationship."""
    values = (
        source_distance_km,
        target_distance_km,
        source_pb_seconds,
        source_current_seconds,
        target_pb_seconds,
    )
    if any(value <= 0 for value in values):
        return None
    if target_distance_km <= source_distance_km:
        return None

    current_to_pb_ratio = source_current_seconds / source_pb_seconds
    if not 0.88 <= current_to_pb_ratio <= 1.15:
        return None

    return {
        "source_distance_km": round(source_distance_km, 4),
        "target_distance_km": round(target_distance_km, 4),
        "source_pb_seconds": round(source_pb_seconds, 1),
        "source_current_seconds": round(source_current_seconds, 1),
        "target_pb_seconds": round(target_pb_seconds, 1),
        "current_to_pb_ratio": round(current_to_pb_ratio, 4),
        "predicted_seconds": round(
            target_pb_seconds * current_to_pb_ratio,
            1,
        ),
        "method": (
            "Current shorter-distance capability carried through the "
            "athlete's own verified cross-distance PB relationship."
        ),
        "model_version": 1,
    }

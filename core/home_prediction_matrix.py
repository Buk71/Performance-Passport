"""Four-distance Race Outlook composed from independent capability anchors.

Distance-specific Race, Workout and Threshold Coach anchors take priority.
Verified PB relationships and the Riegel 1.06 rule remain transparent fallbacks
when a distance lacks direct evidence. The matrix then applies the active
environment profile consistently and never reads from or writes to the database.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from core.distance_prediction_outlook import DistancePredictionOutlook
from core.home_predictions import HomePredictions


RIEGEL_EXPONENT = 1.06
TRAIL_GENERIC_ADJUSTMENT = 0.05

DISTANCES = (
    ("5k", "5K", 5.0),
    ("10k", "10K", 10.0),
    ("half_marathon", "Half", 21.0975),
    ("marathon", "Marathon", 42.195),
)

CONDITIONS = (
    ("ideal", "Ideal"),
    ("typical", "Typical UK"),
    ("warm", "Warm"),
    ("hilly", "Hilly"),
    ("windy", "Windy"),
    ("trail", "Trail"),
)

DISTANCE_BY_LABEL = {
    "5K": 5.0,
    "10K": 10.0,
    "Half marathon": 21.0975,
    "Marathon": 42.195,
}


@dataclass(frozen=True)
class HomePredictionMatrixCell:
    key: str
    label: str
    seconds: float


@dataclass(frozen=True)
class HomePredictionMatrixRow:
    key: str
    label: str
    distance_km: float
    is_active_distance: bool
    confidence: float
    readiness_label: str
    cells: tuple[HomePredictionMatrixCell, ...]


@dataclass(frozen=True)
class HomePredictionMatrix:
    athlete_id: int
    available: bool
    active_distance_label: str
    base_distance_km: float | None
    confidence: float
    rows: tuple[HomePredictionMatrixRow, ...]
    explanation: str


def _trail_multiplier(predictions: HomePredictions) -> float:
    """Mirror Environment Forecast's personalised trail blend."""
    response = next(
        (
            item
            for item in predictions.environment_responses
            if item.key == "trail"
        ),
        None,
    )
    if response is None:
        return 1.0 + TRAIL_GENERIC_ADJUSTMENT

    blend = min(max(response.confidence, 0.0) * 0.75, 0.75)
    adjusted_response = 1.0 * (1.0 - blend) + response.multiplier * blend
    return 1.0 + TRAIL_GENERIC_ADJUSTMENT * adjusted_response


def _condition_multipliers(
    predictions: HomePredictions,
) -> dict[str, float]:
    baseline = predictions.central_seconds
    if baseline is None or baseline <= 0:
        return {}

    multipliers = {
        scenario.key: scenario.central_seconds / baseline
        for scenario in predictions.scenarios
        if scenario.central_seconds > 0
    }
    multipliers["ideal"] = 1.0
    multipliers["trail"] = _trail_multiplier(predictions)
    return multipliers


def build_home_prediction_matrix(
    predictions: HomePredictions,
    personal_bests: dict[str, float] | None = None,
    distance_outlook: DistancePredictionOutlook | None = None,
) -> HomePredictionMatrix:
    """Compose four standard-distance capabilities across race conditions."""
    base_distance_km = DISTANCE_BY_LABEL.get(predictions.distance_label)
    baseline = predictions.central_seconds
    multipliers = _condition_multipliers(predictions)

    if (
        not predictions.available
        or baseline is None
        or baseline <= 0
        or base_distance_km is None
        or not multipliers
    ):
        return HomePredictionMatrix(
            athlete_id=predictions.athlete_id,
            available=False,
            active_distance_label=predictions.distance_label,
            base_distance_km=base_distance_km,
            confidence=predictions.confidence,
            rows=(),
            explanation=(
                "A supported standard-distance capability is required before "
                "the cross-distance outlook can be shown."
            ),
        )

    personal_bests = personal_bests or {}
    active_key = next(
        (
            key
            for key, _label, distance_km in DISTANCES
            if abs(distance_km - base_distance_km) < 0.12
        ),
        None,
    )
    base_pb_seconds = personal_bests.get(active_key) if active_key else None
    anchors = {
        anchor.key: anchor
        for anchor in (distance_outlook.anchors if distance_outlook else ())
        if anchor.available
        and anchor.central_seconds is not None
        and anchor.central_seconds > 0
    }
    personal_rows = 0
    distance_specific_rows = 0
    endurance_calibrated_rows = 0
    ideal_by_key = {}
    confidence_by_key = {}
    readiness_by_key = {}
    for key, label, distance_km in DISTANCES:
        anchor = anchors.get(key)
        if anchor is not None:
            ideal_by_key[key] = float(anchor.central_seconds)
            confidence_by_key[key] = anchor.confidence
            readiness_by_key[key] = anchor.readiness_label
            distance_specific_rows += 1
            if anchor.transfer_fraction > 0:
                endurance_calibrated_rows += 1
            continue
        target_pb_seconds = personal_bests.get(key)
        if (
            base_pb_seconds is not None
            and base_pb_seconds > 0
            and target_pb_seconds is not None
            and target_pb_seconds > 0
        ):
            ideal_seconds = (
                baseline * target_pb_seconds / base_pb_seconds
            )
            if key != active_key:
                personal_rows += 1
        else:
            ideal_seconds = baseline * math.pow(
                distance_km / base_distance_km,
                RIEGEL_EXPONENT,
            )
        ideal_by_key[key] = ideal_seconds
        confidence_by_key[key] = (
            predictions.confidence
            if key == active_key
            else predictions.confidence * 0.75
        )
        readiness_by_key[key] = ""

    # Personal PB relationships and generic fallbacks can come from different
    # fitness eras. Reconcile them before rendering so a longer prediction can
    # never imply covering the additional distance faster. When a contradiction
    # exists, carry the immediately shorter displayed capability through the
    # same transparent Riegel rule used by the generic fallback.
    consistency_adjustments = 0
    previous_key = None
    previous_distance_km = None
    for key, _label, distance_km in DISTANCES:
        if previous_key is not None and previous_distance_km is not None:
            previous_seconds = ideal_by_key[previous_key]
            distance_ratio = distance_km / previous_distance_km
            minimum_elapsed = previous_seconds * distance_ratio
            if ideal_by_key[key] <= minimum_elapsed:
                ideal_by_key[key] = previous_seconds * math.pow(
                    distance_ratio,
                    RIEGEL_EXPONENT,
                )
                consistency_adjustments += 1
        previous_key = key
        previous_distance_km = distance_km

    rows = []
    for key, label, distance_km in DISTANCES:
        ideal_seconds = ideal_by_key[key]
        cells = tuple(
            HomePredictionMatrixCell(
                key=condition_key,
                label=condition_label,
                seconds=ideal_seconds * multipliers.get(condition_key, 1.0),
            )
            for condition_key, condition_label in CONDITIONS
        )
        rows.append(
            HomePredictionMatrixRow(
                key=key,
                label=label,
                distance_km=distance_km,
                is_active_distance=abs(distance_km - base_distance_km) < 0.12,
                confidence=confidence_by_key[key],
                readiness_label=readiness_by_key[key],
                cells=cells,
            )
        )

    return HomePredictionMatrix(
        athlete_id=predictions.athlete_id,
        available=True,
        active_distance_label=predictions.distance_label,
        base_distance_km=base_distance_km,
        confidence=predictions.confidence,
        rows=tuple(rows),
        explanation=(
            (
                f"Each of {distance_specific_rows} distance(s) uses its own "
                "Race, Workout and Threshold Coach evidence. Condition columns "
                "then apply the athlete's current environmental response. "
                + (
                    f"For {endurance_calibrated_rows} longer distance(s), "
                    "current shorter-distance fitness contributes only the "
                    "share supported by recent volume, long-run coverage and "
                    "prior distance completion. "
                    if endurance_calibrated_rows
                    else ""
                )
                if distance_specific_rows
                else "Ballpark cross-distance times translated from the current "
                "active-goal capability using the athlete's verified PB relationship "
                f"for {personal_rows} other distance(s), and Race Coach's 1.06 "
                "equivalence rule where personal evidence is unavailable. "
            )
            + (
                f"A cross-distance consistency guard reconciled "
                f"{consistency_adjustments} contradictory longer-distance "
                "estimate(s). "
                if consistency_adjustments
                else ""
            )
            + "They "
            "describe capability, not distance-specific race readiness."
        ),
    )

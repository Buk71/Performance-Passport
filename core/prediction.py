"""
Performance Passport race prediction foundation.

This module combines explainable evidence. It does not manufacture
predictions when the available evidence cannot support one.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from core.evidence import EvidenceBundle, EvidenceItem


def _goal_distance_km(goal: dict | None) -> float | None:
    if not goal:
        return None
    raw = goal.get("distance_m") or goal.get("distance_km")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value / 1000.0 if value > 250.0 else value


def _as_date(value) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _recent_direct_race_anchor(
    goal: dict | None,
    evidence: EvidenceBundle,
) -> EvidenceItem | None:
    """Return recent high-confidence proof at the requested distance.

    A supported prediction describes ideal capability. It must not be slower
    than a recent, directly comparable Race Coach result unless the app has
    stronger evidence of decline. Confidence is deliberately retained from
    Race Coach rather than promoted by this guard.
    """
    goal_distance = _goal_distance_km(goal)
    if goal_distance is None:
        return None

    history = next(
        (item for item in evidence.items if item.key == "activity_history"),
        None,
    )
    reference_date = _as_date(
        history.metadata.get("latest_activity_date") if history else None
    )
    race = next(
        (item for item in evidence.prediction_items if item.key == "recent_race"),
        None,
    )
    if race is None or race.confidence < 0.70:
        return None

    metadata = race.metadata
    if not metadata.get("direct_goal_distance"):
        return None
    race_distance = metadata.get("projection_distance_km")
    try:
        race_distance = float(race_distance)
    except (TypeError, ValueError):
        return None
    if abs(race_distance - goal_distance) / goal_distance > 0.035:
        return None

    race_date = _as_date(metadata.get("activity_date"))
    if reference_date is None or race_date is None:
        return None
    age_days = (reference_date - race_date).days
    age_limit = 365 if goal_distance >= 30.0 else 210
    if age_days < 0 or age_days > age_limit:
        return None
    return race


@dataclass(frozen=True)
class GoalPrediction:
    athlete_id: int
    goal_id: int | None
    available: bool
    predicted_seconds: float | None
    target_seconds: float | None
    confidence: float
    evidence: tuple[EvidenceItem, ...]
    explanation: str

    @property
    def gap_seconds(self) -> float | None:
        if self.predicted_seconds is None or self.target_seconds is None:
            return None

        return self.predicted_seconds - self.target_seconds

    @property
    def on_target(self) -> bool | None:
        gap = self.gap_seconds

        if gap is None:
            return None

        return gap <= 0


class PredictionEngine:
    """
    Combine race-time evidence into one explainable goal prediction.

    Sprint D3.0 establishes the contract only. Evidence providers will be
    added in later sprints.
    """

    MINIMUM_PREDICTION_ITEMS = 1
    MINIMUM_CONFIDENCE = 0.25

    def predict_goal(
        self,
        athlete_id: int,
        goal: dict | None,
        evidence: EvidenceBundle,
    ) -> GoalPrediction:
        goal_id = goal.get("id") if goal else None
        target_seconds = goal.get("target_time_s") if goal else None

        if goal is None:
            return GoalPrediction(
                athlete_id=athlete_id,
                goal_id=None,
                available=False,
                predicted_seconds=None,
                target_seconds=None,
                confidence=0.0,
                evidence=evidence.items,
                explanation=(
                    "No active goal is configured for this athlete."
                ),
            )

        prediction_items = evidence.prediction_items

        if len(prediction_items) < self.MINIMUM_PREDICTION_ITEMS:
            return GoalPrediction(
                athlete_id=athlete_id,
                goal_id=goal_id,
                available=False,
                predicted_seconds=None,
                target_seconds=(
                    float(target_seconds)
                    if target_seconds is not None
                    else None
                ),
                confidence=evidence.confidence,
                evidence=evidence.items,
                explanation=(
                    "Prediction unavailable: no evidence provider currently "
                    "produces a supported race-time estimate."
                ),
            )

        total_weight = sum(
            item.effective_weight
            for item in prediction_items
        )

        if total_weight <= 0:
            return GoalPrediction(
                athlete_id=athlete_id,
                goal_id=goal_id,
                available=False,
                predicted_seconds=None,
                target_seconds=(
                    float(target_seconds)
                    if target_seconds is not None
                    else None
                ),
                confidence=evidence.confidence,
                evidence=evidence.items,
                explanation=(
                    "Prediction unavailable: the available evidence has no "
                    "usable prediction weight."
                ),
            )

        predicted_seconds = sum(
            item.predicted_seconds * item.effective_weight
            for item in prediction_items
            if item.predicted_seconds is not None
        ) / total_weight

        confidence = sum(
            item.confidence * item.effective_weight
            for item in prediction_items
        ) / total_weight

        direct_anchor = _recent_direct_race_anchor(goal, evidence)
        anchor_applied = bool(
            direct_anchor is not None
            and direct_anchor.predicted_seconds is not None
            and predicted_seconds > direct_anchor.predicted_seconds
        )
        if anchor_applied:
            predicted_seconds = float(direct_anchor.predicted_seconds)
            # The guard cannot manufacture certainty. Keep the lower of the
            # combined confidence and the direct Race Coach confidence.
            confidence = min(confidence, direct_anchor.confidence)

        if confidence < self.MINIMUM_CONFIDENCE:
            return GoalPrediction(
                athlete_id=athlete_id,
                goal_id=goal_id,
                available=False,
                predicted_seconds=None,
                target_seconds=(
                    float(target_seconds)
                    if target_seconds is not None
                    else None
                ),
                confidence=confidence,
                evidence=evidence.items,
                explanation=(
                    "Prediction withheld because the supporting evidence "
                    "confidence is too low."
                ),
            )

        return GoalPrediction(
            athlete_id=athlete_id,
            goal_id=goal_id,
            available=True,
            predicted_seconds=predicted_seconds,
            target_seconds=(
                float(target_seconds)
                if target_seconds is not None
                else None
            ),
            confidence=confidence,
            evidence=evidence.items,
            explanation=(
                f"Prediction combines {len(prediction_items)} explainable "
                "evidence source(s)."
                + (
                    " Recent direct goal-distance Race Coach evidence sets "
                    "the current ideal-capability anchor."
                    if anchor_applied
                    else ""
                )
            ),
        )

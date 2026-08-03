"""
Performance Passport race prediction foundation.

This module combines explainable evidence. It does not manufacture
predictions when the available evidence cannot support one.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.evidence import EvidenceBundle, EvidenceItem


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

        if target_seconds is None:
            return GoalPrediction(
                athlete_id=athlete_id,
                goal_id=goal_id,
                available=False,
                predicted_seconds=None,
                target_seconds=None,
                confidence=evidence.confidence,
                evidence=evidence.items,
                explanation=(
                    "This goal does not have a target time, so a race-time "
                    "prediction is not required."
                ),
            )

        prediction_items = evidence.prediction_items

        if len(prediction_items) < self.MINIMUM_PREDICTION_ITEMS:
            return GoalPrediction(
                athlete_id=athlete_id,
                goal_id=goal_id,
                available=False,
                predicted_seconds=None,
                target_seconds=float(target_seconds),
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
                target_seconds=float(target_seconds),
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

        if confidence < self.MINIMUM_CONFIDENCE:
            return GoalPrediction(
                athlete_id=athlete_id,
                goal_id=goal_id,
                available=False,
                predicted_seconds=None,
                target_seconds=float(target_seconds),
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
            target_seconds=float(target_seconds),
            confidence=confidence,
            evidence=evidence.items,
            explanation=(
                f"Prediction combines {len(prediction_items)} explainable "
                "evidence source(s)."
            ),
        )

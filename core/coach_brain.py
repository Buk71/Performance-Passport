"""
Performance Passport Coach Brain.

The Coach Brain coordinates the active goal, specialist evidence providers
and the prediction engine. It contains no Streamlit rendering logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.database import get_active_goal, get_connection
from core.evidence import (
    EvidenceBundle,
    EvidenceItem,
    EvidenceStatus,
)
from core.evidence_providers import (
    EvidenceProvider,
    RaceEvidenceProvider,
    ThresholdEvidenceProvider,
    WorkoutEvidenceProvider,
)
from core.evidence_providers.base import EvidenceContext
from core.prediction import GoalPrediction, PredictionEngine


@dataclass(frozen=True)
class CoachBrief:
    headline: str
    summary: str
    confidence: float
    evidence: tuple[EvidenceItem, ...]


class CoachBrain:
    """Central intelligence entry point for one athlete."""

    def __init__(
        self,
        athlete_id: int,
        prediction_engine: PredictionEngine | None = None,
        providers: Iterable[EvidenceProvider] | None = None,
    ):
        if athlete_id <= 0:
            raise ValueError("athlete_id must be a positive integer.")

        self.athlete_id = athlete_id
        self.prediction_engine = prediction_engine or PredictionEngine()
        self.providers = tuple(
            providers
            if providers is not None
            else (
                WorkoutEvidenceProvider(),
                RaceEvidenceProvider(),
                ThresholdEvidenceProvider(),
            )
        )

    def get_goal(self) -> dict | None:
        return get_active_goal(self.athlete_id)

    def build_foundation_evidence(self) -> EvidenceBundle:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*), MAX(date(activity_date))
            FROM activities
            WHERE athlete_id = ?
            """,
            (self.athlete_id,),
        )
        activity_count, latest_activity_date = cursor.fetchone()
        conn.close()

        activity_count = activity_count or 0

        if activity_count >= 100:
            status = EvidenceStatus.AVAILABLE
            confidence = 0.90
            summary = (
                f"{activity_count:,} activities provide a strong historical "
                "evidence base."
            )
        elif activity_count >= 20:
            status = EvidenceStatus.AVAILABLE
            confidence = 0.65
            summary = (
                f"{activity_count:,} activities provide a developing "
                "historical evidence base."
            )
        elif activity_count > 0:
            status = EvidenceStatus.BUILDING
            confidence = 0.30
            summary = (
                f"{activity_count:,} activities are available, but more "
                "history is needed."
            )
        else:
            status = EvidenceStatus.UNAVAILABLE
            confidence = 0.0
            summary = "No activities are available for this athlete."

        history_item = EvidenceItem(
            key="activity_history",
            title="Activity history",
            summary=summary,
            status=status,
            confidence=confidence,
            sample_size=activity_count,
            predicted_seconds=None,
            weight=0.5,
            metadata={
                "latest_activity_date": latest_activity_date,
            },
        )

        return EvidenceBundle(
            athlete_id=self.athlete_id,
            purpose="goal_prediction",
            items=(history_item,),
        )

    def build_evidence(self) -> EvidenceBundle:
        goal = self.get_goal()
        context = EvidenceContext(
            athlete_id=self.athlete_id,
            goal=goal,
        )
        bundle = self.build_foundation_evidence()

        for provider in self.providers:
            try:
                item = provider.build(context)
            except Exception as error:
                item = EvidenceItem(
                    key=getattr(provider, "key", "unknown_provider"),
                    title=getattr(
                        provider,
                        "title",
                        provider.__class__.__name__,
                    ),
                    summary=(
                        "This specialist evidence provider could not complete "
                        "its analysis."
                    ),
                    status=EvidenceStatus.UNAVAILABLE,
                    confidence=0.0,
                    sample_size=0,
                    predicted_seconds=None,
                    weight=0.0,
                    metadata={
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                    },
                )

            bundle = bundle.with_item(item)

        return bundle

    def goal_prediction(
        self,
        additional_evidence: tuple[EvidenceItem, ...] = (),
    ) -> GoalPrediction:
        evidence = self.build_evidence()

        for item in additional_evidence:
            evidence = evidence.with_item(item)

        return self.prediction_engine.predict_goal(
            athlete_id=self.athlete_id,
            goal=self.get_goal(),
            evidence=evidence,
        )

    def morning_brief(
        self,
        additional_evidence: tuple[EvidenceItem, ...] = (),
    ) -> CoachBrief:
        prediction = self.goal_prediction(additional_evidence)

        if prediction.goal_id is None:
            return CoachBrief(
                headline="Choose a goal to focus your coaching.",
                summary=(
                    "Performance Passport can analyse your history now, but "
                    "an active goal is needed to organise predictions."
                ),
                confidence=prediction.confidence,
                evidence=prediction.evidence,
            )

        if not prediction.available:
            return CoachBrief(
                headline="Your goal is configured.",
                summary=prediction.explanation,
                confidence=prediction.confidence,
                evidence=prediction.evidence,
            )

        gap = prediction.gap_seconds

        if gap is not None and gap <= 0:
            headline = "Recent race evidence suggests you are on target."
        else:
            headline = "Your first evidence-based prediction is available."

        return CoachBrief(
            headline=headline,
            summary=prediction.explanation,
            confidence=prediction.confidence,
            evidence=prediction.evidence,
        )

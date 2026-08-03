"""
Performance Passport evidence models.

Evidence is the common language used by prediction, recommendation,
discoveries and the Coach Brain.

No Streamlit logic.
No direct UI formatting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceStatus(str, Enum):
    AVAILABLE = "available"
    BUILDING = "building"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class EvidenceItem:
    """
    One explainable piece of coaching evidence.

    predicted_seconds is optional because not every evidence item is capable
    of producing a race-time estimate. For example, training-history volume
    can increase confidence without directly predicting a 10K time.
    """

    key: str
    title: str
    summary: str
    status: EvidenceStatus
    confidence: float = 0.0
    sample_size: int = 0
    predicted_seconds: float | None = None
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Evidence confidence must be between 0 and 1.")

        if self.sample_size < 0:
            raise ValueError("Evidence sample_size cannot be negative.")

        if self.weight < 0:
            raise ValueError("Evidence weight cannot be negative.")

        if self.predicted_seconds is not None and self.predicted_seconds <= 0:
            raise ValueError(
                "Evidence predicted_seconds must be positive when supplied."
            )

    @property
    def usable_for_prediction(self) -> bool:
        return (
            self.status == EvidenceStatus.AVAILABLE
            and self.predicted_seconds is not None
            and self.confidence > 0
            and self.weight > 0
        )

    @property
    def effective_weight(self) -> float:
        if not self.usable_for_prediction:
            return 0.0

        return self.confidence * self.weight


@dataclass(frozen=True)
class EvidenceBundle:
    """A collection of evidence for one athlete and one coaching question."""

    athlete_id: int
    purpose: str
    items: tuple[EvidenceItem, ...] = ()

    @property
    def available_items(self) -> tuple[EvidenceItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.status == EvidenceStatus.AVAILABLE
        )

    @property
    def prediction_items(self) -> tuple[EvidenceItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.usable_for_prediction
        )

    @property
    def total_sample_size(self) -> int:
        return sum(item.sample_size for item in self.available_items)

    @property
    def confidence(self) -> float:
        """
        Return an evidence confidence summary.

        This is not a prediction probability. It describes how strong the
        available evidence base is.
        """

        available = self.available_items

        if not available:
            return 0.0

        weighted_confidence = sum(
            item.confidence * max(item.weight, 0.01)
            for item in available
        )
        total_weight = sum(max(item.weight, 0.01) for item in available)

        return weighted_confidence / total_weight

    def with_item(self, item: EvidenceItem) -> "EvidenceBundle":
        return EvidenceBundle(
            athlete_id=self.athlete_id,
            purpose=self.purpose,
            items=(*self.items, item),
        )

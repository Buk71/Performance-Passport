"""
Base interface for Performance Passport specialist evidence providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.evidence import EvidenceItem


@dataclass(frozen=True)
class EvidenceContext:
    athlete_id: int
    goal: dict | None = None


class EvidenceProvider(ABC):
    """Contract implemented by every specialist coach/evidence provider."""

    key: str
    title: str

    @abstractmethod
    def build(self, context: EvidenceContext) -> EvidenceItem:
        """Build one explainable evidence item."""
        raise NotImplementedError

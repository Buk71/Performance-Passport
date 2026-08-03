"""Specialist evidence providers used by the Coach Brain."""

from core.evidence_providers.base import EvidenceProvider
from core.evidence_providers.race import RaceEvidenceProvider
from core.evidence_providers.threshold import ThresholdEvidenceProvider
from core.evidence_providers.workout import WorkoutEvidenceProvider

__all__ = [
    "EvidenceProvider",
    "RaceEvidenceProvider",
    "ThresholdEvidenceProvider",
    "WorkoutEvidenceProvider",
]

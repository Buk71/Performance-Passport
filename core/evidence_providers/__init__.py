"""Specialist evidence providers used by the Coach Brain."""

from core.evidence_providers.base import EvidenceProvider
from core.evidence_providers.race import RaceEvidenceProvider

__all__ = [
    "EvidenceProvider",
    "RaceEvidenceProvider",
]

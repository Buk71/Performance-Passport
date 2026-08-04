"""
Capability Engine.

Capability is the athlete's best current estimate under ideal, flat
conditions. It is deliberately separate from a race-day forecast.

The engine combines:
- the existing consensus prediction;
- prediction confidence;
- Coach Consensus confidence;
- Athlete Performance DNA confidence;
- the athlete's strongest and developing systems;
- the configured goal target.

Version 1 creates:
- central capability;
- a transparent likely range;
- target gap;
- estimated goal probability;
- strongest and limiting systems;
- explanation and limitations.

Heat, hills, trail, surface and weather adjustments belong to the future
Environment Engine and do not alter this ideal-condition baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from core.coach_consensus import CoachConsensus
from core.performance_dna import PerformanceDNA


SYSTEM_LABELS = {
    "threshold": "Threshold",
    "speed": "Speed / VO₂",
    "endurance": "Endurance",
    "aerobic": "Aerobic",
}


@dataclass(frozen=True)
class Capability:
    available: bool
    central_seconds: float | None
    low_seconds: float | None
    high_seconds: float | None
    confidence: float
    target_seconds: float | None
    target_gap_seconds: float | None
    target_probability: float | None
    strongest_system: str | None
    limiting_system: str | None
    headline: str
    explanation: str
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    model_version: int = 1


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _goal_probability(
    *,
    central_seconds: float,
    uncertainty_seconds: float,
    target_seconds: float,
) -> float:
    """
    Estimate the chance of meeting the target using a smooth logistic curve.

    This is not a betting probability. It is a coaching confidence estimate
    based on the target's position within the current capability range.
    """
    if uncertainty_seconds <= 0:
        return 1.0 if central_seconds <= target_seconds else 0.0

    z = (target_seconds - central_seconds) / uncertainty_seconds
    probability = 1.0 / (1.0 + math.exp(-1.7 * z))
    return _clamp(probability, 0.02, 0.98)


def build_capability(
    *,
    predicted_seconds: float | None,
    prediction_confidence: float,
    performance_dna: PerformanceDNA,
    coach_consensus: CoachConsensus,
    target_seconds: float | None = None,
) -> Capability:
    if predicted_seconds is None or predicted_seconds <= 0:
        return Capability(
            available=False,
            central_seconds=None,
            low_seconds=None,
            high_seconds=None,
            confidence=0.0,
            target_seconds=target_seconds,
            target_gap_seconds=None,
            target_probability=None,
            strongest_system=None,
            limiting_system=None,
            headline="Capability is still building.",
            explanation=(
                "The coaching team does not yet have a usable central "
                "prediction."
            ),
            evidence=(),
            limitations=(
                "Capability requires at least one usable specialist prediction.",
            ),
        )

    prediction_confidence = _clamp(prediction_confidence, 0.0, 1.0)
    dna_confidence = _clamp(
        performance_dna.athlete_dna_confidence,
        0.0,
        1.0,
    )
    consensus_confidence = _clamp(
        coach_consensus.confidence,
        0.0,
        1.0,
    )

    confidence = (
        prediction_confidence * 0.45
        + consensus_confidence * 0.35
        + dna_confidence * 0.20
    )
    confidence = _clamp(confidence, 0.05, 0.97)

    # Range narrows as evidence confidence improves. A minimum uncertainty
    # remains because race execution and conditions are not yet modelled.
    uncertainty_ratio = (
        0.012
        + (1.0 - confidence) * 0.055
    )
    uncertainty_seconds = max(
        predicted_seconds * uncertainty_ratio,
        10.0,
    )

    low_seconds = max(predicted_seconds - uncertainty_seconds, 1.0)
    high_seconds = predicted_seconds + uncertainty_seconds

    system_scores = performance_dna.system_scores
    strongest_system = (
        max(system_scores, key=system_scores.get)
        if system_scores
        else None
    )
    limiting_system = (
        min(system_scores, key=system_scores.get)
        if system_scores
        else None
    )

    target_gap_seconds = None
    target_probability = None

    if target_seconds is not None and target_seconds > 0:
        target_gap_seconds = predicted_seconds - target_seconds
        target_probability = _goal_probability(
            central_seconds=predicted_seconds,
            uncertainty_seconds=uncertainty_seconds,
            target_seconds=target_seconds,
        )

    strongest_label = (
        SYSTEM_LABELS.get(strongest_system)
        if strongest_system
        else None
    )
    limiting_label = (
        SYSTEM_LABELS.get(limiting_system)
        if limiting_system
        else None
    )

    if target_gap_seconds is None:
        headline = "Current ideal-condition capability"
    elif target_gap_seconds <= 0:
        headline = "The current capability supports the active goal."
    elif target_gap_seconds <= uncertainty_seconds:
        headline = "The active goal is within the current capability range."
    else:
        headline = "The active goal remains ahead of current capability."

    explanation_parts = [
        (
            f"The central estimate is supported by "
            f"{coach_consensus.lead_coach or 'the coaching team'}."
        ),
    ]

    if strongest_label:
        explanation_parts.append(
            f"{strongest_label} is the strongest current system."
        )

    if limiting_label and limiting_label != strongest_label:
        explanation_parts.append(
            f"{limiting_label} has the lowest aggregated score and is the "
            "current development priority."
        )

    evidence = [
        f"Prediction confidence: {prediction_confidence:.0%}",
        f"Coach Consensus confidence: {consensus_confidence:.0%}",
        f"Athlete DNA confidence: {dna_confidence:.0%}",
    ]

    if coach_consensus.lead_coach:
        evidence.append(
            f"Lead specialist opinion: {coach_consensus.lead_coach}"
        )

    limitations = [
        (
            "This is ideal, flat-condition capability rather than a "
            "course-specific race forecast."
        ),
        (
            "Heat, humidity, elevation, trail surface and wind are not yet "
            "applied."
        ),
        (
            "Goal probability is a coaching estimate, not a guarantee."
        ),
    ]

    return Capability(
        available=True,
        central_seconds=round(predicted_seconds, 1),
        low_seconds=round(low_seconds, 1),
        high_seconds=round(high_seconds, 1),
        confidence=round(confidence, 4),
        target_seconds=target_seconds,
        target_gap_seconds=(
            round(target_gap_seconds, 1)
            if target_gap_seconds is not None
            else None
        ),
        target_probability=(
            round(target_probability, 4)
            if target_probability is not None
            else None
        ),
        strongest_system=strongest_system,
        limiting_system=limiting_system,
        headline=headline,
        explanation=" ".join(explanation_parts),
        evidence=tuple(evidence),
        limitations=tuple(limitations),
    )


def capability_to_dict(
    capability: Capability,
) -> dict[str, Any]:
    return {
        "available": capability.available,
        "central_seconds": capability.central_seconds,
        "low_seconds": capability.low_seconds,
        "high_seconds": capability.high_seconds,
        "confidence": capability.confidence,
        "target_seconds": capability.target_seconds,
        "target_gap_seconds": capability.target_gap_seconds,
        "target_probability": capability.target_probability,
        "strongest_system": capability.strongest_system,
        "limiting_system": capability.limiting_system,
        "headline": capability.headline,
        "explanation": capability.explanation,
        "evidence": list(capability.evidence),
        "limitations": list(capability.limitations),
        "model_version": capability.model_version,
    }

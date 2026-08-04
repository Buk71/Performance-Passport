"""
Coach Consensus.

This module lets specialist coaches reinforce or challenge one another without
creating a new prediction model.

The Goal Coach listens to:
- Race Coach
- Workout Coach
- Threshold Coach
- Athlete Performance DNA
- the existing central prediction

It explains:
- which coaches agree;
- which coach is more optimistic or cautious;
- which opinion currently leads;
- the athlete's strongest system and likely development priority.

It does not prescribe today's session because Readiness Coach is not connected
yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.performance_dna import PerformanceDNA


@dataclass(frozen=True)
class CoachPosition:
    key: str
    title: str
    predicted_seconds: float
    confidence: float
    difference_seconds: float
    position: str


@dataclass(frozen=True)
class CoachConsensus:
    status: str
    headline: str
    summary: str
    confidence: float
    lead_coach: str | None
    supporting_coaches: tuple[str, ...]
    cautious_coaches: tuple[str, ...]
    optimistic_coaches: tuple[str, ...]
    strongest_system: str | None
    development_priority: str | None
    positions: tuple[CoachPosition, ...]
    notes: tuple[str, ...]


SYSTEM_LABELS = {
    "threshold": "Threshold",
    "speed": "Speed / VO₂",
    "endurance": "Endurance",
    "aerobic": "Aerobic",
}


def _position(
    difference_seconds: float,
    consensus_seconds: float,
) -> str:
    tolerance = max(consensus_seconds * 0.01, 8.0)

    if difference_seconds < -tolerance:
        return "optimistic"
    if difference_seconds > tolerance:
        return "cautious"
    return "aligned"


def _lead_coach(
    positions: list[CoachPosition],
) -> CoachPosition | None:
    if not positions:
        return None

    # Prefer confidence, then closeness to the central consensus.
    return max(
        positions,
        key=lambda item: (
            item.confidence,
            -abs(item.difference_seconds),
        ),
    )


def build_coach_consensus(
    performance_dna: PerformanceDNA,
    *,
    consensus_prediction_s: float | None,
) -> CoachConsensus:
    available_predictions = [
        verdict
        for verdict in performance_dna.verdicts
        if (
            verdict.available
            and verdict.predicted_seconds is not None
        )
    ]

    positions = []

    if (
        consensus_prediction_s is not None
        and consensus_prediction_s > 0
    ):
        for verdict in available_predictions:
            difference = (
                verdict.predicted_seconds
                - consensus_prediction_s
            )
            positions.append(
                CoachPosition(
                    key=verdict.key,
                    title=verdict.title,
                    predicted_seconds=verdict.predicted_seconds,
                    confidence=verdict.confidence,
                    difference_seconds=round(difference, 1),
                    position=_position(
                        difference,
                        consensus_prediction_s,
                    ),
                )
            )

    lead = _lead_coach(positions)
    aligned = [
        item.title
        for item in positions
        if item.position == "aligned"
    ]
    cautious = [
        item.title
        for item in positions
        if item.position == "cautious"
    ]
    optimistic = [
        item.title
        for item in positions
        if item.position == "optimistic"
    ]

    if len(positions) >= 2:
        spread = (
            max(item.predicted_seconds for item in positions)
            - min(item.predicted_seconds for item in positions)
        )
        spread_ratio = (
            spread / consensus_prediction_s
            if consensus_prediction_s
            else 0.0
        )

        if spread_ratio <= 0.02:
            status = "aligned"
            headline = "The specialist coaches are closely aligned."
        elif spread_ratio <= 0.05:
            status = "balanced"
            headline = (
                "The coaches broadly agree, with useful differences "
                "in confidence."
            )
        else:
            status = "mixed"
            headline = (
                "The coaches see meaningfully different signals "
                "in current form."
            )
    elif len(positions) == 1:
        status = "developing"
        headline = (
            f"{positions[0].title} currently carries the goal prediction."
        )
    else:
        status = "building"
        headline = (
            "The Goal Coach is waiting for enough specialist predictions."
        )

    system_scores = performance_dna.system_scores

    if system_scores and any(system_scores.values()):
        strongest_system = max(
            system_scores,
            key=system_scores.get,
        )
        development_priority = min(
            system_scores,
            key=system_scores.get,
        )
    else:
        strongest_system = None
        development_priority = None

    summary_parts = []

    if lead is not None:
        summary_parts.append(
            f"{lead.title} currently provides the lead opinion "
            f"at {lead.confidence:.0%} confidence."
        )

    if aligned:
        summary_parts.append(
            f"{', '.join(aligned)} "
            f"{'is' if len(aligned) == 1 else 'are'} close to the "
            "central consensus."
        )

    if optimistic:
        summary_parts.append(
            f"{', '.join(optimistic)} "
            f"{'is' if len(optimistic) == 1 else 'are'} more optimistic."
        )

    if cautious:
        summary_parts.append(
            f"{', '.join(cautious)} "
            f"{'is' if len(cautious) == 1 else 'are'} more cautious."
        )

    if strongest_system is not None:
        summary_parts.append(
            f"Athlete DNA currently identifies "
            f"{SYSTEM_LABELS[strongest_system]} as the strongest system."
        )

    if development_priority is not None:
        summary_parts.append(
            f"{SYSTEM_LABELS[development_priority]} has the lowest "
            "aggregated score and is the current development priority, "
            "subject to evidence confidence."
        )

    confidence = performance_dna.overall_confidence

    if positions:
        prediction_confidence = sum(
            item.confidence for item in positions
        ) / len(positions)
        confidence = (
            performance_dna.overall_confidence * 0.55
            + prediction_confidence * 0.45
        )

    notes = [
        (
            "Coach Consensus explains existing evidence; it does not "
            "create a separate race-time calculation."
        ),
        (
            "A low system score can indicate limited evidence rather than "
            "a true physiological weakness."
        ),
    ]

    if development_priority is not None:
        priority_confidence = performance_dna.system_confidence.get(
            development_priority,
            0,
        )

        if priority_confidence < 0.55:
            notes.append(
                "The development priority is provisional because its "
                "evidence confidence is still limited."
            )

    return CoachConsensus(
        status=status,
        headline=headline,
        summary=" ".join(summary_parts),
        confidence=round(confidence, 4),
        lead_coach=lead.title if lead is not None else None,
        supporting_coaches=tuple(aligned),
        cautious_coaches=tuple(cautious),
        optimistic_coaches=tuple(optimistic),
        strongest_system=strongest_system,
        development_priority=development_priority,
        positions=tuple(positions),
        notes=tuple(notes),
    )


def coach_consensus_to_dict(
    consensus: CoachConsensus,
) -> dict[str, Any]:
    return {
        "status": consensus.status,
        "headline": consensus.headline,
        "summary": consensus.summary,
        "confidence": consensus.confidence,
        "lead_coach": consensus.lead_coach,
        "supporting_coaches": list(consensus.supporting_coaches),
        "cautious_coaches": list(consensus.cautious_coaches),
        "optimistic_coaches": list(consensus.optimistic_coaches),
        "strongest_system": consensus.strongest_system,
        "development_priority": consensus.development_priority,
        "notes": list(consensus.notes),
        "positions": [
            {
                "key": item.key,
                "title": item.title,
                "predicted_seconds": item.predicted_seconds,
                "confidence": item.confidence,
                "difference_seconds": item.difference_seconds,
                "position": item.position,
            }
            for item in consensus.positions
        ],
        "model_version": 1,
    }

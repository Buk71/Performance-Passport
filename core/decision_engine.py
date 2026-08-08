"""
Performance Passport Decision Engine.

Single responsibility:
    What should the coaching system prioritise next?

The Decision Engine does not re-analyse activities. It consumes existing
evidence produced by the specialist engines and turns it into one transparent,
positive coaching decision.

Inputs:
- Performance DNA: current athlete-system strengths and opportunities;
- Coach Consensus: specialist agreement/disagreement;
- Capability: current goal/capability context;
- Recognition Engine: recent session quality, trend and positive evidence.

Outputs:
- strongest current system;
- primary development opportunity;
- supporting coaching signals;
- current direction/trend;
- a provisional next-session family;
- whether that session can be prescribed yet;
- a positive-first headline and explanation.

Important safeguard:
Readiness/fatigue is not yet a connected specialist. Therefore this engine may
identify the best DEVELOPMENT FOCUS, but it must not confidently prescribe a
hard session for tomorrow. Quality-session recommendations remain explicitly
provisional until Readiness Coach is connected.

Recognition before recommendation.
Evidence before conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from core.capability import Capability
from core.coach_consensus import CoachConsensus
from core.performance_dna import PerformanceDNA
from core.performance_recognition import Recognition


SYSTEM_LABELS = {
    "threshold": "Threshold",
    "speed": "Speed / VO₂",
    "endurance": "Endurance",
    "aerobic": "Aerobic",
}

SYSTEM_SESSION_FAMILIES = {
    "threshold": "Threshold Development",
    "speed": "VO₂ / Speed Development",
    "endurance": "Long Easy / Endurance",
    "aerobic": "Easy Aerobic",
}

QUALITY_SYSTEMS = {
    "threshold",
    "speed",
}


@dataclass(frozen=True)
class CoachingSignal:
    key: str
    label: str
    value: float
    confidence: float
    direction: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    athlete_id: int

    strongest_system: str | None
    strongest_system_label: str | None
    primary_opportunity: str | None
    primary_opportunity_label: str | None

    direction: str
    direction_detail: str

    provisional_next_session: str | None
    recommendation_ready: bool
    recommendation_status: str

    headline: str
    summary: str
    confidence: float

    supporting_coaches: tuple[str, ...]
    coaching_signals: tuple[CoachingSignal, ...]
    recent_recognitions: tuple[str, ...]

    evidence: tuple[str, ...]
    limitations: tuple[str, ...]

    model_version: int = 1


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _system_confidence(
    performance_dna: PerformanceDNA,
    system: str,
) -> float:
    return _clamp(
        float(
            performance_dna.system_confidence.get(system, 0.0)
            or 0.0
        )
    )


def _signal_direction(
    score: float,
    *,
    strongest_score: float,
    weakest_score: float,
) -> str:
    if score == strongest_score and score > weakest_score:
        return "strength"

    if score == weakest_score and score < strongest_score:
        return "opportunity"

    return "supporting"


def _build_system_signals(
    performance_dna: PerformanceDNA,
) -> tuple[CoachingSignal, ...]:
    scores = {
        key: float(value)
        for key, value in performance_dna.system_scores.items()
        if key in SYSTEM_LABELS
    }

    if not scores:
        return ()

    strongest_score = max(scores.values())
    weakest_score = min(scores.values())
    signals = []

    for system in ("aerobic", "threshold", "speed", "endurance"):
        if system not in scores:
            continue

        score = scores[system]
        confidence = _system_confidence(
            performance_dna,
            system,
        )
        direction = _signal_direction(
            score,
            strongest_score=strongest_score,
            weakest_score=weakest_score,
        )

        if direction == "strength":
            interpretation = (
                f"{SYSTEM_LABELS[system]} is currently one of the athlete's "
                "strongest systems."
            )
        elif direction == "opportunity":
            interpretation = (
                f"{SYSTEM_LABELS[system]} has the most room to develop "
                "relative to the athlete's other systems."
            )
        else:
            interpretation = (
                f"{SYSTEM_LABELS[system]} is contributing useful support."
            )

        signals.append(
            CoachingSignal(
                key=system,
                label=SYSTEM_LABELS[system],
                value=round(score, 1),
                confidence=round(confidence, 4),
                direction=direction,
                evidence=(interpretation,),
            )
        )

    return tuple(signals)


def _recent_recognition_items(
    recognitions: Mapping[str, Recognition] | Iterable[Recognition],
    *,
    limit: int = 5,
) -> list[Recognition]:
    if isinstance(recognitions, Mapping):
        items = list(recognitions.values())
    else:
        items = list(recognitions)

    def date_key(item: Recognition):
        # recognition_key begins with YYYY-MM-DD in the current contract.
        return str(item.key or "").split("|", 1)[0]

    items.sort(
        key=date_key,
        reverse=True,
    )

    return items[:limit]


def _direction_from_recognition(
    recent: list[Recognition],
) -> tuple[str, str]:
    if not recent:
        return (
            "Building",
            "Recent recognition evidence is still being assembled.",
        )

    positive = sum(
        item.trend_label in {
            "Trending stronger",
            "Positive trend",
        }
        for item in recent
    )
    consistent = sum(
        item.trend_label == "Consistent"
        for item in recent
    )
    opportunity = sum(
        item.trend_label == "Building opportunity"
        for item in recent
    )

    if positive >= 2:
        return (
            "Improving",
            (
                "Multiple recent comparable sessions are trending positively "
                "against the athlete's own history."
            ),
        )

    if positive >= 1 and opportunity == 0:
        return (
            "Positive",
            (
                "Recent recognition evidence includes an improving "
                "performance signal."
            ),
        )

    if opportunity >= 2:
        return (
            "Opportunity",
            (
                "Recent sessions provide useful evidence about where the "
                "next gains may come from."
            ),
        )

    if consistent >= 2:
        return (
            "Consistent",
            (
                "Recent comparable sessions are holding a stable level."
            ),
        )

    return (
        "Steady",
        (
            "Recent performance is mixed but continues to build useful "
            "coaching evidence."
        ),
    )


def _supporting_coaches(
    performance_dna: PerformanceDNA,
    coach_consensus: CoachConsensus,
    primary_opportunity: str | None,
) -> tuple[str, ...]:
    supporters = []

    if coach_consensus.lead_coach:
        supporters.append(coach_consensus.lead_coach)

    # Add available specialist coaches whose signal broadly maps to the
    # development opportunity. This remains descriptive rather than pretending
    # every coach has explicitly voted for a session.
    mapping = {
        "threshold": {"threshold", "workout"},
        "speed": {"workout", "race"},
        "endurance": {"race", "easy"},
        "aerobic": {"easy", "threshold"},
    }

    relevant_keys = mapping.get(primary_opportunity, set())

    for verdict in performance_dna.verdicts:
        if (
            verdict.available
            and verdict.key in relevant_keys
            and verdict.title not in supporters
        ):
            supporters.append(verdict.title)

    for title in coach_consensus.supporting_coaches:
        if title not in supporters:
            supporters.append(title)

    return tuple(supporters[:4])


def _decision_confidence(
    performance_dna: PerformanceDNA,
    coach_consensus: CoachConsensus,
    capability: Capability,
    opportunity: str | None,
    recent: list[Recognition],
) -> float:
    dna_conf = _clamp(
        float(performance_dna.overall_confidence or 0.0)
    )
    consensus_conf = _clamp(
        float(coach_consensus.confidence or 0.0)
    )
    capability_conf = (
        _clamp(float(capability.confidence or 0.0))
        if capability.available
        else 0.0
    )

    opportunity_conf = (
        _system_confidence(performance_dna, opportunity)
        if opportunity
        else 0.0
    )

    recognition_conf = (
        sum(item.confidence for item in recent) / len(recent)
        if recent
        else 0.0
    )

    # The Decision Engine aggregates existing confidence rather than creating
    # a new opaque certainty score.
    weighted = (
        dna_conf * 0.30
        + consensus_conf * 0.25
        + capability_conf * 0.20
        + opportunity_conf * 0.15
        + recognition_conf * 0.10
    )

    return round(_clamp(weighted, 0.0, 0.97), 4)


def _primary_opportunity(
    performance_dna: PerformanceDNA,
) -> str | None:
    usable = {
        key: float(value)
        for key, value in performance_dna.system_scores.items()
        if key in SYSTEM_LABELS
    }

    if not usable:
        return None

    # Require at least some evidence confidence. If all system confidence is
    # zero, we do not pretend the lowest numerical placeholder is meaningful.
    evidenced = {
        key: value
        for key, value in usable.items()
        if _system_confidence(performance_dna, key) > 0
    }

    if not evidenced:
        return None

    return min(
        evidenced,
        key=lambda key: evidenced[key],
    )


def _strongest_system(
    performance_dna: PerformanceDNA,
) -> str | None:
    usable = {
        key: float(value)
        for key, value in performance_dna.system_scores.items()
        if key in SYSTEM_LABELS
    }

    if not usable:
        return None

    evidenced = {
        key: value
        for key, value in usable.items()
        if _system_confidence(performance_dna, key) > 0
    }

    if not evidenced:
        return None

    return max(
        evidenced,
        key=lambda key: evidenced[key],
    )


def build_decision(
    *,
    performance_dna: PerformanceDNA,
    coach_consensus: CoachConsensus,
    capability: Capability,
    recognition_index: Mapping[str, Recognition] | Iterable[Recognition],
) -> Decision:
    """
    Build the current coaching decision.

    This function is deliberately pure with respect to Streamlit and does not
    query the database. All inputs are existing engine outputs.
    """
    athlete_id = performance_dna.athlete_id
    signals = _build_system_signals(performance_dna)
    recent = _recent_recognition_items(recognition_index)

    strongest = _strongest_system(performance_dna)
    opportunity = _primary_opportunity(performance_dna)

    strongest_label = (
        SYSTEM_LABELS.get(strongest)
        if strongest
        else None
    )
    opportunity_label = (
        SYSTEM_LABELS.get(opportunity)
        if opportunity
        else None
    )

    direction, direction_detail = _direction_from_recognition(recent)

    provisional_next_session = (
        SYSTEM_SESSION_FAMILIES.get(opportunity)
        if opportunity
        else None
    )

    # We may identify the development focus now, but hard sessions cannot be
    # prescribed confidently until readiness/fatigue is connected.
    if provisional_next_session is None:
        recommendation_ready = False
        recommendation_status = "Still learning the development priority"
    elif opportunity in QUALITY_SYSTEMS:
        recommendation_ready = False
        recommendation_status = (
            "Development focus identified; Readiness Coach must confirm timing"
        )
    else:
        recommendation_ready = False
        recommendation_status = (
            "Session family identified; readiness evidence is still required"
        )

    supporters = _supporting_coaches(
        performance_dna,
        coach_consensus,
        opportunity,
    )

    confidence = _decision_confidence(
        performance_dna,
        coach_consensus,
        capability,
        opportunity,
        recent,
    )

    recent_labels = tuple(
        item.celebration
        for item in recent[:3]
        if item.celebration
    )

    if strongest_label and opportunity_label:
        headline = (
            f"{strongest_label} is a current strength; "
            f"{opportunity_label} is the clearest next opportunity."
        )
    elif opportunity_label:
        headline = (
            f"{opportunity_label} is the clearest current opportunity."
        )
    elif strongest_label:
        headline = (
            f"{strongest_label} is providing a strong current foundation."
        )
    else:
        headline = "The coaching picture is still building."

    summary_parts = []

    if direction:
        summary_parts.append(
            f"Recent direction: {direction.lower()}."
        )

    if capability.available and capability.target_probability is not None:
        summary_parts.append(
            (
                "Current goal confidence is "
                f"{capability.target_probability:.0%}."
            )
        )
    elif capability.available:
        summary_parts.append(
            "A current capability estimate is available."
        )

    if opportunity_label:
        summary_parts.append(
            (
                f"The coaching system would prioritise "
                f"{opportunity_label.lower()} development next."
            )
        )

    if provisional_next_session:
        summary_parts.append(
            (
                f"The provisional session family is "
                f"{provisional_next_session}, but timing remains subject to "
                "readiness."
            )
        )

    evidence = []

    if strongest and strongest in performance_dna.system_scores:
        evidence.append(
            (
                f"{strongest_label} system signal: "
                f"{performance_dna.system_scores[strongest]:.1f}"
            )
        )

    if opportunity and opportunity in performance_dna.system_scores:
        evidence.append(
            (
                f"{opportunity_label} system signal: "
                f"{performance_dna.system_scores[opportunity]:.1f}"
            )
        )

    if coach_consensus.lead_coach:
        evidence.append(
            f"Lead specialist: {coach_consensus.lead_coach}"
        )

    evidence.append(
        f"Decision confidence: {confidence:.0%}"
    )

    if recent_labels:
        evidence.append(
            "Recent recognition: " + "; ".join(recent_labels)
        )

    limitations = (
        (
            "Readiness/fatigue is not yet connected, so the engine identifies "
            "development focus but does not confidently prescribe tomorrow's "
            "hard session."
        ),
        (
            "Structured workout rankings remain provisional until rep-level "
            "Workout DNA is connected."
        ),
        (
            "The Decision Engine consumes existing evidence; it does not "
            "silently invent new interpretations of a run."
        ),
    )

    return Decision(
        athlete_id=athlete_id,
        strongest_system=strongest,
        strongest_system_label=strongest_label,
        primary_opportunity=opportunity,
        primary_opportunity_label=opportunity_label,
        direction=direction,
        direction_detail=direction_detail,
        provisional_next_session=provisional_next_session,
        recommendation_ready=recommendation_ready,
        recommendation_status=recommendation_status,
        headline=headline,
        summary=" ".join(summary_parts),
        confidence=confidence,
        supporting_coaches=supporters,
        coaching_signals=signals,
        recent_recognitions=recent_labels,
        evidence=tuple(evidence),
        limitations=limitations,
    )


def decision_to_dict(decision: Decision) -> dict:
    return {
        "athlete_id": decision.athlete_id,
        "strongest_system": decision.strongest_system,
        "strongest_system_label": decision.strongest_system_label,
        "primary_opportunity": decision.primary_opportunity,
        "primary_opportunity_label": decision.primary_opportunity_label,
        "direction": decision.direction,
        "direction_detail": decision.direction_detail,
        "provisional_next_session": decision.provisional_next_session,
        "recommendation_ready": decision.recommendation_ready,
        "recommendation_status": decision.recommendation_status,
        "headline": decision.headline,
        "summary": decision.summary,
        "confidence": decision.confidence,
        "supporting_coaches": list(decision.supporting_coaches),
        "recent_recognitions": list(decision.recent_recognitions),
        "evidence": list(decision.evidence),
        "limitations": list(decision.limitations),
        "coaching_signals": [
            {
                "key": signal.key,
                "label": signal.label,
                "value": signal.value,
                "confidence": signal.confidence,
                "direction": signal.direction,
                "evidence": list(signal.evidence),
            }
            for signal in decision.coaching_signals
        ],
        "model_version": decision.model_version,
    }

"""
Athlete DNA Aggregator.

Workout DNA answers:
    What did this representative workout train?

Athlete DNA answers:
    What does the athlete's current overall profile look like?

The aggregator deliberately prevents one workout from redefining the athlete.
It combines:

- Workout DNA
- Race Coach evidence
- Workout Coach evidence
- Threshold Coach evidence
- Overall historical evidence strength

The output is an early athlete profile, not a medical or laboratory
measurement. Every score includes confidence and transparent contributors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.evidence import EvidenceBundle, EvidenceItem, EvidenceStatus


SYSTEMS = ("threshold", "speed", "endurance", "aerobic")

SYSTEM_LABELS = {
    "threshold": "Threshold",
    "speed": "Speed / VO₂",
    "endurance": "Endurance",
    "aerobic": "Aerobic",
}


@dataclass(frozen=True)
class AthleteSystemScore:
    system: str
    score: float
    confidence: float
    contributors: tuple[str, ...]
    interpretation: str


@dataclass(frozen=True)
class AthleteDNA:
    athlete_id: int
    system_scores: dict[str, float]
    system_confidence: dict[str, float]
    strongest_system: str
    developing_system: str
    overall_confidence: float
    profile_label: str
    summary: str
    details: tuple[AthleteSystemScore, ...]
    model_version: int = 1


def _normalise_key(item: EvidenceItem) -> str:
    key = str(item.key or "").strip().lower()

    aliases = {
        "recent_race": "race",
        "race": "race",
        "race_coach": "race",
        "workout": "workout",
        "workout_coach": "workout",
        "threshold": "threshold",
        "threshold_coach": "threshold",
    }

    return aliases.get(key, key)


def _available(item: EvidenceItem | None) -> bool:
    return (
        item is not None
        and item.status == EvidenceStatus.AVAILABLE
        and item.confidence > 0
    )


def _coach_signal(
    item: EvidenceItem | None,
    *,
    consensus_prediction_s: float | None,
) -> tuple[float, float, str]:
    """
    Convert one specialist opinion into a stable 0-100 profile signal.

    Confidence establishes the base strength. A faster or slower prediction
    than the consensus only makes a modest adjustment, preventing one coach
    from dominating the athlete profile.
    """
    if not _available(item):
        return 50.0, 0.0, "No available specialist opinion"

    signal = 50.0 + 35.0 * item.confidence

    if (
        item.predicted_seconds is not None
        and consensus_prediction_s is not None
        and consensus_prediction_s > 0
    ):
        relative_difference = (
            consensus_prediction_s - item.predicted_seconds
        ) / consensus_prediction_s

        # Cap the fitness adjustment at +/- 10 points.
        signal += max(
            min(relative_difference * 200.0, 10.0),
            -10.0,
        )

    signal = max(35.0, min(signal, 95.0))
    explanation = (
        f"{item.title}: {item.confidence:.0%} confidence"
    )

    return signal, item.confidence, explanation


def _weighted_average(
    values: list[tuple[float, float]],
    *,
    default: float = 50.0,
) -> tuple[float, float]:
    usable = [
        (value, weight)
        for value, weight in values
        if weight > 0
    ]

    if not usable:
        return default, 0.0

    total_weight = sum(weight for _, weight in usable)
    score = sum(value * weight for value, weight in usable) / total_weight

    # Confidence reflects how much of the intended model was populated.
    confidence = min(total_weight, 1.0)

    return score, confidence


def _interpret(score: float) -> str:
    if score >= 85:
        return "Standout current strength"
    if score >= 75:
        return "Strong current system"
    if score >= 65:
        return "Well developed"
    if score >= 55:
        return "Solid, with room to build"
    return "Developing evidence"


def build_athlete_dna(
    evidence_bundle: EvidenceBundle,
    *,
    consensus_prediction_s: float | None = None,
) -> AthleteDNA:
    items = {
        _normalise_key(item): item
        for item in evidence_bundle.items
    }

    race_item = items.get("race")
    workout_item = items.get("workout")
    threshold_item = items.get("threshold")

    race_signal, race_conf, race_reason = _coach_signal(
        race_item,
        consensus_prediction_s=consensus_prediction_s,
    )
    workout_signal, workout_conf, workout_reason = _coach_signal(
        workout_item,
        consensus_prediction_s=consensus_prediction_s,
    )
    threshold_signal, threshold_conf, threshold_reason = _coach_signal(
        threshold_item,
        consensus_prediction_s=consensus_prediction_s,
    )

    workout_dna = (
        workout_item.metadata.get("best_workout_dna", {})
        if workout_item is not None
        else {}
    )
    workout_scores = workout_dna.get("stimulus_scores", {})
    workout_dna_conf = float(
        workout_dna.get("confidence", 0) or 0
    )

    history_score = 50.0 + 40.0 * evidence_bundle.confidence
    history_conf = evidence_bundle.confidence

    model = {
        "threshold": [
            (
                float(workout_scores.get("threshold", 50) or 50),
                0.25 * workout_dna_conf,
                "Representative Workout DNA",
            ),
            (
                threshold_signal,
                0.35 * threshold_conf,
                threshold_reason,
            ),
            (
                race_signal,
                0.20 * race_conf,
                race_reason,
            ),
            (
                workout_signal,
                0.20 * workout_conf,
                workout_reason,
            ),
        ],
        "speed": [
            (
                float(workout_scores.get("speed", 50) or 50),
                0.35 * workout_dna_conf,
                "Representative Workout DNA",
            ),
            (
                race_signal,
                0.30 * race_conf,
                race_reason,
            ),
            (
                workout_signal,
                0.25 * workout_conf,
                workout_reason,
            ),
            (
                threshold_signal,
                0.10 * threshold_conf,
                threshold_reason,
            ),
        ],
        "endurance": [
            (
                float(workout_scores.get("endurance", 50) or 50),
                0.20 * workout_dna_conf,
                "Representative Workout DNA",
            ),
            (
                race_signal,
                0.30 * race_conf,
                race_reason,
            ),
            (
                threshold_signal,
                0.20 * threshold_conf,
                threshold_reason,
            ),
            (
                history_score,
                0.30 * history_conf,
                "Long-term activity history",
            ),
        ],
        "aerobic": [
            (
                float(workout_scores.get("aerobic", 50) or 50),
                0.20 * workout_dna_conf,
                "Representative Workout DNA",
            ),
            (
                threshold_signal,
                0.30 * threshold_conf,
                threshold_reason,
            ),
            (
                race_signal,
                0.20 * race_conf,
                race_reason,
            ),
            (
                history_score,
                0.30 * history_conf,
                "Long-term activity history",
            ),
        ],
    }

    details = []
    system_scores = {}
    system_confidence = {}

    for system in SYSTEMS:
        contributions = model[system]
        score, confidence = _weighted_average(
            [
                (value, weight)
                for value, weight, _ in contributions
            ]
        )

        score = max(0.0, min(score, 100.0))
        system_scores[system] = round(score, 1)
        system_confidence[system] = round(confidence, 4)

        contributors = tuple(
            reason
            for _, weight, reason in contributions
            if weight > 0
        )

        details.append(
            AthleteSystemScore(
                system=system,
                score=round(score, 1),
                confidence=round(confidence, 4),
                contributors=contributors,
                interpretation=_interpret(score),
            )
        )

    strongest_system = max(
        system_scores,
        key=system_scores.get,
    )
    developing_system = min(
        system_scores,
        key=system_scores.get,
    )

    overall_confidence = sum(
        system_confidence.values()
    ) / len(system_confidence)

    strongest_label = SYSTEM_LABELS[strongest_system]
    developing_label = SYSTEM_LABELS[developing_system]

    profile_label = (
        f"{strongest_label}-led athlete profile"
    )
    summary = (
        f"{strongest_label} is the strongest current system. "
        f"{developing_label} currently has the lowest combined score, "
        "which may reflect either a genuine limiter or thinner evidence."
    )

    return AthleteDNA(
        athlete_id=evidence_bundle.athlete_id,
        system_scores=system_scores,
        system_confidence=system_confidence,
        strongest_system=strongest_system,
        developing_system=developing_system,
        overall_confidence=round(overall_confidence, 4),
        profile_label=profile_label,
        summary=summary,
        details=tuple(details),
    )


def athlete_dna_to_dict(dna: AthleteDNA) -> dict[str, Any]:
    return {
        "athlete_id": dna.athlete_id,
        "system_scores": dna.system_scores,
        "system_confidence": dna.system_confidence,
        "strongest_system": dna.strongest_system,
        "developing_system": dna.developing_system,
        "overall_confidence": dna.overall_confidence,
        "profile_label": dna.profile_label,
        "summary": dna.summary,
        "model_version": dna.model_version,
        "details": [
            {
                "system": detail.system,
                "score": detail.score,
                "confidence": detail.confidence,
                "contributors": list(detail.contributors),
                "interpretation": detail.interpretation,
            }
            for detail in dna.details
        ],
    }

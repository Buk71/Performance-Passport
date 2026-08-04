"""
Personal Performance DNA.

This module translates specialist evidence into one athlete-centred coaching
view. It does not replace the specialist coaches; it gives them a shared
language so the Goal Coach can explain where the athlete is strong, where
evidence is limited and why the consensus prediction has changed.

Version 1 uses the coaches already connected:
- Race Coach
- Workout Coach
- Threshold Coach

Future Easy Run, Endurance, Speed, Environment and Readiness coaches can join
without changing the dashboard contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.evidence import EvidenceBundle, EvidenceItem, EvidenceStatus


@dataclass(frozen=True)
class CoachVerdict:
    key: str
    title: str
    icon: str
    status: str
    verdict: str
    confidence: float
    predicted_seconds: float | None
    evidence_summary: str
    signal: str
    available: bool


@dataclass(frozen=True)
class PerformanceDNA:
    athlete_id: int
    overall_confidence: float
    consensus_status: str
    headline: str
    summary: str
    strongest_signal: str | None
    limiting_signal: str | None
    verdicts: tuple[CoachVerdict, ...]
    system_scores: dict[str, float]
    workout_archetype: str | None
    workout_dna_confidence: float
    available_coach_count: int
    total_coach_count: int


COACH_DEFINITIONS = {
    "race": {
        "title": "Race Coach",
        "icon": "🏁",
        "signal": "Race fitness",
    },
    "workout": {
        "title": "Workout Coach",
        "icon": "🏃",
        "signal": "Quality-session fitness",
    },
    "threshold": {
        "title": "Threshold Coach",
        "icon": "❤️",
        "signal": "Threshold strength",
    },
}

FUTURE_COACHES = (
    {
        "key": "easy",
        "title": "Easy Run Coach",
        "icon": "😊",
        "signal": "Aerobic efficiency",
    },
    {
        "key": "endurance",
        "title": "Endurance Coach",
        "icon": "🧱",
        "signal": "Durability",
    },
    {
        "key": "readiness",
        "title": "Readiness Coach",
        "icon": "🧠",
        "signal": "Training readiness",
    },
)


def _confidence_word(confidence: float) -> str:
    if confidence >= 0.85:
        return "Very strong"
    if confidence >= 0.70:
        return "Strong"
    if confidence >= 0.50:
        return "Moderate"
    if confidence > 0:
        return "Limited"
    return "Building"


def _status_from_item(item: EvidenceItem) -> str:
    if item.status != EvidenceStatus.AVAILABLE:
        return "building"

    if item.confidence >= 0.80:
        return "strong"
    if item.confidence >= 0.55:
        return "steady"
    return "limited"


def _verdict_from_item(item: EvidenceItem) -> str:
    if item.status != EvidenceStatus.AVAILABLE:
        return "Still learning"

    if item.predicted_seconds is not None:
        return _confidence_word(item.confidence)

    if item.confidence >= 0.80:
        return "Strong evidence"
    if item.confidence >= 0.55:
        return "Useful evidence"
    return "Early evidence"


def _normalise_key(value) -> str:
    """
    Normalise either an EvidenceItem or a raw string key/title.

    Performance DNA uses this for provider keys and title aliases, so the
    helper must safely accept both forms.
    """
    if isinstance(value, EvidenceItem):
        raw_key = value.key
    else:
        raw_key = value

    key = str(raw_key or "").strip().lower()

    aliases = {
        # Current provider keys
        "recent_race": "race",
        "workout": "workout",
        "threshold": "threshold",

        # Backwards-compatible and human-readable aliases
        "race": "race",
        "race_coach": "race",
        "race_evidence": "race",
        "race_prediction": "race",
        "workout_coach": "workout",
        "workout_evidence": "workout",
        "threshold_coach": "threshold",
        "threshold_evidence": "threshold",
    }

    return aliases.get(key, key)


def _available_verdict(item: EvidenceItem) -> CoachVerdict:
    key = _normalise_key(item)
    definition = COACH_DEFINITIONS.get(
        key,
        {
            "title": item.title,
            "icon": "📊",
            "signal": item.title,
        },
    )

    return CoachVerdict(
        key=key,
        title=definition["title"],
        icon=definition["icon"],
        status=_status_from_item(item),
        verdict=_verdict_from_item(item),
        confidence=item.confidence,
        predicted_seconds=item.predicted_seconds,
        evidence_summary=item.summary,
        signal=definition["signal"],
        available=item.status == EvidenceStatus.AVAILABLE,
    )


def _future_verdict(definition: dict[str, str]) -> CoachVerdict:
    return CoachVerdict(
        key=definition["key"],
        title=definition["title"],
        icon=definition["icon"],
        status="building",
        verdict="Coming next",
        confidence=0.0,
        predicted_seconds=None,
        evidence_summary=(
            f"{definition['title']} is not connected yet. "
            "Performance Passport will not invent an opinion."
        ),
        signal=definition["signal"],
        available=False,
    )


def build_performance_dna(
    evidence_bundle: EvidenceBundle,
    *,
    consensus_prediction_s: float | None = None,
) -> PerformanceDNA:
    item_by_key = {}

    for item in evidence_bundle.items:
        normalised_key = _normalise_key(item)

        if normalised_key not in item_by_key:
            item_by_key[normalised_key] = item

        title_key = (
            (item.title or "")
            .strip()
            .lower()
            .replace(" ", "_")
        )
        title_alias = _normalise_key(title_key)

        if title_alias not in item_by_key:
            item_by_key[title_alias] = item

    verdicts = []

    for key in ("race", "workout", "threshold"):
        item = item_by_key.get(key)

        if item is not None:
            verdicts.append(_available_verdict(item))
        else:
            definition = COACH_DEFINITIONS[key]
            verdicts.append(
                CoachVerdict(
                    key=key,
                    title=definition["title"],
                    icon=definition["icon"],
                    status="building",
                    verdict="Still learning",
                    confidence=0.0,
                    predicted_seconds=None,
                    evidence_summary=(
                        f"{definition['title']} has not returned evidence yet."
                    ),
                    signal=definition["signal"],
                    available=False,
                )
            )

    verdicts.extend(
        _future_verdict(definition)
        for definition in FUTURE_COACHES
    )

    available = [
        verdict
        for verdict in verdicts
        if verdict.available
    ]

    if available:
        total_weight = sum(
            max(verdict.confidence, 0.05)
            for verdict in available
        )
        overall_confidence = sum(
            verdict.confidence * max(verdict.confidence, 0.05)
            for verdict in available
        ) / total_weight
        strongest = max(
            available,
            key=lambda verdict: verdict.confidence,
        )
        weakest = min(
            available,
            key=lambda verdict: verdict.confidence,
        )
    else:
        overall_confidence = 0.0
        strongest = None
        weakest = None

    prediction_verdicts = [
        verdict
        for verdict in available
        if verdict.predicted_seconds is not None
    ]

    if len(prediction_verdicts) >= 2:
        fastest = min(
            verdict.predicted_seconds
            for verdict in prediction_verdicts
        )
        slowest = max(
            verdict.predicted_seconds
            for verdict in prediction_verdicts
        )
        spread = slowest - fastest

        if consensus_prediction_s and consensus_prediction_s > 0:
            spread_ratio = spread / consensus_prediction_s
        else:
            spread_ratio = 0.0

        if spread_ratio <= 0.02:
            consensus_status = "aligned"
            headline = "The coaching team is closely aligned."
        elif spread_ratio <= 0.05:
            consensus_status = "balanced"
            headline = "The coaches broadly agree, with useful caution."
        else:
            consensus_status = "mixed"
            headline = "The coaches see different signals in your form."
    elif len(prediction_verdicts) == 1:
        consensus_status = "developing"
        headline = "One coach currently carries the prediction."
    else:
        consensus_status = "building"
        headline = "The coaching team is still building its view."

    available_count = len(available)

    if strongest is not None:
        summary = (
            f"{strongest.title} currently provides the strongest signal. "
        )
    else:
        summary = ""

    if weakest is not None and weakest.key != strongest.key:
        summary += (
            f"{weakest.title} is the area with the least certain evidence. "
        )

    remaining = len(verdicts) - available_count

    if remaining:
        summary += (
            f"{remaining} specialist coach"
            f"{'es are' if remaining != 1 else ' is'} still being connected."
        )

    workout_item = item_by_key.get("workout")
    workout_dna = (
        workout_item.metadata.get("best_workout_dna", {})
        if workout_item is not None
        else {}
    )

    raw_system_scores = workout_dna.get("stimulus_scores", {})
    system_scores = {
        "threshold": float(raw_system_scores.get("threshold", 0) or 0),
        "speed": float(raw_system_scores.get("speed", 0) or 0),
        "endurance": float(raw_system_scores.get("endurance", 0) or 0),
        "aerobic": float(raw_system_scores.get("aerobic", 0) or 0),
    }
    workout_archetype = workout_dna.get("archetype")
    workout_dna_confidence = float(
        workout_dna.get("confidence", 0) or 0
    )

    if any(system_scores.values()):
        strongest_system = max(
            system_scores,
            key=system_scores.get,
        )
        weakest_system = min(
            system_scores,
            key=system_scores.get,
        )

        label_map = {
            "threshold": "Threshold",
            "speed": "Speed / VO₂",
            "endurance": "Endurance",
            "aerobic": "Aerobic",
        }

        summary += (
            f" Current Workout DNA is strongest in "
            f"{label_map[strongest_system]} and weakest in "
            f"{label_map[weakest_system]}."
        )

    return PerformanceDNA(
        athlete_id=evidence_bundle.athlete_id,
        overall_confidence=round(overall_confidence, 4),
        consensus_status=consensus_status,
        headline=headline,
        summary=summary.strip(),
        strongest_signal=(
            strongest.signal if strongest is not None else None
        ),
        limiting_signal=(
            weakest.signal if weakest is not None else None
        ),
        verdicts=tuple(verdicts),
        system_scores=system_scores,
        workout_archetype=workout_archetype,
        workout_dna_confidence=workout_dna_confidence,
        available_coach_count=available_count,
        total_coach_count=len(verdicts),
    )


def performance_dna_to_dict(
    dna: PerformanceDNA,
) -> dict[str, Any]:
    return {
        "athlete_id": dna.athlete_id,
        "overall_confidence": dna.overall_confidence,
        "consensus_status": dna.consensus_status,
        "headline": dna.headline,
        "summary": dna.summary,
        "strongest_signal": dna.strongest_signal,
        "limiting_signal": dna.limiting_signal,
        "available_coach_count": dna.available_coach_count,
        "total_coach_count": dna.total_coach_count,
        "system_scores": dna.system_scores,
        "workout_archetype": dna.workout_archetype,
        "workout_dna_confidence": dna.workout_dna_confidence,
        "verdicts": [
            {
                "key": verdict.key,
                "title": verdict.title,
                "icon": verdict.icon,
                "status": verdict.status,
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "predicted_seconds": verdict.predicted_seconds,
                "evidence_summary": verdict.evidence_summary,
                "signal": verdict.signal,
                "available": verdict.available,
            }
            for verdict in dna.verdicts
        ],
    }

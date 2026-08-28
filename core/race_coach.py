"""Compose established prediction services into a complete Race Coach view.

Race Coach does not introduce a fourth prediction formula. It asks the current
Race, Workout and Threshold specialists the selected-distance question, aligns
the headline with the same endurance-calibrated anchors used on Home, and
exposes the evidence and readiness distinction needed for an honest race plan.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

from core.coach_brain import CoachBrain
from core.distance_prediction_outlook import (
    DistancePredictionAnchor,
    DistancePredictionOutlook,
    build_distance_prediction_outlook,
)
from core.evidence import EvidenceBundle, EvidenceItem
from core.home_predictions import HomePredictions, build_goal_predictions


MODEL_VERSION = 1
STANDARD_LABELS = {"5K", "10K", "Half marathon", "Marathon"}


@dataclass(frozen=True)
class RaceCoachEvidenceView:
    key: str
    title: str
    status: str
    predicted_seconds: float | None
    confidence: float
    sample_size: int
    effective_weight_share: float
    position: str
    is_lead: bool
    summary: str
    facts: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class RacePacingSegment:
    label: str
    distance: str
    pace_low_s_per_km: float | None
    pace_high_s_per_km: float | None
    cue: str


@dataclass(frozen=True)
class RacePacingGuide:
    available: bool
    basis_label: str
    basis_seconds: float | None
    average_pace_s_per_km: float | None
    target_led: bool
    headline: str
    segments: tuple[RacePacingSegment, ...]
    caveat: str


@dataclass(frozen=True)
class RaceCoachDetail:
    athlete_id: int
    athlete_name: str
    goal: dict[str, Any]
    predictions: HomePredictions
    raw_predictions: HomePredictions
    distance_outlook: DistancePredictionOutlook
    selected_anchor: DistancePredictionAnchor | None
    evidence: tuple[RaceCoachEvidenceView, ...]
    latest_evidence_date: str | None
    alignment_note: str
    model_version: int = MODEL_VERSION


def _athlete_name(athlete_id: int) -> str:
    from core.database import get_connection

    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT first_name, last_name FROM athletes WHERE id = ?",
            (int(athlete_id),),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return f"Athlete {athlete_id}"
    return f"{row[0] or ''} {row[1] or ''}".strip() or f"Athlete {athlete_id}"


def _selected_anchor(
    predictions: HomePredictions,
    outlook: DistancePredictionOutlook,
) -> DistancePredictionAnchor | None:
    if predictions.distance_label not in STANDARD_LABELS:
        return None
    return next(
        (
            anchor
            for anchor in outlook.anchors
            if anchor.label == predictions.distance_label and anchor.available
        ),
        None,
    )


def _goal_probability(
    central_seconds: float,
    low_seconds: float,
    high_seconds: float,
    target_seconds: float | None,
) -> float | None:
    if target_seconds is None or target_seconds <= 0:
        return None
    uncertainty = max((high_seconds - low_seconds) / 2.0, 10.0)
    z = (target_seconds - central_seconds) / uncertainty
    return max(0.02, min(1.0 / (1.0 + math.exp(-1.7 * z)), 0.98))


def _align_predictions(
    predictions: HomePredictions,
    anchor: DistancePredictionAnchor | None,
) -> HomePredictions:
    """Use Home's calibrated standard-distance anchor without hiding its origin."""
    if (
        anchor is None
        or anchor.central_seconds is None
        or predictions.central_seconds is None
    ):
        return predictions
    central = float(anchor.central_seconds)
    raw_central = float(predictions.central_seconds)
    low_width = max(raw_central - float(predictions.low_seconds or raw_central), 10.0)
    high_width = max(float(predictions.high_seconds or raw_central) - raw_central, 10.0)
    low = max(1.0, central - low_width)
    high = central + high_width
    target = predictions.target_seconds
    return replace(
        predictions,
        central_seconds=round(central, 1),
        low_seconds=round(low, 1),
        high_seconds=round(high, 1),
        confidence=anchor.confidence,
        target_gap_seconds=(round(central - target, 1) if target else None),
        target_probability=_goal_probability(central, low, high, target),
        explanation=anchor.explanation,
    )


def _strings(value: Any, *, limit: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if item)[:limit]


def _evidence_facts(item: EvidenceItem) -> tuple[str, ...]:
    metadata: Mapping[str, Any] = item.metadata or {}
    facts = list(_strings(metadata.get("strengths"), limit=3))
    if not facts and item.key == "recent_race":
        title = metadata.get("selected_title")
        date = metadata.get("activity_date")
        distance = metadata.get("distance_km")
        if title:
            facts.append(f"Selected performance: {title}")
        if date:
            facts.append(f"Performance date: {str(date)[:10]}")
        if distance:
            facts.append(f"Recorded distance: {float(distance):.2f} km")
    if not facts and item.key == "workout":
        latest = metadata.get("latest_workout")
        if isinstance(latest, Mapping):
            if latest.get("description"):
                facts.append(str(latest["description"]))
            if latest.get("date"):
                facts.append(f"Latest representative session: {latest['date']}")
    if not facts and item.sample_size:
        facts.append(f"{item.sample_size} qualifying evidence item(s)")
    return tuple(facts[:3])


def _position_for(item: EvidenceItem, predictions: HomePredictions) -> tuple[str, bool]:
    match = next(
        (position for position in predictions.coach_positions if position.title == item.title),
        None,
    )
    if match is None:
        return ("Evidence building" if item.predicted_seconds is None else "Supporting view", False)
    return match.position, bool(match.is_lead)


def _evidence_views(
    bundle: EvidenceBundle,
    predictions: HomePredictions,
) -> tuple[RaceCoachEvidenceView, ...]:
    specialist = [
        item
        for item in bundle.items
        if item.key in {"recent_race", "workout", "threshold"}
    ]
    total_weight = sum(item.effective_weight for item in specialist)
    views = []
    for item in specialist:
        position, is_lead = _position_for(item, predictions)
        views.append(
            RaceCoachEvidenceView(
                key=item.key,
                title=item.title,
                status=item.status.value,
                predicted_seconds=item.predicted_seconds,
                confidence=item.confidence,
                sample_size=item.sample_size,
                effective_weight_share=(
                    item.effective_weight / total_weight if total_weight > 0 else 0.0
                ),
                position=position,
                is_lead=is_lead,
                summary=item.summary,
                facts=_evidence_facts(item),
                limitations=_strings(item.metadata.get("limitations"), limit=2),
            )
        )
    return tuple(views)


def build_race_coach_detail(
    athlete_id: int,
    goal: dict[str, Any],
) -> RaceCoachDetail:
    """Build one selected-distance view without mutating the athlete's goal."""
    brain = CoachBrain(int(athlete_id))
    bundle = brain.build_evidence(goal)
    raw_predictions = build_goal_predictions(
        int(athlete_id),
        goal,
        evidence=bundle,
    )
    distance_outlook = build_distance_prediction_outlook(
        int(athlete_id),
        active_predictions=raw_predictions,
    )
    anchor = _selected_anchor(raw_predictions, distance_outlook)
    predictions = _align_predictions(raw_predictions, anchor)
    history = next(
        (item for item in bundle.items if item.key == "activity_history"),
        None,
    )
    latest_date = (
        history.metadata.get("latest_activity_date")
        if history is not None
        else None
    )
    if anchor is not None and anchor.transfer_fraction > 0:
        alignment_note = (
            f"The selected-distance headline matches Home. Recent endurance "
            f"evidence supports {anchor.transfer_fraction:.0%} of the gap from "
            "current shorter-distance fitness to its standard equivalent."
        )
    elif anchor is not None and anchor.readiness_label:
        alignment_note = (
            f"The selected-distance headline matches Home. Readiness is shown "
            f"separately as {anchor.readiness_label.lower()}."
        )
    else:
        alignment_note = (
            "The selected capability comes directly from the three specialist "
            "views for this distance."
        )
    return RaceCoachDetail(
        athlete_id=int(athlete_id),
        athlete_name=_athlete_name(int(athlete_id)),
        goal=dict(goal),
        predictions=predictions,
        raw_predictions=raw_predictions,
        distance_outlook=distance_outlook,
        selected_anchor=anchor,
        evidence=_evidence_views(bundle, raw_predictions),
        latest_evidence_date=str(latest_date)[:10] if latest_date else None,
        alignment_note=alignment_note,
    )


def build_race_pacing_guide(
    detail: RaceCoachDetail,
    *,
    selected_seconds: float | None,
    selected_low_seconds: float | None,
    selected_high_seconds: float | None,
    target_probability: float | None,
) -> RacePacingGuide:
    """Translate the selected outlook into a restrained three-part pacing cue."""
    predictions = detail.predictions
    anchor = detail.selected_anchor
    distance_km = anchor.distance_km if anchor is not None else None
    if distance_km is None:
        distance_lookup = {
            "5 miles": 8.04672,
            "10 miles": 16.09344,
        }
        distance_km = distance_lookup.get(predictions.distance_label)
    if distance_km is None or selected_seconds is None:
        return RacePacingGuide(
            available=False,
            basis_label="Pacing still building",
            basis_seconds=None,
            average_pace_s_per_km=None,
            target_led=False,
            headline="A supported distance forecast is needed before pacing can be suggested.",
            segments=(),
            caveat="Use effort and established race experience until the evidence is available.",
        )

    target = predictions.target_seconds
    target_supported = bool(
        target is not None
        and selected_low_seconds is not None
        and selected_high_seconds is not None
        and target_probability is not None
        and target_probability >= 0.25
        and target >= selected_low_seconds - max(selected_seconds * 0.005, 10.0)
        and target <= selected_high_seconds
    )
    basis_seconds = float(target if target_supported else selected_seconds)
    average = basis_seconds / distance_km
    if distance_km <= 5.2:
        distances = ("First 1 km", "Kilometres 2–4", "Final kilometre")
    elif distance_km <= 10.2:
        distances = ("First 2 km", "Kilometres 3–8", "Final 2 km")
    elif distance_km <= 22.0:
        distances = ("First 5 km", "5–17 km", "Final 4.1 km")
    else:
        distances = ("First 5 km", "5–32 km", "Final 10.2 km")
    segments = (
        RacePacingSegment(
            label="Settle",
            distance=distances[0],
            pace_low_s_per_km=average + 2.0,
            pace_high_s_per_km=average + (4.0 if distance_km >= 21.0 else 3.0),
            cue="Start under control; do not borrow time from the closing stages.",
        ),
        RacePacingSegment(
            label="Hold",
            distance=distances[1],
            pace_low_s_per_km=average - 1.0,
            pace_high_s_per_km=average + 1.0,
            cue="Settle near average pace and judge effort, terrain and conditions.",
        ),
        RacePacingSegment(
            label="Decide",
            distance=distances[2],
            pace_low_s_per_km=None,
            pace_high_s_per_km=None,
            cue="Increase effort only if form and breathing remain controlled.",
        ),
    )
    return RacePacingGuide(
        available=True,
        basis_label="Target-led pacing" if target_supported else "Capability-led pacing",
        basis_seconds=basis_seconds,
        average_pace_s_per_km=average,
        target_led=target_supported,
        headline=(
            "The target is close enough to the supported range to pace deliberately."
            if target_supported
            else "Use the selected-condition capability as the pacing anchor."
        ),
        segments=segments,
        caveat=(
            "This is a pacing framework, not a promise. Course position, weather, "
            "pain, illness and how the athlete feels take precedence."
        ),
    )

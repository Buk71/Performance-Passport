"""Auditable Coaching Team detail assembled from existing real evidence.

Race, Workout and Threshold remain the only coaches that contribute a direct
goal-time opinion. Aerobic & Durability and Environment are supporting
specialists: they explain progress and conditions without being counted as
extra votes in the established Coach Consensus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.coach_brain import CoachBrain
from core.database import get_connection
from core.evidence import EvidenceBundle, EvidenceItem, EvidenceStatus
from core.home_predictions import HomePredictions, build_goal_predictions, load_run_profiles
from core.progress import ProgressSummary, build_progress_summary


@dataclass(frozen=True)
class CoachFact:
    label: str
    value: str
    detail: str = ""
    activity_id: int | None = None


@dataclass(frozen=True)
class CoachProfile:
    key: str
    title: str
    code: str
    role: str
    available: bool
    contributes_to_consensus: bool
    confidence: float
    sample_size: int
    predicted_seconds: float | None
    position: str | None
    is_lead: bool
    summary: str
    strengths: tuple[str, ...]
    limitations: tuple[str, ...]
    facts: tuple[CoachFact, ...]


@dataclass(frozen=True)
class CoachingTeamDetail:
    athlete_id: int
    athlete_name: str
    goal_name: str
    distance_label: str
    available: bool
    target_seconds: float | None
    central_seconds: float | None
    low_seconds: float | None
    high_seconds: float | None
    confidence: float
    consensus_status: str
    consensus_headline: str
    explanation: str
    lead_coach: str | None
    strongest_system: str | None
    limiting_system: str | None
    prediction_coaches: tuple[CoachProfile, ...]
    supporting_coaches: tuple[CoachProfile, ...]
    notes: tuple[str, ...]
    model_version: int = 1


def _athlete_name(athlete_id: int) -> str | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT first_name, last_name FROM athletes WHERE id = ?",
        (athlete_id,),
    )
    row = cursor.fetchone()
    connection.close()
    if row is None:
        return None
    return f"{row[0] or ''} {row[1] or ''}".strip()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pace(seconds_per_km: Any) -> str:
    seconds = _number(seconds_per_km)
    if seconds is None or seconds <= 0:
        return "—"
    rounded = int(round(seconds))
    minutes, remainder = divmod(rounded, 60)
    return f"{minutes}:{remainder:02d}/km"


def _distance(value: Any) -> str:
    number = _number(value)
    return f"{number:.2f} km" if number is not None else "—"


def _metadata_list(item: EvidenceItem, key: str) -> tuple[str, ...]:
    value = item.metadata.get(key, ())
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(entry) for entry in value if str(entry).strip())


def _selected_fact(
    item: EvidenceItem,
    *,
    date_key: str = "activity_date",
    id_key: str = "activity_id",
) -> CoachFact | None:
    title = str(item.metadata.get("selected_title") or "").strip()
    date = str(item.metadata.get(date_key) or "").strip()
    if not title and not date:
        return None
    activity_id = _integer(item.metadata.get(id_key))
    return CoachFact(
        label="Selected evidence",
        value=title or "Historical evidence",
        detail=date,
        activity_id=activity_id,
    )


def _race_facts(item: EvidenceItem) -> tuple[CoachFact, ...]:
    facts = []
    selected = _selected_fact(item)
    if selected:
        facts.append(selected)
    facts.append(
        CoachFact(
            label="Race distance",
            value=_distance(item.metadata.get("distance_km")),
            detail="Elapsed race evidence remains factual",
        )
    )
    temperature = _number(item.metadata.get("temperature_c"))
    elevation = _number(item.metadata.get("elevation_up_m"))
    context = []
    if temperature is not None:
        context.append(f"{temperature:g}°C")
    if elevation is not None:
        context.append(f"{elevation:g} m climbing")
    facts.append(
        CoachFact(
            label="Conditions recorded",
            value=" · ".join(context) or "Limited context",
            detail="Used for confidence and supported adjustment only",
        )
    )
    return tuple(facts)


def _workout_facts(item: EvidenceItem) -> tuple[CoachFact, ...]:
    facts = []
    selected = _selected_fact(item)
    if selected:
        facts.append(selected)
    rep_count = _integer(item.metadata.get("rep_count"))
    rep_distance = _number(item.metadata.get("average_rep_distance_km"))
    facts.append(
        CoachFact(
            label="Recognised work",
            value=(
                f"{rep_count} reps · {rep_distance:.2f} km typical"
                if rep_count is not None and rep_distance is not None
                else "Decoded workout structure"
            ),
            detail=f"Average work pace {_pace(item.metadata.get('average_rep_pace_s_per_km'))}",
        )
    )
    trend = item.metadata.get("trend")
    if isinstance(trend, dict):
        facts.append(
            CoachFact(
                label="Comparable trend",
                value=str(trend.get("label") or "Building"),
                detail=f"{int(trend.get('sample_size') or 0)} comparable sessions",
            )
        )
    else:
        facts.append(
            CoachFact(
                label="Workout library",
                value=f"{int(item.metadata.get('recognised_workout_count') or 0):,} recognised",
                detail="Race efforts are excluded from this coach",
            )
        )
    return tuple(facts)


def _threshold_facts(item: EvidenceItem) -> tuple[CoachFact, ...]:
    facts = []
    selected = _selected_fact(
        item,
        date_key="selected_date",
        id_key="selected_activity_id",
    )
    if selected:
        facts.append(selected)
    facts.append(
        CoachFact(
            label="Observed threshold",
            value=str(item.metadata.get("threshold_pace_text") or "—"),
            detail="From trusted work phases, not total activity pace",
        )
    )
    recent = int(item.metadata.get("recent_session_count") or 0)
    previous = int(item.metadata.get("previous_session_count") or 0)
    facts.append(
        CoachFact(
            label="Comparable sessions",
            value=f"{recent} recent · {previous} earlier",
            detail=f"Trend: {item.metadata.get('trend') or 'Building'}",
        )
    )
    return tuple(facts)


def _prediction_profiles(
    evidence: EvidenceBundle,
    predictions: HomePredictions,
) -> tuple[CoachProfile, ...]:
    aliases = {"recent_race": "race", "workout": "workout", "threshold": "threshold"}
    items = {
        aliases[item.key]: item
        for item in evidence.items
        if item.key in aliases
    }
    positions = {position.key: position for position in predictions.coach_positions}
    definitions = (
        ("race", "Race Coach", "RC", "Competitive evidence", _race_facts),
        ("workout", "Workout Coach", "WC", "Session evidence", _workout_facts),
        ("threshold", "Threshold Coach", "TC", "Sustainable-speed evidence", _threshold_facts),
    )
    profiles = []
    for key, title, code, role, fact_builder in definitions:
        item = items.get(key)
        position = positions.get(key)
        if item is None:
            profiles.append(
                CoachProfile(
                    key=key,
                    title=title,
                    code=code,
                    role=role,
                    available=False,
                    contributes_to_consensus=True,
                    confidence=0.0,
                    sample_size=0,
                    predicted_seconds=None,
                    position=None,
                    is_lead=False,
                    summary="This coach is still waiting for enough evidence.",
                    strengths=(),
                    limitations=("Performance Passport will not invent an opinion.",),
                    facts=(),
                )
            )
            continue
        profiles.append(
            CoachProfile(
                key=key,
                title=title,
                code=code,
                role=role,
                available=item.status == EvidenceStatus.AVAILABLE,
                contributes_to_consensus=True,
                confidence=item.confidence,
                sample_size=item.sample_size,
                predicted_seconds=(
                    position.predicted_seconds if position else item.predicted_seconds
                ),
                position=position.position if position else None,
                is_lead=bool(position and position.is_lead),
                summary=item.summary,
                strengths=_metadata_list(item, "strengths"),
                limitations=_metadata_list(item, "limitations"),
                facts=fact_builder(item),
            )
        )
    return tuple(profiles)


CONFIDENCE_VALUES = {"Strong": 0.85, "Moderate": 0.62, "Limited": 0.35}


def _aerobic_profile(progress: ProgressSummary | None) -> CoachProfile:
    if progress is None:
        return CoachProfile(
            key="aerobic", title="Aerobic & Durability Coach", code="AD",
            role="Progress specialist", available=False,
            contributes_to_consensus=False, confidence=0.0, sample_size=0,
            predicted_seconds=None, position=None, is_lead=False,
            summary="Longitudinal evidence is still building.", strengths=(),
            limitations=("More reliable running history is needed.",), facts=(),
        )
    aerobic = progress.aerobic
    durability = progress.durability
    confidence = (
        CONFIDENCE_VALUES.get(aerobic.confidence, 0.35)
        + CONFIDENCE_VALUES.get(durability.confidence, 0.35)
    ) / 2
    trend = (
        f"{aerobic.trend_percent:+.1f}%"
        if aerobic.trend_percent is not None else "Building"
    )
    drift = (
        f"{durability.recent_decoupling_percent:.1f}%"
        if durability.recent_decoupling_percent is not None else "Building"
    )
    strengths = (
        f"{aerobic.adjusted_run_count} runs include supported conditions adjustment.",
        f"{aerobic.personalised_run_count} runs use athlete-specific environmental evidence.",
        f"{durability.interrupted_exclusion_count} interrupted long runs were excluded.",
    )
    limitations = []
    if durability.confidence == "Limited":
        limitations.append(
            "Durability remains provisional until more recent and earlier continuous long runs are comparable."
        )
    limitations.append(
        "Aerobic efficiency is an observational within-athlete trend, not a laboratory measurement."
    )
    return CoachProfile(
        key="aerobic",
        title="Aerobic & Durability Coach",
        code="AD",
        role="Progress specialist",
        available=aerobic.available or durability.available,
        contributes_to_consensus=False,
        confidence=confidence,
        sample_size=aerobic.sample_size + durability.total_sample_size,
        predicted_seconds=None,
        position=None,
        is_lead=False,
        summary=f"{aerobic.summary} {durability.summary}",
        strengths=strengths,
        limitations=tuple(limitations),
        facts=(
            CoachFact("Aerobic direction", trend, f"{aerobic.sample_size} comparable runs"),
            CoachFact("Long-run drift", drift, f"{durability.recent_sample_size} recent continuous long runs"),
            CoachFact("Training rhythm", f"{progress.rhythm.active_days_per_week:.1f} days/week", f"{progress.rhythm.reliable_miles_per_week:.1f} reliable mi/week"),
        ),
    )


def _environment_profile(predictions: HomePredictions) -> CoachProfile:
    responses = predictions.environment_responses
    available = [response for response in responses if response.confidence >= 0.25]
    confidence = (
        sum(response.confidence for response in responses) / len(responses)
        if responses else 0.0
    )
    sample_size = sum(response.sample_size for response in responses)
    facts = tuple(
        CoachFact(
            response.label,
            response.response_label,
            f"{response.sample_size} comparable runs · {response.confidence:.0%} confidence",
        )
        for response in responses
    )
    trait = predictions.performance_trait
    summary = (
        f"Earned athlete trait: {trait.title}. {trait.detail}"
        if trait is not None
        else "The coach is learning how heat, hills and trail surfaces change this athlete's response."
    )
    strengths = tuple(
        f"{response.label}: {response.response_label} from {response.sample_size} comparable runs."
        for response in available
    )
    limitations = tuple(
        f"{response.label} remains below the evidence threshold."
        for response in responses
        if response.confidence < 0.25
    )
    return CoachProfile(
        key="environment",
        title="Environment Coach",
        code="EC",
        role="Conditions specialist",
        available=bool(available),
        contributes_to_consensus=False,
        confidence=confidence,
        sample_size=sample_size,
        predicted_seconds=None,
        position=None,
        is_lead=False,
        summary=summary,
        strengths=strengths,
        limitations=limitations + (
            "Environmental percentages scale the generic penalty model; they are not percentage changes in total race pace.",
        ),
        facts=facts,
    )


def build_coaching_team_detail(athlete_id: int) -> CoachingTeamDetail | None:
    """Build one athlete's team without creating any new race prediction."""
    athlete_name = _athlete_name(athlete_id)
    if athlete_name is None:
        return None

    brain = CoachBrain(athlete_id)
    goal = brain.get_goal()
    evidence = brain.build_evidence(goal)
    runs = load_run_profiles(athlete_id)
    predictions = build_goal_predictions(
        athlete_id,
        goal,
        evidence=evidence,
        runs=runs,
    )
    progress = build_progress_summary(athlete_id)
    return CoachingTeamDetail(
        athlete_id=athlete_id,
        athlete_name=athlete_name,
        goal_name=predictions.goal_name,
        distance_label=predictions.distance_label,
        available=predictions.available,
        target_seconds=predictions.target_seconds,
        central_seconds=predictions.central_seconds,
        low_seconds=predictions.low_seconds,
        high_seconds=predictions.high_seconds,
        confidence=predictions.confidence,
        consensus_status=predictions.consensus_status,
        consensus_headline=predictions.consensus_headline,
        explanation=predictions.explanation,
        lead_coach=predictions.lead_coach,
        strongest_system=predictions.strongest_system,
        limiting_system=predictions.limiting_system,
        prediction_coaches=_prediction_profiles(evidence, predictions),
        supporting_coaches=(
            _aerobic_profile(progress),
            _environment_profile(predictions),
        ),
        notes=(
            "Race, Workout and Threshold are the only direct goal-time opinions in the current consensus.",
            "Supporting coaches explain progress and conditions; they are not counted as additional prediction votes.",
            "Confidence describes evidence strength, not certainty that a race result will occur.",
        ),
    )

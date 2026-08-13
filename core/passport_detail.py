"""Production Passport Detail assembled from existing athlete evidence.

Passport answers what the application currently knows about an athlete. It
does not create a second zone model: physiological boundaries come from the
configured threshold profile, historical training ranges come from Training
Blueprint, and longitudinal direction comes from Progress.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import statistics

from core.athlete_passport import AthletePassportData, build_athlete_passport
from core.database import get_connection, get_effective_athlete_thresholds
from core.environment_profile import build_personal_environment_profile
from core.home_predictions import (
    HomeEnvironmentResponse,
    HomePerformanceTrait,
    build_environment_story,
    load_run_profiles,
)
from core.learning_engine import LearnedPattern, build_learning_profile
from core.progress import ProgressSummary, build_progress_summary
from core.training_blueprint import BlueprintCategory, build_training_blueprint


@dataclass(frozen=True)
class PassportAnchor:
    key: str
    label: str
    value: str
    detail: str
    confidence: str


@dataclass(frozen=True)
class PassportTrainingProfile:
    recovery: BlueprintCategory
    easy: BlueprintCategory
    long_easy: BlueprintCategory
    threshold: BlueprintCategory
    vo2: BlueprintCategory
    speed: BlueprintCategory


@dataclass(frozen=True)
class PassportThresholdEvidence:
    decoded_workout_count: int
    strict_progress_count: int
    response_window_count: int
    typical_work_distance_km: float | None


@dataclass(frozen=True)
class PassportDetail:
    athlete: AthletePassportData
    reference_date: str
    confidence: str
    confidence_summary: str
    anchors: tuple[PassportAnchor, ...]
    training: PassportTrainingProfile
    threshold_evidence: PassportThresholdEvidence
    available_training_profiles: int
    training_confidence: float
    environment: tuple[HomeEnvironmentResponse, ...]
    performance_trait: HomePerformanceTrait | None
    learning_patterns: tuple[LearnedPattern, ...]
    trusted_workout_count: int
    learning_summary: str
    evidence_notes: tuple[str, ...]
    progress: ProgressSummary
    threshold_source: str
    model_version: int = 1


def _pace_text(
    seconds_per_km: float | None,
    *,
    nearest_five: bool = False,
) -> str:
    if seconds_per_km is None:
        return "—"
    seconds_per_mile = seconds_per_km * 1.609344
    if nearest_five:
        seconds_per_mile = round(seconds_per_mile / 5.0) * 5
    seconds_per_mile = int(round(seconds_per_mile))
    minutes, seconds = divmod(seconds_per_mile, 60)
    return f"{minutes}:{seconds:02d}/mi"


def _pace_range(fast: float | None, slow: float | None) -> str:
    if fast is None or slow is None:
        return "—"
    fast_text = _pace_text(min(fast, slow), nearest_five=True).removesuffix("/mi")
    slow_text = _pace_text(max(fast, slow), nearest_five=True)
    return fast_text if fast_text == slow_text.removesuffix("/mi") else f"{fast_text}–{slow_text}"


def _confidence_label(value: float) -> str:
    if value >= 0.75:
        return "Strong"
    if value >= 0.45:
        return "Moderate"
    return "Limited"


def _threshold_work_distances(athlete_id: int) -> list[float]:
    """Return trusted decoded threshold volume without claiming a pace trend."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT phase_json
        FROM workout_library
        WHERE athlete_id = ?
          AND phase_confidence >= 0.70
          AND recognition_confidence >= 0.65
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    threshold_types = {
        "threshold",
        "continuous_threshold",
        "long_threshold",
        "sustained_quality",
    }
    distances = []
    for (phase_json,) in rows:
        try:
            phases = json.loads(phase_json or "[]")
        except (TypeError, json.JSONDecodeError):
            continue
        distance = 0.0
        found = False
        for phase in phases if isinstance(phases, list) else ():
            if str(phase.get("phase_type") or "").lower() not in threshold_types:
                continue
            try:
                value = float(phase.get("distance_km") or 0.0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                distance += value
                found = True
        if found:
            distances.append(distance)
    return distances


def _anchors(progress: ProgressSummary, thresholds: dict) -> tuple[PassportAnchor, ...]:
    source = str(thresholds.get("source") or "Not set")
    lt1 = thresholds.get("lt1_hr")
    lt2 = thresholds.get("lt2_hr")
    threshold = progress.threshold
    threshold_range = _pace_range(
        threshold.standard_equivalent_fast_s_per_km,
        threshold.standard_equivalent_slow_s_per_km,
    )
    aerobic = progress.aerobic.trend_percent
    durability = progress.durability.recent_decoupling_percent
    return (
        PassportAnchor(
            key="lt1",
            label="LT1 boundary",
            value=f"{lt1} bpm" if lt1 else "—",
            detail=source,
            confidence="Set" if lt1 else "Missing",
        ),
        PassportAnchor(
            key="lt2",
            label="LT2 boundary",
            value=f"{lt2} bpm" if lt2 else "—",
            detail=source,
            confidence="Set" if lt2 else "Missing",
        ),
        PassportAnchor(
            key="threshold",
            label="Threshold work",
            value=_pace_text(threshold.current_pace_s_per_km),
            detail=(
                f"{threshold_range} cautious 12°C equivalent"
                if threshold_range != "—"
                else "Trusted work-phase pace"
            ),
            confidence=threshold.confidence,
        ),
        PassportAnchor(
            key="aerobic",
            label="Aerobic direction",
            value=f"{aerobic:+.1f}%" if aerobic is not None else "—",
            detail=f"{progress.aerobic.sample_size} comparable runs",
            confidence=progress.aerobic.confidence,
        ),
        PassportAnchor(
            key="durability",
            label="Long-run drift",
            value=f"{durability:.1f}%" if durability is not None else "—",
            detail="Recent uninterrupted Long Easy median",
            confidence=progress.durability.confidence,
        ),
    )


def build_passport_detail(
    athlete_id: int,
    *,
    reference_date: datetime.date | None = None,
) -> PassportDetail | None:
    """Build one auditable current athlete identity without new predictions."""
    progress = build_progress_summary(athlete_id, reference_date=reference_date)
    if progress is None:
        return None

    effective_date = datetime.date.fromisoformat(progress.reference_date)
    athlete = build_athlete_passport(athlete_id, reference_date=effective_date)
    if athlete is None:
        return None

    profiles = [
        run for run in load_run_profiles(athlete_id)
        if not run.activity_date or str(run.activity_date)[:10] <= progress.reference_date
    ]
    blueprint = build_training_blueprint(profiles, athlete_id=athlete_id)
    categories = {category.key: category for category in blueprint.categories}
    personal_environment = build_personal_environment_profile(
        profiles,
        athlete_id=athlete_id,
    )
    environment, trait = build_environment_story(personal_environment)
    learning = build_learning_profile(athlete_id)
    thresholds = get_effective_athlete_thresholds(athlete_id)
    threshold_pattern = next(
        (pattern for pattern in learning.patterns if pattern.family == "threshold"),
        None,
    )
    threshold_distances = _threshold_work_distances(athlete_id)
    threshold_evidence = PassportThresholdEvidence(
        decoded_workout_count=(
            threshold_pattern.trusted_session_count if threshold_pattern else 0
        ),
        strict_progress_count=progress.threshold.total_sample_size,
        response_window_count=(
            threshold_pattern.response_observation_count if threshold_pattern else 0
        ),
        typical_work_distance_km=(
            round(statistics.median(threshold_distances), 3)
            if threshold_distances
            else None
        ),
    )

    support_scores = (
        blueprint.overall_confidence,
        personal_environment.overall_confidence,
        0.90 if progress.aerobic.confidence == "Strong" else 0.60,
    )
    overall_support = sum(support_scores) / len(support_scores)
    confidence = _confidence_label(overall_support)
    confidence_summary = (
        f"{blueprint.available_category_count} of 6 training profiles supported · "
        f"{progress.aerobic.sample_size} comparable aerobic runs · "
        f"{learning.trusted_workout_count} trusted workouts"
    )

    return PassportDetail(
        athlete=athlete,
        reference_date=progress.reference_date,
        confidence=confidence,
        confidence_summary=confidence_summary,
        anchors=_anchors(progress, thresholds),
        training=PassportTrainingProfile(
            recovery=categories["recovery"],
            easy=categories["easy"],
            long_easy=categories["long_easy"],
            threshold=categories["threshold"],
            vo2=categories["vo2"],
            speed=categories["speed"],
        ),
        threshold_evidence=threshold_evidence,
        available_training_profiles=blueprint.available_category_count,
        training_confidence=blueprint.overall_confidence,
        environment=environment,
        performance_trait=trait,
        learning_patterns=learning.patterns[:2],
        trusted_workout_count=learning.trusted_workout_count,
        learning_summary=learning.summary,
        evidence_notes=(
            "LT1 and LT2 are configured boundaries with their source shown; they are not presented as laboratory measurements unless explicitly tested.",
            "Recovery, Easy and Long Easy ranges describe the athlete's strongest conditions-adjusted historical examples, not mandatory pace limits.",
            "Threshold pace comes from trusted work phases. The 12°C flat-road equivalent is a cautious estimate, not a confirmed physiological threshold.",
            "VO₂ and Speed use trusted repetition pace where available. Heart rate is not used as the primary guide because it lags short work.",
            "Environmental responses scale a generic penalty model; the percentage is not a percentage change in total running pace.",
            "Workout-response learning is observational. Association does not establish that a workout caused the later response.",
        ),
        progress=progress,
        threshold_source=str(thresholds.get("source") or "Not set"),
    )

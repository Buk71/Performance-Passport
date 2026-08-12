"""Real-data race prediction adapter for Performance Passport Home.

This module does not create a new prediction formula. It composes the existing
Coach Brain, Performance DNA, Coach Consensus, Capability and Environment
Forecast engines into a compact Home-facing result.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.capability import build_capability
from core.coach_brain import CoachBrain
from core.coach_consensus import build_coach_consensus
from core.coaching import RunProfile
from core.database import (
    get_connection,
    get_effective_athlete_thresholds,
)
from core.easy_run_coach import build_easy_run_coach
from core.environment_forecast import build_environment_forecast
from core.environment_profile import build_personal_environment_profile
from core.evidence_engine import build_athlete_evidence_profile
from core.performance_dna import build_performance_dna


SYSTEM_LABELS = {
    "threshold": "Threshold",
    "speed": "Speed / VO₂",
    "endurance": "Endurance",
    "aerobic": "Aerobic",
}

SCENARIO_KEYS = ("ideal", "typical", "warm", "hilly", "windy")


@dataclass(frozen=True)
class HomePredictionScenario:
    key: str
    label: str
    description: str
    central_seconds: float
    low_seconds: float
    high_seconds: float
    pace_seconds_per_km: float | None
    adjustment_percent: float
    confidence: float
    personalised: bool


@dataclass(frozen=True)
class HomeCoachPosition:
    key: str
    title: str
    predicted_seconds: float
    confidence: float
    difference_seconds: float
    position: str
    is_lead: bool


@dataclass(frozen=True)
class HomeEnvironmentResponse:
    key: str
    label: str
    multiplier: float
    confidence: float
    sample_size: int
    response_label: str


@dataclass(frozen=True)
class HomePerformanceTrait:
    key: str
    title: str
    detail: str
    confidence: float


@dataclass(frozen=True)
class HomePredictions:
    athlete_id: int
    available: bool
    goal_name: str
    distance_label: str
    target_seconds: float | None
    central_seconds: float | None
    low_seconds: float | None
    high_seconds: float | None
    confidence: float
    target_gap_seconds: float | None
    target_probability: float | None
    strongest_system: str | None
    limiting_system: str | None
    lead_coach: str | None
    consensus_status: str
    consensus_headline: str
    evidence_source_count: int
    coach_positions: tuple[HomeCoachPosition, ...]
    environment_responses: tuple[HomeEnvironmentResponse, ...]
    performance_trait: HomePerformanceTrait | None
    scenarios: tuple[HomePredictionScenario, ...]
    explanation: str


def _goal_distance_km(goal: dict | None) -> float | None:
    if goal is None:
        return None

    for key in (
        "distance_km",
        "goal_distance_km",
        "target_distance_km",
        "distance_m",
    ):
        raw_value = goal.get(key)
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        return value / 1000.0 if value > 250 else value

    name = str(goal.get("goal_name") or "").lower()
    if "marathon" in name and "half" not in name:
        return 42.195
    if "half" in name:
        return 21.0975
    if "10k" in name or "10 km" in name:
        return 10.0
    if "5k" in name or "5 km" in name:
        return 5.0
    return None


def _distance_label(distance_km: float | None) -> str:
    if distance_km is None:
        return "Race"
    known = (
        (5.0, "5K"),
        (8.04672, "5 miles"),
        (10.0, "10K"),
        (16.09344, "10 miles"),
        (21.0975, "Half marathon"),
        (42.195, "Marathon"),
    )
    for value, label in known:
        if abs(distance_km - value) <= 0.12:
            return label
    return f"{distance_km:g} km"


def _response_label(multiplier: float, confidence: float) -> str:
    if confidence < 0.25:
        return "Still learning"

    difference = abs(multiplier - 1.0)
    if difference < 0.08:
        return "Typical response"
    if multiplier < 1.0:
        return f"{difference:.0%} less affected"
    return f"{difference:.0%} more affected"


def _environment_story(
    personal_profile,
) -> tuple[
    tuple[HomeEnvironmentResponse, ...],
    HomePerformanceTrait | None,
]:
    definitions = (
        (
            "heat",
            "Heat",
            "Heat Handler",
            personal_profile.heat_multiplier,
            personal_profile.heat_confidence,
            personal_profile.heat_sample_size,
        ),
        (
            "hills",
            "Hills",
            "Hill Tamer",
            personal_profile.hill_multiplier,
            personal_profile.hill_confidence,
            personal_profile.hill_sample_size,
        ),
        (
            "trail",
            "Trail",
            "Trail Warrior",
            personal_profile.trail_multiplier,
            personal_profile.trail_confidence,
            personal_profile.trail_sample_size,
        ),
    )

    responses = tuple(
        HomeEnvironmentResponse(
            key=key,
            label=label,
            multiplier=multiplier,
            confidence=confidence,
            sample_size=sample_size,
            response_label=_response_label(multiplier, confidence),
        )
        for key, label, _title, multiplier, confidence, sample_size
        in definitions
    )

    strengths = [
        item
        for item in definitions
        if item[4] >= 0.50 and item[3] <= 0.92
    ]
    if not strengths:
        return responses, None

    key, label, title, multiplier, confidence, sample_size = min(
        strengths,
        key=lambda item: (item[3], -item[4]),
    )
    difference = max(1.0 - multiplier, 0.0)
    trait = HomePerformanceTrait(
        key=key,
        title=title,
        detail=(
            f"Your {label.lower()} penalty is estimated {difference:.0%} "
            f"lower than the standard model, learned from "
            f"{sample_size} comparable runs."
        ),
        confidence=confidence,
    )
    return responses, trait


def _load_run_profiles(athlete_id: int) -> list[RunProfile]:
    thresholds = get_effective_athlete_thresholds(athlete_id)
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            activity_date,
            title,
            distance_m,
            moving_time_s,
            avg_hr,
            max_hr,
            sport_id,
            elevation_up_m,
            temperature_c,
            humidity
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_datetime DESC, id DESC
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    connection.close()

    profiles = []
    for row in rows:
        distance_value = row[2]
        try:
            distance_value = float(distance_value or 0.0)
        except (TypeError, ValueError):
            distance_value = 0.0
        distance_km = (
            distance_value / 1000.0
            if distance_value > 250.0
            else distance_value
        )
        profiles.append(
            RunProfile(
                athlete_id=athlete_id,
                activity_date=row[0],
                title=row[1],
                distance_km=distance_km,
                moving_time_seconds=row[3],
                avg_hr=row[4],
                run_max_hr=row[5],
                sport_id=row[6],
                elevation_m=row[7],
                temperature_c=row[8],
                humidity=row[9],
                lt1_hr=thresholds.get("lt1_hr"),
                lt2_hr=thresholds.get("lt2_hr"),
                athlete_max_hr=thresholds.get("athlete_max_hr"),
            )
        )
    return profiles


def build_home_predictions(athlete_id: int) -> HomePredictions:
    """Build the active-goal prediction using the existing real engines."""
    brain = CoachBrain(athlete_id)
    goal = brain.get_goal()
    goal_name = str(
        (goal or {}).get("goal_name")
        or (goal or {}).get("race_name")
        or "Active goal"
    )
    distance_km = _goal_distance_km(goal)

    evidence = brain.build_evidence()
    prediction = brain.prediction_engine.predict_goal(
        athlete_id,
        goal,
        evidence,
    )

    runs = _load_run_profiles(athlete_id)
    evidence_connection = get_connection()
    evidence_profile = build_athlete_evidence_profile(
        evidence_connection,
        athlete_id=athlete_id,
    )
    evidence_connection.close()
    easy_run_coach = build_easy_run_coach(
        runs,
        evidence_profile=evidence_profile,
    )

    prediction_seconds = (
        prediction.predicted_seconds if prediction.available else None
    )
    performance_dna = build_performance_dna(
        evidence,
        consensus_prediction_s=prediction_seconds,
        easy_run_coach=easy_run_coach,
    )
    consensus = build_coach_consensus(
        performance_dna,
        consensus_prediction_s=prediction_seconds,
    )
    capability = build_capability(
        predicted_seconds=prediction_seconds,
        prediction_confidence=(
            prediction.confidence if prediction.available else 0.0
        ),
        performance_dna=performance_dna,
        coach_consensus=consensus,
        target_seconds=(goal.get("target_time_s") if goal else None),
    )

    personal_profile = build_personal_environment_profile(
        runs,
        athlete_id=athlete_id,
    )
    environment_responses, performance_trait = _environment_story(
        personal_profile
    )
    forecast = build_environment_forecast(
        capability,
        distance_km=distance_km,
        personal_profile=personal_profile,
    )

    forecast_by_key = {
        scenario.key: scenario for scenario in forecast.scenarios
    }
    scenarios = tuple(
        HomePredictionScenario(
            key=scenario.key,
            label=scenario.label.split(" ", 1)[-1],
            description=scenario.description,
            central_seconds=scenario.central_seconds,
            low_seconds=scenario.low_seconds,
            high_seconds=scenario.high_seconds,
            pace_seconds_per_km=scenario.pace_seconds_per_km,
            adjustment_percent=scenario.adjustment_percent,
            confidence=scenario.confidence,
            personalised=scenario.personalised,
        )
        for key in SCENARIO_KEYS
        if (scenario := forecast_by_key.get(key)) is not None
    )

    explanation = (
        capability.explanation
        if capability.available
        else prediction.explanation
    )
    coach_positions = tuple(
        HomeCoachPosition(
            key=position.key,
            title=position.title,
            predicted_seconds=position.predicted_seconds,
            confidence=position.confidence,
            difference_seconds=position.difference_seconds,
            position=position.position,
            is_lead=position.title == consensus.lead_coach,
        )
        for position in consensus.positions
    )

    return HomePredictions(
        athlete_id=athlete_id,
        available=capability.available and forecast.available,
        goal_name=goal_name,
        distance_label=_distance_label(distance_km),
        target_seconds=(goal.get("target_time_s") if goal else None),
        central_seconds=capability.central_seconds,
        low_seconds=capability.low_seconds,
        high_seconds=capability.high_seconds,
        confidence=capability.confidence,
        target_gap_seconds=capability.target_gap_seconds,
        target_probability=capability.target_probability,
        strongest_system=(
            SYSTEM_LABELS.get(capability.strongest_system)
            if capability.strongest_system
            else None
        ),
        limiting_system=(
            SYSTEM_LABELS.get(capability.limiting_system)
            if capability.limiting_system
            else None
        ),
        lead_coach=consensus.lead_coach,
        consensus_status=consensus.status,
        consensus_headline=consensus.headline,
        evidence_source_count=len(evidence.prediction_items),
        coach_positions=coach_positions,
        environment_responses=environment_responses,
        performance_trait=performance_trait,
        scenarios=scenarios,
        explanation=explanation,
    )

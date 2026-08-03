from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.session import (
    CoachRoute,
    Session,
    SessionEvidence,
    SessionPurpose,
    SessionType,
)
from core.splits import is_boundary_fragment, parse_splits, recognise_workout


RUNNING_SPORT_ID = "965611"
WALKING_SPORT_ID = "965617"

RACE_WORDS = (
    "race", "parkrun", "5k", "10k", "half marathon",
    "marathon", "cross country", "xc", "handicap",
)

WORKOUT_WORDS = (
    "threshold", "tempo", "interval", "intervals", "reps",
    "fartlek", "hill reps", "track", "vo2", "cruise",
)


@dataclass(frozen=True)
class ActivityFacts:
    activity_id: int
    athlete_id: int
    activity_date: str | None
    title: str
    sport_id: str | None
    distance_km: float | None
    moving_time_s: float | None
    elapsed_time_s: float | None
    avg_hr: float | None
    max_hr: float | None
    elevation_up_m: float | None
    temperature_c: float | None
    humidity: float | None
    wind_speed: float | None
    route_name: str | None
    raw_json_text: str | None


def _contains_any(title: str, words: tuple[str, ...]) -> bool:
    normalised = (title or "").lower()
    return any(word in normalised for word in words)


def _extract_raw_splits(raw_json_text: str | None) -> str | None:
    if not raw_json_text:
        return None
    try:
        raw = json.loads(raw_json_text)
    except (TypeError, json.JSONDecodeError):
        return None
    return raw.get("splits") or raw.get("splitsCustom")


def _continuous_split_pattern(raw_splits: str | None) -> tuple[bool, dict[str, Any]]:
    splits = parse_splits(raw_splits)

    if len(splits) < 2:
        return True, {
            "split_count": len(splits),
            "reason": "Too few splits to show deliberate interruption.",
        }

    boundaries = [s for s in splits if is_boundary_fragment(s)]
    recognition = recognise_workout(splits)

    if recognition.recovery_splits or recognition.unknown_recovery_count > 0:
        return False, {
            "split_count": len(splits),
            "boundary_count": len(boundaries),
            "recovery_count": len(recognition.recovery_splits),
            "unknown_recovery_count": recognition.unknown_recovery_count,
            "recognition": recognition.description,
        }

    substantial = [
        s for s in splits
        if s.duration_s >= 120 and s.distance_km >= 0.70
    ]

    if len(substantial) >= 3:
        return True, {
            "split_count": len(splits),
            "substantial_split_count": len(substantial),
            "boundary_count": len(boundaries),
            "reason": (
                "Repeated substantial laps had no recovery or interruption evidence."
            ),
        }

    if recognition.workout_type in (
        "No split data",
        "Unclassified",
        "Continuous sustained effort",
    ):
        return True, {
            "split_count": len(splits),
            "boundary_count": len(boundaries),
            "recognition": recognition.description,
        }

    return False, {
        "split_count": len(splits),
        "boundary_count": len(boundaries),
        "recognition": recognition.description,
    }


def classify_session(facts: ActivityFacts) -> Session:
    evidence: list[SessionEvidence] = []
    routes = [
        CoachRoute.ENVIRONMENT,
        CoachRoute.RECOVERY,
        CoachRoute.PROGRESS,
    ]

    sport_id = str(facts.sport_id or "")

    if sport_id == WALKING_SPORT_ID:
        return Session(
            activity_id=facts.activity_id,
            athlete_id=facts.athlete_id,
            activity_date=facts.activity_date,
            title=facts.title,
            sport_id=facts.sport_id,
            session_type=SessionType.WALK,
            purpose=SessionPurpose.GENERAL,
            confidence=1.0,
            distance_km=facts.distance_km,
            moving_time_s=facts.moving_time_s,
            elapsed_time_s=facts.elapsed_time_s,
            suitable_coaches=tuple(routes),
        )

    if sport_id != RUNNING_SPORT_ID:
        return Session(
            activity_id=facts.activity_id,
            athlete_id=facts.athlete_id,
            activity_date=facts.activity_date,
            title=facts.title,
            sport_id=facts.sport_id,
            session_type=SessionType.CROSS_TRAINING,
            purpose=SessionPurpose.GENERAL,
            confidence=0.98,
            distance_km=facts.distance_km,
            moving_time_s=facts.moving_time_s,
            elapsed_time_s=facts.elapsed_time_s,
            suitable_coaches=tuple(routes),
        )

    if _contains_any(facts.title, RACE_WORDS):
        routes.extend([CoachRoute.RACE, CoachRoute.GOAL])
        evidence.append(
            SessionEvidence(
                key="race_title",
                description="Title contains race-like language.",
                strength=0.75,
                supports=SessionType.RACE.value,
            )
        )
        return Session(
            activity_id=facts.activity_id,
            athlete_id=facts.athlete_id,
            activity_date=facts.activity_date,
            title=facts.title,
            sport_id=facts.sport_id,
            session_type=SessionType.RACE,
            purpose=SessionPurpose.RACE,
            confidence=0.75,
            distance_km=facts.distance_km,
            moving_time_s=facts.moving_time_s,
            elapsed_time_s=facts.elapsed_time_s,
            evidence=tuple(evidence),
            suitable_coaches=tuple(dict.fromkeys(routes)),
        )

    raw_splits = _extract_raw_splits(facts.raw_json_text)
    continuous, details = _continuous_split_pattern(raw_splits)
    title_workout = _contains_any(facts.title, WORKOUT_WORDS)

    if title_workout or not continuous:
        routes.extend([CoachRoute.WORKOUT, CoachRoute.THRESHOLD])
        confidence = 0.92 if title_workout and not continuous else 0.80
        evidence.append(
            SessionEvidence(
                key="structured_evidence",
                description=(
                    "Title or split pattern indicates deliberate recovery or interruption."
                ),
                strength=confidence,
                supports=SessionType.STRUCTURED_WORKOUT.value,
                metadata=details,
            )
        )
        return Session(
            activity_id=facts.activity_id,
            athlete_id=facts.athlete_id,
            activity_date=facts.activity_date,
            title=facts.title,
            sport_id=facts.sport_id,
            session_type=SessionType.STRUCTURED_WORKOUT,
            purpose=(
                SessionPurpose.THRESHOLD
                if _contains_any(facts.title, ("threshold", "tempo", "cruise"))
                else SessionPurpose.UNKNOWN
            ),
            confidence=confidence,
            distance_km=facts.distance_km,
            moving_time_s=facts.moving_time_s,
            elapsed_time_s=facts.elapsed_time_s,
            avg_hr=facts.avg_hr,
            max_hr=facts.max_hr,
            elevation_up_m=facts.elevation_up_m,
            temperature_c=facts.temperature_c,
            humidity=facts.humidity,
            wind_speed=facts.wind_speed,
            route_name=facts.route_name,
            evidence=tuple(evidence),
            suitable_coaches=tuple(dict.fromkeys(routes)),
            metadata={"split_classification": details},
        )

    routes.append(CoachRoute.EASY)
    evidence.append(
        SessionEvidence(
            key="continuous_pattern",
            description="No deliberate recovery or interruption pattern was found.",
            strength=0.88,
            supports=SessionType.CONTINUOUS_RUN.value,
            metadata=details,
        )
    )
    return Session(
        activity_id=facts.activity_id,
        athlete_id=facts.athlete_id,
        activity_date=facts.activity_date,
        title=facts.title,
        sport_id=facts.sport_id,
        session_type=SessionType.CONTINUOUS_RUN,
        purpose=SessionPurpose.GENERAL,
        confidence=0.88,
        distance_km=facts.distance_km,
        moving_time_s=facts.moving_time_s,
        elapsed_time_s=facts.elapsed_time_s,
        avg_hr=facts.avg_hr,
        max_hr=facts.max_hr,
        elevation_up_m=facts.elevation_up_m,
        temperature_c=facts.temperature_c,
        humidity=facts.humidity,
        wind_speed=facts.wind_speed,
        route_name=facts.route_name,
        evidence=tuple(evidence),
        suitable_coaches=tuple(dict.fromkeys(routes)),
        metadata={"split_classification": details},
    )

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
from core.database import get_athlete_sport_roles
from core.race_detection import score_race_evidence
from core.splits import is_boundary_fragment, parse_splits, recognise_workout
from core.workout_title_intent import parse_workout_title


RACE_WORDS = (
    "race", "parkrun", "5k", "10k", "half marathon",
    "marathon", "cross country", "xc", "handicap",
)

WORKOUT_WORDS = (
    "threshold", "tempo", "interval", "intervals", "reps",
    "repetition", "repetitions", "fartlek", "hill reps",
    "track session", "vo2", "cruise", "strides",
    "drills", "ladder", "workout", "session",
)

# Downstream features may use a confident shared classification as their source
# of truth. Below this floor, they should retain conservative legacy/fallback
# handling rather than turning an ambiguous historical split pattern into fact.
RELIABLE_SESSION_CONFIDENCE = 0.70


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
    athlete_lt2_hr: float | None = None
    athlete_max_hr: float | None = None


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


def _continuous_split_pattern(
    raw_splits: str | None,
) -> tuple[bool, dict[str, Any]]:
    """
    Distinguish ordinary auto-laps from deliberate workout structure.

    Repeated distances alone never prove repetitions. A run is considered
    structured only when there is credible interruption evidence such as:
    - recorded recovery laps;
    - lap/stop/start boundaries between work segments;
    - clear alternating effort and recovery pace;
    - explicit workout wording handled by classify_session().
    """
    splits = parse_splits(raw_splits)

    if len(splits) < 2:
        return True, {
            "split_count": len(splits),
            "reason": "Too few splits to show deliberate interruption.",
        }

    boundaries = [
        split for split in splits if is_boundary_fragment(split)
    ]
    meaningful = [
        split for split in splits if not is_boundary_fragment(split)
    ]

    substantial = [
        split
        for split in meaningful
        if split.duration_s >= 120
        and split.distance_km >= 0.70
        and split.pace_s_per_km is not None
    ]

    # Auto-lap protection:
    # A sequence of broadly equal mile/km laps with no short connectors is
    # a continuous run, even if normal pace variation confuses the workout
    # recogniser.
    if len(substantial) >= 3:
        distances = [split.distance_km for split in substantial]
        average_distance = sum(distances) / len(distances)
        maximum_distance_error = max(
            abs(distance - average_distance)
            for distance in distances
        )

        distance_variation = (
            maximum_distance_error / average_distance
            if average_distance > 0
            else 1.0
        )

        short_connectors = [
            split
            for split in meaningful
            if split not in substantial
            and split.duration_s < 120
            and split.distance_km < 0.35
        ]

        substantial_share = len(substantial) / max(len(meaningful), 1)

        if (
            distance_variation <= 0.10
            and substantial_share >= 0.70
            and not short_connectors
            and not boundaries
        ):
            return True, {
                "split_count": len(splits),
                "substantial_split_count": len(substantial),
                "average_lap_distance_km": round(average_distance, 3),
                "distance_variation": round(distance_variation, 4),
                "reason": (
                    "Repeated similar auto-laps had no recovery, connector "
                    "or stop/start evidence."
                ),
            }

    recognition = recognise_workout(splits)

    if recognition.recovery_splits:
        return False, {
            "split_count": len(splits),
            "boundary_count": len(boundaries),
            "recovery_count": len(recognition.recovery_splits),
            "unknown_recovery_count":
                recognition.unknown_recovery_count,
            "recognition": recognition.description,
            "reason": "Recorded recovery segments were detected.",
        }

    if recognition.unknown_recovery_count > 0:
        return False, {
            "split_count": len(splits),
            "boundary_count": len(boundaries),
            "unknown_recovery_count":
                recognition.unknown_recovery_count,
            "recognition": recognition.description,
            "reason": (
                "Stop/start boundary evidence was detected between "
                "meaningful work segments."
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
            "reason": "No deliberate recovery pattern was detected.",
        }

    # A recognised repeating pattern without recovery evidence is still
    # treated as continuous. This prevents mile auto-laps becoming reps.
    return True, {
        "split_count": len(splits),
        "boundary_count": len(boundaries),
        "recognition": recognition.description,
        "reason": (
            "Repeated segments were present, but no deliberate recovery "
            "or interruption evidence supported a structured workout."
        ),
    }


def _score_continuous(
    *,
    title: str,
    continuous_pattern: bool,
    split_details: dict[str, Any],
    moving_time_s: float | None,
    elapsed_time_s: float | None,
) -> tuple[float, list[str]]:
    score = 45.0
    reasons = []

    if continuous_pattern:
        score += 35.0
        reasons.append("No deliberate recovery pattern was detected.")

    if split_details.get("substantial_split_count", 0) >= 3:
        score += 12.0
        reasons.append("Repeated substantial laps resemble auto-laps.")

    if moving_time_s and elapsed_time_s and elapsed_time_s > 0:
        ratio = max(0.0, min(moving_time_s / elapsed_time_s, 1.0))
        if ratio >= 0.985:
            score += 8.0
            reasons.append(f"Moving ratio was {ratio:.1%}.")
        elif ratio < 0.94:
            score -= 8.0

    title_intent = parse_workout_title(title)
    if _contains_any(title, WORKOUT_WORDS):
        score -= 22.0
        reasons.append("Workout wording reduced continuous-run confidence.")

    if title_intent is not None:
        score -= 18.0
        reasons.append(
            "The title describes explicit repetition structure."
        )

    return max(0.0, min(score, 100.0)), reasons


def _score_structured(
    *,
    title: str,
    continuous_pattern: bool,
    split_details: dict[str, Any],
    raw_splits: str | None,
) -> tuple[float, list[str]]:
    score = 15.0
    reasons = []

    title_intent = parse_workout_title(title)
    has_workout_wording = _contains_any(title, WORKOUT_WORDS)

    if has_workout_wording:
        score += 42.0
        reasons.append("Title contains explicit workout language.")

    if title_intent is not None:
        score += 20.0
        reasons.append(
            f"Title describes {title_intent.total_reps} planned repetition(s)."
        )

    recovery_count = split_details.get("recovery_count", 0) or 0
    unknown_recovery_count = (
        split_details.get("unknown_recovery_count", 0) or 0
    )
    boundary_count = split_details.get("boundary_count", 0) or 0

    if recovery_count:
        score += min(recovery_count * 8.0, 32.0)
        reasons.append(
            f"{recovery_count} recorded recovery segment(s) detected."
        )

    if unknown_recovery_count:
        score += min(unknown_recovery_count * 7.0, 28.0)
        reasons.append(
            f"{unknown_recovery_count} likely stopped-watch recovery gap(s)."
        )

    if boundary_count:
        score += min(boundary_count * 2.5, 15.0)
        reasons.append(
            f"{boundary_count} lap/stop/start boundary fragment(s) detected."
        )

    splits = parse_splits(raw_splits)
    recognition = recognise_workout(splits)

    if recognition.rep_count >= 3:
        score += min(recognition.rep_count * 2.0, 18.0)
        reasons.append(
            f"{recognition.rep_count} faster work segment(s) were recognised."
        )

    if recognition.workout_type == "Mixed interval session":
        score += 12.0
        reasons.append("A mixed-distance work pattern was recognised.")
    elif recognition.workout_type not in (
        "No split data",
        "Unclassified",
        "Continuous sustained effort",
    ):
        score += 7.0
        reasons.append(
            f"Split decoder recognised {recognition.workout_type.lower()}."
        )

    if continuous_pattern and not has_workout_wording and title_intent is None:
        score -= 20.0
        reasons.append(
            "No clear interruption evidence reduced workout confidence."
        )

    return max(0.0, min(score, 100.0)), reasons


def _score_race(
    facts: ActivityFacts,
    raw: dict[str, Any],
) -> tuple[float, list[str], Any]:
    race_signals = score_race_evidence(
        title=facts.title,
        distance_km=facts.distance_km,
        moving_time_s=facts.moving_time_s,
        elapsed_time_s=facts.elapsed_time_s,
        avg_hr=facts.avg_hr,
        max_hr=facts.max_hr,
        athlete_lt2_hr=facts.athlete_lt2_hr,
        athlete_max_hr=facts.athlete_max_hr,
        official_race_name=raw.get("race_name"),
        official_distance_m=raw.get("race_officialDistance"),
        official_time_s=raw.get("race_officialTime"),
        officially_measured=bool(raw.get("race_officiallyMeasured")),
    )
    return (
        max(0.0, min(race_signals.total, 100.0)),
        list(race_signals.reasons),
        race_signals,
    )


def classify_session(facts: ActivityFacts) -> Session:
    evidence: list[SessionEvidence] = []
    routes = [
        CoachRoute.ENVIRONMENT,
        CoachRoute.RECOVERY,
        CoachRoute.PROGRESS,
    ]

    sport_id = str(facts.sport_id or "")
    sport_roles = get_athlete_sport_roles(facts.athlete_id)
    sport_role = sport_roles.get(sport_id)

    if sport_role == "walking":
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
            metadata={
                "classification_scores": {
                    "walk": 100.0,
                    "continuous_run": 0.0,
                    "structured_workout": 0.0,
                    "race": 0.0,
                }
            },
        )

    if sport_role != "running":
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
            metadata={
                "classification_scores": {
                    "cross_training": 98.0,
                    "continuous_run": 0.0,
                    "structured_workout": 0.0,
                    "race": 0.0,
                }
            },
        )

    raw = {}
    if facts.raw_json_text:
        try:
            raw = json.loads(facts.raw_json_text)
        except (TypeError, json.JSONDecodeError):
            raw = {}

    raw_splits = _extract_raw_splits(facts.raw_json_text)
    continuous_pattern, split_details = _continuous_split_pattern(
        raw_splits
    )

    continuous_score, continuous_reasons = _score_continuous(
        title=facts.title,
        continuous_pattern=continuous_pattern,
        split_details=split_details,
        moving_time_s=facts.moving_time_s,
        elapsed_time_s=facts.elapsed_time_s,
    )
    workout_score, workout_reasons = _score_structured(
        title=facts.title,
        continuous_pattern=continuous_pattern,
        split_details=split_details,
        raw_splits=raw_splits,
    )
    race_score, race_reasons, race_signals = _score_race(facts, raw)

    scores = {
        "continuous_run": round(continuous_score, 1),
        "structured_workout": round(workout_score, 1),
        "race": round(race_score, 1),
    }

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner, winner_score = ordered[0]
    runner_up, runner_up_score = ordered[1]
    margin = winner_score - runner_up_score

    reasons_by_type = {
        "continuous_run": continuous_reasons,
        "structured_workout": workout_reasons,
        "race": race_reasons,
    }

    confidence = max(
        0.35,
        min((winner_score / 100.0) * 0.75 + min(margin / 40.0, 1.0) * 0.25, 0.98),
    )

    metadata = {
        "split_classification": split_details,
        "classification_scores": scores,
        "classification_reasons": reasons_by_type,
        "winner": winner,
        "runner_up": runner_up,
        "score_margin": round(margin, 1),
    }

    if winner == "race":
        routes.extend([CoachRoute.RACE, CoachRoute.GOAL])
        session_type = SessionType.RACE
        purpose = SessionPurpose.RACE
    elif winner == "structured_workout":
        routes.extend([CoachRoute.WORKOUT, CoachRoute.THRESHOLD])
        session_type = SessionType.STRUCTURED_WORKOUT
        if _contains_any(
            facts.title,
            ("threshold", "tempo", "cruise"),
        ):
            purpose = SessionPurpose.THRESHOLD
        elif _contains_any(facts.title, ("fartlek",)):
            purpose = SessionPurpose.FARTLEK
        elif _contains_any(facts.title, ("hill rep", "hill session")):
            purpose = SessionPurpose.HILLS
        elif _contains_any(
            facts.title,
            ("vo2", "5k pace", "3k pace"),
        ):
            purpose = SessionPurpose.VO2
        else:
            purpose = SessionPurpose.UNKNOWN
    else:
        routes.append(CoachRoute.EASY)
        session_type = SessionType.CONTINUOUS_RUN
        purpose = SessionPurpose.GENERAL

    evidence.append(
        SessionEvidence(
            key="explainable_classification",
            description=(
                f"{winner.replace('_', ' ').title()} scored "
                f"{winner_score:.1f}; {runner_up.replace('_', ' ').title()} "
                f"scored {runner_up_score:.1f}."
            ),
            strength=confidence,
            supports=winner,
            metadata=metadata,
        )
    )

    return Session(
        activity_id=facts.activity_id,
        athlete_id=facts.athlete_id,
        activity_date=facts.activity_date,
        title=facts.title,
        sport_id=facts.sport_id,
        session_type=session_type,
        purpose=purpose,
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
        metadata=metadata,
    )

"""
Hall of Fame Engine.

Celebrates both traditional personal bests and performances whose quality is
easy to miss when looking only at raw pace.

Version 1 includes:
- standard-distance PBs using elapsed time;
- Best Easy Run;
- Best Long Easy Run;
- Best Hot Run;
- Best Trail Run;
- Hidden Gem: strongest environmentally adjusted performance whose raw pace
  understates its quality.

The engine is athlete-specific and uses the same environmental adjustment
foundation as the coaching system. Workout-specific awards will become more
precise when rep-level Workout DNA is connected.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

from core.coaching import RunProfile, equivalent_performance, get_athlete_sport_roles
from core.database import get_connection, get_effective_athlete_thresholds


STANDARD_DISTANCES = (
    ("mile", "1 Mile", 1609.344),
    ("5k", "5K", 5000.0),
    ("10k", "10K", 10000.0),
    ("10_mile", "10 Miles", 16093.44),
    ("half_marathon", "Half Marathon", 21097.5),
    ("marathon", "Marathon", 42195.0),
)

TRAIL_WORDS = (
    "trail",
    "forest",
    "off road",
    "off-road",
    "cross country",
    "xc",
)

QUALITY_WORDS = (
    "threshold",
    "tempo",
    "interval",
    "vo2",
    "reps",
    "race",
    "parkrun",
)


@dataclass(frozen=True)
class HallRun:
    activity_id: int
    activity_date: str | None
    title: str
    distance_km: float
    moving_time_s: float
    elapsed_time_s: float | None
    actual_pace_s_per_km: float
    equivalent_pace_s_per_km: float
    avg_hr: float | None
    temperature_c: float | None
    humidity: float | None
    wind_speed: float | None
    elevation_m: float | None
    route_name: str | None
    equipment_ids: str | None
    score: float
    category: str
    reason: str
    environment_note: str


@dataclass(frozen=True)
class PersonalBest:
    key: str
    label: str
    activity_id: int
    activity_date: str | None
    title: str
    distance_m: float
    elapsed_time_s: float
    pace_s_per_km: float


@dataclass(frozen=True)
class HallOfFame:
    athlete_id: int
    personal_bests: tuple[PersonalBest, ...]
    awards: tuple[HallRun, ...]
    candidate_count: int
    headline: str
    summary: str
    limitations: tuple[str, ...]
    model_version: int = 1


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_trail(title: str) -> bool:
    text = title.lower()
    return any(word in text for word in TRAIL_WORDS)


def _is_quality_title(title: str) -> bool:
    text = title.lower()
    return any(word in text for word in QUALITY_WORDS)


def _activity_rows(athlete_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id,
            activity_date,
            title,
            sport_id,
            distance_m,
            moving_time_s,
            elapsed_time_s,
            avg_hr,
            max_hr,
            elevation_up_m,
            temperature_c,
            humidity,
            wind_speed,
            route_name,
            equipment_ids,
            raw_json
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_datetime DESC
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def _running_sport_ids(athlete_id: int) -> set[str]:
    roles = get_athlete_sport_roles(athlete_id)
    return {
        str(sport_id)
        for sport_id, role in roles.items()
        if role == "running"
    }


def _profiles(athlete_id: int) -> list[tuple[int, RunProfile, dict[str, Any]]]:
    thresholds = get_effective_athlete_thresholds(athlete_id)
    running_ids = _running_sport_ids(athlete_id)
    profiles = []

    for row in _activity_rows(athlete_id):
        (
            activity_id,
            activity_date,
            title,
            sport_id,
            distance_m,
            moving_time_s,
            elapsed_time_s,
            avg_hr,
            max_hr,
            elevation_m,
            temperature_c,
            humidity,
            wind_speed,
            route_name,
            equipment_ids,
            raw_json,
        ) = row

        if running_ids and str(sport_id or "") not in running_ids:
            continue

        stored_distance = _safe_float(distance_m) or 0.0

        # The current Runalyze importer stores kilometres in the historical
        # distance_m column. Retain compatibility with any future/imported
        # rows that genuinely store metres.
        distance_km = (
            stored_distance / 1000.0
            if stored_distance > 250.0
            else stored_distance
        )
        moving = _safe_float(moving_time_s)

        if distance_km < 3 or moving is None or moving <= 0:
            continue

        pace = moving / distance_km

        if pace < 150 or pace > 720:
            continue

        profile = RunProfile(
            athlete_id=athlete_id,
            activity_date=activity_date,
            title=title or "Run",
            distance_km=distance_km,
            moving_time_seconds=moving,
            avg_hr=_safe_float(avg_hr),
            run_max_hr=_safe_float(max_hr),
            sport_id=sport_id,
            elevation_m=_safe_float(elevation_m),
            temperature_c=_safe_float(temperature_c),
            humidity=_safe_float(humidity),
            lt1_hr=thresholds.get("lt1_hr"),
            lt2_hr=thresholds.get("lt2_hr"),
            athlete_max_hr=thresholds.get("athlete_max_hr"),
        )

        metadata = {
            "elapsed_time_s": _safe_float(elapsed_time_s),
            "wind_speed": _safe_float(wind_speed),
            "route_name": route_name,
            "equipment_ids": equipment_ids,
            "raw_json": raw_json,
        }
        profiles.append((activity_id, profile, metadata))

    return profiles


def _equivalent_pace(profile: RunProfile) -> float:
    actual = profile.moving_time_seconds / profile.distance_km

    try:
        result = equivalent_performance(profile)
        adjusted = _safe_float(result.equivalent_pace_seconds_per_km)
        if adjusted is None or adjusted < 150 or adjusted > 720:
            return actual
        return adjusted
    except Exception:
        return actual


def _percentile(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(item <= value for item in values) / len(values)


def _quality_score(profile: RunProfile, equivalent_pace: float, efficiencies: list[float]) -> float:
    avg_hr = _safe_float(profile.avg_hr)

    if avg_hr and avg_hr > 0:
        efficiency = (1000.0 / equivalent_pace) / avg_hr
        efficiency_percentile = _percentile(efficiency, efficiencies)
    else:
        efficiency_percentile = 0.50

    lt1 = _safe_float(profile.lt1_hr)
    if avg_hr is not None and lt1:
        ratio = avg_hr / lt1
        if ratio <= 0.92:
            control = 0.96
        elif ratio <= 0.98:
            control = 0.90
        elif ratio <= 1.03:
            control = 0.78
        else:
            control = 0.58
    else:
        control = 0.70

    actual_pace = profile.moving_time_seconds / profile.distance_km
    environment_gain = max(actual_pace - equivalent_pace, 0.0)
    environment_bonus = min(environment_gain / 45.0, 1.0)

    score = (
        efficiency_percentile * 62
        + control * 28
        + environment_bonus * 10
    )
    return round(min(max(score, 0.0), 100.0), 1)


def _environment_note(
    profile: RunProfile,
    wind_speed: float | None,
    actual_pace: float,
    equivalent_pace: float,
) -> str:
    parts = []
    if profile.temperature_c is not None:
        parts.append(f"{profile.temperature_c:.0f}°C")
    if profile.humidity is not None:
        parts.append(f"{profile.humidity:.0f}% humidity")
    if wind_speed is not None:
        parts.append(f"{wind_speed:.0f} km/h wind")
    if _is_trail(profile.title or ""):
        parts.append("trail")
    if profile.elevation_m is not None and profile.distance_km > 0:
        climb = profile.elevation_m / profile.distance_km
        if climb >= 15:
            parts.append("hilly")

    gain = max(actual_pace - equivalent_pace, 0.0)
    if gain >= 2:
        parts.append(f"{gain:.0f} sec/km condition adjustment")

    return " · ".join(parts) if parts else "Normal conditions"


def _hall_run(
    activity_id: int,
    profile: RunProfile,
    metadata: dict[str, Any],
    score: float,
    category: str,
    reason: str,
) -> HallRun:
    actual = profile.moving_time_seconds / profile.distance_km
    equivalent = _equivalent_pace(profile)
    return HallRun(
        activity_id=activity_id,
        activity_date=profile.activity_date,
        title=profile.title or "Run",
        distance_km=round(profile.distance_km, 3),
        moving_time_s=round(profile.moving_time_seconds, 1),
        elapsed_time_s=metadata.get("elapsed_time_s"),
        actual_pace_s_per_km=round(actual, 1),
        equivalent_pace_s_per_km=round(equivalent, 1),
        avg_hr=_safe_float(profile.avg_hr),
        temperature_c=_safe_float(profile.temperature_c),
        humidity=_safe_float(profile.humidity),
        wind_speed=metadata.get("wind_speed"),
        elevation_m=_safe_float(profile.elevation_m),
        route_name=metadata.get("route_name"),
        equipment_ids=metadata.get("equipment_ids"),
        score=round(score, 1),
        category=category,
        reason=reason,
        environment_note=_environment_note(
            profile,
            metadata.get("wind_speed"),
            actual,
            equivalent,
        ),
    )


def _personal_bests(
    athlete_id: int,
    profiles: list[tuple[int, RunProfile, dict[str, Any]]],
) -> tuple[PersonalBest, ...]:
    pbs = []

    for key, label, target_m in STANDARD_DISTANCES:
        candidates = []

        for activity_id, profile, metadata in profiles:
            elapsed = metadata.get("elapsed_time_s")
            if elapsed is None or elapsed <= 0:
                continue

            activity_distance_m = profile.distance_km * 1000.0
            tolerance = max(target_m * 0.025, 120.0)

            if abs(activity_distance_m - target_m) <= tolerance:
                candidates.append(
                    (
                        elapsed,
                        activity_id,
                        profile,
                        activity_distance_m,
                    )
                )

        if not candidates:
            continue

        elapsed, activity_id, profile, distance_m = min(
            candidates,
            key=lambda item: item[0],
        )

        pbs.append(
            PersonalBest(
                key=key,
                label=label,
                activity_id=activity_id,
                activity_date=profile.activity_date,
                title=profile.title or label,
                distance_m=round(distance_m, 1),
                elapsed_time_s=round(elapsed, 1),
                pace_s_per_km=round(elapsed / (target_m / 1000.0), 1),
            )
        )

    return tuple(pbs)


def build_hall_of_fame(athlete_id: int) -> HallOfFame:
    profiles = _profiles(athlete_id)

    if not profiles:
        return HallOfFame(
            athlete_id=athlete_id,
            personal_bests=(),
            awards=(),
            candidate_count=0,
            headline="Hall of Fame is still learning",
            summary="No suitable running activities were found.",
            limitations=("Import running history to build awards.",),
        )

    efficiencies = []
    evaluated = []

    for activity_id, profile, metadata in profiles:
        equivalent = _equivalent_pace(profile)
        avg_hr = _safe_float(profile.avg_hr)
        if avg_hr and avg_hr > 0:
            efficiencies.append((1000.0 / equivalent) / avg_hr)

    for activity_id, profile, metadata in profiles:
        equivalent = _equivalent_pace(profile)
        score = _quality_score(profile, equivalent, efficiencies)
        evaluated.append((activity_id, profile, metadata, score))

    awards = []

    easy_candidates = [
        item for item in evaluated
        if not _is_quality_title(item[1].title or "")
        and item[1].avg_hr is not None
        and (
            item[1].lt1_hr is None
            or item[1].avg_hr <= item[1].lt1_hr * 1.03
        )
    ]

    if easy_candidates:
        winner = max(easy_candidates, key=lambda item: item[3])
        awards.append(
            _hall_run(
                *winner,
                category="Best Easy Run Ever",
                reason=(
                    "Highest combined adjusted aerobic efficiency, heart-rate "
                    "control and environmental context."
                ),
            )
        )

    long_candidates = [
        item for item in easy_candidates
        if item[1].distance_km >= 15.0
    ]
    if long_candidates:
        winner = max(long_candidates, key=lambda item: item[3])
        awards.append(
            _hall_run(
                *winner,
                category="Best Long Easy Run",
                reason="Best quality score among easy runs of at least 15 km.",
            )
        )

    hot_candidates = [
        item for item in evaluated
        if item[1].temperature_c is not None
        and item[1].temperature_c >= 20
    ]
    if hot_candidates:
        winner = max(hot_candidates, key=lambda item: item[3])
        awards.append(
            _hall_run(
                *winner,
                category="Best Hot Run",
                reason="Strongest quality after adjusting for warm conditions.",
            )
        )

    trail_candidates = [
        item for item in evaluated
        if _is_trail(item[1].title or "")
    ]
    if trail_candidates:
        winner = max(trail_candidates, key=lambda item: item[3])
        awards.append(
            _hall_run(
                *winner,
                category="Best Trail Run",
                reason="Strongest quality among recognised trail runs.",
            )
        )

    hidden_candidates = []
    for item in evaluated:
        activity_id, profile, metadata, score = item
        actual = profile.moving_time_seconds / profile.distance_km
        equivalent = _equivalent_pace(profile)
        condition_gain = actual - equivalent

        if condition_gain >= 8 and score >= 75:
            hidden_candidates.append((condition_gain * score, item))

    if hidden_candidates:
        _, winner = max(hidden_candidates, key=lambda item: item[0])
        awards.append(
            _hall_run(
                *winner,
                category="Hidden Gem",
                reason=(
                    "Raw pace understated the performance more than almost any "
                    "other high-quality run."
                ),
            )
        )

    return HallOfFame(
        athlete_id=athlete_id,
        personal_bests=_personal_bests(athlete_id, profiles),
        awards=tuple(awards),
        candidate_count=len(profiles),
        headline="Your greatest runs, not only your fastest",
        summary=(
            f"Performance Passport reviewed {len(profiles):,} running "
            "activities using elapsed-time PBs and environmentally adjusted "
            "training quality."
        ),
        limitations=(
            "PBs use elapsed time and a small GPS-distance tolerance.",
            "Easy, hot, trail and hidden-gem awards are athlete-relative.",
            "Threshold, VO₂ and speed awards will be added after rep-level "
            "Workout DNA is connected.",
            "Environmental adjustment currently uses available temperature, "
            "humidity, elevation and surface evidence; wind is shown where "
            "stored but is not yet personalised.",
        ),
    )

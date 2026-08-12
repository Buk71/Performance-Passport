"""
Performance Recognition Engine 2.0.

Recognition before recommendation.
Every run deserves one genuine achievement before one clear improvement.

The engine has four jobs:
1. classify each running activity into a runner-friendly category;
2. rank it against the athlete's own comparable history;
3. recognise difficult environmental context before judging raw pace;
4. find the strongest genuine positive in the session.

Rankings are always calculated, but the user-facing headline is positive-first.
The rank is evidence supporting the recognition rather than the judgement.

Environmental inputs:
- temperature;
- humidity and dew point via the existing environmental model;
- elevation gain;
- wind speed, conservatively because direction is not stored;
- trail/off-road surface where the source/title supports it.

Continuity inputs:
- moving time versus elapsed time;
- moving percentage where both are available.

Categories:
- Recovery
- Easy
- Long Easy
- Threshold Development
- VO2 Development
- Speed Development
- Structured Workout
- Race

Structured-workout rankings use the shared split-aware session classifier.
Their whole-session rankings remain provisional because recoveries make summary
pace and heart rate less precise than rep-level Workout DNA.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
from typing import Any, Iterable

from core.activity_reliability import has_reliable_distance_and_pace
from core.race_detection import score_athlete_relative_race_effort
from core.coaching import (
    RunProfile,
    equivalent_performance,
    get_athlete_sport_roles,
)
from core.database import get_connection, get_effective_athlete_thresholds
from core.session import SessionPurpose, SessionType
from core.session_intelligence import (
    ActivityFacts,
    RELIABLE_SESSION_CONFIDENCE,
    classify_session,
)


TRAIL_WORDS = (
    "trail",
    "forest",
    "off road",
    "off-road",
    "cross country",
    "xc",
)

RACE_WORDS = (
    "race",
    "parkrun",
    "5k race",
    "10k race",
    "half marathon",
    "marathon",
)

THRESHOLD_WORDS = (
    "threshold",
    "tempo",
    "cruise",
)

VO2_WORDS = (
    "vo2",
    "interval",
    "intervals",
    "800",
    "1000",
    "1k",
    "1200",
    "mile rep",
)

SPEED_WORDS = (
    "speed",
    "sprint",
    "strides",
    "stride",
    "200",
    "300",
    "400",
    "hill rep",
    "hill reps",
)


@dataclass(frozen=True)
class RecognitionAchievement:
    key: str
    label: str
    detail: str
    strength: float
    icon: str


@dataclass(frozen=True)
class Recognition:
    key: str
    category_key: str
    category_label: str
    icon: str

    rank: int
    total: int
    percentile: float
    top_percent: float

    rank_12m: int | None
    total_12m: int
    rank_90d: int | None
    total_90d: int

    confidence: float
    confidence_label: str
    celebration: str
    positive_detail: str
    achievements: tuple[RecognitionAchievement, ...]

    actual_pace_s_per_km: float
    adjusted_pace_s_per_km: float
    environment_adjustment_s_per_km: float
    environment_factors: tuple[str, ...]

    moving_percent: float | None
    continuity_label: str | None

    trend_label: str | None
    trend_detail: str | None

    provisional: bool


@dataclass(frozen=True)
class _ActivityContext:
    wind_speed: float | None
    moving_time_s: float | None
    elapsed_time_s: float | None
    moving_percent: float | None
    route_name: str | None
    session_type: SessionType | None
    session_purpose: SessionPurpose | None
    session_confidence: float | None
    pace_reliable: bool


@dataclass(frozen=True)
class _Candidate:
    key: str
    run: RunProfile
    category_key: str
    category_label: str
    icon: str

    signal: float
    actual_pace: float
    adjusted_pace: float
    environment_adjustment: float
    environment_factors: tuple[str, ...]

    moving_percent: float | None

    base_confidence: float
    provisional: bool


def recognition_key(run: RunProfile) -> str:
    return "|".join(
        (
            str(run.activity_date or ""),
            str(run.title or ""),
            f"{float(run.distance_km or 0.0):.3f}",
        )
    )


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def _date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _contains(title: str, words: tuple[str, ...]) -> bool:
    return any(word in title for word in words)


def _is_running(run: RunProfile) -> bool:
    if run.athlete_id is None:
        return str(run.sport_id or "") in {
            "965611",
            "966023",
            "run",
            "running",
        }

    roles = get_athlete_sport_roles(run.athlete_id)
    return roles.get(str(run.sport_id or "")) == "running"


def _category(
    run: RunProfile,
    *,
    elapsed_time_s: float | None = None,
    session_type: SessionType | None = None,
    session_purpose: SessionPurpose | None = None,
) -> tuple[str, str, str] | None:
    if not _is_running(run):
        return None

    title = str(run.title or "").lower()
    distance = _safe_float(run.distance_km)
    avg_hr = _safe_float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)
    lt2 = _safe_float(run.lt2_hr)

    if distance is None or distance < 3:
        return None

    # The shared classifier sees recorded recoveries and lap boundaries.  It
    # must outrank generic titles and whole-run averages, which can make a
    # stopped-watch interval session look implausibly easy or fast.
    if session_type == SessionType.STRUCTURED_WORKOUT:
        if session_purpose == SessionPurpose.THRESHOLD:
            return "threshold", "Threshold Development", "❤️"
        if session_purpose in {SessionPurpose.VO2, SessionPurpose.FARTLEK}:
            return "vo2", "VO₂ Development", "⚡"
        if session_purpose == SessionPurpose.HILLS:
            return "speed", "Hill Development", "⛰️"
        return "workout", "Structured Workout", "🔴"

    if session_type == SessionType.RACE:
        return "race", "Race", "🏁"

    if _contains(title, RACE_WORDS):
        return "race", "Race", "🏁"

    relative_race = score_athlete_relative_race_effort(
        athlete_id=run.athlete_id,
        title=title,
        distance_km=distance,
        moving_time_s=run.moving_time_seconds,
        elapsed_time_s=elapsed_time_s,
    )

    if relative_race.is_race_quality:
        return "race", "Race / Hard Effort", "🏁"

    if _contains(title, SPEED_WORDS):
        return "speed", "Speed Development", "⚡"

    if _contains(title, VO2_WORDS):
        return "vo2", "VO₂ Development", "⚡"

    if _contains(title, THRESHOLD_WORDS):
        return "threshold", "Threshold Development", "❤️"

    if (
        avg_hr is not None
        and lt1 is not None
        and lt2 is not None
        and avg_hr >= lt1 * 0.98
        and avg_hr <= lt2 * 1.02
    ):
        return "threshold", "Threshold Development", "❤️"

    if distance >= 15:
        return "long_easy", "Long Easy", "🧱"

    if (
        avg_hr is not None
        and lt1 is not None
        and distance <= 8
        and avg_hr <= lt1 * 0.91
    ):
        return "recovery", "Recovery", "🔋"

    if (
        avg_hr is None
        or lt1 is None
        or avg_hr <= lt1 * 1.03
    ):
        return "easy", "Easy", "😊"

    return "steady", "Steady Run", "🏃"


def _activity_context_lookup(
    athlete_id: int,
) -> dict[str, _ActivityContext]:
    thresholds = get_effective_athlete_thresholds(athlete_id)
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
            raw_json
        FROM activities
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    lookup = {}

    for (
        activity_id,
        activity_date,
        title,
        sport_id,
        distance_value,
        moving_time_s,
        elapsed_time_s,
        avg_hr,
        max_hr,
        elevation_up_m,
        temperature_c,
        humidity,
        wind_speed,
        route_name,
        raw_json,
    ) in rows:
        distance = _safe_float(distance_value) or 0.0

        # Historical Runalyze rows use km in distance_m. Preserve compatibility
        # with future/other importers that genuinely store metres.
        distance_km = distance / 1000.0 if distance > 250 else distance

        key = "|".join(
            (
                str(activity_date or ""),
                str(title or ""),
                f"{distance_km:.3f}",
            )
        )

        moving = _safe_float(moving_time_s)
        elapsed = _safe_float(elapsed_time_s)

        session = classify_session(
            ActivityFacts(
                activity_id=int(activity_id),
                athlete_id=athlete_id,
                activity_date=activity_date,
                title=title or "Activity",
                sport_id=str(sport_id) if sport_id is not None else None,
                distance_km=distance_km,
                moving_time_s=moving,
                elapsed_time_s=elapsed,
                avg_hr=_safe_float(avg_hr),
                max_hr=_safe_float(max_hr),
                elevation_up_m=_safe_float(elevation_up_m),
                temperature_c=_safe_float(temperature_c),
                humidity=_safe_float(humidity),
                wind_speed=_safe_float(wind_speed),
                route_name=route_name,
                raw_json_text=raw_json,
                athlete_lt2_hr=thresholds.get("lt2_hr"),
                athlete_max_hr=thresholds.get("athlete_max_hr"),
            )
        )

        moving_percent = None

        if (
            moving is not None
            and elapsed is not None
            and moving > 0
            and elapsed > 0
        ):
            moving_percent = min(
                max((moving / elapsed) * 100.0, 0.0),
                100.0,
            )

        lookup[key] = _ActivityContext(
            wind_speed=_safe_float(wind_speed),
            moving_time_s=moving,
            elapsed_time_s=elapsed,
            moving_percent=moving_percent,
            route_name=route_name,
            session_type=session.session_type,
            session_purpose=session.purpose,
            session_confidence=session.confidence,
            pace_reliable=has_reliable_distance_and_pace(
                title=title,
                sport_id=str(sport_id) if sport_id is not None else None,
                route_name=route_name,
                raw_json_text=raw_json,
            ),
        )

    return lookup


def _trail_surface_penalty(run: RunProfile) -> tuple[float, str | None]:
    title = str(run.title or "").lower()

    if any(word in title for word in TRAIL_WORDS):
        # Conservative until explicit surface data is available.
        return 6.0, "trail/off-road surface"

    return 0.0, None


def _elevation_penalty(run: RunProfile) -> tuple[float, str | None]:
    ascent = _safe_float(run.elevation_m)
    distance = _safe_float(run.distance_km)

    if ascent is None or distance is None or distance <= 0:
        return 0.0, None

    climbing_density = max(ascent / distance, 0.0)

    # Total ascent alone cannot support precise GAP. Recognition uses a small,
    # capped allowance so hills are acknowledged without dominating the rank.
    penalty = min(climbing_density * 0.30, 15.0)

    if penalty < 1.0:
        return 0.0, None

    return penalty, f"{ascent:.0f} m climbing"


def _wind_penalty(
    wind_speed: float | None,
) -> tuple[float, str | None]:
    if wind_speed is None or wind_speed < 10:
        return 0.0, None

    # Direction is unavailable. Only recognise a conservative fraction.
    penalty = min((wind_speed - 10.0) * 0.18, 8.0)

    if penalty <= 0:
        return 0.0, None

    return penalty, f"{wind_speed:.0f} km/h wind"


def _environment_adjusted_pace(
    run: RunProfile,
    *,
    wind_speed: float | None,
) -> tuple[float, float, tuple[str, ...]]:
    actual = (
        float(run.moving_time_seconds)
        / float(run.distance_km)
    )

    existing_penalty = 0.0
    factors = []

    try:
        performance = equivalent_performance(run)

        if performance is not None:
            existing_penalty = max(
                actual
                - float(
                    performance.equivalent_pace_seconds_per_km
                ),
                0.0,
            )

            adjustment = performance.adjustment

            if adjustment.temperature_penalty_seconds_per_km > 0.5:
                factors.append(
                    f"{adjustment.temperature_c:.0f}°C heat"
                )

            if adjustment.humidity_penalty_seconds_per_km > 0.5:
                if adjustment.dew_point_c is not None:
                    factors.append(
                        f"{adjustment.dew_point_c:.0f}°C dew point"
                    )
                else:
                    factors.append("humidity")
    except Exception:
        pass

    elevation_penalty, elevation_note = _elevation_penalty(run)
    wind_penalty, wind_note = _wind_penalty(wind_speed)
    surface_penalty, surface_note = _trail_surface_penalty(run)

    for note in (
        elevation_note,
        wind_note,
        surface_note,
    ):
        if note:
            factors.append(note)

    total_penalty = (
        existing_penalty
        + elevation_penalty
        + wind_penalty
        + surface_penalty
    )

    # Recognition should never manufacture implausible performances.
    total_penalty = min(
        total_penalty,
        actual * 0.18,
    )

    adjusted = max(
        actual - total_penalty,
        150.0,
    )

    return adjusted, total_penalty, tuple(factors)


def _aerobic_control(run: RunProfile) -> float:
    avg_hr = _safe_float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)

    if avg_hr is None or lt1 is None or lt1 <= 0:
        return 0.75

    ratio = avg_hr / lt1

    if ratio <= 0.90:
        return 0.98
    if ratio <= 0.95:
        return 0.95
    if ratio <= 0.99:
        return 0.91
    if ratio <= 1.01:
        return 0.85
    if ratio <= 1.03:
        return 0.74
    return 0.58


def _performance_signal(
    run: RunProfile,
    *,
    category_key: str,
    adjusted_pace: float,
) -> tuple[float, float, bool]:
    avg_hr = _safe_float(run.avg_hr)

    if category_key in {
        "recovery",
        "easy",
        "long_easy",
        "steady",
    }:
        if avg_hr is not None and avg_hr > 0:
            efficiency = (1000.0 / adjusted_pace) / avg_hr
            control = _aerobic_control(run)

            # Efficiency drives the ordering. Control protects the purpose of
            # an easy run from being rewarded simply for being run too hard.
            signal = efficiency * (0.76 + 0.24 * control)
            return signal, 0.90, False

        return 1000.0 / adjusted_pace, 0.62, True

    if category_key == "race":
        return 1000.0 / adjusted_pace, 0.88, False

    # Whole-session averages include recoveries. Useful, but provisional.
    intensity = 1.0

    if avg_hr is not None and run.lt1_hr:
        intensity = max(
            min(avg_hr / float(run.lt1_hr), 1.15),
            0.85,
        )

    signal = (1000.0 / adjusted_pace) * intensity
    return signal, 0.58, True


def _rank(
    candidate: _Candidate,
    group: list[_Candidate],
) -> tuple[int, int]:
    ordered = sorted(
        group,
        key=lambda item: (
            item.signal,
            item.adjusted_pace * -1,
        ),
        reverse=True,
    )

    return ordered.index(candidate) + 1, len(ordered)


def _confidence(
    *,
    base_confidence: float,
    total: int,
    run: RunProfile,
    environment_factors: tuple[str, ...],
    moving_percent: float | None,
    provisional: bool,
) -> tuple[float, str]:
    sample_factor = min(total / 25.0, 1.0)

    data_points = 0
    possible = 5

    if run.avg_hr is not None:
        data_points += 1
    if run.temperature_c is not None:
        data_points += 1
    if run.humidity is not None:
        data_points += 1
    if run.elevation_m is not None:
        data_points += 1
    if moving_percent is not None:
        data_points += 1

    completeness = data_points / possible

    confidence = (
        base_confidence * 0.62
        + sample_factor * 0.23
        + completeness * 0.15
    )

    if provisional:
        confidence = min(confidence, 0.64)

    confidence = min(max(confidence, 0.0), 0.98)

    if confidence >= 0.86:
        label = "High confidence"
    elif confidence >= 0.70:
        label = "Good confidence"
    elif confidence >= 0.52:
        label = "Developing confidence"
    else:
        label = "Early evidence"

    return round(confidence, 4), label


def _continuity_achievement(
    moving_percent: float | None,
) -> RecognitionAchievement | None:
    if moving_percent is None:
        return None

    if moving_percent >= 99.5:
        return RecognitionAchievement(
            key="continuous",
            label="Excellent flow",
            detail=f"{moving_percent:.1f}% of elapsed time was moving.",
            strength=0.92,
            icon="▶️",
        )

    if moving_percent >= 97.0:
        return RecognitionAchievement(
            key="minimal_interruptions",
            label="Minimal interruptions",
            detail=f"{moving_percent:.1f}% moving kept the session flowing.",
            strength=0.76,
            icon="▶️",
        )

    return None


def _achievement_candidates(
    *,
    candidate: _Candidate,
    rank: int,
    total: int,
) -> list[RecognitionAchievement]:
    achievements = []
    run = candidate.run

    top_percent = (rank / total) * 100 if total else 100.0

    if rank == 1 and total >= 3:
        achievements.append(
            RecognitionAchievement(
                key="best_ever",
                label=f"Best {candidate.category_label} ever",
                detail=(
                    "This is the strongest comparable session currently "
                    "in your history."
                ),
                strength=1.00,
                icon="🏆",
            )
        )
    elif top_percent <= 5:
        achievements.append(
            RecognitionAchievement(
                key="top_5",
                label=f"Top 5% {candidate.category_label}",
                detail="One of your standout sessions in this category.",
                strength=0.97,
                icon="⭐",
            )
        )
    elif top_percent <= 10:
        achievements.append(
            RecognitionAchievement(
                key="top_10",
                label=f"Top 10% {candidate.category_label}",
                detail=(
                    "A genuinely strong session compared with your own "
                    "history."
                ),
                strength=0.93,
                icon="⭐",
            )
        )
    elif top_percent <= 25:
        achievements.append(
            RecognitionAchievement(
                key="top_25",
                label=f"Top 25% {candidate.category_label}",
                detail="Another high-quality session banked.",
                strength=0.84,
                icon="⭐",
            )
        )

    if candidate.environment_adjustment >= 10:
        context = (
            ", ".join(candidate.environment_factors[:2])
            if candidate.environment_factors
            else "difficult conditions"
        )
        achievements.append(
            RecognitionAchievement(
                key="environment_resilience",
                label="Strong conditions performance",
                detail=(
                    f"Your raw pace understated the run because of {context}."
                ),
                strength=0.91,
                icon="🌦️",
            )
        )
    elif candidate.environment_adjustment >= 5:
        achievements.append(
            RecognitionAchievement(
                key="conditions_handled",
                label="Conditions handled well",
                detail=(
                    "The environmental context is recognised before your "
                    "performance is ranked."
                ),
                strength=0.76,
                icon="🌦️",
            )
        )

    avg_hr = _safe_float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)

    if (
        candidate.category_key in {
            "recovery",
            "easy",
            "long_easy",
        }
        and avg_hr is not None
        and lt1 is not None
    ):
        ratio = avg_hr / lt1

        if ratio <= 0.92:
            achievements.append(
                RecognitionAchievement(
                    key="aerobic_control",
                    label="Excellent aerobic control",
                    detail=(
                        "You kept the effort comfortably controlled and "
                        "protected the purpose of the session."
                    ),
                    strength=0.88,
                    icon="❤️",
                )
            )
        elif ratio <= 0.98:
            achievements.append(
                RecognitionAchievement(
                    key="controlled_effort",
                    label="Well-controlled effort",
                    detail=(
                        "Heart rate stayed in a productive personal easy "
                        "range."
                    ),
                    strength=0.74,
                    icon="❤️",
                )
            )

    continuity = _continuity_achievement(
        candidate.moving_percent
    )

    if continuity is not None:
        achievements.append(continuity)

    if candidate.category_key == "long_easy":
        achievements.append(
            RecognitionAchievement(
                key="endurance_banked",
                label="Valuable endurance banked",
                detail=(
                    "Long-run consistency is one of the foundations of "
                    "durable fitness."
                ),
                strength=0.70,
                icon="🧱",
            )
        )

    if not achievements:
        achievements.append(
            RecognitionAchievement(
                key="consistency",
                label="Another useful session banked",
                detail=(
                    "Consistency matters: this run adds another piece of "
                    "evidence to your personal coaching picture."
                ),
                strength=0.55,
                icon="✨",
            )
        )

    achievements.sort(
        key=lambda achievement: achievement.strength,
        reverse=True,
    )

    return achievements


def _trend(
    candidate: _Candidate,
    group: list[_Candidate],
) -> tuple[str | None, str | None]:
    dated = [
        item
        for item in group
        if _date(item.run.activity_date) is not None
    ]
    dated.sort(
        key=lambda item: _date(item.run.activity_date),
        reverse=True,
    )

    if candidate not in dated:
        return None, None

    position = dated.index(candidate)

    # We only call a trend when enough earlier comparable runs exist.
    previous = dated[position + 1: position + 6]

    if len(previous) < 3:
        return None, None

    previous_average = sum(
        item.signal
        for item in previous
    ) / len(previous)

    if previous_average <= 0:
        return None, None

    relative = (
        candidate.signal - previous_average
    ) / previous_average

    if relative >= 0.04:
        return (
            "Trending stronger",
            "This performance is clearly above your previous five comparable sessions.",
        )

    if relative >= 0.015:
        return (
            "Positive trend",
            "This performance is above your recent comparable-session average.",
        )

    if relative <= -0.05:
        return (
            "Building opportunity",
            "Recent comparable sessions have been stronger, giving the coach useful evidence for the next improvement.",
        )

    return (
        "Consistent",
        "This sits close to the level of your recent comparable sessions.",
    )


def build_recognition_index(
    runs: Iterable[RunProfile],
    *,
    athlete_id: int,
    reference_date: datetime.date | None = None,
) -> dict[str, Recognition]:
    reference_date = reference_date or datetime.date.today()
    context_lookup = _activity_context_lookup(athlete_id)
    candidates = []

    for run in runs:
        if (
            run.distance_km is None
            or run.moving_time_seconds is None
            or run.distance_km <= 0
            or run.moving_time_seconds <= 0
        ):
            continue

        key = recognition_key(run)
        context = context_lookup.get(
            key,
            _ActivityContext(
                wind_speed=None,
                moving_time_s=None,
                elapsed_time_s=None,
                moving_percent=None,
                route_name=None,
                session_type=None,
                session_purpose=None,
                session_confidence=None,
                pace_reliable=True,
            ),
        )

        # The session remains part of training history and can still inform
        # duration/heart-rate load. Device-estimated treadmill distance and
        # pace must not enter athlete-relative performance comparisons.
        if not context.pace_reliable:
            continue

        category = _category(
            run,
            elapsed_time_s=context.elapsed_time_s,
            session_type=(
                context.session_type
                if (
                    context.session_confidence is not None
                    and context.session_confidence
                    >= RELIABLE_SESSION_CONFIDENCE
                )
                else None
            ),
            session_purpose=(
                context.session_purpose
                if (
                    context.session_confidence is not None
                    and context.session_confidence
                    >= RELIABLE_SESSION_CONFIDENCE
                )
                else None
            ),
        )

        if category is None:
            continue

        adjusted, environment_adjustment, environment_factors = (
            _environment_adjusted_pace(
                run,
                wind_speed=context.wind_speed,
            )
        )

        actual = (
            float(run.moving_time_seconds)
            / float(run.distance_km)
        )

        category_key, category_label, icon = category
        signal, base_confidence, provisional = _performance_signal(
            run,
            category_key=category_key,
            adjusted_pace=adjusted,
        )

        candidates.append(
            _Candidate(
                key=key,
                run=run,
                category_key=category_key,
                category_label=category_label,
                icon=icon,
                signal=signal,
                actual_pace=actual,
                adjusted_pace=adjusted,
                environment_adjustment=environment_adjustment,
                environment_factors=environment_factors,
                moving_percent=context.moving_percent,
                base_confidence=base_confidence,
                provisional=provisional,
            )
        )

    by_category = {}

    for candidate in candidates:
        by_category.setdefault(
            candidate.category_key,
            [],
        ).append(candidate)

    result = {}

    for candidate in candidates:
        group = by_category[candidate.category_key]
        rank, total = _rank(candidate, group)

        group_12m = []
        group_90d = []

        for item in group:
            item_date = _date(item.run.activity_date)

            if item_date is None:
                continue

            age_days = (reference_date - item_date).days

            if 0 <= age_days <= 365:
                group_12m.append(item)

            if 0 <= age_days <= 90:
                group_90d.append(item)

        rank_12m = None
        rank_90d = None

        if candidate in group_12m:
            rank_12m, _ = _rank(candidate, group_12m)

        if candidate in group_90d:
            rank_90d, _ = _rank(candidate, group_90d)

        percentile = (
            1.0
            if total <= 1
            else 1.0 - ((rank - 1) / total)
        )
        top_percent = (rank / total) * 100.0

        achievements = _achievement_candidates(
            candidate=candidate,
            rank=rank,
            total=total,
        )
        primary = achievements[0]

        confidence, confidence_label = _confidence(
            base_confidence=candidate.base_confidence,
            total=total,
            run=candidate.run,
            environment_factors=candidate.environment_factors,
            moving_percent=candidate.moving_percent,
            provisional=candidate.provisional,
        )

        if candidate.moving_percent is None:
            continuity_label = None
        elif candidate.moving_percent >= 99.5:
            continuity_label = "Continuous"
        elif candidate.moving_percent >= 97:
            continuity_label = "Minimal interruptions"
        elif candidate.moving_percent >= 92:
            continuity_label = "Some interruptions"
        else:
            continuity_label = "Interrupted session"

        trend_label, trend_detail = _trend(
            candidate,
            group,
        )

        result[candidate.key] = Recognition(
            key=candidate.key,
            category_key=candidate.category_key,
            category_label=candidate.category_label,
            icon=candidate.icon,
            rank=rank,
            total=total,
            percentile=round(percentile, 4),
            top_percent=round(top_percent, 1),
            rank_12m=rank_12m,
            total_12m=len(group_12m),
            rank_90d=rank_90d,
            total_90d=len(group_90d),
            confidence=confidence,
            confidence_label=confidence_label,
            celebration=primary.label,
            positive_detail=primary.detail,
            achievements=tuple(achievements[:4]),
            actual_pace_s_per_km=round(candidate.actual_pace, 1),
            adjusted_pace_s_per_km=round(candidate.adjusted_pace, 1),
            environment_adjustment_s_per_km=round(
                candidate.environment_adjustment,
                1,
            ),
            environment_factors=candidate.environment_factors,
            moving_percent=(
                round(candidate.moving_percent, 1)
                if candidate.moving_percent is not None
                else None
            ),
            continuity_label=continuity_label,
            trend_label=trend_label,
            trend_detail=trend_detail,
            provisional=candidate.provisional,
        )

    return result

"""
Performance Recognition Engine.

Recognition before recommendation.
Every run deserves one genuine achievement before one clear improvement.

The engine ranks running activities against the athlete's own comparable
history. Environmental context is applied before ranking so raw pace does not
unfairly penalise runs completed in difficult conditions.

Environmental inputs currently recognised:
- temperature;
- humidity and derived dew point through the existing coaching engine;
- elevation gain;
- wind speed, conservatively because direction is not stored;
- trail/off-road surface when recognised from the activity title.

Rankings are category-specific:
- Recovery
- Easy
- Long Easy
- Threshold Development
- VO2 Development
- Speed Development
- Race

Development-workout rankings are intentionally lower confidence until
rep-level Workout DNA is connected.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
from typing import Any, Iterable

from core.coaching import (
    RunProfile,
    equivalent_performance,
    get_athlete_sport_roles,
)
from core.database import get_connection


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
    celebration: str
    positive_detail: str
    actual_pace_s_per_km: float
    adjusted_pace_s_per_km: float
    environment_adjustment_s_per_km: float
    environment_factors: tuple[str, ...]
    provisional: bool


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
    confidence: float
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


def _category(run: RunProfile) -> tuple[str, str, str] | None:
    if not _is_running(run):
        return None

    title = str(run.title or "").lower()
    distance = _safe_float(run.distance_km)
    avg_hr = _safe_float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)
    lt2 = _safe_float(run.lt2_hr)

    if distance is None or distance < 3:
        return None

    if _contains(title, RACE_WORDS):
        return "race", "Race", "🏁"

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


def _wind_lookup(
    athlete_id: int,
) -> dict[str, float]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            activity_date,
            title,
            distance_m,
            wind_speed
        FROM activities
        WHERE athlete_id = ?
          AND wind_speed IS NOT NULL
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    lookup = {}

    for activity_date, title, distance_value, wind_speed in rows:
        distance = _safe_float(distance_value) or 0.0

        # Current Runalyze rows store kilometres in the historical distance_m
        # column; retain compatibility with genuine metre values.
        distance_km = distance / 1000.0 if distance > 250 else distance

        key = "|".join(
            (
                str(activity_date or ""),
                str(title or ""),
                f"{distance_km:.3f}",
            )
        )
        wind = _safe_float(wind_speed)

        if wind is not None:
            lookup[key] = wind

    return lookup


def _trail_surface_penalty(run: RunProfile) -> tuple[float, str | None]:
    title = str(run.title or "").lower()

    if any(word in title for word in TRAIL_WORDS):
        # Conservative proxy until explicit surface data is imported.
        return 6.0, "trail/off-road surface"

    return 0.0, None


def _elevation_penalty(run: RunProfile) -> tuple[float, str | None]:
    ascent = _safe_float(run.elevation_m)
    distance = _safe_float(run.distance_km)

    if ascent is None or distance is None or distance <= 0:
        return 0.0, None

    climbing_density = max(ascent / distance, 0.0)

    # Total ascent cannot provide exact grade-adjusted pace. Use only a
    # conservative recognition adjustment, capped so hills cannot dominate.
    penalty = min(climbing_density * 0.30, 15.0)

    if penalty < 1.0:
        return 0.0, None

    return penalty, f"{ascent:.0f} m climbing"


def _wind_penalty(
    wind_speed: float | None,
) -> tuple[float, str | None]:
    if wind_speed is None or wind_speed < 10:
        return 0.0, None

    # Direction is unknown, so only a small fraction of wind speed is used.
    # This recognises exposed conditions without pretending every wind was a
    # headwind.
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

    # Never let context create an implausible equivalent pace.
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
        return 0.97
    if ratio <= 0.95:
        return 0.94
    if ratio <= 0.99:
        return 0.90
    if ratio <= 1.01:
        return 0.84
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

            # Efficiency drives the ordering; HR control prevents an
            # accidentally hard "easy" run being rewarded for speed alone.
            signal = efficiency * (0.78 + 0.22 * control)
            return signal, 0.90, False

        return 1000.0 / adjusted_pace, 0.62, True

    if category_key == "race":
        return 1000.0 / adjusted_pace, 0.86, False

    # Whole-activity pace for structured workouts includes recoveries.
    # Allow a useful provisional ranking but state the limitation clearly.
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
        key=lambda item: item.signal,
        reverse=True,
    )
    return ordered.index(candidate) + 1, len(ordered)


def _celebration(
    *,
    rank: int,
    total: int,
    category_label: str,
    environment_adjustment: float,
    environment_factors: tuple[str, ...],
    run: RunProfile,
) -> tuple[str, str]:
    top_percent = (rank / total) * 100 if total else 100.0

    if rank == 1 and total >= 3:
        return (
            f"Best {category_label} ever",
            "This is the strongest comparable session currently in your history.",
        )

    if top_percent <= 5:
        return (
            f"Top 5% {category_label}",
            "One of your standout sessions in this category.",
        )

    if top_percent <= 10:
        return (
            f"Top 10% {category_label}",
            "A genuinely strong session compared with your own history.",
        )

    if top_percent <= 25:
        return (
            f"Top 25% {category_label}",
            "Another high-quality session banked.",
        )

    if environment_adjustment >= 8:
        context = (
            ", ".join(environment_factors[:2])
            if environment_factors
            else "difficult conditions"
        )
        return (
            "Tough conditions handled well",
            f"Your raw pace understated the run because of {context}.",
        )

    avg_hr = _safe_float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)

    if (
        avg_hr is not None
        and lt1 is not None
        and avg_hr <= lt1 * 0.95
    ):
        return (
            "Excellent aerobic control",
            "You kept the effort comfortably controlled and protected the purpose of the run.",
        )

    if category_label == "Long Easy":
        return (
            "Valuable endurance banked",
            "Long-run consistency is one of the foundations of durable fitness.",
        )

    return (
        "Another useful session banked",
        "Consistency matters: this run adds another piece of evidence to your personal coaching picture.",
    )


def build_recognition_index(
    runs: Iterable[RunProfile],
    *,
    athlete_id: int,
    reference_date: datetime.date | None = None,
) -> dict[str, Recognition]:
    reference_date = reference_date or datetime.date.today()
    wind_lookup = _wind_lookup(athlete_id)
    candidates = []

    for run in runs:
        category = _category(run)

        if category is None:
            continue

        if (
            run.distance_km is None
            or run.moving_time_seconds is None
            or run.distance_km <= 0
            or run.moving_time_seconds <= 0
        ):
            continue

        key = recognition_key(run)
        adjusted, environment_adjustment, environment_factors = (
            _environment_adjusted_pace(
                run,
                wind_speed=wind_lookup.get(key),
            )
        )
        actual = (
            float(run.moving_time_seconds)
            / float(run.distance_km)
        )

        category_key, category_label, icon = category
        signal, confidence, provisional = _performance_signal(
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
                confidence=confidence,
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
        run_date = _date(candidate.run.activity_date)

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

        celebration, positive_detail = _celebration(
            rank=rank,
            total=total,
            category_label=candidate.category_label,
            environment_adjustment=candidate.environment_adjustment,
            environment_factors=candidate.environment_factors,
            run=candidate.run,
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
            confidence=round(candidate.confidence, 4),
            celebration=celebration,
            positive_detail=positive_detail,
            actual_pace_s_per_km=round(candidate.actual_pace, 1),
            adjusted_pace_s_per_km=round(candidate.adjusted_pace, 1),
            environment_adjustment_s_per_km=round(
                candidate.environment_adjustment,
                1,
            ),
            environment_factors=candidate.environment_factors,
            provisional=candidate.provisional,
        )

    return result

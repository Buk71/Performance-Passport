"""
Coach Blueprints.

Each coach learns what the athlete's strongest historical sessions look like.

Version 2 replaces technical data-science categories with runner-friendly
session purposes:

Easy Coach
- Recovery
- Easy
- Long Easy

Development Coaches
- Threshold Development
- VO2 Development
- Speed Development

Important safeguards:
- only activities mapped to the athlete's running sport are included;
- implausible running paces are rejected;
- easy-run pace bands are shown in the dashboard in minutes per mile;
- workout-average pace is not shown for development sessions because warm-up,
  recoveries and cool-down make the activity average misleading;
- small samples remain clearly labelled.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
from typing import Any, Iterable

from core.coaching import (
    RunProfile,
    equivalent_performance,
    get_athlete_sport_roles,
)


MILES_PER_KM = 0.621371192237334
MIN_REALISTIC_PACE_S_PER_KM = 150.0
MAX_REALISTIC_PACE_S_PER_KM = 720.0

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

RACE_WORDS = (
    "race",
    "parkrun",
    "5k race",
    "10k race",
    "half marathon",
    "marathon",
)


@dataclass(frozen=True)
class BlueprintCategory:
    key: str
    label: str
    coach: str
    icon: str
    sample_size: int
    benchmark_size: int
    confidence: float
    hr_low: int | None
    hr_high: int | None
    hr_typical: int | None
    pace_low_s_per_km: float | None
    pace_high_s_per_km: float | None
    typical_distance_km: float | None
    show_pace: bool
    source: str
    summary: str


@dataclass(frozen=True)
class TrainingBlueprint:
    athlete_id: int
    categories: tuple[BlueprintCategory, ...]
    available_category_count: int
    overall_confidence: float
    headline: str
    summary: str
    limitations: tuple[str, ...]
    model_version: int = 2


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def _pace(run: RunProfile) -> float | None:
    distance = _safe_float(run.distance_km)
    moving_time = _safe_float(run.moving_time_seconds)

    if (
        distance is None
        or moving_time is None
        or distance <= 0
        or moving_time <= 0
    ):
        return None

    pace = moving_time / distance

    if not (
        MIN_REALISTIC_PACE_S_PER_KM
        <= pace
        <= MAX_REALISTIC_PACE_S_PER_KM
    ):
        return None

    return pace


def _equivalent_pace(run: RunProfile) -> float | None:
    pace = _pace(run)

    if pace is None:
        return None

    try:
        result = equivalent_performance(run)

        if result is None:
            return pace

        adjusted = _safe_float(
            result.equivalent_pace_seconds_per_km
        )

        # Environmental correction must never create an implausible
        # running pace. Fall back to the actual pace when it does.
        if (
            adjusted is None
            or adjusted < MIN_REALISTIC_PACE_S_PER_KM
            or adjusted > MAX_REALISTIC_PACE_S_PER_KM
        ):
            return pace

        return adjusted
    except Exception:
        return pace


def _is_running_activity(run: RunProfile) -> bool:
    if run.athlete_id is None:
        return str(run.sport_id or "") in {
            "965611",
            "966023",
            "run",
            "running",
        }

    roles = get_athlete_sport_roles(run.athlete_id)
    return roles.get(str(run.sport_id or "")) == "running"


def _contains(title: str, words: tuple[str, ...]) -> bool:
    return any(word in title for word in words)


def _is_race(run: RunProfile) -> bool:
    return _contains(
        str(run.title or "").lower(),
        RACE_WORDS,
    )


def _session_type(run: RunProfile) -> str | None:
    if not _is_running_activity(run) or _pace(run) is None:
        return None

    title = str(run.title or "").lower()
    distance = _safe_float(run.distance_km)
    avg_hr = _safe_float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)
    lt2 = _safe_float(run.lt2_hr)

    if (
        distance is None
        or avg_hr is None
        or distance < 3.0
        or _is_race(run)
    ):
        return None

    # Workout categories are checked first because activity-average HR can
    # remain deceptively low when recoveries are included.
    if _contains(title, SPEED_WORDS):
        return "speed"

    if _contains(title, VO2_WORDS):
        return "vo2"

    if _contains(title, THRESHOLD_WORDS):
        return "threshold"

    # HR-supported fallback for untitled threshold sessions.
    if (
        lt1 is not None
        and lt2 is not None
        and avg_hr >= lt1 * 0.98
        and avg_hr <= lt2 * 1.02
    ):
        return "threshold"

    # Easy categories.
    if lt1 is not None and avg_hr > lt1 * 1.03:
        return None

    if distance >= 15.0:
        return "long_easy"

    if (
        distance <= 8.0
        and lt1 is not None
        and avg_hr <= lt1 * 0.91
    ):
        return "recovery"

    return "easy"


def _efficiency(run: RunProfile) -> float | None:
    pace = _equivalent_pace(run)
    avg_hr = _safe_float(run.avg_hr)

    if pace is None or avg_hr is None or avg_hr <= 0:
        return None

    return (1000.0 / pace) / avg_hr


def _percentile(
    values: list[float],
    percentile: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return ordered[lower]

    fraction = position - lower
    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * fraction
    )


def _confidence(sample_size: int) -> float:
    if sample_size <= 0:
        return 0.0
    if sample_size >= 30:
        return 0.95
    if sample_size >= 15:
        return 0.82
    if sample_size >= 8:
        return 0.68
    if sample_size >= 4:
        return 0.48
    return 0.25


def _build_category(
    *,
    key: str,
    label: str,
    coach: str,
    icon: str,
    runs: list[RunProfile],
    show_pace: bool,
) -> BlueprintCategory:
    scored = []

    for run in runs:
        score = _efficiency(run)

        if score is not None:
            scored.append((run, score))

    if not scored:
        return BlueprintCategory(
            key=key,
            label=label,
            coach=coach,
            icon=icon,
            sample_size=0,
            benchmark_size=0,
            confidence=0.0,
            hr_low=None,
            hr_high=None,
            hr_typical=None,
            pace_low_s_per_km=None,
            pace_high_s_per_km=None,
            typical_distance_km=None,
            show_pace=show_pace,
            source="Still learning",
            summary="Not enough comparable sessions yet.",
        )

    # Easy sessions can be ranked by adjusted aerobic efficiency.
    # For development workouts this is only a conservative activity-level
    # proxy until rep-level workout structure is connected.
    scored.sort(
        key=lambda item: item[1],
        reverse=True,
    )
    benchmark_size = max(
        3,
        int(math.ceil(len(scored) * 0.30)),
    )
    benchmark = scored[
        : min(benchmark_size, len(scored))
    ]

    heart_rates = [
        float(run.avg_hr)
        for run, _ in benchmark
        if run.avg_hr is not None
    ]
    distances = [
        float(run.distance_km)
        for run, _ in benchmark
        if run.distance_km is not None
    ]

    paces = []

    if show_pace:
        for run, _ in benchmark:
            pace = _equivalent_pace(run)

            if pace is not None:
                paces.append(pace)

    hr_low = _percentile(heart_rates, 0.25)
    hr_high = _percentile(heart_rates, 0.75)
    hr_typical = (
        statistics.median(heart_rates)
        if heart_rates
        else None
    )
    pace_low = _percentile(paces, 0.25)
    pace_high = _percentile(paces, 0.75)
    typical_distance = (
        statistics.median(distances)
        if distances
        else None
    )
    confidence = _confidence(len(scored))

    if confidence >= 0.80:
        strength = "Strong personal pattern"
    elif confidence >= 0.55:
        strength = "Useful emerging pattern"
    else:
        strength = "Early pattern"

    if show_pace:
        summary = (
            f"{strength}, learned from {len(scored)} comparable runs "
            f"and the best {len(benchmark)} adjusted-efficiency examples."
        )
    else:
        summary = (
            f"{strength}, learned from {len(scored)} recognised sessions. "
            "Rep-level workout structure will refine this blueprint later."
        )

    return BlueprintCategory(
        key=key,
        label=label,
        coach=coach,
        icon=icon,
        sample_size=len(scored),
        benchmark_size=len(benchmark),
        confidence=round(confidence, 4),
        hr_low=(
            int(round(hr_low))
            if hr_low is not None
            else None
        ),
        hr_high=(
            int(round(hr_high))
            if hr_high is not None
            else None
        ),
        hr_typical=(
            int(round(hr_typical))
            if hr_typical is not None
            else None
        ),
        pace_low_s_per_km=(
            round(pace_low, 1)
            if pace_low is not None
            else None
        ),
        pace_high_s_per_km=(
            round(pace_high, 1)
            if pace_high is not None
            else None
        ),
        typical_distance_km=(
            round(typical_distance, 1)
            if typical_distance is not None
            else None
        ),
        show_pace=show_pace,
        source="Athlete history",
        summary=summary,
    )


def build_training_blueprint(
    runs: Iterable[RunProfile],
    *,
    athlete_id: int,
) -> TrainingBlueprint:
    definitions = (
        (
            "recovery",
            "Recovery",
            "Easy Coach",
            "😊",
            True,
        ),
        (
            "easy",
            "Easy",
            "Easy Coach",
            "😊",
            True,
        ),
        (
            "long_easy",
            "Long Easy",
            "Easy Coach",
            "😊",
            True,
        ),
        (
            "threshold",
            "Threshold Development",
            "Threshold Coach",
            "❤️",
            False,
        ),
        (
            "vo2",
            "VO₂ Development",
            "Speed Coach",
            "⚡",
            False,
        ),
        (
            "speed",
            "Speed Development",
            "Speed Coach",
            "⚡",
            False,
        ),
    )

    grouped = {
        key: []
        for key, *_ in definitions
    }

    for run in runs:
        key = _session_type(run)

        if key in grouped:
            grouped[key].append(run)

    categories = tuple(
        _build_category(
            key=key,
            label=label,
            coach=coach,
            icon=icon,
            runs=grouped[key],
            show_pace=show_pace,
        )
        for (
            key,
            label,
            coach,
            icon,
            show_pace,
        ) in definitions
    )

    available = [
        category
        for category in categories
        if category.sample_size >= 4
    ]
    overall_confidence = (
        statistics.fmean(
            category.confidence
            for category in available
        )
        if available
        else 0.0
    )

    if len(available) >= 5:
        headline = "Your coach blueprints are well developed"
    elif len(available) >= 3:
        headline = "Your coach blueprints are taking shape"
    else:
        headline = "Your coaches are still learning your patterns"

    summary = (
        f"{len(available)} of {len(categories)} runner-friendly session "
        "types have enough history to show a personal pattern. Easy-run "
        "blueprints include pace; development workouts remain HR and "
        "distance-led until rep-level structure is connected."
    )

    return TrainingBlueprint(
        athlete_id=athlete_id,
        categories=categories,
        available_category_count=len(available),
        overall_confidence=round(
            overall_confidence,
            4,
        ),
        headline=headline,
        summary=summary,
        limitations=(
            "Blueprints describe historical patterns rather than prescribe "
            "medical or physiological limits.",
            "Manual laboratory or coach-tested thresholds remain the active "
            "physiological boundaries when selected.",
            "Threshold, VO₂ and speed activity-average pace is deliberately "
            "hidden because recoveries distort it.",
            "Workout DNA will later add rep distance, rep pace and recovery "
            "structure to development blueprints.",
        ),
    )

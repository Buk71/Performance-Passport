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
from datetime import date, datetime
import json
import math
import statistics
from typing import Any, Iterable

from core.coaching import (
    RunProfile,
    equivalent_performance,
    get_athlete_sport_roles,
)
from core.database import get_connection


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
    rep_distance_typical_km: float | None = None
    rep_distance_low_km: float | None = None
    rep_distance_high_km: float | None = None
    rep_pace_typical_s_per_km: float | None = None
    rep_pace_low_s_per_km: float | None = None
    rep_pace_high_s_per_km: float | None = None
    recovery_typical_s: float | None = None
    rep_count_typical: float | None = None
    quality_volume_typical_km: float | None = None
    rep_metric_sample_size: int = 0
    recent_rep_count_typical: float | None = None
    recent_quality_volume_typical_km: float | None = None
    historical_rep_count_typical: float | None = None
    historical_quality_volume_typical_km: float | None = None
    comparable_distance_label: str | None = None
    current_profile_sample_size: int = 0
    historical_profile_sample_size: int = 0


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



def _median(values):
    return statistics.median(values) if values else None


def _phase_bucket(phase: dict) -> str | None:
    phase_type = str(phase.get("phase_type") or "").lower()

    try:
        distance = float(
            phase.get("average_rep_distance_km") or 0.0
        )
    except (TypeError, ValueError):
        distance = 0.0

    if phase_type == "short_intervals":
        return "speed"

    if phase_type == "long_intervals":
        return "speed" if distance and distance < 0.60 else "vo2"

    return None


def _distance_family(distance_km: float) -> tuple[str, float]:
    """
    Canonical rep families used for comparable-session learning.
    Tolerances are deliberately broad enough for GPS/lap drift.
    """
    families = (
        ("200m", 0.200),
        ("300m", 0.300),
        ("400m", 0.400),
        ("500m", 0.500),
        ("600m", 0.600),
        ("800m", 0.800),
        ("1km", 1.000),
        ("1200m", 1.200),
        ("1 mile", 1.609344),
    )

    label, target = min(
        families,
        key=lambda item: abs(distance_km - item[1]),
    )

    tolerance = max(0.06, target * 0.10)

    if abs(distance_km - target) <= tolerance:
        return label, target

    if distance_km < 1.0:
        metres = int(round(distance_km * 1000 / 50) * 50)
        return f"{metres}m", distance_km

    return f"{distance_km:.2f}km", distance_km


def _safe_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _load_rep_level_blueprints(
    athlete_id: int,
) -> dict[str, dict]:
    """
    Learn Speed Coach from comparable sessions, not one blended history.

    Priority:
      1. same rep-distance family + recent sessions
      2. same rep-distance family + broader history
      3. broader trusted Speed/VO2 history

    Each workout phase is treated as a session-level observation, so 20 x 400m
    is recognised as a materially different training dose from 10 x 400m.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            activity_date,
            phase_json,
            recognition_confidence,
            phase_confidence
        FROM workout_library
        WHERE athlete_id = ?
          AND recognition_confidence >= 0.65
          AND phase_confidence >= 0.70
        ORDER BY activity_date DESC, id DESC
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    buckets = {"speed": [], "vo2": []}

    for activity_date, phase_json, recognition_confidence, phase_confidence in rows:
        try:
            phases = json.loads(phase_json or "[]")
        except (TypeError, json.JSONDecodeError):
            continue

        if not isinstance(phases, list):
            continue

        for phase in phases:
            if not isinstance(phase, dict):
                continue

            bucket = _phase_bucket(phase)
            if bucket not in buckets:
                continue

            def number(key):
                try:
                    value = phase.get(key)
                    return float(value) if value is not None else None
                except (TypeError, ValueError):
                    return None

            pace = number("pace_s_per_km")
            rep_distance = number("average_rep_distance_km")
            reps = number("rep_count")
            total_distance = number("distance_km")
            recovery = number("recovery_duration_s")

            if (
                pace is None
                or not math.isfinite(pace)
                or not (150.0 <= pace <= 480.0)
            ):
                continue

            if (
                rep_distance is None
                or not (0.10 <= rep_distance <= 2.0)
            ):
                continue

            family_label, family_target = _distance_family(rep_distance)

            buckets[bucket].append(
                {
                    "date": _safe_date(activity_date),
                    "pace": pace,
                    "rep_distance": rep_distance,
                    "family_label": family_label,
                    "family_target": family_target,
                    "reps": reps,
                    "total_distance": total_distance,
                    "recovery": recovery,
                    "confidence": min(
                        float(recognition_confidence or 0.0),
                        float(phase_confidence or 0.0),
                    ),
                }
            )

    result = {}

    for bucket, items in buckets.items():
        if not items:
            continue

        dated = [item for item in items if item["date"] is not None]
        latest_date = max((item["date"] for item in dated), default=None)

        # Recent = last 120 days of this athlete's available workout history.
        # This is intentionally anchored to their latest activity, not today's
        # wall-clock date, so historical imports remain reproducible.
        if latest_date is not None:
            recent_cutoff = latest_date.fromordinal(
                latest_date.toordinal() - 120
            )
            recent_items = [
                item for item in items
                if item["date"] is not None and item["date"] >= recent_cutoff
            ]
        else:
            recent_items = list(items)

        # Determine the athlete's current rep family by frequency in recent
        # sessions, breaking ties in favour of the most recently used family.
        family_counts = {}
        family_latest = {}
        for item in recent_items:
            family = item["family_label"]
            family_counts[family] = family_counts.get(family, 0) + 1
            if item["date"] is not None:
                family_latest[family] = max(
                    family_latest.get(family, item["date"]),
                    item["date"],
                )

        if family_counts:
            current_family = max(
                family_counts,
                key=lambda family: (
                    family_counts[family],
                    family_latest.get(family, date.min),
                ),
            )
        else:
            current_family = items[0]["family_label"]

        comparable_recent = [
            item for item in recent_items
            if item["family_label"] == current_family
        ]
        comparable_history = [
            item for item in items
            if item["family_label"] == current_family
        ]

        # Need at least two comparable recent observations before calling it a
        # current pattern; otherwise fall back to the same-distance history.
        current_profile = (
            comparable_recent
            if len(comparable_recent) >= 2
            else comparable_history
        )

        if not current_profile:
            current_profile = recent_items or items

        def values(source, key, predicate=lambda value: True):
            output = []
            for item in source:
                value = item.get(key)
                if value is None:
                    continue
                if predicate(value):
                    output.append(value)
            return output

        current_paces = values(
            current_profile, "pace",
            lambda value: 150.0 <= value <= 480.0,
        )
        current_distances = values(
            current_profile, "rep_distance",
            lambda value: value > 0,
        )
        current_recoveries = values(
            current_profile, "recovery",
            lambda value: 10.0 <= value <= 600.0,
        )
        current_reps = values(
            current_profile, "reps",
            lambda value: value > 0,
        )
        current_volumes = values(
            current_profile, "total_distance",
            lambda value: value > 0,
        )

        historical_reps = values(
            comparable_history, "reps",
            lambda value: value > 0,
        )
        historical_volumes = values(
            comparable_history, "total_distance",
            lambda value: value > 0,
        )

        result[bucket] = {
            "sample_size": len(items),
            "benchmark_size": len(current_profile),
            "pace_low": _percentile(current_paces, 0.25),
            "pace_high": _percentile(current_paces, 0.75),
            "pace_typical": _median(current_paces),
            "distance_low": _percentile(current_distances, 0.25),
            "distance_high": _percentile(current_distances, 0.75),
            "distance_typical": _median(current_distances),
            "recovery_typical": _median(current_recoveries),
            "rep_count_typical": _median(current_reps),
            "quality_volume_typical": _median(current_volumes),
            "recent_rep_count_typical": _median(current_reps),
            "recent_quality_volume_typical": _median(current_volumes),
            "historical_rep_count_typical": _median(historical_reps),
            "historical_quality_volume_typical": _median(historical_volumes),
            "comparable_distance_label": current_family,
            "current_profile_sample_size": len(current_profile),
            "historical_profile_sample_size": len(comparable_history),
        }

    return result



def _apply_rep_metrics(
    category: BlueprintCategory,
    metrics: dict | None,
) -> BlueprintCategory:
    if not metrics:
        return category

    family = metrics.get("comparable_distance_label") or "similar reps"
    current_n = int(metrics.get("current_profile_sample_size") or 0)

    return BlueprintCategory(
        key=category.key,
        label=category.label,
        coach=category.coach,
        icon=category.icon,
        sample_size=max(category.sample_size, int(metrics["sample_size"])),
        benchmark_size=max(category.benchmark_size, int(metrics["benchmark_size"])),
        confidence=max(category.confidence, _confidence(int(metrics["sample_size"]))),
        hr_low=category.hr_low,
        hr_high=category.hr_high,
        hr_typical=category.hr_typical,
        pace_low_s_per_km=category.pace_low_s_per_km,
        pace_high_s_per_km=category.pace_high_s_per_km,
        typical_distance_km=category.typical_distance_km,
        show_pace=category.show_pace,
        source="Workout DNA · recent comparable sessions",
        summary=(
            f"Current {family} pattern learned from {current_n} comparable "
            "session blocks. Rep pace, session volume and recovery are compared "
            "with like-for-like history before broader Speed Coach evidence."
        ),
        rep_distance_typical_km=metrics["distance_typical"],
        rep_distance_low_km=metrics["distance_low"],
        rep_distance_high_km=metrics["distance_high"],
        rep_pace_typical_s_per_km=metrics["pace_typical"],
        rep_pace_low_s_per_km=metrics["pace_low"],
        rep_pace_high_s_per_km=metrics["pace_high"],
        recovery_typical_s=metrics["recovery_typical"],
        rep_count_typical=metrics["rep_count_typical"],
        quality_volume_typical_km=metrics["quality_volume_typical"],
        rep_metric_sample_size=int(metrics["sample_size"]),
        recent_rep_count_typical=metrics.get(
            "recent_rep_count_typical",
            metrics.get("rep_count_typical"),
        ),
        recent_quality_volume_typical_km=metrics.get(
            "recent_quality_volume_typical",
            metrics.get("quality_volume_typical"),
        ),
        historical_rep_count_typical=metrics.get(
            "historical_rep_count_typical",
            metrics.get("rep_count_typical"),
        ),
        historical_quality_volume_typical_km=metrics.get(
            "historical_quality_volume_typical",
            metrics.get("quality_volume_typical"),
        ),
        comparable_distance_label=family,
        current_profile_sample_size=(
            current_n
            or int(metrics.get("benchmark_size") or 0)
        ),
        historical_profile_sample_size=int(
            metrics.get("historical_profile_sample_size")
            or metrics.get("sample_size")
            or 0
        ),
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

    rep_blueprints = _load_rep_level_blueprints(athlete_id)

    categories = tuple(
        _apply_rep_metrics(
            category,
            rep_blueprints.get(category.key),
        )
        if category.key in {"vo2", "speed"}
        else category
        for category in categories
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
        "blueprints use aerobic efficiency; Speed Coach now uses trusted "
        "rep-level pace, distance and recovery evidence."
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
            "Activity-average pace remains hidden for development workouts "
            "because warm-up and recoveries distort it.",
            "For short speed/VO₂ work, activity-average HR is supporting "
            "context only because heart rate lags short repetitions.",
            "Speed Coach prioritises rep distance, rep pace, recovery and "
            "quality volume from trusted Workout DNA.",
        ),
    )

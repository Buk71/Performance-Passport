"""
Performance Passport Learning Engine v1.

Purpose
-------
Learn athlete-specific associations from REAL historical training.

This first version is deliberately observational. It asks:

    "After high-confidence workouts of this type, did the athlete's subsequent
    quality-session execution tend to improve, stay similar, or decline?"

It does NOT claim causation and it does NOT yet alter prescriptions. That comes
only after the learned patterns have been inspected and trusted.

Data quality rules
------------------
Only workout-library records with:
- a real decoded phase structure;
- phase confidence >= 0.70;
- recognition confidence >= 0.65;
- a real execution score

are allowed into v1 response learning.

Response window
---------------
For each trusted workout, compare the athlete's average trusted workout
execution in the 21 days BEFORE the workout with the 21 days AFTER it.

The trigger workout itself is excluded.

This is intentionally local: it reduces distortion from long-term fitness
changes, decoder changes and different eras of the athlete's history.

Race links are supporting evidence only. A workout-to-race link increases
confidence that the workout belongs to meaningful race preparation, but v1
does not claim that workout caused the race result.

Every conclusion remains athlete-specific.
Evidence before conclusions.
Correlation is not causation.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import math
import statistics
from collections import Counter, defaultdict
from typing import Any

from core.database import get_connection


WINDOW_DAYS = 21
MIN_PHASE_CONFIDENCE = 0.70
MIN_RECOGNITION_CONFIDENCE = 0.65
MIN_WINDOW_SAMPLES = 2
POSITIVE_DELTA_POINTS = 1.0


PHASE_ALIASES = {
    "continuous_threshold": "threshold",
    "long_threshold": "threshold",
    "sustained_quality": "threshold",
    "intervals": "long_intervals",
    "mile_repetitions": "long_intervals",
    "short_interval": "short_intervals",
    "short_reps": "short_intervals",
}


@dataclass(frozen=True)
class LearningObservation:
    workout_id: int
    activity_id: int
    activity_date: str
    activity_title: str
    family: str
    workout_signature: str

    execution_score: float
    phase_confidence: float
    recognition_confidence: float

    pre_execution_avg: float | None
    post_execution_avg: float | None
    response_delta: float | None
    response_direction: str

    pre_sample_count: int
    post_sample_count: int

    race_link_count: int
    best_race_link_confidence: float | None


@dataclass(frozen=True)
class LearnedPattern:
    family: str
    family_label: str

    trusted_session_count: int
    response_observation_count: int
    pure_session_count: int
    mixed_session_count: int

    average_trigger_execution: float
    average_response_delta: float | None
    median_response_delta: float | None
    positive_response_rate: float | None

    race_link_count: int
    best_race_link_confidence: float | None

    best_associated_signature: str | None
    best_signature_average_delta: float | None
    best_signature_observations: int

    confidence: float
    confidence_label: str
    direction: str
    headline: str
    explanation: str


@dataclass(frozen=True)
class AthleteLearningProfile:
    athlete_id: int
    trusted_workout_count: int
    learned_pattern_count: int
    patterns: tuple[LearnedPattern, ...]
    strongest_association: str | None
    summary: str
    limitations: tuple[str, ...]
    model_version: int = 1


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _date(value: Any) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _canonical_phase_type(value: Any) -> str:
    phase_type = str(value or "").strip().lower()
    return PHASE_ALIASES.get(phase_type, phase_type)


def _phase_family(phases: list[dict[str, Any]]) -> str | None:
    types = {
        _canonical_phase_type(phase.get("phase_type"))
        for phase in phases
    }

    has_threshold = "threshold" in types
    has_short = "short_intervals" in types
    has_long = "long_intervals" in types
    has_strides = "strides" in types

    if has_threshold and has_short:
        return "mixed_quality"

    if has_threshold:
        return "threshold"

    if has_short:
        return "short_intervals"

    if has_long:
        return "long_intervals"

    if has_strides:
        return "strides"

    return None


def _family_components(phases: list[dict[str, Any]]) -> set[str]:
    types = {
        _canonical_phase_type(phase.get("phase_type"))
        for phase in phases
    }

    components = set()

    if "threshold" in types:
        components.add("threshold")

    if "short_intervals" in types:
        components.add("short_intervals")

    if "long_intervals" in types:
        components.add("long_intervals")

    if "strides" in types:
        components.add("strides")

    return components


def _is_pure_family(
    family: str,
    components: set[str],
) -> bool:
    return components == {family}


def _family_label(family: str) -> str:
    return {
        "threshold": "Threshold",
        "short_intervals": "Short Intervals / VO₂",
        "long_intervals": "Long Intervals",
        "strides": "Strides / Speed",
        "mixed_quality": "Mixed Quality",
    }.get(family, family.replace("_", " ").title())


def _trusted_rows(
    athlete_id: int,
) -> list[dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            wl.id,
            wl.activity_id,
            wl.activity_date,
            COALESCE(a.title, wl.workout_signature),
            wl.workout_signature,
            wl.phase_json,
            wl.execution_score,
            wl.recognition_confidence,
            wl.phase_confidence
        FROM workout_library wl
        LEFT JOIN activities a
            ON a.id = wl.activity_id
        WHERE wl.athlete_id = ?
          AND wl.execution_score IS NOT NULL
          AND wl.phase_confidence >= ?
          AND wl.recognition_confidence >= ?
        ORDER BY wl.activity_date, wl.id
        """,
        (
            athlete_id,
            MIN_PHASE_CONFIDENCE,
            MIN_RECOGNITION_CONFIDENCE,
        ),
    )
    rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            workout_id,
            COUNT(*),
            MAX(link_confidence)
        FROM workout_race_links
        GROUP BY workout_id
        """
    )
    race_support = {
        row[0]: (
            int(row[1] or 0),
            _safe_float(row[2]),
        )
        for row in cursor.fetchall()
    }

    conn.close()

    trusted = []

    for row in rows:
        try:
            phases = json.loads(row[5] or "[]")
        except (TypeError, json.JSONDecodeError):
            phases = []

        if not isinstance(phases, list) or not phases:
            continue

        family = _phase_family(phases)
        components = _family_components(phases)

        if family is None:
            continue

        workout_date = _date(row[2])
        execution = _safe_float(row[6])
        phase_confidence = _safe_float(row[8])
        recognition_confidence = _safe_float(row[7])

        if (
            workout_date is None
            or execution is None
            or phase_confidence is None
            or recognition_confidence is None
        ):
            continue

        race_count, race_conf = race_support.get(
            row[0],
            (0, None),
        )

        trusted.append(
            {
                "workout_id": int(row[0]),
                "activity_id": int(row[1]),
                "activity_date": workout_date,
                "activity_date_text": str(row[2])[:10],
                "activity_title": str(row[3] or row[4] or "Workout"),
                "workout_signature": str(row[4] or "workout"),
                "family": family,
                "components": components,
                "execution_score": execution,
                "phase_confidence": phase_confidence,
                "recognition_confidence": recognition_confidence,
                "race_link_count": race_count,
                "race_link_confidence": race_conf,
            }
        )

    return trusted


def _window_execution(
    rows: list[dict[str, Any]],
    *,
    trigger: dict[str, Any],
    before: bool,
) -> list[float]:
    trigger_date = trigger["activity_date"]
    values = []

    for item in rows:
        if item["workout_id"] == trigger["workout_id"]:
            continue

        delta_days = (
            item["activity_date"] - trigger_date
        ).days

        if before:
            in_window = -WINDOW_DAYS <= delta_days < 0
        else:
            in_window = 0 < delta_days <= WINDOW_DAYS

        if in_window:
            values.append(item["execution_score"])

    return values


def _response_direction(delta: float | None) -> str:
    if delta is None:
        return "insufficient"

    if delta >= POSITIVE_DELTA_POINTS:
        return "positive"

    if delta <= -POSITIVE_DELTA_POINTS:
        return "weaker"

    return "stable"


def build_learning_observations(
    athlete_id: int,
) -> tuple[LearningObservation, ...]:
    rows = _trusted_rows(athlete_id)
    observations = []

    for trigger in rows:
        pre_values = _window_execution(
            rows,
            trigger=trigger,
            before=True,
        )
        post_values = _window_execution(
            rows,
            trigger=trigger,
            before=False,
        )

        pre_avg = (
            statistics.fmean(pre_values)
            if len(pre_values) >= MIN_WINDOW_SAMPLES
            else None
        )
        post_avg = (
            statistics.fmean(post_values)
            if len(post_values) >= MIN_WINDOW_SAMPLES
            else None
        )

        delta = (
            post_avg - pre_avg
            if pre_avg is not None and post_avg is not None
            else None
        )

        observations.append(
            LearningObservation(
                workout_id=trigger["workout_id"],
                activity_id=trigger["activity_id"],
                activity_date=trigger["activity_date_text"],
                activity_title=trigger["activity_title"],
                family=trigger["family"],
                workout_signature=trigger["workout_signature"],
                execution_score=round(
                    trigger["execution_score"],
                    2,
                ),
                phase_confidence=round(
                    trigger["phase_confidence"],
                    4,
                ),
                recognition_confidence=round(
                    trigger["recognition_confidence"],
                    4,
                ),
                pre_execution_avg=(
                    round(pre_avg, 2)
                    if pre_avg is not None
                    else None
                ),
                post_execution_avg=(
                    round(post_avg, 2)
                    if post_avg is not None
                    else None
                ),
                response_delta=(
                    round(delta, 2)
                    if delta is not None
                    else None
                ),
                response_direction=_response_direction(
                    delta
                ),
                pre_sample_count=len(pre_values),
                post_sample_count=len(post_values),
                race_link_count=trigger["race_link_count"],
                best_race_link_confidence=(
                    round(
                        trigger["race_link_confidence"],
                        4,
                    )
                    if trigger["race_link_confidence"] is not None
                    else None
                ),
            )
        )

    return tuple(observations)


def _best_signature(
    observations: list[LearningObservation],
) -> tuple[str | None, float | None, int]:
    grouped = defaultdict(list)

    for item in observations:
        if item.response_delta is None:
            continue

        grouped[item.workout_signature].append(
            item.response_delta
        )

    candidates = []

    for signature, deltas in grouped.items():
        if len(deltas) < 2:
            continue

        candidates.append(
            (
                statistics.fmean(deltas),
                len(deltas),
                signature,
            )
        )

    if not candidates:
        return None, None, 0

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    average_delta, count, signature = candidates[0]

    return (
        signature,
        round(average_delta, 2),
        count,
    )


def _pattern_confidence(
    *,
    trusted_count: int,
    response_count: int,
    race_link_count: int,
) -> tuple[float, str]:
    response_depth = min(
        response_count / 12.0,
        1.0,
    )
    trusted_depth = min(
        trusted_count / 20.0,
        1.0,
    )
    race_support = min(
        race_link_count / 5.0,
        1.0,
    )

    confidence = (
        response_depth * 0.60
        + trusted_depth * 0.30
        + race_support * 0.10
    )
    confidence = max(
        0.10,
        min(confidence, 0.95),
    )

    if confidence >= 0.82:
        label = "High"
    elif confidence >= 0.66:
        label = "Good"
    elif confidence >= 0.45:
        label = "Developing"
    else:
        label = "Early evidence"

    return round(confidence, 4), label


def _pattern_direction(
    average_delta: float | None,
    positive_rate: float | None,
    response_count: int,
) -> str:
    if (
        average_delta is None
        or positive_rate is None
        or response_count < 4
    ):
        return "building"

    if average_delta >= 1.5 and positive_rate >= 0.60:
        return "strong_positive"

    if average_delta >= 0.5 and positive_rate >= 0.50:
        return "positive"

    if average_delta <= -1.5 and positive_rate <= 0.35:
        return "weaker"

    return "mixed"


def _pattern_language(
    *,
    family_label: str,
    direction: str,
    average_delta: float | None,
    response_count: int,
) -> tuple[str, str]:
    if response_count == 0 or average_delta is None:
        return (
            f"{family_label}: still learning",
            (
                "There are trusted sessions in the history, but not enough "
                "complete before/after response windows yet."
            ),
        )

    if direction == "strong_positive":
        return (
            f"{family_label} has one of the strongest positive associations.",
            (
                f"Across {response_count} usable historical response windows, "
                f"subsequent quality-session execution averaged "
                f"{average_delta:+.1f} points versus the preceding 21 days."
            ),
        )

    if direction == "positive":
        return (
            f"{family_label} is showing a positive historical association.",
            (
                f"Across {response_count} usable response windows, subsequent "
                f"quality-session execution averaged {average_delta:+.1f} "
                "points versus the preceding 21 days."
            ),
        )

    if direction == "weaker":
        return (
            f"{family_label} needs more careful interpretation.",
            (
                f"Across {response_count} usable response windows, subsequent "
                f"quality-session execution averaged {average_delta:+.1f} "
                "points versus the preceding 21 days. This is an association, "
                "not proof that the workouts caused the change."
            ),
        )

    return (
        f"{family_label} has a mixed historical response.",
        (
            f"Across {response_count} usable response windows, subsequent "
            f"quality-session execution averaged {average_delta:+.1f} points. "
            "The evidence is not consistent enough to call this a clear "
            "positive or negative response."
        ),
    )


def _build_pattern(
    family: str,
    observations: list[LearningObservation],
    *,
    history_total: int | None = None,
    pure_count: int | None = None,
    mixed_count: int | None = None,
) -> LearnedPattern:
    response_observations = [
        item
        for item in observations
        if item.response_delta is not None
    ]
    deltas = [
        item.response_delta
        for item in response_observations
        if item.response_delta is not None
    ]

    average_delta = (
        statistics.fmean(deltas)
        if deltas
        else None
    )
    median_delta = (
        statistics.median(deltas)
        if deltas
        else None
    )
    positive_rate = (
        sum(
            item.response_direction == "positive"
            for item in response_observations
        )
        / len(response_observations)
        if response_observations
        else None
    )

    race_link_count = sum(
        item.race_link_count
        for item in observations
    )
    race_confs = [
        item.best_race_link_confidence
        for item in observations
        if item.best_race_link_confidence is not None
    ]
    best_race_conf = (
        max(race_confs)
        if race_confs
        else None
    )

    best_signature, best_signature_delta, best_signature_n = (
        _best_signature(observations)
    )

    confidence, confidence_label = _pattern_confidence(
        trusted_count=len(observations),
        response_count=len(response_observations),
        race_link_count=race_link_count,
    )

    direction = _pattern_direction(
        average_delta,
        positive_rate,
        len(response_observations),
    )
    family_label = _family_label(family)
    headline, explanation = _pattern_language(
        family_label=family_label,
        direction=direction,
        average_delta=average_delta,
        response_count=len(response_observations),
    )

    return LearnedPattern(
        family=family,
        family_label=family_label,
        trusted_session_count=(
            history_total
            if history_total is not None
            else len(observations)
        ),
        response_observation_count=len(
            response_observations
        ),
        pure_session_count=(
            pure_count
            if pure_count is not None
            else len(observations)
        ),
        mixed_session_count=(
            mixed_count
            if mixed_count is not None
            else 0
        ),
        average_trigger_execution=round(
            statistics.fmean(
                item.execution_score
                for item in observations
            ),
            2,
        ),
        average_response_delta=(
            round(average_delta, 2)
            if average_delta is not None
            else None
        ),
        median_response_delta=(
            round(median_delta, 2)
            if median_delta is not None
            else None
        ),
        positive_response_rate=(
            round(positive_rate, 4)
            if positive_rate is not None
            else None
        ),
        race_link_count=race_link_count,
        best_race_link_confidence=(
            round(best_race_conf, 4)
            if best_race_conf is not None
            else None
        ),
        best_associated_signature=best_signature,
        best_signature_average_delta=best_signature_delta,
        best_signature_observations=best_signature_n,
        confidence=confidence,
        confidence_label=confidence_label,
        direction=direction,
        headline=headline,
        explanation=explanation,
    )


def _history_counts(
    athlete_id: int,
) -> dict[str, tuple[int, int, int]]:
    """
    Return family -> (total participating, pure, mixed).

    A mixed threshold + short-interval session contributes to the historical
    count of BOTH threshold and short intervals. This prevents useful training
    history from disappearing into a separate bucket.
    """
    rows = _trusted_rows(athlete_id)
    counts = defaultdict(lambda: [0, 0, 0])

    for row in rows:
        components = row["components"]

        for family in components:
            counts[family][0] += 1

            if _is_pure_family(family, components):
                counts[family][1] += 1
            else:
                counts[family][2] += 1

    return {
        family: tuple(values)
        for family, values in counts.items()
    }


def build_learning_profile(
    athlete_id: int,
) -> AthleteLearningProfile:
    observations = build_learning_observations(
        athlete_id
    )

    grouped = defaultdict(list)

    trusted_rows = {
        row["workout_id"]: row
        for row in _trusted_rows(athlete_id)
    }

    for observation in observations:
        row = trusted_rows.get(observation.workout_id)

        if row is None:
            grouped[observation.family].append(
                observation
            )
            continue

        components = row["components"]

        for family in components:
            grouped[family].append(
                observation
            )

    history_counts = _history_counts(athlete_id)

    patterns = []

    for family, counts in history_counts.items():
        total, pure_count, mixed_count = counts
        patterns.append(
            _build_pattern(
                family,
                grouped.get(family, []),
                history_total=total,
                pure_count=pure_count,
                mixed_count=mixed_count,
            )
        )

    direction_order = {
        "strong_positive": 0,
        "positive": 1,
        "mixed": 2,
        "building": 3,
        "weaker": 4,
    }

    patterns.sort(
        key=lambda pattern: (
            direction_order.get(
                pattern.direction,
                9,
            ),
            -pattern.confidence,
            -pattern.response_observation_count,
        )
    )

    strongest = None

    positive_patterns = [
        pattern
        for pattern in patterns
        if pattern.direction in {
            "strong_positive",
            "positive",
        }
        and pattern.average_response_delta is not None
    ]

    if positive_patterns:
        strongest = max(
            positive_patterns,
            key=lambda pattern: (
                pattern.average_response_delta,
                pattern.confidence,
            ),
        ).family_label

    if not observations:
        summary = (
            "PP does not yet have enough high-confidence decoded workout "
            "history to learn athlete-specific response patterns."
        )
    elif strongest:
        summary = (
            f"The clearest positive historical association currently appears "
            f"around {strongest.lower()} sessions. PP is observing this pattern "
            "only; it is not yet changing prescriptions from it."
        )
    else:
        summary = (
            "PP has begun tracking real before/after workout responses, but "
            "no workout family has a strong enough positive association yet."
        )

    limitations = (
        (
            "v1 measures association using quality-workout execution in the "
            "21 days before and after each trusted workout."
        ),
        (
            "A positive association does not prove the workout caused the "
            "later improvement; training sequences, recovery and racing all "
            "contribute."
        ),
        (
            "Only high-confidence phase-decoded workouts are included. This "
            "deliberately excludes many older or ambiguous workout records."
        ),
        (
            "The Learning Engine is observation-only in v0.18.0. It will not "
            "change Session Designer prescriptions until the learned patterns "
            "have been reviewed."
        ),
    )

    return AthleteLearningProfile(
        athlete_id=athlete_id,
        trusted_workout_count=len(observations),
        learned_pattern_count=len(patterns),
        patterns=tuple(patterns),
        strongest_association=strongest,
        summary=summary,
        limitations=limitations,
    )

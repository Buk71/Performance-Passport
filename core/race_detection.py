"""
Shared race and race-quality effort classification.

Both Session Intelligence and Race Coach use this scoring service so that
diagnostics and coaching agree about what constitutes race evidence.
"""

from __future__ import annotations

from dataclasses import dataclass


STANDARD_DISTANCES_KM = (
    1.609344,
    3.0,
    5.0,
    8.04672,
    10.0,
    16.09344,
    21.0975,
    42.195,
)

RACE_WORDS = (
    "race",
    "parkrun",
    "5k",
    "10k",
    "10 km",
    "10 mile",
    "half marathon",
    "marathon",
    "cross country",
    "xc",
    "handicap",
    "road race",
    "trail race",
    "fell race",
    "time trial",
)

TRAINING_WORDS = (
    "interval",
    "intervals",
    "threshold",
    "tempo",
    "reps",
    "fartlek",
    "easy",
    "recovery",
    "warm up",
    "warm-up",
    "cool down",
    "cool-down",
)


@dataclass(frozen=True)
class RaceSignals:
    total: float
    classification: str
    confidence: float
    distance: float
    continuity: float
    effort: float
    official: float
    title: float
    training_penalty: float
    matched_distance_km: float | None
    moving_ratio: float | None
    reasons: tuple[str, ...]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _title_signal(title: str) -> float:
    normalised = (title or "").strip().lower()
    matches = sum(word in normalised for word in RACE_WORDS)

    if matches >= 2:
        return 1.0
    if matches == 1:
        return 0.75
    return 0.0


def _training_penalty(title: str) -> float:
    normalised = (title or "").strip().lower()
    return 1.0 if any(word in normalised for word in TRAINING_WORDS) else 0.0


def _distance_signal(distance_km: float | None) -> tuple[float, float | None]:
    if distance_km is None or distance_km <= 0:
        return 0.0, None

    closest = min(
        STANDARD_DISTANCES_KM,
        key=lambda standard: abs(standard - distance_km),
    )
    error = abs(distance_km - closest) / closest

    if error <= 0.012:
        return 1.0, closest
    if error <= 0.025:
        return 0.90, closest
    if error <= 0.05:
        return 0.68, closest
    if error <= 0.08:
        return 0.42, closest
    return 0.0, None


def _continuity_signal(
    moving_time_s: float | None,
    elapsed_time_s: float | None,
) -> tuple[float, float | None]:
    if (
        moving_time_s is None
        or elapsed_time_s is None
        or elapsed_time_s <= 0
    ):
        return 0.45, None

    ratio = _clamp(moving_time_s / elapsed_time_s)

    if ratio >= 0.995:
        return 1.0, ratio
    if ratio >= 0.985:
        return 0.90, ratio
    if ratio >= 0.97:
        return 0.72, ratio
    if ratio >= 0.94:
        return 0.42, ratio
    return 0.08, ratio


def _effort_signal(
    avg_hr: float | None,
    max_hr: float | None,
    athlete_lt2_hr: float | None,
    athlete_max_hr: float | None,
) -> float:
    """
    Estimate race-like effort from available heart-rate evidence.

    Maximum HR is weighted more strongly than average HR because:
    - short races can have a lower average due to warm-up lag or sensor lag;
    - device ecosystems may summarise average HR differently;
    - a peak very close to the athlete's known maximum is strong evidence
      of genuine racing even when average HR sits below LT2.
    """
    avg_signal = None
    max_signal = None

    if avg_hr and athlete_lt2_hr and athlete_lt2_hr > 0:
        ratio = avg_hr / athlete_lt2_hr
        avg_signal = _clamp((ratio - 0.84) / 0.20)

    if max_hr and athlete_max_hr and athlete_max_hr > 0:
        ratio = max_hr / athlete_max_hr
        max_signal = _clamp((ratio - 0.80) / 0.19)

    if avg_signal is None and max_signal is None:
        return 0.35

    if avg_signal is None:
        return max_signal

    if max_signal is None:
        return avg_signal

    # Peak HR is the stronger behavioural race signal.
    return avg_signal * 0.30 + max_signal * 0.70


def score_race_evidence(
    *,
    title: str,
    distance_km: float | None,
    moving_time_s: float | None,
    elapsed_time_s: float | None,
    avg_hr: float | None,
    max_hr: float | None,
    athlete_lt2_hr: float | None,
    athlete_max_hr: float | None,
    official_race_name: str | None = None,
    official_distance_m: float | None = None,
    official_time_s: float | None = None,
    officially_measured: bool = False,
) -> RaceSignals:
    distance, matched_distance = _distance_signal(distance_km)
    continuity, moving_ratio = _continuity_signal(
        moving_time_s,
        elapsed_time_s,
    )
    effort = _effort_signal(
        avg_hr,
        max_hr,
        athlete_lt2_hr,
        athlete_max_hr,
    )
    title_signal = _title_signal(title)
    training_penalty = _training_penalty(title)

    official = 0.0
    if official_race_name:
        official += 0.35
    if official_distance_m:
        official += 0.25
    if official_time_s:
        official += 0.25
    if officially_measured:
        official += 0.15
    official = _clamp(official)

    total = (
        distance * 30.0
        + continuity * 25.0
        + effort * 30.0
        + official * 12.0
        + title_signal * 12.0
        - training_penalty * 35.0
    )

    explicit_confirmation = official >= 0.35 or title_signal >= 0.75

    strong_behavioural_confirmation = (
        distance >= 0.90
        and continuity >= 0.90
        and effort >= 0.62
        and training_penalty == 0.0
    )

    if (
        strong_behavioural_confirmation
        and total >= 68.0
    ):
        classification = "confirmed_race"
    elif (
        total >= 70.0
        and distance >= 0.68
        and continuity >= 0.72
        and effort >= 0.55
    ):
        classification = "confirmed_race"
    elif (
        explicit_confirmation
        and total >= 55.0
        and distance >= 0.42
        and continuity >= 0.42
    ):
        classification = "confirmed_race"
    elif (
        total >= 58.0
        and distance >= 0.68
        and continuity >= 0.72
        and effort >= 0.45
    ):
        classification = "race_quality_effort"
    else:
        classification = "not_race"

    reasons = [
        f"Standard-distance evidence {distance:.0%}",
        f"Continuity evidence {continuity:.0%}",
        f"Effort evidence {effort:.0%}",
    ]

    if title_signal:
        reasons.append(f"Race-title evidence {title_signal:.0%}")
    if official:
        reasons.append(f"Official race metadata {official:.0%}")
    if training_penalty:
        reasons.append("Training-language penalty applied")

    return RaceSignals(
        total=total,
        classification=classification,
        confidence=_clamp(total / 100.0),
        distance=distance,
        continuity=continuity,
        effort=effort,
        official=official,
        title=title_signal,
        training_penalty=training_penalty,
        matched_distance_km=matched_distance,
        moving_ratio=moving_ratio,
        reasons=tuple(reasons),
    )

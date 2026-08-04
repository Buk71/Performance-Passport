"""
Personal Environment Profile.

This module learns conservative athlete-specific environmental response from
historical running profiles already loaded by the dashboard.

It focuses on comparable aerobic runs and estimates three relative effects:
- heat response;
- climbing response;
- trail/surface response.

The model is intentionally cautious:
- it uses median-like trimmed averages;
- it compares pace relative to heart rate;
- it requires minimum samples;
- personal coefficients are blended with generic forecasts rather than
  replacing them outright;
- insufficient evidence leaves the generic model unchanged.

This is a coaching model, not a physiological laboratory measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
from typing import Any, Iterable


@dataclass(frozen=True)
class PersonalEnvironmentProfile:
    athlete_id: int | None
    heat_multiplier: float
    hill_multiplier: float
    trail_multiplier: float
    heat_sample_size: int
    hill_sample_size: int
    trail_sample_size: int
    heat_confidence: float
    hill_confidence: float
    trail_confidence: float
    overall_confidence: float
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    model_version: int = 1


def _value(run: Any, name: str, default=None):
    return getattr(run, name, default)


def _safe_float(value, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _date_key(run: Any) -> str:
    return str(_value(run, "activity_date", "") or "")


def _is_probable_quality_title(title: str) -> bool:
    text = title.lower()
    excluded = (
        "race",
        "parkrun",
        "threshold",
        "tempo",
        "interval",
        "reps",
        "fartlek",
        "track",
        "vo2",
        "hill rep",
        "time trial",
    )
    return any(word in text for word in excluded)


def _is_trail(run: Any) -> bool:
    title = str(_value(run, "title", "") or "").lower()
    sport = str(_value(run, "sport_id", "") or "").lower()
    return (
        "trail" in title
        or "forest" in title
        or "off road" in title
        or "off-road" in title
        or "cross country" in title
        or "xc" in title
        or "trail" in sport
    )


def _efficiency(run: Any) -> float | None:
    """
    Pace per heart-beat proxy.

    Lower is better. We only use this for within-athlete comparisons.
    """
    distance_km = _safe_float(_value(run, "distance_km"))
    moving_time = _safe_float(_value(run, "moving_time_seconds"))
    avg_hr = _safe_float(_value(run, "avg_hr"))

    if (
        distance_km is None
        or moving_time is None
        or avg_hr is None
        or distance_km < 4.0
        or distance_km > 20.0
        or moving_time <= 0
        or avg_hr <= 80
    ):
        return None

    pace_s_per_km = moving_time / distance_km
    return pace_s_per_km / avg_hr


def _climbing_density(run: Any) -> float | None:
    distance_km = _safe_float(_value(run, "distance_km"))
    elevation_m = _safe_float(_value(run, "elevation_m"))

    if (
        distance_km is None
        or elevation_m is None
        or distance_km <= 0
        or elevation_m < 0
    ):
        return None

    return elevation_m / distance_km


def _trimmed_mean(values: list[float]) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) >= 8:
        trim = max(int(len(ordered) * 0.15), 1)
        ordered = ordered[trim:-trim]

    if not ordered:
        return None

    return statistics.fmean(ordered)


def _confidence(sample_size: int, target: int) -> float:
    if sample_size <= 0:
        return 0.0

    return min(sample_size / target, 1.0)


def _comparable_runs(runs: Iterable[Any]) -> list[Any]:
    usable = []

    for run in runs:
        title = str(_value(run, "title", "") or "")

        if _is_probable_quality_title(title):
            continue

        efficiency = _efficiency(run)

        if efficiency is None:
            continue

        usable.append(run)

    usable.sort(key=_date_key, reverse=True)
    return usable[:500]


def build_personal_environment_profile(
    runs: Iterable[Any],
    *,
    athlete_id: int | None = None,
) -> PersonalEnvironmentProfile:
    comparable = _comparable_runs(runs)
    reasons = []
    limitations = []

    cool_values = []
    warm_values = []
    flat_values = []
    hilly_values = []
    road_values = []
    trail_values = []

    for run in comparable:
        efficiency = _efficiency(run)

        if efficiency is None:
            continue

        temperature = _safe_float(
            _value(run, "temperature_c")
        )
        climbing_density = _climbing_density(run)
        trail = _is_trail(run)

        if temperature is not None:
            if 5 <= temperature <= 15:
                cool_values.append(efficiency)
            elif temperature >= 20:
                warm_values.append(efficiency)

        if climbing_density is not None:
            if climbing_density < 8:
                flat_values.append(efficiency)
            elif climbing_density >= 18:
                hilly_values.append(efficiency)

        if trail:
            trail_values.append(efficiency)
        else:
            road_values.append(efficiency)

    # Multipliers represent relative sensitivity versus the generic model.
    heat_multiplier = 1.0
    hill_multiplier = 1.0
    trail_multiplier = 1.0

    cool_eff = _trimmed_mean(cool_values)
    warm_eff = _trimmed_mean(warm_values)

    if (
        cool_eff is not None
        and warm_eff is not None
        and len(cool_values) >= 5
        and len(warm_values) >= 5
    ):
        observed_heat_cost = max(warm_eff / cool_eff - 1.0, 0.0)

        # Generic warm-vs-cool expectation is roughly 2%. Convert the
        # observed cost into a restrained multiplier.
        heat_multiplier = max(
            0.65,
            min(observed_heat_cost / 0.020, 1.60),
        )
        reasons.append(
            f"Heat response learned from {len(warm_values)} warm and "
            f"{len(cool_values)} cool comparable runs."
        )
    else:
        limitations.append(
            "Not enough comparable cool and warm runs to personalise heat."
        )

    flat_eff = _trimmed_mean(flat_values)
    hilly_eff = _trimmed_mean(hilly_values)

    if (
        flat_eff is not None
        and hilly_eff is not None
        and len(flat_values) >= 6
        and len(hilly_values) >= 4
    ):
        observed_hill_cost = max(hilly_eff / flat_eff - 1.0, 0.0)
        hill_multiplier = max(
            0.65,
            min(observed_hill_cost / 0.026, 1.60),
        )
        reasons.append(
            f"Hill response learned from {len(hilly_values)} hilly and "
            f"{len(flat_values)} flatter comparable runs."
        )
    else:
        limitations.append(
            "Not enough comparable flat and hilly runs to personalise hills."
        )

    road_eff = _trimmed_mean(road_values)
    trail_eff = _trimmed_mean(trail_values)

    if (
        road_eff is not None
        and trail_eff is not None
        and len(road_values) >= 8
        and len(trail_values) >= 4
    ):
        observed_trail_cost = max(trail_eff / road_eff - 1.0, 0.0)
        trail_multiplier = max(
            0.65,
            min(observed_trail_cost / 0.050, 1.60),
        )
        reasons.append(
            f"Trail response learned from {len(trail_values)} trail and "
            f"{len(road_values)} road comparable runs."
        )
    else:
        limitations.append(
            "Not enough comparable road and trail runs to personalise surface."
        )

    heat_confidence = _confidence(
        min(len(cool_values), len(warm_values)),
        12,
    )
    hill_confidence = _confidence(
        min(len(flat_values), len(hilly_values)),
        10,
    )
    trail_confidence = _confidence(
        min(len(road_values), len(trail_values)),
        10,
    )

    confidences = [
        heat_confidence,
        hill_confidence,
        trail_confidence,
    ]
    populated = [value for value in confidences if value > 0]
    overall_confidence = (
        statistics.fmean(populated)
        if populated
        else 0.0
    )

    if not reasons:
        reasons.append(
            "Generic environmental response retained while personal evidence "
            "continues to build."
        )

    return PersonalEnvironmentProfile(
        athlete_id=athlete_id,
        heat_multiplier=round(heat_multiplier, 4),
        hill_multiplier=round(hill_multiplier, 4),
        trail_multiplier=round(trail_multiplier, 4),
        heat_sample_size=min(len(cool_values), len(warm_values)),
        hill_sample_size=min(len(flat_values), len(hilly_values)),
        trail_sample_size=min(len(road_values), len(trail_values)),
        heat_confidence=round(heat_confidence, 4),
        hill_confidence=round(hill_confidence, 4),
        trail_confidence=round(trail_confidence, 4),
        overall_confidence=round(overall_confidence, 4),
        reasons=tuple(reasons),
        limitations=tuple(limitations),
    )


def environment_profile_to_dict(
    profile: PersonalEnvironmentProfile,
) -> dict[str, Any]:
    return {
        "athlete_id": profile.athlete_id,
        "heat_multiplier": profile.heat_multiplier,
        "hill_multiplier": profile.hill_multiplier,
        "trail_multiplier": profile.trail_multiplier,
        "heat_sample_size": profile.heat_sample_size,
        "hill_sample_size": profile.hill_sample_size,
        "trail_sample_size": profile.trail_sample_size,
        "heat_confidence": profile.heat_confidence,
        "hill_confidence": profile.hill_confidence,
        "trail_confidence": profile.trail_confidence,
        "overall_confidence": profile.overall_confidence,
        "reasons": list(profile.reasons),
        "limitations": list(profile.limitations),
        "model_version": profile.model_version,
    }

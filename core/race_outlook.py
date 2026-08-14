"""Interactive race-day translation of the existing ideal capability.

The active-goal prediction remains the fitness estimate. This module only
answers how user-selected race conditions may change the realised time. It
reuses the same transparent heat, humidity, climbing, wind and surface
allowances used elsewhere in Performance Passport.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from core.coaching import (
    calculate_dew_point,
    humidity_adjustment_seconds_per_km,
    temperature_adjustment_seconds_per_km,
    terrain_rating_from_climbing_density,
)
from core.home_predictions import HomePredictions


@dataclass(frozen=True)
class RaceConditions:
    temperature_c: float = 12.0
    humidity_percent: float = 70.0
    total_ascent_m: float = 0.0
    wind_speed_kmh: float = 5.0
    wind_exposure: str = "Mixed"
    surface: str = "Road"


@dataclass(frozen=True)
class RaceConditionFactor:
    key: str
    label: str
    context: str
    penalty_seconds_per_km: float
    total_seconds: float
    personalised: bool
    confidence: float
    evidence: str


@dataclass(frozen=True)
class InteractiveRaceOutlook:
    athlete_id: int
    available: bool
    goal_name: str
    distance_label: str
    distance_km: float | None
    target_seconds: float | None
    ideal_seconds: float | None
    ideal_low_seconds: float | None
    ideal_high_seconds: float | None
    selected_seconds: float | None
    selected_low_seconds: float | None
    selected_high_seconds: float | None
    selected_pace_s_per_km: float | None
    condition_cost_seconds: float | None
    condition_cost_percent: float | None
    target_gap_seconds: float | None
    target_probability: float | None
    confidence: float
    confidence_label: str
    headline: str
    summary: str
    conditions_summary: str
    factors: tuple[RaceConditionFactor, ...]
    limitations: tuple[str, ...]
    model_version: int = 1


def _distance_km(predictions: HomePredictions) -> float | None:
    mapping = {
        "5K": 5.0,
        "10K": 10.0,
        "5 miles": 8.04672,
        "10 miles": 16.09344,
        "Half marathon": 21.0975,
        "Marathon": 42.195,
    }
    return mapping.get(predictions.distance_label)


def _response(predictions: HomePredictions, key: str):
    return next(
        (item for item in predictions.environment_responses if item.key == key),
        None,
    )


def _personalised_scale(predictions: HomePredictions, key: str) -> tuple[float, float, bool, str]:
    response = _response(predictions, key)
    if response is None or response.confidence < 0.25:
        return 1.0, 0.35, False, "Generic model; personal evidence is still building"
    blend = min(response.confidence * 0.75, 0.75)
    scale = 1.0 * (1.0 - blend) + response.multiplier * blend
    return (
        scale,
        response.confidence,
        True,
        f"Personal response blended from {response.sample_size} comparable runs",
    )


def _goal_probability(
    *,
    central_seconds: float,
    low_seconds: float,
    high_seconds: float,
    target_seconds: float | None,
) -> float | None:
    if target_seconds is None or target_seconds <= 0:
        return None
    uncertainty = max((high_seconds - low_seconds) / 2.0, 10.0)
    z = (target_seconds - central_seconds) / uncertainty
    return max(0.02, min(1.0 / (1.0 + math.exp(-1.7 * z)), 0.98))


def _confidence_label(value: float) -> str:
    if value >= 0.75:
        return "Strong"
    if value >= 0.50:
        return "Moderate"
    return "Limited"


def _unavailable(predictions: HomePredictions) -> InteractiveRaceOutlook:
    return InteractiveRaceOutlook(
        athlete_id=predictions.athlete_id,
        available=False,
        goal_name=predictions.goal_name,
        distance_label=predictions.distance_label,
        distance_km=None,
        target_seconds=predictions.target_seconds,
        ideal_seconds=None,
        ideal_low_seconds=None,
        ideal_high_seconds=None,
        selected_seconds=None,
        selected_low_seconds=None,
        selected_high_seconds=None,
        selected_pace_s_per_km=None,
        condition_cost_seconds=None,
        condition_cost_percent=None,
        target_gap_seconds=None,
        target_probability=None,
        confidence=0.0,
        confidence_label="Limited",
        headline="Race Outlook is still building",
        summary="A supported distance capability is needed before race conditions can be explored.",
        conditions_summary="No selected forecast available",
        factors=(),
        limitations=("No usable active-goal capability was available.",),
    )


def build_interactive_race_outlook(
    predictions: HomePredictions,
    conditions: RaceConditions,
) -> InteractiveRaceOutlook:
    """Apply selected conditions to an existing ideal capability."""
    distance_km = _distance_km(predictions)
    if (
        not predictions.available
        or distance_km is None
        or predictions.central_seconds is None
    ):
        return _unavailable(predictions)

    temperature = max(-5.0, min(float(conditions.temperature_c), 40.0))
    humidity = max(10.0, min(float(conditions.humidity_percent), 100.0))
    ascent = max(0.0, float(conditions.total_ascent_m))
    wind = max(0.0, float(conditions.wind_speed_kmh))
    exposure = conditions.wind_exposure if conditions.wind_exposure in {"Sheltered", "Mixed", "Exposed"} else "Mixed"
    surface = conditions.surface if conditions.surface in {"Road", "Firm trail"} else "Road"

    dew_point = calculate_dew_point(temperature, humidity)
    generic_heat = (
        temperature_adjustment_seconds_per_km(temperature)
        + humidity_adjustment_seconds_per_km(temperature, dew_point)
    )
    heat_scale, heat_conf, heat_personal, heat_evidence = _personalised_scale(
        predictions, "heat"
    )
    heat_penalty = generic_heat * heat_scale

    climb_density = ascent / distance_km
    generic_hills = min(climb_density * 0.30, 15.0)
    hill_scale, hill_conf, hill_personal, hill_evidence = _personalised_scale(
        predictions, "hills"
    )
    hill_penalty = generic_hills * hill_scale

    exposure_scale = {"Sheltered": 0.25, "Mixed": 0.55, "Exposed": 1.0}[exposure]
    wind_penalty = min(max(wind - 10.0, 0.0) * 0.18, 8.0) * exposure_scale

    generic_surface = 6.0 if surface == "Firm trail" else 0.0
    trail_scale, trail_conf, trail_personal, trail_evidence = _personalised_scale(
        predictions, "trail"
    )
    surface_penalty = generic_surface * trail_scale

    factor_values = (
        (
            "heat",
            "Heat & humidity",
            f"{temperature:.0f}°C · {humidity:.0f}% humidity · {dew_point:.0f}°C dew point",
            heat_penalty,
            heat_personal,
            heat_conf,
            heat_evidence,
        ),
        (
            "hills",
            "Climbing",
            f"{ascent:.0f} m ascent · {terrain_rating_from_climbing_density(climb_density)}",
            hill_penalty,
            hill_personal,
            hill_conf,
            hill_evidence,
        ),
        (
            "wind",
            "Wind",
            f"{wind:.0f} km/h · {exposure.lower()} exposure",
            wind_penalty,
            False,
            0.45 if wind_penalty else 0.75,
            "Generic conservative allowance; direction and gusts are unknown",
        ),
        (
            "surface",
            "Surface",
            surface,
            surface_penalty,
            trail_personal if generic_surface else False,
            trail_conf if generic_surface else 0.90,
            trail_evidence if generic_surface else "Road baseline; no surface allowance",
        ),
    )
    ideal = float(predictions.central_seconds)
    ideal_low = float(predictions.low_seconds or ideal)
    ideal_high = float(predictions.high_seconds or ideal)
    raw_penalty_per_km = sum(item[3] for item in factor_values)
    # Match Recognition's safety rule: conditions must not manufacture an
    # implausible result or overwhelm the underlying capability estimate.
    ideal_pace = ideal / distance_km
    total_penalty_per_km = min(raw_penalty_per_km, ideal_pace * 0.18)
    safety_scale = (
        total_penalty_per_km / raw_penalty_per_km
        if raw_penalty_per_km > 0
        else 1.0
    )
    factors = tuple(
        RaceConditionFactor(
            key=key,
            label=label,
            context=context,
            penalty_seconds_per_km=round(penalty * safety_scale, 2),
            total_seconds=round(penalty * safety_scale * distance_km, 1),
            personalised=personalised,
            confidence=round(confidence, 4),
            evidence=evidence,
        )
        for key, label, context, penalty, personalised, confidence, evidence
        in factor_values
    )
    condition_cost = total_penalty_per_km * distance_km

    selected = ideal + condition_cost
    # Selected conditions add uncertainty because exact exposure, route shape
    # and execution are unknowable from summary inputs alone.
    condition_uncertainty = condition_cost * 0.20
    selected_low = ideal_low + condition_cost - condition_uncertainty
    selected_high = ideal_high + condition_cost + condition_uncertainty
    target = predictions.target_seconds
    target_probability = _goal_probability(
        central_seconds=selected,
        low_seconds=selected_low,
        high_seconds=selected_high,
        target_seconds=target,
    )
    active_factor_confidences = [
        item.confidence for item in factors if item.penalty_seconds_per_km > 0
    ]
    condition_confidence = (
        sum(active_factor_confidences) / len(active_factor_confidences)
        if active_factor_confidences
        else 1.0
    )
    confidence = predictions.confidence * (0.75 + 0.25 * condition_confidence)
    target_gap = selected - float(target) if target else None

    if target_gap is not None and target_gap <= 0:
        headline = "Selected conditions still support the comparison target"
    elif target_gap is not None and target_gap <= (selected_high - selected_low) / 2:
        headline = "The comparison target remains within the selected-condition range"
    elif condition_cost <= 5:
        headline = "Selected conditions are close to ideal"
    else:
        headline = "Selected conditions make the comparison target more demanding"

    conditions_summary = (
        f"{temperature:.0f}°C · {humidity:.0f}% humidity · {ascent:.0f} m ascent · "
        f"{wind:.0f} km/h {exposure.lower()} wind · {surface.lower()}"
    )
    return InteractiveRaceOutlook(
        athlete_id=predictions.athlete_id,
        available=True,
        goal_name=predictions.goal_name,
        distance_label=predictions.distance_label,
        distance_km=distance_km,
        target_seconds=target,
        ideal_seconds=round(ideal, 1),
        ideal_low_seconds=round(ideal_low, 1),
        ideal_high_seconds=round(ideal_high, 1),
        selected_seconds=round(selected, 1),
        selected_low_seconds=round(selected_low, 1),
        selected_high_seconds=round(selected_high, 1),
        selected_pace_s_per_km=round(selected / distance_km, 1),
        condition_cost_seconds=round(condition_cost, 1),
        condition_cost_percent=round(condition_cost / ideal * 100.0, 2),
        target_gap_seconds=round(target_gap, 1) if target_gap is not None else None,
        target_probability=round(target_probability, 4) if target_probability is not None else None,
        confidence=round(confidence, 4),
        confidence_label=_confidence_label(confidence),
        headline=headline,
        summary=(
            "Underlying capability is unchanged. This forecast translates that "
            "same fitness into the selected race-day conditions."
        ),
        conditions_summary=conditions_summary,
        factors=factors,
        limitations=(
            "A safety cap prevents combined summary adjustments from exceeding 18% of ideal pace.",
            "The forecast uses total ascent, not the exact location or steepness of each climb.",
            "Wind direction, gusts, shelter, drafting and course turns are represented only by a conservative exposure choice.",
            "Firm trail is a broad surface class; mud and technical terrain require course-specific evidence.",
            "Goal likelihood is a coaching estimate from the selected forecast range, not a guarantee or betting probability.",
        ),
    )

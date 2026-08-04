"""
Environment Forecast Engine.

The Capability Engine estimates ideal, flat-condition capability.
The Environment Forecast Engine translates that capability into practical
race scenarios without changing the underlying fitness estimate.

Version 1 provides transparent generic scenarios:
- Ideal
- Typical UK
- Warm
- Hot
- Hilly
- Trail

Future versions will replace generic adjustments with:
- personal heat response;
- dew-point and humidity response;
- course-specific elevation;
- surface-specific response;
- wind;
- race-day weather and route data.

This module intentionally keeps capability and forecast separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.capability import Capability
from core.environment_profile import PersonalEnvironmentProfile


@dataclass(frozen=True)
class ForecastScenario:
    key: str
    label: str
    description: str
    central_seconds: float
    low_seconds: float
    high_seconds: float
    pace_seconds_per_km: float | None
    adjustment_percent: float
    confidence: float
    personalised: bool
    notes: tuple[str, ...]


@dataclass(frozen=True)
class EnvironmentForecast:
    available: bool
    distance_km: float | None
    baseline_seconds: float | None
    scenarios: tuple[ForecastScenario, ...]
    headline: str
    summary: str
    confidence: float
    limitations: tuple[str, ...]
    model_version: int = 1


SCENARIOS = (
    {
        "key": "ideal",
        "label": "❄️ Ideal",
        "description": "Cool, flat road and light wind",
        "adjustment": 0.000,
        "confidence_modifier": 1.00,
    },
    {
        "key": "typical",
        "label": "🌤 Typical UK",
        "description": "Mild conditions on a normal road course",
        "adjustment": 0.006,
        "confidence_modifier": 0.97,
    },
    {
        "key": "warm",
        "label": "☀️ Warm",
        "description": "Around 20–22°C with moderate humidity",
        "adjustment": 0.018,
        "confidence_modifier": 0.90,
    },
    {
        "key": "hot",
        "label": "🔥 Hot",
        "description": "Around 26–28°C with meaningful heat stress",
        "adjustment": 0.040,
        "confidence_modifier": 0.82,
    },
    {
        "key": "hilly",
        "label": "⛰️ Hilly",
        "description": "A rolling road course with sustained climbing",
        "adjustment": 0.026,
        "confidence_modifier": 0.84,
    },
    {
        "key": "trail",
        "label": "🌲 Trail",
        "description": "Firm trail with uneven surface and turns",
        "adjustment": 0.050,
        "confidence_modifier": 0.76,
    },
)


def _pace_seconds_per_km(
    time_seconds: float,
    distance_km: float | None,
) -> float | None:
    if distance_km is None or distance_km <= 0:
        return None

    return time_seconds / distance_km


def build_environment_forecast(
    capability: Capability,
    *,
    distance_km: float | None,
    personal_profile: PersonalEnvironmentProfile | None = None,
) -> EnvironmentForecast:
    if not capability.available or capability.central_seconds is None:
        return EnvironmentForecast(
            available=False,
            distance_km=distance_km,
            baseline_seconds=None,
            scenarios=(),
            headline="Environmental forecasts are still building.",
            summary=(
                "A current capability estimate is required before conditions "
                "can be translated into scenario forecasts."
            ),
            confidence=0.0,
            limitations=(
                "No usable capability estimate was available.",
            ),
        )

    baseline = capability.central_seconds
    baseline_low = capability.low_seconds or baseline
    baseline_high = capability.high_seconds or baseline

    scenarios = []

    for definition in SCENARIOS:
        adjustment = float(definition["adjustment"])
        personal_multiplier = 1.0
        personal_confidence = 0.0

        if personal_profile is not None:
            if definition["key"] in {"warm", "hot"}:
                personal_multiplier = personal_profile.heat_multiplier
                personal_confidence = personal_profile.heat_confidence
            elif definition["key"] == "hilly":
                personal_multiplier = personal_profile.hill_multiplier
                personal_confidence = personal_profile.hill_confidence
            elif definition["key"] == "trail":
                personal_multiplier = personal_profile.trail_multiplier
                personal_confidence = personal_profile.trail_confidence

        if personal_confidence > 0:
            # Blend personal response with the generic model. Strong evidence
            # can contribute up to 75% of the final scenario adjustment.
            blend = min(personal_confidence * 0.75, 0.75)
            adjusted_multiplier = (
                1.0 * (1.0 - blend)
                + personal_multiplier * blend
            )
            adjustment *= adjusted_multiplier

        multiplier = 1.0 + adjustment
        central = baseline * multiplier
        low = baseline_low * multiplier
        high = baseline_high * multiplier
        confidence = min(
            capability.confidence
            * float(definition["confidence_modifier"]),
            0.97,
        )

        personalised = personal_confidence >= 0.25
        notes = [
            (
                "Personal historical response blended with the generic model."
                if personalised
                else "Generic scenario adjustment retained while personal "
                "evidence builds."
            )
        ]

        if definition["key"] == "ideal":
            notes = [
                (
                    "This is the same ideal-condition baseline produced by "
                    "the Capability Engine."
                )
            ]

        scenarios.append(
            ForecastScenario(
                key=definition["key"],
                label=definition["label"],
                description=definition["description"],
                central_seconds=round(central, 1),
                low_seconds=round(low, 1),
                high_seconds=round(high, 1),
                pace_seconds_per_km=(
                    round(
                        _pace_seconds_per_km(
                            central,
                            distance_km,
                        ),
                        1,
                    )
                    if _pace_seconds_per_km(
                        central,
                        distance_km,
                    )
                    is not None
                    else None
                ),
                adjustment_percent=round(adjustment * 100, 1),
                confidence=round(confidence, 4),
                personalised=personalised,
                notes=tuple(notes),
            )
        )

    return EnvironmentForecast(
        available=True,
        distance_km=distance_km,
        baseline_seconds=baseline,
        scenarios=tuple(scenarios),
        headline="How current capability changes with conditions",
        summary=(
            "The athlete's underlying capability stays the same; each "
            "scenario estimates how conditions may change the realised time. "
            "Where enough comparable history exists, personal response is "
            "blended with the generic model."
        ),
        confidence=capability.confidence,
        limitations=(
            "Personal adjustments remain conservative and are blended "
            "with generic assumptions.",
            "Humidity, dew point, wind, exact elevation and technical trail "
            "difficulty are not yet entered separately.",
            "Future versions will learn each athlete's personal heat, hill "
            "and surface response.",
        ),
    )


def environment_forecast_to_dict(
    forecast: EnvironmentForecast,
) -> dict[str, Any]:
    return {
        "available": forecast.available,
        "distance_km": forecast.distance_km,
        "baseline_seconds": forecast.baseline_seconds,
        "headline": forecast.headline,
        "summary": forecast.summary,
        "confidence": forecast.confidence,
        "limitations": list(forecast.limitations),
        "model_version": forecast.model_version,
        "scenarios": [
            {
                "key": scenario.key,
                "label": scenario.label,
                "description": scenario.description,
                "central_seconds": scenario.central_seconds,
                "low_seconds": scenario.low_seconds,
                "high_seconds": scenario.high_seconds,
                "pace_seconds_per_km":
                    scenario.pace_seconds_per_km,
                "adjustment_percent":
                    scenario.adjustment_percent,
                "confidence": scenario.confidence,
                "personalised": scenario.personalised,
                "notes": list(scenario.notes),
            }
            for scenario in forecast.scenarios
        ],
    }

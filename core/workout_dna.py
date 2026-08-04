"""
Workout DNA foundation.

Workout DNA translates reconstructed workout phases into a shared,
device-independent description of physiological training intent.

Version 1 provides:
- one stable WorkoutDNA model;
- stimulus scores for threshold, speed, endurance and aerobic systems;
- primary and secondary training intents;
- execution and evidence confidence;
- transparent explanations of why each system received its score.

This module has no Streamlit logic and does not yet alter predictions.
Future specialist coaches will read the same WorkoutDNA object.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable


SYSTEMS = ("threshold", "speed", "endurance", "aerobic")

SYSTEM_LABELS = {
    "threshold": "Threshold Development",
    "speed": "Speed / VO₂ Development",
    "endurance": "Aerobic Endurance",
    "aerobic": "Aerobic Support",
}

PHASE_ALIASES = {
    "continuous_threshold": "threshold",
    "long_threshold": "threshold",
    "sustained_quality": "threshold",
    "tempo": "threshold",
    "vo2": "short_intervals",
    "short_reps": "short_intervals",
    "short_interval": "short_intervals",
    "mile_repetitions": "long_intervals",
    "intervals": "long_intervals",
    "float": "recovery",
    "active_float": "recovery",
}

# Base physiological contribution of each phase type.
# Scores are later scaled by duration, volume, recovery style and execution.
PHASE_STIMULUS = {
    "threshold": {
        "threshold": 1.00,
        "speed": 0.18,
        "endurance": 0.62,
        "aerobic": 0.78,
    },
    "long_intervals": {
        "threshold": 0.72,
        "speed": 0.55,
        "endurance": 0.58,
        "aerobic": 0.52,
    },
    "short_intervals": {
        "threshold": 0.42,
        "speed": 1.00,
        "endurance": 0.28,
        "aerobic": 0.30,
    },
    "strides": {
        "threshold": 0.08,
        "speed": 0.72,
        "endurance": 0.04,
        "aerobic": 0.05,
    },
    "long_run": {
        "threshold": 0.22,
        "speed": 0.05,
        "endurance": 1.00,
        "aerobic": 0.82,
    },
    "steady": {
        "threshold": 0.35,
        "speed": 0.08,
        "endurance": 0.72,
        "aerobic": 0.85,
    },
    "recovery": {
        "threshold": 0.04,
        "speed": 0.02,
        "endurance": 0.16,
        "aerobic": 0.28,
    },
    "warmup": {
        "threshold": 0.03,
        "speed": 0.03,
        "endurance": 0.10,
        "aerobic": 0.22,
    },
    "cooldown": {
        "threshold": 0.02,
        "speed": 0.01,
        "endurance": 0.10,
        "aerobic": 0.20,
    },
}


@dataclass(frozen=True)
class WorkoutDNA:
    activity_id: int | None
    athlete_id: int | None
    primary_system: str
    secondary_systems: tuple[str, ...]
    stimulus_scores: dict[str, float]
    execution_quality: float | None
    confidence: float
    source: str
    archetype: str
    phase_count: int
    quality_phase_count: int
    total_quality_duration_s: float
    total_quality_distance_km: float
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]

    @property
    def primary_label(self) -> str:
        return SYSTEM_LABELS.get(
            self.primary_system,
            self.primary_system.replace("_", " ").title(),
        )


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalise_phase_type(value: Any) -> str:
    phase_type = str(value or "unknown").strip().lower()
    return PHASE_ALIASES.get(phase_type, phase_type)


def _safe_phases(
    phases: str | Iterable[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if phases is None:
        return []

    if isinstance(phases, str):
        try:
            decoded = json.loads(phases)
        except (TypeError, json.JSONDecodeError):
            return []

        phases = decoded

    if not isinstance(phases, (list, tuple)):
        return []

    return [
        phase
        for phase in phases
        if isinstance(phase, dict)
    ]


def _phase_load(phase: dict[str, Any]) -> float:
    """
    Estimate how much useful stimulus one phase carries.

    Duration drives the score. Distance and repetitions add modest support,
    while preventing tiny fragments from dominating the workout.
    """
    duration_s = max(_float(phase.get("duration_s")), 0.0)
    distance_km = max(_float(phase.get("distance_km")), 0.0)
    rep_count = max(int(_float(phase.get("rep_count"), 1.0)), 1)

    duration_load = min(duration_s / 1200.0, 1.40)
    distance_load = min(distance_km / 5.0, 1.20)
    repetition_load = min(rep_count / 10.0, 1.00)

    return max(
        duration_load * 0.60
        + distance_load * 0.25
        + repetition_load * 0.15,
        0.05,
    )


def _archetype(
    phase_types: list[str],
    phases: list[dict[str, Any]],
) -> str:
    quality_types = [
        phase_type
        for phase_type in phase_types
        if phase_type
        in {
            "threshold",
            "long_intervals",
            "short_intervals",
            "strides",
            "long_run",
            "steady",
        }
    ]

    has_threshold = "threshold" in quality_types
    has_long = "long_intervals" in quality_types
    has_short = "short_intervals" in quality_types
    has_float = any(
        (
            _normalise_phase_type(phase.get("phase_type"))
            == "recovery"
            and (
                phase.get("metadata", {}).get("recovery_style") == "float"
                or phase.get("metadata", {}).get("workout_archetype")
                == "threshold_with_float"
            )
        )
        for phase in phases
    )

    if has_threshold and has_short:
        return "Mixed threshold and speed"
    if has_threshold and has_float:
        return "Threshold with float recoveries"
    if has_threshold and has_long:
        return "Threshold endurance"
    if has_threshold:
        return "Threshold development"
    if has_short:
        return "Speed / VO₂ development"
    if has_long:
        return "Long interval development"
    if "long_run" in quality_types:
        return "Endurance development"
    if "steady" in quality_types:
        return "Steady aerobic development"

    return "Structured workout"


def build_workout_dna(
    *,
    phases: str | Iterable[dict[str, Any]] | None,
    activity_id: int | None = None,
    athlete_id: int | None = None,
    execution_score: float | None = None,
    recognition_confidence: float = 0.0,
    phase_confidence: float = 0.0,
    source: str = "unknown",
) -> WorkoutDNA:
    """
    Build one transparent WorkoutDNA object from normalised workout phases.

    Inputs are deliberately generic so both CSV and FIT phase sources use
    exactly the same engine.
    """
    phase_list = _safe_phases(phases)

    raw_scores = {system: 0.0 for system in SYSTEMS}
    reasons = []
    limitations = []
    quality_phase_count = 0
    quality_duration_s = 0.0
    quality_distance_km = 0.0
    phase_types = []

    for phase in phase_list:
        phase_type = _normalise_phase_type(
            phase.get("phase_type")
        )
        phase_types.append(phase_type)
        contribution = PHASE_STIMULUS.get(phase_type)

        if contribution is None:
            continue

        load = _phase_load(phase)
        duration_s = max(_float(phase.get("duration_s")), 0.0)
        distance_km = max(_float(phase.get("distance_km")), 0.0)

        if phase_type in {
            "threshold",
            "long_intervals",
            "short_intervals",
            "strides",
            "long_run",
            "steady",
        }:
            quality_phase_count += 1
            quality_duration_s += duration_s
            quality_distance_km += distance_km

        for system, base_score in contribution.items():
            raw_scores[system] += base_score * load

        label = str(
            phase.get("label")
            or phase_type.replace("_", " ").title()
        )
        rep_count = max(
            int(_float(phase.get("rep_count"), 1.0)),
            1,
        )

        if phase_type in {
            "threshold",
            "long_intervals",
            "short_intervals",
            "long_run",
            "steady",
        }:
            reasons.append(
                f"{label} contributed {rep_count} quality block"
                f"{'s' if rep_count != 1 else ''}."
            )

    maximum = max(raw_scores.values(), default=0.0)

    if maximum <= 0:
        stimulus_scores = {system: 0.0 for system in SYSTEMS}
        primary_system = "aerobic"
        secondary_systems = ()
        limitations.append(
            "No recognised quality phases were available for Workout DNA."
        )
    else:
        # Scale the strongest system towards 100 while preserving meaningful
        # differences between systems.
        scale = min(100.0 / maximum, 100.0)
        stimulus_scores = {
            system: round(
                max(0.0, min(score * scale, 100.0)),
                1,
            )
            for system, score in raw_scores.items()
        }

        ranked = sorted(
            stimulus_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        primary_system = ranked[0][0]
        primary_score = ranked[0][1]
        secondary_systems = tuple(
            system
            for system, score in ranked[1:]
            if score >= max(primary_score * 0.55, 35.0)
        )

    execution_quality = (
        max(0.0, min(_float(execution_score), 100.0))
        if execution_score is not None
        else None
    )

    execution_confidence = (
        execution_quality / 100.0
        if execution_quality is not None
        else 0.55
    )

    structural_confidence = min(
        quality_phase_count / 3.0,
        1.0,
    )

    confidence = min(
        max(_float(recognition_confidence), 0.0) * 0.35
        + max(_float(phase_confidence), 0.0) * 0.40
        + structural_confidence * 0.15
        + execution_confidence * 0.10,
        0.99,
    )

    if source == "fit":
        confidence = min(confidence + 0.03, 0.99)
        reasons.append(
            "FIT-derived phases supplied the highest-detail structure."
        )
    elif source == "runalyze_csv":
        reasons.append(
            "Workout DNA was reconstructed from Runalyze CSV phases."
        )

    if execution_quality is None:
        limitations.append(
            "Execution quality was unavailable, so a neutral value was used."
        )

    if quality_phase_count < 2:
        limitations.append(
            "Only limited quality-phase structure was available."
        )

    return WorkoutDNA(
        activity_id=activity_id,
        athlete_id=athlete_id,
        primary_system=primary_system,
        secondary_systems=secondary_systems,
        stimulus_scores=stimulus_scores,
        execution_quality=execution_quality,
        confidence=round(confidence, 4),
        source=source,
        archetype=_archetype(phase_types, phase_list),
        phase_count=len(phase_list),
        quality_phase_count=quality_phase_count,
        total_quality_duration_s=round(quality_duration_s, 1),
        total_quality_distance_km=round(quality_distance_km, 3),
        reasons=tuple(dict.fromkeys(reasons)),
        limitations=tuple(dict.fromkeys(limitations)),
    )


def workout_dna_to_dict(dna: WorkoutDNA) -> dict[str, Any]:
    return {
        "activity_id": dna.activity_id,
        "athlete_id": dna.athlete_id,
        "primary_system": dna.primary_system,
        "primary_label": dna.primary_label,
        "secondary_systems": list(dna.secondary_systems),
        "stimulus_scores": dna.stimulus_scores,
        "execution_quality": dna.execution_quality,
        "confidence": dna.confidence,
        "source": dna.source,
        "archetype": dna.archetype,
        "phase_count": dna.phase_count,
        "quality_phase_count": dna.quality_phase_count,
        "total_quality_duration_s": dna.total_quality_duration_s,
        "total_quality_distance_km": dna.total_quality_distance_km,
        "reasons": list(dna.reasons),
        "limitations": list(dna.limitations),
        "model_version": 1,
    }

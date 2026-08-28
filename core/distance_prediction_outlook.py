"""Lean, distance-specific anchors for the Lead Coach race matrix.

The Home matrix used to translate one active-goal prediction through PB ratios.
That was fast, but it meant a 5K race, half-marathon endurance and marathon
history were not assessed independently. This service asks the existing Race,
Workout and Threshold coaches one question per standard distance. It builds no
new physiological formula and is safe to cache at the presentation boundary.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from core.coach_brain import CoachBrain
from core.endurance_transfer import (
    calibrate_endurance_anchors,
    load_endurance_profile,
)
from core.home_predictions import HomePredictions


DISTANCE_DEFINITIONS = (
    ("5k", "5K", 5.0),
    ("10k", "10K", 10.0),
    ("half_marathon", "Half marathon", 21.0975),
    ("marathon", "Marathon", 42.195),
)


@dataclass(frozen=True)
class DistancePredictionAnchor:
    key: str
    label: str
    distance_km: float
    available: bool
    central_seconds: float | None
    confidence: float
    evidence_source_count: int
    source: str
    explanation: str
    raw_central_seconds: float | None = None
    speed_equivalent_seconds: float | None = None
    readiness_score: float | None = None
    readiness_label: str = ""
    endurance_summary: str = ""
    transfer_fraction: float = 0.0


@dataclass(frozen=True)
class DistancePredictionOutlook:
    athlete_id: int
    anchors: tuple[DistancePredictionAnchor, ...]

    @property
    def available_count(self) -> int:
        return sum(anchor.available for anchor in self.anchors)


def _build_distance_anchor(
    athlete_id: int,
    definition: tuple[str, str, float],
) -> DistancePredictionAnchor:
    """Build one independent distance view with its own read-only coach."""
    key, label, distance_km = definition
    goal = {
        "id": None,
        "goal_name": f"{label} capability",
        "distance_m": distance_km * 1000.0,
        "target_time_s": None,
    }
    brain = CoachBrain(athlete_id)
    evidence = brain.build_evidence(goal)
    prediction = brain.prediction_engine.predict_goal(
        athlete_id,
        goal,
        evidence,
    )
    return DistancePredictionAnchor(
        key=key,
        label=label,
        distance_km=distance_km,
        available=prediction.available,
        central_seconds=prediction.predicted_seconds,
        confidence=prediction.confidence,
        evidence_source_count=len(evidence.prediction_items),
        source="distance_specific_coaches",
        explanation=prediction.explanation,
    )


def build_distance_prediction_outlook(
    athlete_id: int,
    *,
    active_predictions: HomePredictions | None = None,
) -> DistancePredictionOutlook:
    """Build four independent real-evidence predictions for one athlete."""
    anchors_by_key: dict[str, DistancePredictionAnchor] = {}
    missing_definitions = []

    for key, label, distance_km in DISTANCE_DEFINITIONS:
        is_active = bool(
            active_predictions is not None
            and active_predictions.available
            and active_predictions.distance_label == label
            and active_predictions.central_seconds is not None
        )
        if is_active:
            anchors_by_key[key] = DistancePredictionAnchor(
                key=key,
                label=label,
                distance_km=distance_km,
                available=True,
                central_seconds=active_predictions.central_seconds,
                confidence=active_predictions.confidence,
                evidence_source_count=(
                    active_predictions.evidence_source_count
                ),
                source="active_goal_coaches",
                explanation=active_predictions.explanation,
            )
            continue
        missing_definitions.append((key, label, distance_km))

    # Each distance asks the same read-only evidence services an independent
    # question. Running those questions concurrently changes wall-clock time,
    # not the underlying evidence, weighting or calibration.
    if missing_definitions:
        with ThreadPoolExecutor(
            max_workers=min(len(missing_definitions), 3),
            thread_name_prefix="pp-distance",
        ) as executor:
            built = executor.map(
                lambda definition: _build_distance_anchor(
                    athlete_id,
                    definition,
                ),
                missing_definitions,
            )
            for anchor in built:
                anchors_by_key[anchor.key] = anchor

    anchors = tuple(
        anchors_by_key[key]
        for key, _label, _distance_km in DISTANCE_DEFINITIONS
    )

    endurance_profile = load_endurance_profile(athlete_id)
    calibrated = calibrate_endurance_anchors(anchors, endurance_profile)

    return DistancePredictionOutlook(
        athlete_id=athlete_id,
        anchors=calibrated,
    )

"""
Historical Workout Similarity Engine.

This engine compares one stored workout with the same athlete's historical
Workout Library and returns the most similar workouts that have a linked race
outcome.

Version 1 is deliberately transparent and conservative:
- histories never cross athlete_id;
- warm-up, cool-down and recovery phases do not drive similarity;
- phase type, volume, rep structure and rep distance carry most weight;
- pace and execution provide supporting evidence;
- it does not replace the existing prediction yet.

The next sprint can use these inspected matches to create an
athlete-calibrated prediction.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

from core.database import (
    create_workout_library_tables,
    get_connection,
)


QUALITY_PHASES = {
    "threshold",
    "long_intervals",
    "short_intervals",
    "strides",
    "tempo",
    "vo2",
}

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
class SimilarWorkoutMatch:
    workout_activity_id: int
    workout_date: str | None
    workout_signature: str
    similarity: float
    race_activity_id: int
    race_date: str | None
    race_title: str
    race_distance_km: float
    race_time_s: float
    days_after: int
    link_confidence: float
    reasons: tuple[str, ...]
    differences: tuple[str, ...]
    feature_scores: dict[str, float]


@dataclass(frozen=True)
class SimilarityResult:
    athlete_id: int
    current_activity_id: int
    match_count: int
    linked_history_count: int
    distinct_workout_count: int
    distinct_race_count: int
    confidence: float
    matches: tuple[SimilarWorkoutMatch, ...]
    limitations: tuple[str, ...]


def _safe_phases(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []

    try:
        phases = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []

    if not isinstance(phases, list):
        return []

    return [phase for phase in phases if isinstance(phase, dict)]


def _canonical_type(value: Any) -> str:
    phase_type = str(value or "unknown").strip().lower()
    return PHASE_ALIASES.get(phase_type, phase_type)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _quality_features(
    phases: list[dict[str, Any]],
    execution_score: float | None,
) -> dict[str, Any]:
    by_type: dict[str, dict[str, float]] = {}

    for phase in phases:
        phase_type = _canonical_type(phase.get("phase_type"))

        if phase_type not in QUALITY_PHASES:
            continue

        distance = max(_float(phase.get("distance_km")), 0.0)
        duration = max(_float(phase.get("duration_s")), 0.0)
        rep_count = max(int(_float(phase.get("rep_count"), 1.0)), 1)

        average_rep_distance = phase.get("average_rep_distance_km")
        if average_rep_distance is None and rep_count > 0:
            average_rep_distance = distance / rep_count
        average_rep_distance = max(_float(average_rep_distance), 0.0)

        pace = phase.get("pace_s_per_km")
        if pace is None and distance > 0 and duration > 0:
            pace = duration / distance
        pace = _float(pace, 0.0)

        recovery = phase.get("recovery_duration_s")
        recovery = (
            _float(recovery)
            if recovery is not None
            else None
        )

        current = by_type.setdefault(
            phase_type,
            {
                "distance_km": 0.0,
                "duration_s": 0.0,
                "rep_count": 0.0,
                "weighted_rep_distance": 0.0,
                "weighted_pace": 0.0,
                "pace_weight": 0.0,
                "weighted_recovery": 0.0,
                "recovery_weight": 0.0,
            },
        )

        current["distance_km"] += distance
        current["duration_s"] += duration
        current["rep_count"] += rep_count
        current["weighted_rep_distance"] += (
            average_rep_distance * rep_count
        )

        if pace > 0 and distance > 0:
            current["weighted_pace"] += pace * distance
            current["pace_weight"] += distance

        if recovery is not None and rep_count > 1:
            current["weighted_recovery"] += recovery * (rep_count - 1)
            current["recovery_weight"] += rep_count - 1

    for values in by_type.values():
        reps = max(values["rep_count"], 1.0)
        values["average_rep_distance_km"] = (
            values["weighted_rep_distance"] / reps
        )
        values["pace_s_per_km"] = (
            values["weighted_pace"] / values["pace_weight"]
            if values["pace_weight"] > 0
            else None
        )
        values["recovery_duration_s"] = (
            values["weighted_recovery"] / values["recovery_weight"]
            if values["recovery_weight"] > 0
            else None
        )

    quality_distance = sum(
        values["distance_km"] for values in by_type.values()
    )
    quality_duration = sum(
        values["duration_s"] for values in by_type.values()
    )

    return {
        "by_type": by_type,
        "phase_types": set(by_type.keys()),
        "quality_distance_km": quality_distance,
        "quality_duration_s": quality_duration,
        "execution_score": (
            _float(execution_score) / 100.0
            if execution_score is not None
            else None
        ),
    }


def _ratio_similarity(a: float, b: float, floor: float = 0.0) -> float:
    if a <= floor and b <= floor:
        return 1.0
    if a <= floor or b <= floor:
        return 0.0

    ratio = min(a, b) / max(a, b)
    return max(0.0, min(ratio, 1.0))


def _relative_similarity(
    a: float | None,
    b: float | None,
    tolerance: float,
) -> float | None:
    if a is None or b is None or a <= 0 or b <= 0:
        return None

    relative_difference = abs(a - b) / max(a, b)
    return max(0.0, 1.0 - relative_difference / tolerance)


def _weighted_average(values: list[tuple[float | None, float]]) -> float:
    usable = [
        (value, weight)
        for value, weight in values
        if value is not None and weight > 0
    ]

    if not usable:
        return 0.0

    total_weight = sum(weight for _, weight in usable)
    return sum(value * weight for value, weight in usable) / total_weight


def _compare_features(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[float, list[str], list[str], dict[str, float]]:
    current_types = current["phase_types"]
    candidate_types = candidate["phase_types"]

    union = current_types | candidate_types
    intersection = current_types & candidate_types

    type_score = (
        len(intersection) / len(union)
        if union
        else 0.0
    )

    volume_score = _ratio_similarity(
        current["quality_distance_km"],
        candidate["quality_distance_km"],
    )
    duration_score = _ratio_similarity(
        current["quality_duration_s"],
        candidate["quality_duration_s"],
    )

    per_type_scores = []
    rep_scores = []
    distance_scores = []
    pace_scores = []
    recovery_scores = []

    reasons: list[str] = []
    differences: list[str] = []

    for phase_type in sorted(intersection):
        a = current["by_type"][phase_type]
        b = candidate["by_type"][phase_type]

        type_volume = _ratio_similarity(
            a["distance_km"],
            b["distance_km"],
        )
        per_type_scores.append(type_volume)

        rep_score = _ratio_similarity(
            a["rep_count"],
            b["rep_count"],
        )
        rep_scores.append(rep_score)

        rep_distance_score = _relative_similarity(
            a["average_rep_distance_km"],
            b["average_rep_distance_km"],
            tolerance=0.35,
        )
        distance_scores.append(rep_distance_score)

        pace_score = _relative_similarity(
            a["pace_s_per_km"],
            b["pace_s_per_km"],
            tolerance=0.18,
        )
        pace_scores.append(pace_score)

        recovery_score = _relative_similarity(
            a["recovery_duration_s"],
            b["recovery_duration_s"],
            tolerance=0.60,
        )
        recovery_scores.append(recovery_score)

        label = phase_type.replace("_", " ").title()

        if type_volume >= 0.85:
            reasons.append(f"{label} volume closely matched")
        elif type_volume < 0.55:
            differences.append(f"{label} volume differed")

        if rep_score >= 0.85:
            reasons.append(f"{label} rep count matched")
        elif rep_score < 0.60:
            differences.append(f"{label} rep count differed")

        if (
            rep_distance_score is not None
            and rep_distance_score >= 0.85
        ):
            reasons.append(f"{label} rep distance closely matched")
        elif (
            rep_distance_score is not None
            and rep_distance_score < 0.55
        ):
            differences.append(f"{label} rep distance differed")

        if pace_score is not None and pace_score >= 0.85:
            reasons.append(f"{label} pace was similar")
        elif pace_score is not None and pace_score < 0.55:
            differences.append(f"{label} pace differed")

        if (
            recovery_score is not None
            and recovery_score >= 0.80
        ):
            reasons.append(f"{label} recovery structure was similar")

    execution_score = _relative_similarity(
        current["execution_score"],
        candidate["execution_score"],
        tolerance=0.35,
    )

    if execution_score is not None and execution_score >= 0.85:
        reasons.append("Execution quality closely matched")
    elif execution_score is not None and execution_score < 0.55:
        differences.append("Execution quality differed")

    phase_volume_score = (
        sum(per_type_scores) / len(per_type_scores)
        if per_type_scores
        else 0.0
    )
    rep_count_score = (
        sum(rep_scores) / len(rep_scores)
        if rep_scores
        else 0.0
    )
    rep_distance_score = _weighted_average(
        [(value, 1.0) for value in distance_scores]
    )
    pace_score = _weighted_average(
        [(value, 1.0) for value in pace_scores]
    )
    recovery_score = _weighted_average(
        [(value, 1.0) for value in recovery_scores]
    )

    score = _weighted_average(
        [
            (type_score, 0.24),
            (phase_volume_score, 0.18),
            (rep_count_score, 0.14),
            (rep_distance_score, 0.16),
            (volume_score, 0.10),
            (duration_score, 0.05),
            (pace_score, 0.08),
            (recovery_score, 0.03),
            (execution_score, 0.02),
        ]
    )

    feature_scores = {
        "phase_type": round(type_score, 4),
        "phase_volume": round(phase_volume_score, 4),
        "rep_count": round(rep_count_score, 4),
        "rep_distance": round(rep_distance_score, 4),
        "total_volume": round(volume_score, 4),
        "duration": round(duration_score, 4),
        "pace": round(pace_score, 4),
        "recovery": round(recovery_score, 4),
        "execution": round(execution_score or 0.0, 4),
    }

    # Avoid long repetitive explanations in the UI.
    reasons = list(dict.fromkeys(reasons))[:5]
    differences = list(dict.fromkeys(differences))[:3]

    return (
        max(0.0, min(score, 1.0)),
        reasons,
        differences,
        feature_scores,
    )


def find_similar_linked_workouts(
    *,
    athlete_id: int,
    current_activity_id: int,
    limit: int = 10,
    minimum_similarity: float = 0.45,
) -> SimilarityResult:
    """
    Compare one workout against linked historical workouts for the same athlete.

    Multiple race links for the same historical workout are allowed because
    they are separate outcomes. The UI can therefore reveal whether one
    workout preceded several races in the valid 3-35 day window.
    """
    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    cursor.execute(
        """
        SELECT
            id,
            phase_json,
            execution_score
        FROM workout_library
        WHERE athlete_id = ?
          AND activity_id = ?
        """,
        (athlete_id, current_activity_id),
    )
    current_row = cursor.fetchone()

    if current_row is None:
        conn.close()
        return SimilarityResult(
            athlete_id=athlete_id,
            current_activity_id=current_activity_id,
            match_count=0,
            linked_history_count=0,
            distinct_workout_count=0,
            distinct_race_count=0,
            confidence=0.0,
            matches=(),
            limitations=(
                "The selected workout was not found in the Workout Library.",
            ),
        )

    current_features = _quality_features(
        _safe_phases(current_row[1]),
        current_row[2],
    )

    cursor.execute(
        """
        SELECT
            wl.activity_id,
            wl.activity_date,
            wl.workout_signature,
            wl.phase_json,
            wl.execution_score,
            wrl.race_activity_id,
            race.activity_date,
            COALESCE(race.title, 'Race effort'),
            wrl.race_distance_km,
            wrl.race_time_s,
            wrl.days_after,
            wrl.link_confidence
        FROM workout_library wl
        JOIN workout_race_links wrl
          ON wrl.workout_id = wl.id
        JOIN activities race
          ON race.id = wrl.race_activity_id
        WHERE wl.athlete_id = ?
          AND wl.activity_id <> ?
        ORDER BY wl.activity_date DESC,
                 wrl.link_confidence DESC
        """,
        (athlete_id, current_activity_id),
    )
    rows = cursor.fetchall()
    conn.close()

    matches = []

    for row in rows:
        candidate_features = _quality_features(
            _safe_phases(row[3]),
            row[4],
        )

        similarity, reasons, differences, feature_scores = (
            _compare_features(current_features, candidate_features)
        )

        if similarity < minimum_similarity:
            continue

        link_confidence = float(row[11] or 0.0)

        # Linked-race confidence gently affects ranking without changing the
        # workout-to-workout similarity percentage shown to the athlete.
        ranking_score = similarity * (0.85 + 0.15 * link_confidence)

        matches.append(
            (
                ranking_score,
                SimilarWorkoutMatch(
                    workout_activity_id=int(row[0]),
                    workout_date=row[1],
                    workout_signature=row[2],
                    similarity=round(similarity, 4),
                    race_activity_id=int(row[5]),
                    race_date=row[6],
                    race_title=row[7],
                    race_distance_km=float(row[8]),
                    race_time_s=float(row[9]),
                    days_after=int(row[10]),
                    link_confidence=link_confidence,
                    reasons=tuple(reasons),
                    differences=tuple(differences),
                    feature_scores=feature_scores,
                ),
            )
        )

    matches.sort(key=lambda item: item[0], reverse=True)
    selected = tuple(match for _, match in matches[: max(limit, 0)])

    if not selected:
        confidence = 0.0
        limitations = (
            "No sufficiently similar workout with a linked race outcome "
            "was found in this athlete's history.",
        )
    else:
        average_similarity = sum(
            match.similarity for match in selected
        ) / len(selected)
        average_link = sum(
            match.link_confidence for match in selected
        ) / len(selected)
        sample_factor = min(len(selected) / 5.0, 1.0)

        confidence = min(
            average_similarity * 0.55
            + average_link * 0.25
            + sample_factor * 0.20,
            0.95,
        )

        limitations = (
            "Similarity is descriptive in v1 and does not yet replace the "
            "formula-based Workout Coach prediction.",
            "Race outcomes may reflect weather, course profile, taper and "
            "race effort that are not yet normalised here.",
        )

    distinct_workout_count = len(
        {int(row[0]) for row in rows}
    )
    distinct_race_count = len(
        {int(row[5]) for row in rows}
    )

    return SimilarityResult(
        athlete_id=athlete_id,
        current_activity_id=current_activity_id,
        match_count=len(selected),
        linked_history_count=len(rows),
        distinct_workout_count=distinct_workout_count,
        distinct_race_count=distinct_race_count,
        confidence=round(confidence, 4),
        matches=selected,
        limitations=limitations,
    )



RIEGEL_EXPONENT = 1.06


def _equivalent_time(
    *,
    race_time_s: float,
    race_distance_km: float,
    goal_distance_km: float,
) -> float | None:
    """Convert a race outcome to the selected goal distance."""
    if (
        race_time_s <= 0
        or race_distance_km <= 0
        or goal_distance_km <= 0
    ):
        return None

    return race_time_s * math.pow(
        goal_distance_km / race_distance_km,
        RIEGEL_EXPONENT,
    )


def _weighted_quantile(
    values: list[tuple[float, float]],
    quantile: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(values, key=lambda item: item[0])
    total_weight = sum(max(weight, 0.0) for _, weight in ordered)

    if total_weight <= 0:
        return None

    target = max(0.0, min(quantile, 1.0)) * total_weight
    cumulative = 0.0

    for value, weight in ordered:
        cumulative += max(weight, 0.0)

        if cumulative >= target:
            return value

    return ordered[-1][0]


def predict_from_similarity(
    result: SimilarityResult,
    *,
    goal_distance_km: float,
) -> dict[str, Any] | None:
    """
    Produce an athlete-specific prediction from linked historical outcomes.

    One race may be linked to several preceding workouts. To prevent that
    single race being counted repeatedly, only the strongest workout match
    for each distinct race is retained.

    The central estimate uses the weighted 45th percentile rather than the
    simple mean. This gently favours stronger performances and reduces the
    damage caused by controlled or non-all-out races until the future
    Effort & Intent Engine can identify them explicitly.
    """
    if goal_distance_km <= 0 or not result.matches:
        return None

    best_by_race: dict[int, SimilarWorkoutMatch] = {}

    for match in result.matches:
        existing = best_by_race.get(match.race_activity_id)

        if existing is None:
            best_by_race[match.race_activity_id] = match
            continue

        existing_rank = (
            existing.similarity
            * (0.80 + 0.20 * existing.link_confidence)
        )
        new_rank = (
            match.similarity
            * (0.80 + 0.20 * match.link_confidence)
        )

        if new_rank > existing_rank:
            best_by_race[match.race_activity_id] = match

    outcomes = []

    for match in best_by_race.values():
        equivalent = _equivalent_time(
            race_time_s=match.race_time_s,
            race_distance_km=match.race_distance_km,
            goal_distance_km=goal_distance_km,
        )

        if equivalent is None:
            continue

        # Similarity dominates. Link confidence supports the ranking.
        weight = (
            math.pow(max(match.similarity, 0.01), 3.0)
            * (0.70 + 0.30 * match.link_confidence)
        )

        outcomes.append(
            {
                "race_activity_id": match.race_activity_id,
                "workout_activity_id": match.workout_activity_id,
                "workout_date": match.workout_date,
                "race_date": match.race_date,
                "race_title": match.race_title,
                "race_distance_km": match.race_distance_km,
                "race_time_s": match.race_time_s,
                "equivalent_goal_time_s": round(equivalent, 1),
                "days_after": match.days_after,
                "similarity": match.similarity,
                "link_confidence": match.link_confidence,
                "weight": round(weight, 5),
                "reasons": list(match.reasons),
                "differences": list(match.differences),
            }
        )

    if not outcomes:
        return None

    weighted_values = [
        (outcome["equivalent_goal_time_s"], outcome["weight"])
        for outcome in outcomes
    ]

    central = _weighted_quantile(weighted_values, 0.45)
    faster_bound = _weighted_quantile(weighted_values, 0.20)
    slower_bound = _weighted_quantile(weighted_values, 0.75)

    if central is None:
        return None

    # Ensure the displayed range remains useful with very small samples.
    minimum_half_range = max(central * 0.012, 8.0)

    low = (
        min(faster_bound, central - minimum_half_range)
        if faster_bound is not None
        else central - minimum_half_range
    )
    high = (
        max(slower_bound, central + minimum_half_range)
        if slower_bound is not None
        else central + minimum_half_range
    )

    distinct_races = len(outcomes)
    average_similarity = sum(
        outcome["similarity"] * outcome["weight"]
        for outcome in outcomes
    ) / sum(outcome["weight"] for outcome in outcomes)
    average_link = sum(
        outcome["link_confidence"] * outcome["weight"]
        for outcome in outcomes
    ) / sum(outcome["weight"] for outcome in outcomes)

    sample_factor = min(distinct_races / 5.0, 1.0)

    confidence = min(
        average_similarity * 0.55
        + average_link * 0.20
        + sample_factor * 0.25,
        0.92,
    )

    reliability = (
        "Strong"
        if distinct_races >= 5 and confidence >= 0.75
        else "Moderate"
        if distinct_races >= 2 and confidence >= 0.55
        else "Limited"
    )

    return {
        "central_seconds": round(central, 1),
        "low_seconds": round(max(low, 1.0), 1),
        "high_seconds": round(max(high, central), 1),
        "confidence": round(confidence, 4),
        "reliability": reliability,
        "goal_distance_km": round(goal_distance_km, 4),
        "distinct_race_count": distinct_races,
        "linked_match_count": result.match_count,
        "outcomes": sorted(
            outcomes,
            key=lambda item: item["weight"],
            reverse=True,
        ),
        "method": (
            "Historical workout similarity with distinct-race "
            "deduplication and controlled-race guardrail"
        ),
        "model_version": 1,
        "limitations": [
            "Race intent is not yet explicitly known.",
            "The central estimate gently favours stronger linked outcomes "
            "so controlled races do not drag the prediction down as much.",
            "Heat, hills, trail surface and taper are not yet normalised.",
        ],
    }


def compare_workout_phase_json(
    current_phase_json: str | None,
    candidate_phase_json: str | None,
    *,
    current_execution_score: float | None = None,
    candidate_execution_score: float | None = None,
) -> dict[str, Any]:
    """
    Compare two stored workout phase payloads.

    This public helper lets PB Shape and future coaches use the same
    transparent workout fingerprint as Historical Similarity.
    """
    current = _quality_features(
        _safe_phases(current_phase_json),
        current_execution_score,
    )
    candidate = _quality_features(
        _safe_phases(candidate_phase_json),
        candidate_execution_score,
    )

    similarity, reasons, differences, feature_scores = _compare_features(
        current,
        candidate,
    )

    pace_ratios = []
    volume_ratios = []

    for phase_type in sorted(
        current["phase_types"] & candidate["phase_types"]
    ):
        current_phase = current["by_type"][phase_type]
        candidate_phase = candidate["by_type"][phase_type]

        current_pace = current_phase.get("pace_s_per_km")
        candidate_pace = candidate_phase.get("pace_s_per_km")

        if (
            current_pace is not None
            and candidate_pace is not None
            and current_pace > 0
            and candidate_pace > 0
        ):
            weight = max(
                min(
                    current_phase.get("distance_km", 0.0),
                    candidate_phase.get("distance_km", 0.0),
                ),
                0.25,
            )
            pace_ratios.append(
                (current_pace / candidate_pace, weight)
            )

        current_volume = current_phase.get("distance_km", 0.0)
        candidate_volume = candidate_phase.get("distance_km", 0.0)

        if current_volume > 0 and candidate_volume > 0:
            volume_ratios.append(
                (
                    current_volume / candidate_volume,
                    max(min(current_volume, candidate_volume), 0.25),
                )
            )

    def weighted_ratio(values):
        if not values:
            return None

        total_weight = sum(weight for _, weight in values)
        return sum(value * weight for value, weight in values) / total_weight

    return {
        "similarity": similarity,
        "reasons": reasons,
        "differences": differences,
        "feature_scores": feature_scores,
        "pace_ratio": weighted_ratio(pace_ratios),
        "volume_ratio": weighted_ratio(volume_ratios),
    }

def similarity_result_to_dict(result: SimilarityResult) -> dict[str, Any]:
    return {
        "athlete_id": result.athlete_id,
        "current_activity_id": result.current_activity_id,
        "match_count": result.match_count,
        "linked_history_count": result.linked_history_count,
        "distinct_workout_count": result.distinct_workout_count,
        "distinct_race_count": result.distinct_race_count,
        "confidence": result.confidence,
        "limitations": list(result.limitations),
        "matches": [
            {
                "workout_activity_id": match.workout_activity_id,
                "workout_date": match.workout_date,
                "workout_signature": match.workout_signature,
                "similarity": match.similarity,
                "race_activity_id": match.race_activity_id,
                "race_date": match.race_date,
                "race_title": match.race_title,
                "race_distance_km": match.race_distance_km,
                "race_time_s": match.race_time_s,
                "days_after": match.days_after,
                "link_confidence": match.link_confidence,
                "reasons": list(match.reasons),
                "differences": list(match.differences),
                "feature_scores": match.feature_scores,
            }
            for match in result.matches
        ],
    }

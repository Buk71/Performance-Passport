"""
Workout Coach v2.

The coach uses:
- the latest recognised workout;
- the strongest five recent workouts;
- evidence quality and representativeness;
- trends across genuinely comparable sessions.

It supports both manual lap/stop workouts and programmed sessions. A workout
does not need boundary fragments when alternating work/recovery structure is
clear in the decoded splits.
"""

from __future__ import annotations

from collections import Counter
import datetime
import math
from statistics import mean, median

from core.database import get_athlete_sport_roles, get_connection
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider
from core.session import SessionType
from core.session_intelligence import ActivityFacts, classify_session
from core.workout_library import upsert_workout
from core.workout_similarity import (
    find_similar_linked_workouts,
    similarity_result_to_dict,
)
from core.workout_race_linker import refresh_workout_race_links
from core.workout_phases import (
    phases_to_dicts,
    reconstruct_workout_phases,
)
from core.workouts import get_or_decode_workout


RECENT_WINDOW_DAYS = 365
TOP_EVIDENCE_COUNT = 5


def _as_date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _estimate_easy_pace(
    rows,
    reference_date: datetime.date,
) -> tuple[float | None, int]:
    """
    Estimate the athlete's current easy pace from recent genuine easy runs.

    The estimate is deliberately conservative:
    - running activities only (already filtered by the query);
    - 4-20 km;
    - mostly continuous;
    - average HR below 95% of LT1;
    - no race/workout wording;
    - last 180 days, with a 365-day fallback.
    """
    excluded_words = (
        "race",
        "parkrun",
        "threshold",
        "tempo",
        "interval",
        "reps",
        "fartlek",
        "track",
        "vo2",
        "hill reps",
    )

    def candidates(window_days):
        values = []

        for row in rows:
            activity_date = _as_date(row[2])

            if activity_date is None:
                continue

            age_days = (reference_date - activity_date).days

            if age_days < 0 or age_days > window_days:
                continue

            title = (row[3] or "").lower()

            if any(word in title for word in excluded_words):
                continue

            distance_km = (
                float(row[5]) if row[5] is not None else None
            )
            moving_time_s = (
                float(row[6]) if row[6] is not None else None
            )
            elapsed_time_s = (
                float(row[7]) if row[7] is not None else None
            )
            avg_hr = float(row[8]) if row[8] is not None else None
            lt1_hr = float(row[16]) if row[16] is not None else None

            if (
                distance_km is None
                or moving_time_s is None
                or distance_km < 4.0
                or distance_km > 20.0
                or moving_time_s < 1200
                or moving_time_s > 9000
            ):
                continue

            if elapsed_time_s and elapsed_time_s > 0:
                moving_ratio = moving_time_s / elapsed_time_s
                if moving_ratio < 0.95:
                    continue

            if avg_hr and lt1_hr and avg_hr > lt1_hr * 0.95:
                continue

            pace = moving_time_s / distance_km

            if 240 <= pace <= 420:
                values.append(pace)

        return values

    values = candidates(180)

    if len(values) < 8:
        values = candidates(365)

    if len(values) < 4:
        return None, len(values)

    return round(median(values), 1), len(values)


def _explicit_workout_title(title: str) -> bool:
    value = (title or "").lower()
    words = (
        "threshold",
        "tempo",
        "interval",
        "intervals",
        "reps",
        "fartlek",
        "hill",
        "track",
        "vo2",
        "cruise",
        "session",
    )
    return any(word in value for word in words)


def _programmed_structure_evidence(workout) -> bool:
    """
    Accept programmed-watch sessions without manual boundary fragments.

    Clear recorded recoveries, mixed work families or several alternating
    work segments can establish a workout independently of lap/stop artefacts.
    """
    data = workout.recognition_json
    recoveries = data.get("recovery_splits", [])
    boundaries = data.get("boundary_splits", [])
    unknown_recoveries = data.get("unknown_recovery_count", 0) or 0

    if recoveries:
        return True

    if boundaries or unknown_recoveries:
        return True

    if workout.workout_type == "Mixed interval session":
        return workout.rep_count >= 3

    return (
        workout.rep_count >= 3
        and workout.workout_type
        in {
            "Short intervals",
            "Long intervals",
            "Mile repetitions",
            "Long threshold repetitions",
        }
    )


def _trust_score(session, workout, activity_date, reference_date) -> float:
    age_days = (
        max((reference_date - activity_date).days, 0)
        if activity_date
        else RECENT_WINDOW_DAYS
    )
    recency = max(0.0, 1.0 - age_days / RECENT_WINDOW_DAYS)

    execution = (
        workout.execution_score / 100.0
        if workout.execution_score is not None
        else 0.50
    )

    structure_bonus = 0.0
    data = workout.recognition_json

    if data.get("recovery_splits"):
        structure_bonus += 0.05
    if data.get("boundary_splits"):
        structure_bonus += 0.03
    if workout.workout_type == "Mixed interval session":
        structure_bonus += 0.03

    score = (
        session.confidence * 25.0
        + workout.confidence * 30.0
        + execution * 25.0
        + recency * 20.0
        + structure_bonus * 100.0
    )

    return min(round(score, 1), 100.0)


def _reason_for_trust(item) -> list[str]:
    session = item["session"]
    workout = item["workout"]
    reasons = [
        f"Session classification {session.confidence:.0%}",
        f"Workout recognition {workout.confidence:.0%}",
    ]

    if workout.execution_score is not None:
        reasons.append(f"Execution {workout.execution_score:.0f}/100")

    data = workout.recognition_json

    if data.get("recovery_splits"):
        reasons.append("Recorded work/recovery structure")
    elif data.get("boundary_splits"):
        reasons.append("Manual lap/stop boundary pattern")
    elif workout.rep_count >= 3:
        reasons.append("Repeated programmed work pattern")

    return reasons


def _comparable(reference, candidate) -> bool:
    ref_workout = reference["workout"]
    candidate_workout = candidate["workout"]

    if ref_workout.workout_type != candidate_workout.workout_type:
        return False

    ref_distance = ref_workout.average_rep_distance_km
    candidate_distance = candidate_workout.average_rep_distance_km

    if not ref_distance or not candidate_distance:
        return False

    tolerance = max(ref_distance * 0.20, 0.08)
    return abs(candidate_distance - ref_distance) <= tolerance


def _trend(comparable_items) -> dict:
    usable = [
        item
        for item in comparable_items
        if item["workout"].average_rep_pace_s_per_km is not None
    ]

    if len(usable) < 3:
        return {
            "label": "Not enough comparable sessions",
            "confidence": "Limited",
            "change_seconds_per_km": None,
            "sample_size": len(usable),
        }

    ordered = sorted(
        usable,
        key=lambda item: item["activity_date"] or datetime.date.min,
        reverse=True,
    )

    split_at = max(1, min(2, len(ordered) // 2))
    recent = ordered[:split_at]
    earlier = ordered[split_at:]

    if not earlier:
        return {
            "label": "Not enough comparable sessions",
            "confidence": "Limited",
            "change_seconds_per_km": None,
            "sample_size": len(usable),
        }

    recent_pace = mean(
        item["workout"].average_rep_pace_s_per_km
        for item in recent
    )
    earlier_pace = mean(
        item["workout"].average_rep_pace_s_per_km
        for item in earlier
    )
    change = earlier_pace - recent_pace

    if change >= 4.0:
        label = "Improving"
    elif change <= -4.0:
        label = "Declining"
    else:
        label = "Stable"

    confidence = "Strong" if len(usable) >= 5 else "Moderate"

    return {
        "label": label,
        "confidence": confidence,
        "change_seconds_per_km": round(change, 1),
        "recent_pace_seconds_per_km": round(recent_pace, 1),
        "earlier_pace_seconds_per_km": round(earlier_pace, 1),
        "sample_size": len(usable),
    }


GOAL_DISTANCES_KM = (5.0, 10.0, 16.09344, 21.0975, 42.195)

# Convert average work-rep pace into estimated ideal-condition race pace.
# Values above 1.0 mean the race pace is expected to be slower than rep pace.
WORKOUT_RACE_FACTORS = {
    "Short intervals": {
        5.0: 1.08,
        10.0: 1.16,
        16.09344: 1.23,
        21.0975: 1.28,
        42.195: 1.43,
    },
    "Long intervals": {
        5.0: 1.02,
        10.0: 1.08,
        16.09344: 1.14,
        21.0975: 1.18,
        42.195: 1.31,
    },
    "Mile repetitions": {
        5.0: 0.99,
        10.0: 1.04,
        16.09344: 1.09,
        21.0975: 1.13,
        42.195: 1.25,
    },
    "Long threshold repetitions": {
        5.0: 0.94,
        10.0: 0.98,
        16.09344: 1.02,
        21.0975: 1.05,
        42.195: 1.16,
    },
    "Continuous sustained effort": {
        5.0: 0.93,
        10.0: 0.97,
        16.09344: 1.01,
        21.0975: 1.04,
        42.195: 1.15,
    },
    "Mixed interval session": {
        5.0: 1.01,
        10.0: 1.07,
        16.09344: 1.13,
        21.0975: 1.18,
        42.195: 1.31,
    },
    "Structured workout": {
        5.0: 1.01,
        10.0: 1.07,
        16.09344: 1.13,
        21.0975: 1.18,
        42.195: 1.31,
    },
}


def _nearest_goal_distance(distance_km: float) -> float:
    return min(
        GOAL_DISTANCES_KM,
        key=lambda value: abs(value - distance_km),
    )


def _prediction_factor(
    workout_type: str,
    goal_distance_km: float,
) -> float:
    factors = WORKOUT_RACE_FACTORS.get(
        workout_type,
        WORKOUT_RACE_FACTORS["Structured workout"],
    )
    nearest = _nearest_goal_distance(goal_distance_km)
    return factors[nearest]


def _work_splits(workout) -> list[dict]:
    return [
        split
        for split in workout.recognition_json.get("work_splits", [])
        if float(split.get("distance_km") or 0.0) > 0
        and float(split.get("duration_s") or 0.0) > 0
    ]


def _total_work_distance_km(workout) -> float:
    return sum(
        float(split.get("distance_km") or 0.0)
        for split in _work_splits(workout)
    )


def _group_work_components(
    workout,
    raw_json_text: str | None = None,
    easy_pace_s_per_km: float | None = None,
) -> tuple[list[dict], dict]:
    phase_result = reconstruct_workout_phases(
        raw_json_text,
        easy_pace_s_per_km=easy_pace_s_per_km,
    )
    components = []

    for phase in phase_result.phases:
        if phase.phase_type not in {
            "threshold",
            "long_intervals",
            "short_intervals",
        }:
            continue

        components.append(
            {
                "component_type": phase.phase_type,
                "label": phase.label,
                "rep_count": phase.rep_count,
                "average_rep_distance_km": (
                    phase.average_rep_distance_km
                    or (
                        phase.distance_km / phase.rep_count
                        if phase.rep_count
                        else phase.distance_km
                    )
                ),
                "total_work_distance_km": phase.distance_km,
                "average_pace_s_per_km": phase.pace_s_per_km,
                "recovery_duration_s": phase.recovery_duration_s,
                "source": phase.source,
                "confidence": phase.confidence,
            }
        )

    if components:
        return components, {
            "source": phase_result.source,
            "confidence": phase_result.confidence,
            "summary": phase_result.summary,
            "reasons": list(phase_result.reasons),
            "limitations": list(phase_result.limitations),
            "phases": phases_to_dicts(phase_result),
        }

    # Conservative fallback to the legacy component grouping.
    splits = sorted(
        _work_splits(workout),
        key=lambda split: float(split.get("distance_km") or 0.0),
    )
    families: list[list[dict]] = []

    for split in splits:
        distance = float(split["distance_km"])
        placed = False

        for family in families:
            centre = mean(
                float(item["distance_km"])
                for item in family
            )
            tolerance = max(centre * 0.18, 0.07)

            if abs(distance - centre) <= tolerance:
                family.append(split)
                placed = True
                break

        if not placed:
            families.append([split])

    for family in families:
        total_distance = sum(
            float(split["distance_km"])
            for split in family
        )
        total_time = sum(
            float(split["duration_s"])
            for split in family
        )

        if total_distance <= 0 or total_time <= 0:
            continue

        average_distance = total_distance / len(family)

        if average_distance >= 1.20:
            component_type = "threshold"
            label = "Long threshold blocks"
        elif average_distance >= 0.65:
            component_type = "long_intervals"
            label = "Long intervals"
        elif average_distance >= 0.25:
            component_type = "short_intervals"
            label = "Short intervals"
        else:
            continue

        components.append(
            {
                "component_type": component_type,
                "label": label,
                "rep_count": len(family),
                "average_rep_distance_km": round(
                    average_distance,
                    3,
                ),
                "total_work_distance_km": round(
                    total_distance,
                    3,
                ),
                "average_pace_s_per_km": round(
                    total_time / total_distance,
                    1,
                ),
                "recovery_duration_s": None,
                "source": "legacy_csv_fallback",
                "confidence": 0.55,
            }
        )

    return components, {
        "source": "legacy_csv_fallback",
        "confidence": 0.55,
        "summary": "Legacy component grouping",
        "reasons": [],
        "limitations": [
            "The phase engine could not reconstruct a complete workout."
        ],
        "phases": [],
    }


COMPONENT_FACTORS = {
    "threshold": {
        5.0: 0.94,
        10.0: 0.98,
        16.09344: 1.02,
        21.0975: 1.05,
        42.195: 1.16,
    },
    "long_intervals": {
        5.0: 1.00,
        10.0: 1.05,
        16.09344: 1.10,
        21.0975: 1.14,
        42.195: 1.27,
    },
    "short_intervals": {
        5.0: 1.04,
        10.0: 1.10,
        16.09344: 1.17,
        21.0975: 1.22,
        42.195: 1.38,
    },
    "strides": {
        5.0: 1.10,
        10.0: 1.20,
        16.09344: 1.28,
        21.0975: 1.34,
        42.195: 1.50,
    },
}


def _component_prediction(
    component: dict,
    goal_distance_km: float,
) -> dict:
    goal_key = _nearest_goal_distance(goal_distance_km)
    factor = COMPONENT_FACTORS[
        component["component_type"]
    ][goal_key]

    predicted_seconds = (
        component["average_pace_s_per_km"]
        * factor
        * goal_distance_km
    )

    volume_target = {
        "threshold": min(max(goal_distance_km * 0.25, 2.5), 8.0),
        "long_intervals": min(max(goal_distance_km * 0.20, 2.5), 7.0),
        "short_intervals": min(max(goal_distance_km * 0.12, 2.0), 5.0),
        "strides": 2.0,
    }[component["component_type"]]

    volume_quality = min(
        component["total_work_distance_km"] / volume_target,
        1.0,
    )

    type_quality = {
        "threshold": 1.00,
        "long_intervals": 0.90,
        "short_intervals": 0.82,
        "strides": 0.45,
    }[component["component_type"]]

    quality = (
        volume_quality * 0.55
        + type_quality * 0.45
    )

    return {
        **component,
        "factor": round(factor, 3),
        "predicted_seconds": round(predicted_seconds, 1),
        "quality": round(quality, 4),
    }


def _workout_prediction_quality(item, goal_distance_km: float) -> float:
    workout = item["workout"]
    execution = (
        workout.execution_score / 100.0
        if workout.execution_score is not None
        else 0.55
    )

    components, phase_metadata = _group_work_components(
        workout,
        item.get("raw_json_text"),
        item.get("easy_pace_s_per_km"),
    )

    if components:
        component_quality = max(
            _component_prediction(
                component,
                goal_distance_km,
            )["quality"]
            for component in components
        )
    else:
        component_quality = 0.40

    return max(
        0.20,
        min(
            workout.confidence * 0.35
            + execution * 0.25
            + component_quality * 0.40,
            1.0,
        ),
    )


def _predict_from_workout(item, goal_distance_km: float) -> dict | None:
    workout = item["workout"]
    components, phase_metadata = _group_work_components(
        workout,
        item.get("raw_json_text"),
        item.get("easy_pace_s_per_km"),
    )

    if not components:
        rep_pace = workout.average_rep_pace_s_per_km

        if rep_pace is None or rep_pace <= 0:
            return None

        factor = _prediction_factor(
            workout.workout_type,
            goal_distance_km,
        )
        component_estimates = [
            {
                "component_type": "generic",
                "label": workout.workout_type,
                "rep_count": workout.rep_count,
                "average_rep_distance_km":
                    workout.average_rep_distance_km,
                "total_work_distance_km":
                    _total_work_distance_km(workout),
                "average_pace_s_per_km": round(rep_pace, 1),
                "factor": round(factor, 3),
                "predicted_seconds": round(
                    rep_pace * factor * goal_distance_km,
                    1,
                ),
                "quality": 0.55,
            }
        ]
    else:
        component_estimates = [
            _component_prediction(
                component,
                goal_distance_km,
            )
            for component in components
            if component["component_type"] != "strides"
        ]

    if not component_estimates:
        return None

    total_component_weight = sum(
        component["quality"]
        * max(component["total_work_distance_km"], 0.5)
        for component in component_estimates
    )

    if total_component_weight <= 0:
        return None

    predicted_seconds = sum(
        component["predicted_seconds"]
        * component["quality"]
        * max(component["total_work_distance_km"], 0.5)
        for component in component_estimates
    ) / total_component_weight

    quality = _workout_prediction_quality(
        item,
        goal_distance_km,
    )

    component_summary = " + ".join(
        f"{component['rep_count']} x "
        f"{component['average_rep_distance_km']:.2f} km "
        f"{component['label'].lower()}"
        for component in component_estimates
    )

    return {
        "activity_id": item["session"].activity_id,
        "date": (
            item["session"].activity_date[:10]
            if item["session"].activity_date
            else "Unknown"
        ),
        "title": item["session"].title,
        "description": workout.description,
        "workout_type": workout.workout_type,
        "component_summary": component_summary,
        "components": component_estimates,
        "phase_engine": phase_metadata,
        "predicted_seconds": round(predicted_seconds, 1),
        "quality": round(quality, 4),
        "trust_score": item["trust_score"],
        "work_distance_km": round(
            _total_work_distance_km(workout),
            2,
        ),
    }


def _combine_workout_predictions(
    items,
    goal_distance_km: float | None,
) -> dict | None:
    if not goal_distance_km or goal_distance_km <= 0:
        return None

    estimates = []

    for item in items:
        estimate = _predict_from_workout(item, goal_distance_km)
        if estimate is None:
            continue

        # Trust chooses representative workouts; prediction quality judges
        # whether that workout can estimate the selected race distance.
        weight = (
            max(item["trust_score"], 1.0) / 100.0
            * estimate["quality"]
        )
        estimate["weight"] = round(weight, 4)
        estimates.append(estimate)

    if not estimates:
        return None

    total_weight = sum(item["weight"] for item in estimates)

    if total_weight <= 0:
        return None

    central = sum(
        item["predicted_seconds"] * item["weight"]
        for item in estimates
    ) / total_weight

    weighted_variance = sum(
        item["weight"]
        * math.pow(item["predicted_seconds"] - central, 2)
        for item in estimates
    ) / total_weight
    disagreement_s = math.sqrt(max(weighted_variance, 0.0))

    average_quality = sum(
        item["quality"] * item["weight"]
        for item in estimates
    ) / total_weight

    sample_factor = min(len(estimates) / TOP_EVIDENCE_COUNT, 1.0)
    disagreement_factor = max(
        0.35,
        1.0 - disagreement_s / max(central * 0.05, 1.0),
    )

    confidence = min(
        0.90,
        average_quality * 0.65
        + sample_factor * 0.20
        + disagreement_factor * 0.15,
    )

    # Range reflects both model uncertainty and disagreement between sessions.
    uncertainty_fraction = max(
        0.012,
        (1.0 - confidence) * 0.055,
    )
    half_range = max(
        central * uncertainty_fraction,
        disagreement_s * 0.75,
        8.0,
    )

    return {
        "central_seconds": round(central, 1),
        "low_seconds": round(max(central - half_range, 1.0), 1),
        "high_seconds": round(central + half_range, 1),
        "confidence": round(confidence, 4),
        "goal_distance_km": round(goal_distance_km, 4),
        "disagreement_seconds": round(disagreement_s, 1),
        "estimate_count": len(estimates),
        "estimates": estimates,
        "conditions": "Ideal, flat conditions",
        "model_version": 2,
    }


WORKOUT_LIBRARY_DECODER_VERSION = 1


def _workout_signature(
    phase_metadata: dict,
    workout_type: str,
) -> str:
    """
    Create a stable, human-readable workout fingerprint.

    Examples:
        threshold_1-short_intervals_10
        long_intervals_5
    """
    parts = []

    for phase in phase_metadata.get("phases", []):
        phase_type = str(phase.get("phase_type") or "unknown")
        if phase_type in {"warmup", "cooldown", "recovery"}:
            continue

        rep_count = int(phase.get("rep_count") or 1)
        average_distance = phase.get("average_rep_distance_km")

        if average_distance is not None:
            distance_m = int(round(float(average_distance) * 1000 / 25) * 25)
            parts.append(f"{phase_type}_{rep_count}x{distance_m}m")
        else:
            parts.append(f"{phase_type}_{rep_count}")

    if not parts:
        safe_type = (
            (workout_type or "structured_workout")
            .strip()
            .lower()
            .replace(" ", "_")
        )
        parts.append(safe_type)

    return "-".join(parts)


class WorkoutEvidenceProvider(EvidenceProvider):
    key = "workout"
    title = "Workout Coach"

    def build(self, context: EvidenceContext) -> EvidenceItem:
        conn = get_connection()
        cursor = conn.cursor()

        sport_roles = get_athlete_sport_roles(context.athlete_id)
        running_ids = [
            sport_id
            for sport_id, role in sport_roles.items()
            if role == "running"
        ]

        if not running_ids:
            conn.close()
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary="No running sport mapping is available.",
                status=EvidenceStatus.BUILDING,
                confidence=0.15,
                sample_size=0,
                predicted_seconds=None,
                weight=0.0,
                metadata={
                    "limitations": [
                        "Workout Coach cannot inspect activities until the "
                        "athlete's running sport is identified."
                    ]
                },
            )

        placeholders = ",".join("?" for _ in running_ids)

        cursor.execute(
            f"""
            SELECT
                a.id,
                a.athlete_id,
                a.activity_date,
                a.title,
                a.sport_id,
                a.distance_m,
                a.moving_time_s,
                a.elapsed_time_s,
                a.avg_hr,
                a.max_hr,
                a.elevation_up_m,
                a.temperature_c,
                a.humidity,
                a.wind_speed,
                a.route_name,
                a.raw_json,
                at.lt1_hr,
                at.lt2_hr,
                at.max_hr
            FROM activities a
            JOIN athletes at ON at.id = a.athlete_id
            WHERE a.athlete_id = ?
              AND CAST(a.sport_id AS TEXT) IN ({placeholders})
              AND a.raw_json IS NOT NULL
            ORDER BY a.activity_datetime DESC
            """,
            (context.athlete_id, *running_ids),
        )

        rows = cursor.fetchall()
        conn.close()

        reference_date = max(
            (
                _as_date(row[2])
                for row in rows
                if _as_date(row[2]) is not None
            ),
            default=datetime.date.today(),
        )

        easy_pace_s_per_km, easy_pace_sample_size = (
            _estimate_easy_pace(rows, reference_date)
        )

        session_counts = Counter()
        candidates = []
        library_records_written = 0
        library_write_errors = 0

        for row in rows:
            facts = ActivityFacts(
                activity_id=row[0],
                athlete_id=row[1],
                activity_date=row[2],
                title=row[3] or "Activity",
                sport_id=str(row[4]) if row[4] is not None else None,
                distance_km=float(row[5]) if row[5] is not None else None,
                moving_time_s=float(row[6]) if row[6] is not None else None,
                elapsed_time_s=float(row[7]) if row[7] is not None else None,
                avg_hr=float(row[8]) if row[8] is not None else None,
                max_hr=float(row[9]) if row[9] is not None else None,
                elevation_up_m=(
                    float(row[10]) if row[10] is not None else None
                ),
                temperature_c=(
                    float(row[11]) if row[11] is not None else None
                ),
                humidity=float(row[12]) if row[12] is not None else None,
                wind_speed=float(row[13]) if row[13] is not None else None,
                route_name=row[14],
                raw_json_text=row[15],
                athlete_lt2_hr=(
                    float(row[17]) if row[17] is not None else None
                ),
                athlete_max_hr=(
                    float(row[18]) if row[18] is not None else None
                ),
            )

            session = classify_session(facts)
            session_counts[session.session_type.value] += 1

            workout = get_or_decode_workout(row[0], row[15])

            if workout.workout_type in ("No split data", "Unclassified"):
                continue

            accepted = (
                session.session_type == SessionType.STRUCTURED_WORKOUT
                or _explicit_workout_title(session.title)
                or _programmed_structure_evidence(workout)
            )

            if not accepted:
                continue

            activity_date = _as_date(session.activity_date)
            item = {
                "session": session,
                "workout": workout,
                "activity_date": activity_date,
                "raw_json_text": row[15],
                "easy_pace_s_per_km": easy_pace_s_per_km,
            }

            phase_components, phase_metadata = _group_work_components(
                workout,
                row[15],
                easy_pace_s_per_km,
            )
            item["phase_components"] = phase_components
            item["phase_metadata"] = phase_metadata

            try:
                upsert_workout(
                    activity_id=session.activity_id,
                    athlete_id=session.athlete_id,
                    activity_date=(
                        session.activity_date[:10]
                        if session.activity_date
                        else None
                    ),
                    session_type=(
                        workout.workout_type
                        or session.session_type.value
                    ),
                    workout_signature=_workout_signature(
                        phase_metadata,
                        workout.workout_type,
                    ),
                    phases=phase_metadata.get("phases", []),
                    execution_score=workout.execution_score,
                    recognition_confidence=workout.confidence,
                    phase_confidence=float(
                        phase_metadata.get("confidence") or 0.0
                    ),
                    source=str(
                        phase_metadata.get("source")
                        or "runalyze_csv"
                    ),
                    decoder_version=WORKOUT_LIBRARY_DECODER_VERSION,
                )
                library_records_written += 1
            except Exception:
                # Library persistence must never stop the coach from working.
                library_write_errors += 1

            item["trust_score"] = _trust_score(
                session,
                workout,
                activity_date,
                reference_date,
            )
            item["trust_reasons"] = _reason_for_trust(item)
            candidates.append(item)

        try:
            race_link_summary = refresh_workout_race_links(
                context.athlete_id
            )
        except Exception:
            race_link_summary = None

        if not candidates:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary=(
                    "No confidently recognised workout was found. "
                    "Continuous auto-lap runs were excluded."
                ),
                status=EvidenceStatus.BUILDING,
                confidence=0.25,
                sample_size=0,
                predicted_seconds=None,
                weight=0.0,
                metadata={
                    "session_counts": dict(session_counts),
                    "limitations": [
                        "Programmed sessions require alternating work/recovery "
                        "or another clear repeated work pattern.",
                        "Some workouts may need richer FIT workout-step data.",
                    ],
                },
            )

        chronological = sorted(
            candidates,
            key=lambda item: item["activity_date"] or datetime.date.min,
            reverse=True,
        )
        latest = chronological[0]

        recent_candidates = [
            item
            for item in candidates
            if item["activity_date"] is not None
            and (reference_date - item["activity_date"]).days
            <= RECENT_WINDOW_DAYS
        ] or candidates

        strongest = sorted(
            recent_candidates,
            key=lambda item: item["trust_score"],
            reverse=True,
        )[:TOP_EVIDENCE_COUNT]

        best = strongest[0]

        try:
            historical_similarity = find_similar_linked_workouts(
                athlete_id=context.athlete_id,
                current_activity_id=best["session"].activity_id,
                limit=10,
            )
            historical_similarity_metadata = (
                similarity_result_to_dict(historical_similarity)
            )
        except Exception as error:
            historical_similarity_metadata = {
                "match_count": 0,
                "linked_history_count": 0,
                "confidence": 0.0,
                "matches": [],
                "limitations": [
                    "Historical similarity could not be calculated: "
                    f"{type(error).__name__}"
                ],
            }

        goal = context.goal or {}
        goal_distance_km = (
            float(goal["distance_m"]) / 1000.0
            if goal.get("distance_m")
            else None
        )
        workout_prediction = _combine_workout_predictions(
            strongest,
            goal_distance_km,
        )

        comparable = [
            item for item in recent_candidates if _comparable(best, item)
        ]
        trend = _trend(comparable)

        latest_is_representative = (
            latest["trust_score"] >= best["trust_score"] - 10.0
            and _comparable(best, latest)
        )

        warning = None
        if not latest_is_representative:
            warning = (
                "The latest workout is not the strongest representation of "
                "current fitness, so Workout Coach is placing more weight on "
                "earlier high-quality sessions."
            )

        latest_session = latest["session"]
        latest_workout = latest["workout"]
        best_session = best["session"]
        best_workout = best["workout"]

        summary_parts = [
            f"Latest session: {latest_workout.description} on "
            f"{(latest_session.activity_date or 'unknown')[:10]}.",
            f"Best current evidence: {best_workout.description} on "
            f"{(best_session.activity_date or 'unknown')[:10]}.",
        ]

        if trend["label"] != "Not enough comparable sessions":
            summary_parts.append(
                f"Recent comparable trend: {trend['label'].lower()} across "
                f"{trend['sample_size']} session(s)."
            )
        else:
            summary_parts.append(
                "There are not yet enough directly comparable workouts for "
                "a reliable trend."
            )

        if workout_prediction:
            summary_parts.append(
                f"Workout-derived goal prediction: "
                f"{int(round(workout_prediction['central_seconds'] // 60))}:"
                f"{int(round(workout_prediction['central_seconds'] % 60)):02d} "
                f"under ideal, flat conditions."
            )

        if warning:
            summary_parts.append(warning)

        top_workouts = []
        for rank, item in enumerate(strongest, start=1):
            session = item["session"]
            workout = item["workout"]
            top_workouts.append(
                {
                    "rank": rank,
                    "activity_id": session.activity_id,
                    "date": (
                        session.activity_date[:10]
                        if session.activity_date
                        else "Unknown"
                    ),
                    "title": session.title,
                    "workout_type": workout.workout_type,
                    "description": workout.description,
                    "trust_score": item["trust_score"],
                    "execution_score": workout.execution_score,
                    "recognition_confidence": workout.confidence,
                    "session_confidence": session.confidence,
                    "average_rep_pace_s_per_km":
                        workout.average_rep_pace_s_per_km,
                    "trust_reasons": item["trust_reasons"],
                }
            )

        recognition_confidence = min(
            0.96,
            (
                best["session"].confidence * 0.35
                + best["workout"].confidence * 0.40
                + min(len(strongest) / TOP_EVIDENCE_COUNT, 1.0) * 0.25
            ),
        )

        prediction_confidence = (
            workout_prediction["confidence"]
            if workout_prediction
            else 0.0
        )

        confidence = (
            min(recognition_confidence, prediction_confidence)
            if workout_prediction
            else recognition_confidence
        )

        strengths = [
            f"{len(candidates)} recognised workout(s) in the athlete history",
            f"Strongest {len(strongest)} recent workout(s) were ranked by "
            "recency, structure, recognition and execution",
            f"Best evidence trust score {best['trust_score']:.0f}/100",
        ]

        if latest_is_representative:
            strengths.append("Latest workout is representative of current evidence")

        limitations = [
            "Trends compare only sessions with similar workout type and rep distance.",
            "Runalyze CSV splits do not contain full lap-level heart rate or power.",
            "Warm-up, cool-down and recovery splits are excluded from "
            "work pace when they are within 12% of the athlete's current "
            "easy pace.",
            "Remaining faster splits are grouped by similar distance before "
            "threshold, long-interval and short-interval predictions are combined.",
            "Transparent component conversion factors are still less reliable "
            "than a recent genuine race and therefore carry lower weight.",
            "The current estimate represents ideal, flat conditions; scenario "
            "forecasts for heat, hills and trails will be added separately.",
        ]

        if warning:
            limitations.append(warning)

        return EvidenceItem(
            key=self.key,
            title=self.title,
            summary=" ".join(summary_parts),
            status=EvidenceStatus.AVAILABLE,
            confidence=confidence,
            sample_size=len(candidates),
            predicted_seconds=(
                workout_prediction["central_seconds"]
                if workout_prediction
                else None
            ),
            weight=0.65 if workout_prediction else 0.0,
            metadata={
                "activity_id": latest_session.activity_id,
                "activity_date": latest_session.activity_date,
                "selected_title": latest_session.title,
                "workout_type": latest_workout.workout_type,
                "description": latest_workout.description,
                "execution_score": latest_workout.execution_score,
                "rep_count": latest_workout.rep_count,
                "average_rep_distance_km":
                    latest_workout.average_rep_distance_km,
                "average_rep_pace_s_per_km":
                    latest_workout.average_rep_pace_s_per_km,
                "rep_pace_variation_percent":
                    latest_workout.rep_pace_variation_percent,
                "workout_json": latest_workout.recognition_json,
                "latest_workout": {
                    "date": (
                        latest_session.activity_date[:10]
                        if latest_session.activity_date
                        else "Unknown"
                    ),
                    "title": latest_session.title,
                    "description": latest_workout.description,
                    "trust_score": latest["trust_score"],
                    "representative": latest_is_representative,
                },
                "easy_pace_filter": {
                    "easy_pace_s_per_km": easy_pace_s_per_km,
                    "sample_size": easy_pace_sample_size,
                    "work_cutoff_ratio": 0.88,
                    "work_cutoff_s_per_km": (
                        easy_pace_s_per_km * 0.88
                        if easy_pace_s_per_km is not None
                        else None
                    ),
                },
                "workout_phases": best.get("phase_metadata", {}),
                "best_evidence": {
                    "date": (
                        best_session.activity_date[:10]
                        if best_session.activity_date
                        else "Unknown"
                    ),
                    "title": best_session.title,
                    "description": best_workout.description,
                    "trust_score": best["trust_score"],
                },
                "top_workouts": top_workouts,
                "workout_prediction": workout_prediction,
                "historical_similarity":
                    historical_similarity_metadata,
                "prediction_confidence": prediction_confidence,
                "recognition_confidence": recognition_confidence,
                "trend": trend,
                "latest_not_representative": not latest_is_representative,
                "representative_warning": warning,
                "recognised_workout_count": len(candidates),
                "workout_library": {
                    "records_written": library_records_written,
                    "write_errors": library_write_errors,
                    "decoder_version": WORKOUT_LIBRARY_DECODER_VERSION,
                },
                "workout_race_links": (
                    {
                        "workout_count":
                            race_link_summary.workout_count,
                        "race_candidate_count":
                            race_link_summary.race_candidate_count,
                        "links_written":
                            race_link_summary.links_written,
                        "links_deleted":
                            race_link_summary.links_deleted,
                        "errors": race_link_summary.errors,
                    }
                    if race_link_summary is not None
                    else None
                ),
                "session_counts": dict(session_counts),
                "strengths": strengths,
                "limitations": limitations,
            },
        )

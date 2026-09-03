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

from core.activity_reliability import has_reliable_distance_and_pace
from core.database import (
    get_athlete_sport_roles,
    get_connection,
    get_effective_activity_heart_rate,
)
from core.distance_calibration import (
    build_personal_pb_shape_bridge,
    personal_pb_shape_bridge_to_dict,
)
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider
from core.pb_shape import build_pb_shape, pb_shape_to_dict
from core.race_detection import score_race_evidence
from core.session import SessionType
from core.session_intelligence import ActivityFacts, classify_session
from core.workout_dna import build_workout_dna, workout_dna_to_dict
from core.workout_library import upsert_workout
from core.workout_similarity import (
    find_similar_linked_workouts,
    predict_from_similarity,
    similarity_result_to_dict,
)
from core.workout_race_linker import refresh_workout_race_links
from core.workout_phases import (
    phases_to_dicts,
    reconstruct_workout_phases,
)
from core.workouts import get_or_decode_workout
from core.workout_title_intent import build_title_intent_evidence, parse_workout_title


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

    if "parkrun" in value or "race" in value:
        return False

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



def _is_race_quality_session(facts: ActivityFacts) -> bool:
    """
    Keep genuine races and race-quality efforts out of Workout Coach.

    A race can contain split patterns that look like repetitions. Race intent
    belongs to Race Coach; Workout Coach should only learn from training
    sessions.
    """
    raw = {}

    try:
        import json
        raw = json.loads(facts.raw_json_text or "{}")
    except Exception:
        raw = {}

    signals = score_race_evidence(
        title=facts.title or "",
        distance_km=facts.distance_km,
        moving_time_s=facts.moving_time_s,
        elapsed_time_s=facts.elapsed_time_s,
        avg_hr=facts.avg_hr,
        max_hr=facts.max_hr,
        athlete_lt2_hr=facts.athlete_lt2_hr,
        athlete_max_hr=facts.athlete_max_hr,
        official_race_name=raw.get("race_name"),
        official_distance_m=raw.get("race_officialDistance"),
        official_time_s=raw.get("race_officialTime"),
        officially_measured=bool(
            raw.get("race_officiallyMeasured")
        ),
    )

    return signals.classification in {
        "confirmed_race",
        "race_quality_effort",
    }




def _obvious_continuous_run(
    facts: ActivityFacts,
    workout,
    title_intent,
) -> bool:
    """
    Reject auto-lapped continuous runs that happen to look like repetitions.

    A 12-mile SLR naturally contains twelve one-mile auto-laps. With no
    recovery/boundary pattern and a clear continuous-run title, those laps are
    not twelve work reps.
    """
    if title_intent is not None:
        return False

    title = (facts.title or "").lower()
    continuous_words = (
        "long run",
        "slr",
        "recovery",
        "easy run",
        "easy ",
        "aerobic",
        "steady run",
    )

    named_continuous = any(word in title for word in continuous_words)
    titleless_easy_long = (
        facts.distance_km is not None
        and facts.distance_km >= 4.0
        and facts.avg_hr is not None
        and facts.athlete_lt1_hr is not None
        and facts.avg_hr <= facts.athlete_lt1_hr * (
            1.06 if facts.distance_km >= 12.0 else 0.98
        )
    )
    if not named_continuous and not titleless_easy_long:
        return False

    data = workout.recognition_json
    recovery_count = len(data.get("recovery_splits") or ())
    if recovery_count and (
        not titleless_easy_long
        or recovery_count >= max(2, int(workout.rep_count * 0.50))
    ):
        return False
    if data.get("boundary_splits") and not titleless_easy_long:
        return False
    if data.get("unknown_recovery_count") and not titleless_easy_long:
        return False

    # With clear continuous-run intent and no recovery/boundary structure,
    # repeated mile/kilometre laps are simply auto-laps. Do not require every
    # final partial lap to have been labelled "work" by the low-level decoder.
    return workout.rep_count >= 3


def _display_description(item) -> str:
    evidence = item.get("title_intent_evidence")
    if evidence:
        return str(evidence.get("display_description") or item["workout"].description)
    return item["workout"].description


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

    # Repeated equal-distance laps with no recovery/boundary evidence are most
    # often ordinary auto-laps (for example a 12-mile long run). They must not
    # establish a workout on their own. Explicit titles and the phase engine
    # are handled separately by the caller.
    return False


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
    title: str | None = None,
) -> tuple[list[dict], dict]:
    title_evidence = build_title_intent_evidence(
        title or "",
        raw_json_text,
    )

    if title_evidence is not None:
        components = [
            component
            for component in title_evidence["components"]
            if component.get("average_pace_s_per_km") is not None
        ]

        if components:
            return components, title_evidence["metadata"]

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

    recorded_recoveries = workout.recognition_json.get("recovery_splits") or []
    recorded_recovery_durations = [
        float(item.get("duration_s") or 0.0)
        for item in recorded_recoveries
        if float(item.get("duration_s") or 0.0) > 0
    ]
    supported_interval_structure = (
        workout.rep_count >= 3
        and len(recorded_recoveries) >= max(2, int((workout.rep_count - 1) * 0.60))
    )
    fallback_confidence = (
        min(max(float(workout.confidence or 0.0), 0.78), 0.93)
        if supported_interval_structure else 0.55
    )

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
        elif average_distance >= 0.16:
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
                "recovery_duration_s": (
                    round(float(median(recorded_recovery_durations)), 1)
                    if supported_interval_structure and recorded_recovery_durations
                    else None
                ),
                "source": (
                    "recorded_interval_recoveries" if supported_interval_structure
                    else "legacy_csv_fallback"
                ),
                "confidence": fallback_confidence,
            }
        )

    return components, {
        "source": (
            "recorded_interval_recoveries" if supported_interval_structure
            else "legacy_csv_fallback"
        ),
        "confidence": fallback_confidence,
        "summary": (
            "Repeated fast work with recorded slower recovery"
            if supported_interval_structure else "Legacy component grouping"
        ),
        "reasons": (
            [f"{workout.rep_count} repeated work reps were separated by "
             f"{len(recorded_recoveries)} recorded slower recoveries."]
            if supported_interval_structure else []
        ),
        "limitations": (
            [] if supported_interval_structure else
            ["The phase engine could not reconstruct a complete workout."]
        ),
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

    components = item.get("phase_components")
    phase_metadata = item.get("phase_metadata")

    if components is None or phase_metadata is None:
        components, phase_metadata = _group_work_components(
            workout,
            item.get("raw_json_text"),
            item.get("easy_pace_s_per_km"),
            item["session"].title,
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
    components = item.get("phase_components")
    phase_metadata = item.get("phase_metadata")

    if components is None or phase_metadata is None:
        components, phase_metadata = _group_work_components(
            workout,
            item.get("raw_json_text"),
            item.get("easy_pace_s_per_km"),
            item["session"].title,
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
        "description": _display_description(item),
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


def _distance_relevant_workout_prediction(
    *,
    candidate_workouts: list[dict],
    goal_distance_km: float | None,
    reference_date: datetime.date,
    similarity_prediction: dict | None,
    pb_shape_prediction: dict | None,
) -> dict | None:
    """Prevent short, controlled race histories dominating endurance goals.

    Workout similarity can be personally useful at 5K and 10K. A collection
    of old 5K park/trail runs is not comparable half-marathon evidence,
    however, even when the workouts preceding those runs looked similar.
    Longer goals therefore prefer recent, confidently decoded threshold and
    long-interval work whenever direct longer-race history is absent.
    """
    if goal_distance_km is None or goal_distance_km < 8.0:
        return None

    historical_outcomes = (
        similarity_prediction.get("outcomes", [])
        if similarity_prediction
        else []
    )
    representative_races = []
    for outcome in historical_outcomes:
        race_distance = float(outcome.get("race_distance_km") or 0.0)
        race_date = _as_date(outcome.get("race_date"))
        race_age = (
            (reference_date - race_date).days
            if race_date is not None
            else None
        )
        if (
            race_distance >= goal_distance_km * 0.60
            and race_age is not None
            and 0 <= race_age <= 365
        ):
            representative_races.append(outcome)

    unique_workouts = {
        int(item["session"].activity_id): item
        for item in candidate_workouts
    }
    estimates = []
    minimum_relevant_distance = min(
        max(goal_distance_km * (0.22 if goal_distance_km >= 15.0 else 0.18), 3.0),
        7.0,
    )

    for item in unique_workouts.values():
        activity_date = item.get("activity_date")
        if activity_date is None:
            continue
        age_days = (reference_date - activity_date).days
        if age_days < 0 or age_days > 120:
            continue

        estimate = _predict_from_workout(item, goal_distance_km)
        if estimate is None:
            continue
        relevant_components = [
            component
            for component in estimate.get("components", [])
            if component.get("component_type") in {"threshold", "long_intervals"}
            and float(component.get("confidence") or 0.0) >= 0.75
        ]
        if goal_distance_km < 15.0:
            # A 10K-specific override is earned only by a recent genuinely
            # repeated substantial session with recorded recoveries. This
            # prevents slow auto-laps and old controlled runs outvoting the
            # athlete's six real kilometre repetitions.
            relevant_components = [
                component for component in relevant_components
                if component.get("component_type") == "long_intervals"
                and int(component.get("rep_count") or 0) >= 4
                and float(component.get("average_rep_distance_km") or 0.0) >= 0.75
                and component.get("recovery_duration_s") is not None
            ]
            if age_days > 14:
                continue
        relevant_distance = sum(
            float(component.get("total_work_distance_km") or 0.0)
            for component in relevant_components
        )
        if relevant_distance < minimum_relevant_distance:
            continue

        component_weight = sum(
            max(float(component.get("quality") or 0.0), 0.10)
            * max(float(component.get("total_work_distance_km") or 0.0), 0.10)
            for component in relevant_components
        )
        if component_weight <= 0:
            continue
        component_estimates = []
        for component in relevant_components:
            predicted_seconds = float(component["predicted_seconds"])
            rep_distance = float(component.get("average_rep_distance_km") or 0.0)
            total_distance = float(component.get("total_work_distance_km") or 0.0)
            rep_count = int(component.get("rep_count") or 0)
            recovery = component.get("recovery_duration_s")
            pace = float(component.get("average_pace_s_per_km") or 0.0)
            rep_duration = pace * rep_distance
            recovery_ratio = (
                float(recovery) / rep_duration
                if recovery is not None and rep_duration > 0
                else None
            )

            if (
                goal_distance_km >= 15.0
                and
                component.get("component_type") == "long_intervals"
                and rep_distance >= 1.0
                and rep_count >= 4
                and total_distance >= goal_distance_km * 0.28
                and recovery_ratio is not None
                and recovery_ratio <= 0.40
            ):
                # Six substantial 1,200 m reps off short controlled rests
                # carry much stronger half-marathon evidence than the
                # generic long-interval factor assumes. Keep them out of
                # threshold pace, while calibrating their endurance value.
                endurance_factor = 1.07 + max(recovery_ratio - 0.30, 0.0) * 0.12
                predicted_seconds = pace * endurance_factor * goal_distance_km

            component_estimates.append(
                predicted_seconds
                * max(float(component.get("quality") or 0.0), 0.10)
                * max(total_distance, 0.10)
            )

        endurance_seconds = sum(component_estimates) / component_weight
        known_event_pb = (
            float(pb_shape_prediction.get("pb_time_s") or 0.0)
            if pb_shape_prediction else 0.0
        )
        if (
            goal_distance_km >= 15.0
            and known_event_pb > 0
            and endurance_seconds > known_event_pb * 1.13
        ):
            # Controlled auto-lap runs can resemble long threshold blocks.
            # They are not fitness evidence when they imply a result far
            # slower than the athlete's independently verified event PB.
            continue

        # Current fitness should materially outweigh older training rather
        # than treating a workout from weeks ago as effectively identical.
        recency_weight = max(0.45, math.pow(0.5, age_days / 45.0))
        coverage_weight = min(relevant_distance / (goal_distance_km * 0.35), 1.0)
        weight = (
            max(float(estimate.get("quality") or 0.0), 0.30)
            * max(float(item.get("trust_score") or 0.0) / 100.0, 0.40)
            * recency_weight
            * (0.60 + coverage_weight * 0.40)
        )
        estimates.append(
            {
                "activity_id": int(item["session"].activity_id),
                "date": activity_date.isoformat(),
                "title": item["session"].title,
                "predicted_seconds": round(endurance_seconds, 1),
                "relevant_work_distance_km": round(relevant_distance, 2),
                "component_types": sorted(
                    {component["component_type"] for component in relevant_components}
                ),
                "age_days": age_days,
                "weight": round(weight, 4),
            }
        )

    if not estimates:
        return None

    total_weight = sum(estimate["weight"] for estimate in estimates)
    central = sum(
        estimate["predicted_seconds"] * estimate["weight"]
        for estimate in estimates
    ) / total_weight

    known_pb_seconds = (
        float(pb_shape_prediction.get("pb_time_s") or 0.0)
        if pb_shape_prediction
        else 0.0
    )
    pb_anchor_used = (
        known_pb_seconds > 0
        and abs(central - known_pb_seconds) / known_pb_seconds <= 0.15
    )
    pb_anchor_weight = (
        0.10 if len(estimates) >= 2 else 0.18
    ) if pb_anchor_used else 0.0
    if pb_anchor_used:
        central = (
            central * (1.0 - pb_anchor_weight)
            + known_pb_seconds * pb_anchor_weight
        )

    average_work_distance = sum(
        estimate["relevant_work_distance_km"] * estimate["weight"]
        for estimate in estimates
    ) / total_weight
    specificity = min(
        average_work_distance / max(goal_distance_km * 0.35, 1.0),
        1.0,
    )
    confidence = min(
        0.84,
        0.52
        + specificity * 0.16
        + min(len(estimates), 3) * 0.035
        + (0.035 if pb_anchor_used else 0.0),
    )
    uncertainty = max(central * (0.025 + (1.0 - confidence) * 0.035), 35.0)

    return {
        "central_seconds": round(central, 1),
        "low_seconds": round(max(central - uncertainty, 1.0), 1),
        "high_seconds": round(central + uncertainty, 1),
        "confidence": round(confidence, 4),
        "goal_distance_km": round(goal_distance_km, 4),
        "estimate_count": len(estimates),
        "estimates": sorted(
            estimates,
            key=lambda estimate: estimate["weight"],
            reverse=True,
        ),
        "representative_race_count": len(representative_races),
        "historical_outcome_count": len(historical_outcomes),
        "pb_anchor_seconds": known_pb_seconds if pb_anchor_used else None,
        "pb_anchor_weight": pb_anchor_weight,
        "conditions": "Ideal, flat conditions",
        "method": (
            "Recent distance-relevant threshold and long-interval work; "
            "shorter linked races cannot dominate an endurance goal."
        ),
        "model_version": 1,
    }


def _endurance_workout_rank(
    item: dict,
    goal_distance_km: float,
    reference_date: datetime.date,
) -> float:
    """Rank recent, substantial endurance work above generic old sessions."""
    relevant_distance = sum(
        float(component.get("total_work_distance_km") or 0.0)
        for component in item.get("phase_components", [])
        if component.get("component_type") in {"threshold", "long_intervals"}
        and component.get("average_pace_s_per_km") is not None
        and float(component.get("confidence") or 0.0) >= 0.75
    )
    coverage = min(
        relevant_distance / max(goal_distance_km * 0.35, 1.0),
        1.0,
    )
    activity_date = item.get("activity_date")
    age_days = (
        max((reference_date - activity_date).days, 0)
        if activity_date is not None
        else 365
    )
    recency = max(0.0, 1.0 - age_days / 90.0)
    return round(
        float(item.get("trust_score") or 0.0) * 0.45
        + coverage * 20.0
        + recency * 35.0,
        4,
    )


def _cross_distance_pb_shape_prediction(
    *,
    athlete_id: int,
    candidate_workouts: list[dict],
    goal_distance_km: float | None,
    goal_pb_shape: dict | None,
    reference_date: datetime.date,
) -> dict | None:
    """Build a cautious personal endurance fallback from shorter PB Shape.

    This is used only when the current workout has no direct goal-distance PB
    Shape and no genuinely distance-relevant prediction. It searches the
    strongest current workouts for a supported shorter-distance PB comparison,
    then carries that shape ratio through the athlete's own target-distance PB.
    """
    if (
        goal_distance_km is None
        or goal_distance_km < 15.0
        or not goal_pb_shape
        or not goal_pb_shape.get("pb_time_s")
        or not goal_pb_shape.get("pb_date")
    ):
        return None

    source_distances = (
        (10.0, 5.0)
        if goal_distance_km < 30.0
        else (21.0975, 10.0)
    )
    ranked_candidates = sorted(
        candidate_workouts,
        key=lambda item: float(item.get("trust_score") or 0.0),
        reverse=True,
    )[:6]
    options = []

    for source_distance in source_distances:
        for item in ranked_candidates:
            activity_id = int(item["session"].activity_id)
            try:
                source_shape = pb_shape_to_dict(
                    build_pb_shape(
                        athlete_id=athlete_id,
                        current_activity_id=activity_id,
                        goal_distance_km=source_distance,
                    )
                )
            except Exception:
                continue

            if (
                source_shape.get("central_seconds") is None
                or not source_shape.get("pb_time_s")
                or source_shape.get("pb_workout_count", 0) < 1
                or float(source_shape.get("confidence") or 0.0) < 0.45
            ):
                continue

            bridge = build_personal_pb_shape_bridge(
                source_distance_km=source_distance,
                target_distance_km=goal_distance_km,
                source_pb_seconds=float(source_shape["pb_time_s"]),
                source_current_seconds=float(source_shape["central_seconds"]),
                source_confidence=float(source_shape["confidence"]),
                target_pb_seconds=float(goal_pb_shape["pb_time_s"]),
                target_pb_date=goal_pb_shape.get("pb_date"),
                reference_date=reference_date,
            )
            if bridge is None:
                continue

            prediction = personal_pb_shape_bridge_to_dict(bridge)
            prediction.update(
                {
                    "activity_id": activity_id,
                    "date": (
                        item["session"].activity_date[:10]
                        if item["session"].activity_date
                        else "Unknown"
                    ),
                    "title": item["session"].title,
                    "description": _display_description(item),
                    "source_pb_shape": source_shape,
                    "target_pb_shape": goal_pb_shape,
                }
            )
            options.append(prediction)

        if options:
            # Prefer the nearest supported source distance.
            break

    if not options:
        return None

    return max(
        options,
        key=lambda item: (
            float(item["confidence"]),
            -abs(float(item["shape_ratio"]) - 1.0),
        ),
    )


WORKOUT_LIBRARY_DECODER_VERSION = 3


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

    def __init__(self, history_days: int | None = RECENT_WINDOW_DAYS):
        """Limit expensive raw workout evidence to the current evidence horizon.

        Production defaults to the validated 365-day horizon. Passing
        history_days=None explicitly preserves the legacy full-history path
        for diagnostics and parity checks.
        """
        self.history_days = (
            int(history_days)
            if history_days is not None
            else None
        )

        if self.history_days is not None and self.history_days <= 0:
            raise ValueError("history_days must be positive or None")

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

        history_cutoff = None
        if self.history_days is not None:
            cursor.execute(
                f"""
                SELECT MAX(substr(a.activity_date, 1, 10))
                FROM activities a
                WHERE a.athlete_id = ?
                  AND CAST(a.sport_id AS TEXT) IN ({placeholders})
                  AND a.raw_json IS NOT NULL
                """,
                (context.athlete_id, *running_ids),
            )
            latest_date_raw = cursor.fetchone()[0]
            latest_date = _as_date(latest_date_raw)
            if latest_date is not None:
                history_cutoff = (
                    latest_date
                    - datetime.timedelta(days=self.history_days)
                ).isoformat()

        history_filter_sql = (
            " AND substr(a.activity_date, 1, 10) >= ?"
            if history_cutoff is not None
            else ""
        )
        query_params = [
            context.athlete_id,
            *running_ids,
        ]
        if history_cutoff is not None:
            query_params.append(history_cutoff)

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
              {history_filter_sql}
            ORDER BY a.activity_datetime DESC
            """,
            tuple(query_params),
        )

        rows = [
            row for row in cursor.fetchall()
            if has_reliable_distance_and_pace(
                title=row[3],
                sport_id=str(row[4] or ""),
                route_name=row[14],
                raw_json_text=row[15],
            )
        ]
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
                avg_hr=get_effective_activity_heart_rate(
                    row[1], row[0], float(row[8]) if row[8] is not None else None
                ),
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
                athlete_lt1_hr=(
                    float(row[16]) if row[16] is not None else None
                ),
            )

            session = classify_session(facts)
            session_counts[session.session_type.value] += 1
            forced_workout = session.metadata.get("manual_override") in {
                "workout", "threshold"
            }

            if session.metadata.get("activity_intent") in {
                "easy_with_strides", "easy_with_pickups", "standalone_strides",
                "easy", "long_run",
            }:
                if session.metadata.get("activity_intent") == "easy_with_pickups":
                    session_counts["easy_with_pickups_excluded"] += 1
                else:
                    session_counts["easy_with_strides_excluded"] += 1
                continue

            if session.metadata.get("manual_override") == "race":
                session_counts["manual_race_excluded"] += 1
                continue

            if not forced_workout and _is_race_quality_session(facts):
                session_counts["race_quality_excluded"] += 1
                continue

            event_title = (facts.title or "").lower()
            if not forced_workout and ("parkrun" in event_title or "race" in event_title):
                session_counts["event_effort_excluded"] += 1
                continue

            title_intent = parse_workout_title(facts.title)
            workout = get_or_decode_workout(row[0], row[15])

            if not forced_workout and _obvious_continuous_run(
                facts,
                workout,
                title_intent,
            ):
                session_counts["continuous_autolap_excluded"] += 1
                continue

            title_intent_evidence = build_title_intent_evidence(
                facts.title,
                row[15],
            )

            phase_components, phase_metadata = _group_work_components(
                workout,
                row[15],
                easy_pace_s_per_km,
                facts.title,
            )
            phase_establishes_workout = (
                float(phase_metadata.get("confidence") or 0.0) >= 0.65
                and any(
                    component.get("component_type")
                    in {
                        "threshold",
                        "long_intervals",
                        "short_intervals",
                    }
                    for component in phase_components
                )
            )

            accepted = (
                session.session_type == SessionType.STRUCTURED_WORKOUT
                or _explicit_workout_title(session.title)
                or (
                    workout.workout_type
                    not in ("No split data", "Unclassified")
                    and _programmed_structure_evidence(workout)
                )
                or phase_establishes_workout
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

            item["phase_components"] = phase_components
            item["phase_metadata"] = phase_metadata
            item["title_intent_evidence"] = title_intent_evidence

            workout_dna = build_workout_dna(
                phases=phase_metadata.get("phases", []),
                activity_id=session.activity_id,
                athlete_id=session.athlete_id,
                execution_score=workout.execution_score,
                recognition_confidence=workout.confidence,
                phase_confidence=float(
                    phase_metadata.get("confidence") or 0.0
                ),
                source=str(
                    phase_metadata.get("source")
                    or "runalyze_csv"
                ),
            )
            item["workout_dna"] = workout_dna_to_dict(
                workout_dna
            )

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

            if (
                title_intent_evidence is not None
                and float(
                    title_intent_evidence["metadata"].get("confidence") or 0.0
                ) >= 0.85
            ):
                item["trust_score"] = min(
                    item["trust_score"] + 5.0,
                    100.0,
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

        goal = context.goal or {}
        goal_distance_km = (
            float(goal["distance_m"]) / 1000.0
            if goal.get("distance_m")
            else None
        )
        endurance_road_goal = (
            goal_distance_km is not None
            and goal_distance_km >= 15.0
            and "trail" not in " ".join(
                str(goal.get(field) or "")
                for field in ("goal_name", "goal_type", "race_name")
            ).lower()
        )
        strongest = sorted(
            recent_candidates,
            key=(
                lambda item: _endurance_workout_rank(
                    item,
                    goal_distance_km,
                    reference_date,
                )
            )
            if goal_distance_km is not None and goal_distance_km >= 15.0
            else lambda item: item["trust_score"],
            reverse=True,
        )[:TOP_EVIDENCE_COUNT]

        best = strongest[0]

        try:
            historical_similarity = find_similar_linked_workouts(
                athlete_id=context.athlete_id,
                current_activity_id=best["session"].activity_id,
                limit=10,
                reference_date=reference_date,
                goal_distance_km=goal_distance_km,
                road_goal=endurance_road_goal,
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

        formula_prediction = _combine_workout_predictions(
            strongest,
            goal_distance_km,
        )

        try:
            pb_shape_result = (
                build_pb_shape(
                    athlete_id=context.athlete_id,
                    current_activity_id=best["session"].activity_id,
                    goal_distance_km=goal_distance_km,
                )
                if goal_distance_km is not None
                else None
            )
            pb_shape_prediction = (
                pb_shape_to_dict(pb_shape_result)
                if pb_shape_result is not None
                else None
            )
        except Exception as error:
            pb_shape_prediction = {
                "central_seconds": None,
                "confidence": 0.0,
                "status": "error",
                "matches": [],
                "limitations": [
                    "PB Shape could not be calculated: "
                    f"{type(error).__name__}"
                ],
            }

        similarity_prediction = (
            predict_from_similarity(
                historical_similarity,
                goal_distance_km=goal_distance_km,
                reference_date=reference_date,
                road_goal=endurance_road_goal,
            )
            if (
                goal_distance_km is not None
                and "historical_similarity" in locals()
            )
            else None
        )
        distance_relevant_prediction = _distance_relevant_workout_prediction(
            candidate_workouts=(
                recent_candidates
                if goal_distance_km is not None and 8.0 <= goal_distance_km < 15.0
                else [*strongest, latest]
            ),
            goal_distance_km=goal_distance_km,
            reference_date=reference_date,
            similarity_prediction=similarity_prediction,
            pb_shape_prediction=pb_shape_prediction,
        )
        cross_distance_pb_shape_prediction = (
            _cross_distance_pb_shape_prediction(
                athlete_id=context.athlete_id,
                candidate_workouts=recent_candidates,
                goal_distance_km=goal_distance_km,
                goal_pb_shape=pb_shape_prediction,
                reference_date=reference_date,
            )
            if distance_relevant_prediction is None
            else None
        )

        # PB Shape is the most personal and explainable workout prediction.
        # For longer goals, current distance-specific work outranks linked
        # short races that do not actually represent the selected distance.
        if (
            pb_shape_prediction
            and pb_shape_prediction.get("central_seconds") is not None
            and pb_shape_prediction.get("pb_workout_count", 0) >= 1
            and pb_shape_prediction.get("confidence", 0) >= 0.45
        ):
            workout_prediction = pb_shape_prediction
            prediction_source = "pb_shape"
        elif distance_relevant_prediction is not None:
            workout_prediction = distance_relevant_prediction
            prediction_source = "distance_relevant_workout"
        elif cross_distance_pb_shape_prediction is not None:
            workout_prediction = cross_distance_pb_shape_prediction
            prediction_source = "cross_distance_pb_shape"
        elif (
            similarity_prediction
            and similarity_prediction["distinct_race_count"] >= 2
            and similarity_prediction["confidence"] >= 0.55
        ):
            workout_prediction = similarity_prediction
            prediction_source = "historical_similarity"
        else:
            workout_prediction = formula_prediction
            prediction_source = "formula_fallback"

        if prediction_source == "cross_distance_pb_shape":
            prediction_activity_id = workout_prediction.get("activity_id")
            best = next(
                (
                    item
                    for item in recent_candidates
                    if item["session"].activity_id == prediction_activity_id
                ),
                best,
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

        latest_description = _display_description(latest)
        best_description = _display_description(best)

        summary_parts = [
            f"Latest session: {latest_description} on "
            f"{(latest_session.activity_date or 'unknown')[:10]}.",
            f"Best current evidence: {best_description} on "
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
            prediction_label = (
                "PB Shape prediction"
                if prediction_source == "pb_shape"
                else "Distance-specific workout prediction"
                if prediction_source == "distance_relevant_workout"
                else "Personal cross-distance workout prediction"
                if prediction_source == "cross_distance_pb_shape"
                else "Historical workout prediction"
                if prediction_source == "historical_similarity"
                else "Formula fallback prediction"
            )
            total_seconds = int(round(workout_prediction["central_seconds"]))
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            prediction_clock = (
                f"{hours}:{minutes:02d}:{seconds:02d}"
                if hours
                else f"{minutes}:{seconds:02d}"
            )
            summary_parts.append(
                f"{prediction_label}: {prediction_clock} "
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
                    "description": _display_description(item),
                    "trust_score": item["trust_score"],
                    "execution_score": workout.execution_score,
                    "recognition_confidence": workout.confidence,
                    "session_confidence": session.confidence,
                    "average_rep_pace_s_per_km":
                        workout.average_rep_pace_s_per_km,
                    "trust_reasons": item["trust_reasons"],
                    "workout_dna": item.get("workout_dna"),
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
            (
                "Best current workout DNA: "
                f"{best.get('workout_dna', {}).get('primary_label', 'Unknown')}"
            ),
            f"Strongest {len(strongest)} recent workout(s) were ranked by "
            "recency, structure, recognition and execution",
            f"Best evidence trust score {best['trust_score']:.0f}/100",
        ]

        if latest_is_representative:
            strengths.append("Latest workout is representative of current evidence")

        limitations = [
            "Explicit workout titles now outrank split-only inference when the title structure can be matched to exported splits.",
            "Repeated auto-laps alone never establish a workout; PP requires explicit session intent, recovery/boundary structure, or a confident phase reconstruction.",
            "Race and race-quality efforts are excluded from Workout Coach even if their splits resemble repetitions.",
            "Trends compare only sessions with similar workout type and rep distance.",
            "Runalyze CSV splits do not contain full lap-level heart rate or power.",
            "Warm-up, cool-down and recovery splits are excluded from "
            "work pace when they are within 12% of the athlete's current "
            "easy pace.",
            "Remaining faster splits are grouped by similar distance before "
            "threshold, long-interval and short-interval predictions are combined.",
            "Transparent component conversion factors are still less reliable "
            "than a recent genuine race and therefore carry lower weight.",
            "Historical similarity becomes the primary estimate only when "
            "at least two distinct linked race outcomes provide moderate evidence.",
            "For endurance goals, recent trusted threshold and long-interval "
            "work takes priority when linked race history is too short or "
            "too old to represent the selected distance.",
            "Controlled race intent is not yet explicit, so the historical "
            "model gently favours stronger outcomes and remains lower-weighted "
            "than strong Race Coach evidence.",
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
            weight=(
                0.65
                if (
                    workout_prediction
                    and prediction_source == "pb_shape"
                )
                else 0.55
                if (
                    workout_prediction
                    and prediction_source == "distance_relevant_workout"
                )
                else 0.45
                if (
                    workout_prediction
                    and prediction_source == "cross_distance_pb_shape"
                )
                else 0.55
                if (
                    workout_prediction
                    and prediction_source == "historical_similarity"
                )
                else 0.25
                if workout_prediction
                else 0.0
            ),
            metadata={
                "activity_id": latest_session.activity_id,
                "activity_date": latest_session.activity_date,
                "selected_title": latest_session.title,
                "workout_type": latest_workout.workout_type,
                "description": latest_description,
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
                    "description": latest_description,
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
                "latest_workout_dna": latest.get("workout_dna"),
                "best_workout_dna": best.get("workout_dna"),
                "best_evidence": {
                    "date": (
                        best_session.activity_date[:10]
                        if best_session.activity_date
                        else "Unknown"
                    ),
                    "title": best_session.title,
                    "description": best_description,
                    "trust_score": best["trust_score"],
                },
                "top_workouts": top_workouts,
                "workout_prediction": workout_prediction,
                "prediction_source": prediction_source,
                "pb_shape_prediction": pb_shape_prediction,
                "similarity_prediction": similarity_prediction,
                "formula_prediction": formula_prediction,
                "distance_relevant_prediction": distance_relevant_prediction,
                "cross_distance_pb_shape_prediction": (
                    cross_distance_pb_shape_prediction
                ),
                "historical_similarity":
                    historical_similarity_metadata,
                "prediction_confidence": prediction_confidence,
                "recognition_confidence": recognition_confidence,
                "trend": trend,
                "latest_not_representative": not latest_is_representative,
                "representative_warning": warning,
                "recognised_workout_count": len(candidates),
                "history_horizon": {
                    "history_days": self.history_days,
                    "cutoff_date": history_cutoff,
                    "raw_rows_loaded": len(rows),
                },
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

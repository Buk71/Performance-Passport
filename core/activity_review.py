"""Evidence-backed Activity Review adapter.

Activity Review is the athlete-facing explanation layer for one recorded
session.  It does not create another classifier or ranking model.  Instead it
joins the existing sources of truth:

- Session Intelligence for classification and confidence;
- Activity Reliability for pace eligibility;
- Split Intelligence for work/recovery structure;
- Performance Recognition for athlete-relative comparisons.

The adapter is deliberately deterministic.  Missing source evidence remains
missing rather than being inferred for presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import math

from core.activity_reliability import has_reliable_distance_and_pace
from core.coaching import RunProfile
from core.database import (
    get_athlete_sport_roles,
    get_connection,
    get_effective_athlete_thresholds,
)
from core.performance_recognition import (
    Recognition,
    build_recognition_index,
    recognition_key,
)
from core.session import SessionType
from core.session_intelligence import ActivityFacts, classify_session
from core.splits import (
    Split,
    WorkoutRecognition,
    is_boundary_fragment,
    parse_splits,
    recognise_workout,
)


SESSION_LABELS = {
    "continuous_run": "Continuous run",
    "structured_workout": "Structured workout",
    "race": "Race effort",
    "walk": "Walk",
    "cross_training": "Cross-training",
    "unknown": "Unclassified activity",
}

PURPOSE_LABELS = {
    "easy": "Easy",
    "recovery": "Recovery",
    "steady": "Steady",
    "long": "Long run",
    "progression": "Progression",
    "continuous_tempo": "Continuous tempo",
    "threshold": "Threshold",
    "vo2": "VO2 development",
    "hills": "Hills",
    "fartlek": "Fartlek",
    "race": "Race",
    "general": "General aerobic",
    "unknown": "Purpose still emerging",
}

BENEFITS = {
    "recovery": "Supports recovery while maintaining running rhythm.",
    "easy": "Builds aerobic fitness without spending unnecessary intensity.",
    "long_easy": "Builds endurance and the ability to hold form late in longer races.",
    "steady": "Builds aerobic strength between easy and threshold intensity.",
    "threshold": "Raises the sustainable pace you can hold near race effort.",
    "vo2": "Develops aerobic power so faster race pace feels more controlled.",
    "speed": "Improves running economy, leg speed and neuromuscular sharpness.",
    "workout": "Develops race-specific fitness through deliberate work and recovery.",
    "race": "Provides direct evidence of current race capability.",
}


@dataclass(frozen=True)
class ActivityListItem:
    activity_id: int
    activity_date: str | None
    title: str
    route_name: str | None
    distance_km: float | None
    moving_time_s: float | None


@dataclass(frozen=True)
class ReviewScore:
    key: str
    label: str
    score: float
    reasons: tuple[str, ...]
    winner: bool


@dataclass(frozen=True)
class ReviewSplit:
    index: int
    role: str
    distance_km: float
    duration_s: int
    pace_s_per_km: float | None


@dataclass(frozen=True)
class ReviewComparison:
    category: str
    rank: int
    total: int
    top_percent: float
    rank_12m: int | None
    total_12m: int
    confidence: float
    confidence_label: str
    celebration: str
    detail: str
    actual_pace_s_per_km: float
    adjusted_pace_s_per_km: float
    adjustment_s_per_km: float
    environment_factors: tuple[str, ...]
    provisional: bool
    basis_detail: str


@dataclass(frozen=True)
class ActivityReview:
    activity_id: int
    athlete_id: int
    activity_date: str | None
    activity_datetime: str | None
    title: str
    route_name: str | None
    source: str | None

    session_type: str
    session_label: str
    purpose: str
    purpose_label: str
    classification_confidence: float
    confidence_label: str
    classification_summary: str
    scores: tuple[ReviewScore, ...]

    distance_km: float | None
    moving_time_s: float | None
    elapsed_time_s: float | None
    stopped_time_s: float | None
    moving_percent: float | None
    pace_s_per_km: float | None
    avg_hr: float | None
    max_hr: float | None
    elevation_up_m: float | None
    temperature_c: float | None
    humidity: float | None
    wind_speed: float | None

    pace_reliable: bool
    reliability_label: str
    reliability_detail: str

    split_count: int
    boundary_count: int
    recovery_count: int
    unknown_recovery_count: int
    workout_description: str | None
    workout_confidence: float | None
    splits: tuple[ReviewSplit, ...]
    structure_notes: tuple[str, ...]

    comparison: ReviewComparison | None
    coaching_headline: str
    coaching_detail: str
    coaching_benefit: str
    limitations: tuple[str, ...]


def _safe_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _distance_km(value) -> float | None:
    result = _safe_float(value)
    if result is None or result <= 0:
        return None
    # Historical Runalyze imports use kilometres in the legacy distance_m
    # column. FIT/direct imports may use the column's canonical metre unit.
    return result / 1000.0 if result > 250.0 else result


def _display_title(title: str | None, route_name: str | None) -> str:
    if title and str(title).strip():
        return str(title).strip()
    if route_name and str(route_name).strip():
        return f"{str(route_name).strip()} Run"
    return "Untitled Run"


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.80:
        return "High confidence"
    if confidence >= 0.65:
        return "Moderate confidence"
    return "Review confidence"


def _raw_splits(raw_json_text: str | None) -> str | None:
    if not raw_json_text:
        return None
    try:
        raw = json.loads(raw_json_text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw.get("splits") or raw.get("splitsCustom")


def _activity_rows(athlete_id: int):
    connection = get_connection()
    connection.row_factory = None
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            id, athlete_id, source, activity_datetime, activity_date, title,
            sport_id, distance_m, moving_time_s, elapsed_time_s, avg_hr,
            max_hr, elevation_up_m, temperature_c, humidity, wind_speed,
            route_name, raw_json
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_datetime DESC, id DESC
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


def list_review_activities(
    athlete_id: int,
    *,
    since: datetime.date | None = None,
) -> tuple[ActivityListItem, ...]:
    """Return running activities suitable for the athlete-facing selector."""
    roles = get_athlete_sport_roles(athlete_id)
    items = []

    for row in _activity_rows(athlete_id):
        sport_id = str(row[6] or "")
        if roles.get(sport_id) != "running":
            continue

        activity_date = row[4]
        if since is not None and activity_date:
            try:
                parsed = datetime.date.fromisoformat(str(activity_date)[:10])
            except (TypeError, ValueError):
                parsed = None
            if parsed is not None and parsed < since:
                continue

        items.append(
            ActivityListItem(
                activity_id=int(row[0]),
                activity_date=activity_date,
                title=_display_title(row[5], row[16]),
                route_name=row[16],
                distance_km=_distance_km(row[7]),
                moving_time_s=_safe_float(row[8]),
            )
        )

    return tuple(items)


def _run_profiles(athlete_id: int, rows) -> list[RunProfile]:
    thresholds = get_effective_athlete_thresholds(athlete_id)
    return [
        RunProfile(
            athlete_id=athlete_id,
            activity_date=row[4],
            title=row[5],
            sport_id=row[6],
            distance_km=_distance_km(row[7]),
            moving_time_seconds=_safe_float(row[8]),
            avg_hr=_safe_float(row[10]),
            run_max_hr=_safe_float(row[11]),
            elevation_m=_safe_float(row[12]),
            temperature_c=_safe_float(row[13]),
            humidity=_safe_float(row[14]),
            lt1_hr=thresholds.get("lt1_hr"),
            lt2_hr=thresholds.get("lt2_hr"),
            athlete_max_hr=thresholds.get("athlete_max_hr"),
        )
        for row in rows
    ]


def _selected_recognition(
    athlete_id: int,
    rows,
    selected_row,
) -> Recognition | None:
    runs = _run_profiles(athlete_id, rows)
    index = build_recognition_index(runs, athlete_id=athlete_id)
    selected_run = RunProfile(
        athlete_id=athlete_id,
        activity_date=selected_row[4],
        title=selected_row[5],
        sport_id=selected_row[6],
        distance_km=_distance_km(selected_row[7]),
        moving_time_seconds=_safe_float(selected_row[8]),
        avg_hr=_safe_float(selected_row[10]),
        run_max_hr=_safe_float(selected_row[11]),
        elevation_m=_safe_float(selected_row[12]),
        temperature_c=_safe_float(selected_row[13]),
        humidity=_safe_float(selected_row[14]),
    )
    return index.get(recognition_key(selected_run))


def _review_scores(session) -> tuple[ReviewScore, ...]:
    raw_scores = session.metadata.get("classification_scores", {})
    raw_reasons = session.metadata.get("classification_reasons", {})
    winner = session.metadata.get("winner")
    labels = (
        ("continuous_run", "Continuous"),
        ("structured_workout", "Workout"),
        ("race", "Race"),
    )
    return tuple(
        ReviewScore(
            key=key,
            label=label,
            score=float(raw_scores.get(key, 0.0) or 0.0),
            reasons=tuple(raw_reasons.get(key, ()) or ()),
            winner=winner == key,
        )
        for key, label in labels
    )


def _split_reviews(
    splits: tuple[Split, ...],
    recognition: WorkoutRecognition,
    *,
    structured: bool,
) -> tuple[ReviewSplit, ...]:
    work = {split.index for split in recognition.work_splits}
    recovery = {split.index for split in recognition.recovery_splits}
    warmup = {split.index for split in recognition.warmup_splits}
    cooldown = {split.index for split in recognition.cooldown_splits}

    result = []
    for split in splits:
        if is_boundary_fragment(split):
            role = "Boundary"
        elif not structured:
            role = "Lap"
        elif split.index in work:
            role = "Work"
        elif split.index in recovery:
            role = "Recovery"
        elif split.index in warmup:
            role = "Warm-up"
        elif split.index in cooldown:
            role = "Cool-down"
        else:
            role = "Other"

        result.append(
            ReviewSplit(
                index=split.index,
                role=role,
                distance_km=split.distance_km,
                duration_s=split.duration_s,
                pace_s_per_km=split.pace_s_per_km,
            )
        )
    return tuple(result)


def _comparison(
    recognition: Recognition | None,
    *,
    session_type: str,
    session_confidence: float,
) -> ReviewComparison | None:
    if recognition is None:
        return None

    if (
        session_type == "race"
        and recognition.category_key != "race"
        and session_confidence < 0.70
    ):
        basis_detail = (
            "Race evidence is below the 70% shared-confidence threshold, so "
            f"the comparison stays conservatively within {recognition.category_label}."
        )
    else:
        basis_detail = (
            f"Compared only with your {recognition.category_label} sessions."
        )

    return ReviewComparison(
        category=recognition.category_label,
        rank=recognition.rank,
        total=recognition.total,
        top_percent=recognition.top_percent,
        rank_12m=recognition.rank_12m,
        total_12m=recognition.total_12m,
        confidence=recognition.confidence,
        confidence_label=recognition.confidence_label,
        celebration=recognition.celebration,
        detail=recognition.positive_detail,
        actual_pace_s_per_km=recognition.actual_pace_s_per_km,
        adjusted_pace_s_per_km=recognition.adjusted_pace_s_per_km,
        adjustment_s_per_km=recognition.environment_adjustment_s_per_km,
        environment_factors=recognition.environment_factors,
        provisional=recognition.provisional,
        basis_detail=basis_detail,
    )


def _coaching_text(
    *,
    session_type: str,
    pace_reliable: bool,
    recognition: Recognition | None,
    workout: WorkoutRecognition,
) -> tuple[str, str, str]:
    if recognition is not None:
        benefit = BENEFITS.get(
            recognition.category_key,
            "Adds useful evidence to your individual coaching picture.",
        )
        return (
            recognition.celebration,
            recognition.positive_detail,
            benefit,
        )

    if not pace_reliable:
        return (
            "Training contribution recorded",
            (
                "Duration and heart-rate evidence remain useful, while the "
                "recorded treadmill distance and pace are deliberately not "
                "judged against outdoor runs."
            ),
            "Preserves the training load without distorting performance evidence.",
        )

    if session_type == "structured_workout":
        return (
            "Deliberate quality work recognised",
            workout.description,
            BENEFITS["workout"],
        )

    return (
        "Useful training evidence added",
        (
            "The session is recorded and classified, but there is not yet a "
            "robust athlete-relative pace comparison for this activity."
        ),
        "Every reliable session improves the athlete-specific evidence base.",
    )


def build_activity_review(
    athlete_id: int,
    activity_id: int,
) -> ActivityReview | None:
    rows = _activity_rows(athlete_id)
    selected = next(
        (row for row in rows if int(row[0]) == int(activity_id)),
        None,
    )
    if selected is None:
        return None

    thresholds = get_effective_athlete_thresholds(athlete_id)
    distance_km = _distance_km(selected[7])
    moving_time_s = _safe_float(selected[8])
    elapsed_time_s = _safe_float(selected[9])
    title_for_classifier = str(selected[5] or "Untitled activity")

    facts = ActivityFacts(
        activity_id=int(selected[0]),
        athlete_id=athlete_id,
        activity_date=selected[4],
        title=title_for_classifier,
        sport_id=str(selected[6]) if selected[6] is not None else None,
        distance_km=distance_km,
        moving_time_s=moving_time_s,
        elapsed_time_s=elapsed_time_s,
        avg_hr=_safe_float(selected[10]),
        max_hr=_safe_float(selected[11]),
        elevation_up_m=_safe_float(selected[12]),
        temperature_c=_safe_float(selected[13]),
        humidity=_safe_float(selected[14]),
        wind_speed=_safe_float(selected[15]),
        route_name=selected[16],
        raw_json_text=selected[17],
        athlete_lt2_hr=thresholds.get("lt2_hr"),
        athlete_max_hr=thresholds.get("athlete_max_hr"),
    )
    session = classify_session(facts)

    pace_reliable = has_reliable_distance_and_pace(
        title=selected[5],
        sport_id=str(selected[6]) if selected[6] is not None else None,
        route_name=selected[16],
        raw_json_text=selected[17],
    )
    pace_s_per_km = (
        moving_time_s / distance_km
        if pace_reliable and moving_time_s and distance_km
        else None
    )

    recognition = (
        _selected_recognition(athlete_id, rows, selected)
        if pace_reliable
        else None
    )

    raw_splits = _raw_splits(selected[17])
    parsed_splits = parse_splits(raw_splits)
    workout = recognise_workout(parsed_splits)
    structured = session.session_type == SessionType.STRUCTURED_WORKOUT
    split_details = session.metadata.get("split_classification", {})

    if not pace_reliable:
        reliability_label = "Pace excluded"
        reliability_detail = (
            "Explicit treadmill or indoor-running evidence was found. Time "
            "and heart rate still count; distance, pace, records and "
            "athlete-relative pace rankings do not."
        )
    elif pace_s_per_km is None:
        reliability_label = "Pace unavailable"
        reliability_detail = (
            "The source does not contain enough distance and moving-time "
            "evidence for a pace comparison."
        )
    elif structured:
        reliability_label = "Rep pace preferred"
        reliability_detail = (
            "Whole-session pace mixes work and recovery. Split-level work "
            "pace is the better description; any whole-session comparison "
            "is marked provisional."
        )
    else:
        reliability_label = "Pace evidence usable"
        reliability_detail = (
            "No treadmill reliability exclusion was found. Moving pace may "
            "enter comparisons, with continuity and conditions shown beside it."
        )

    stopped_time_s = None
    moving_percent = None
    if moving_time_s is not None and elapsed_time_s and elapsed_time_s > 0:
        stopped_time_s = max(elapsed_time_s - moving_time_s, 0.0)
        moving_percent = min(max(moving_time_s / elapsed_time_s * 100.0, 0.0), 100.0)

    structure_notes = []
    if parsed_splits:
        if structured:
            structure_notes.append(workout.description)
            if workout.unknown_recovery_count:
                structure_notes.append(
                    f"{workout.unknown_recovery_count} likely stopped-watch "
                    "recovery gap(s) were detected, but their duration was not recorded."
                )
        elif session.session_type == SessionType.RACE:
            if moving_percent is not None and moving_percent >= 99.5:
                structure_notes.append(
                    f"{len(parsed_splits)} recorded laps were present with no "
                    "stopped time. Lap variation did not override the "
                    "race-effort evidence."
                )
            else:
                structure_notes.append(
                    "Recorded laps are shown as route splits; workout-style "
                    "recovery inference was not used for this race effort."
                )
        else:
            structure_notes.append(
                split_details.get("reason")
                or "Recorded laps did not show a deliberate work/recovery pattern."
            )
    else:
        structure_notes.append("No decodable lap or split data was available.")

    limitations = list(workout.limitations if structured else ())
    if elapsed_time_s is None or moving_time_s is None:
        limitations.append("Continuity cannot be calculated from this source.")
    elif stopped_time_s and not parsed_splits:
        limitations.append(
            "Total stopped time is known, but individual stops were not recorded."
        )
    if recognition is not None and recognition.provisional:
        limitations.append(
            "The comparable-session ranking is provisional for this session type."
        )

    coaching_headline, coaching_detail, coaching_benefit = _coaching_text(
        session_type=session.session_type.value,
        pace_reliable=pace_reliable,
        recognition=recognition,
        workout=workout,
    )

    winner = session.metadata.get("winner", session.session_type.value)
    runner_up = session.metadata.get("runner_up", "unknown")
    margin = float(session.metadata.get("score_margin", 0.0) or 0.0)
    classification_summary = (
        f"{str(winner).replace('_', ' ').title()} led "
        f"{str(runner_up).replace('_', ' ')} by {margin:.1f} points."
    )

    return ActivityReview(
        activity_id=int(selected[0]),
        athlete_id=athlete_id,
        activity_date=selected[4],
        activity_datetime=selected[3],
        title=_display_title(selected[5], selected[16]),
        route_name=selected[16],
        source=selected[2],
        session_type=session.session_type.value,
        session_label=SESSION_LABELS.get(
            session.session_type.value,
            session.session_type.value.replace("_", " ").title(),
        ),
        purpose=session.purpose.value,
        purpose_label=PURPOSE_LABELS.get(
            session.purpose.value,
            session.purpose.value.replace("_", " ").title(),
        ),
        classification_confidence=session.confidence,
        confidence_label=_confidence_label(session.confidence),
        classification_summary=classification_summary,
        scores=_review_scores(session),
        distance_km=distance_km,
        moving_time_s=moving_time_s,
        elapsed_time_s=elapsed_time_s,
        stopped_time_s=stopped_time_s,
        moving_percent=moving_percent,
        pace_s_per_km=pace_s_per_km,
        avg_hr=_safe_float(selected[10]),
        max_hr=_safe_float(selected[11]),
        elevation_up_m=_safe_float(selected[12]),
        temperature_c=_safe_float(selected[13]),
        humidity=_safe_float(selected[14]),
        wind_speed=_safe_float(selected[15]),
        pace_reliable=pace_reliable,
        reliability_label=reliability_label,
        reliability_detail=reliability_detail,
        split_count=len(parsed_splits),
        boundary_count=len(workout.boundary_splits),
        recovery_count=len(workout.recovery_splits),
        unknown_recovery_count=workout.unknown_recovery_count,
        workout_description=workout.description if parsed_splits else None,
        workout_confidence=workout.confidence if parsed_splits else None,
        splits=_split_reviews(parsed_splits, workout, structured=structured),
        structure_notes=tuple(structure_notes),
        comparison=_comparison(
            recognition,
            session_type=session.session_type.value,
            session_confidence=session.confidence,
        ),
        coaching_headline=coaching_headline,
        coaching_detail=coaching_detail,
        coaching_benefit=coaching_benefit,
        limitations=tuple(dict.fromkeys(limitations)),
    )

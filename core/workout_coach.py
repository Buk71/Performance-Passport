"""Compose one completed run into an auditable Workout Coach review.

Workout Coach does not reclassify activities or invent a second set of
training zones.  It joins the existing Activity Review, approved Training
Block, physiological thresholds, decoded-workout library and live Training
Coach so the athlete can answer five separate questions:

1. What did I actually do?
2. Did it fulfil the planned purpose?
3. Where did the recorded effort sit relative to LT1 and LT2?
4. Can this run legitimately influence a prediction?
5. What is the next sensible coaching direction?
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.activity_review import ActivityReview, build_activity_review
from core.database import get_connection, get_effective_athlete_thresholds
from core.next_run import build_next_run_recommendation
from core.operational_block import build_operational_block_week


MODEL_VERSION = 1


@dataclass(frozen=True)
class PlannedExecutionContext:
    available: bool
    block_name: str | None
    week_label: str | None
    planned_title: str
    planned_detail: str
    planned_family: str | None
    performed_title: str
    performed_family: str | None
    alignment: str
    alignment_label: str
    detail: str


@dataclass(frozen=True)
class WorkoutHeartRateZone:
    key: str
    label: str
    range_text: str
    purpose: str
    is_current: bool


@dataclass(frozen=True)
class WorkoutHeartRateContext:
    available: bool
    current_label: str
    current_detail: str
    average_hr: float | None
    lt1_hr: int | None
    lt2_hr: int | None
    max_hr: int | None
    source: str
    zones: tuple[WorkoutHeartRateZone, ...]


@dataclass(frozen=True)
class PredictionContribution:
    status: str
    headline: str
    detail: str
    coaches: tuple[str, ...]
    confidence: float
    execution_score: float | None = None


@dataclass(frozen=True)
class NextCoachingDirection:
    available: bool
    timing: str
    title: str
    detail: str
    confidence: float
    confidence_label: str
    caveat: str


@dataclass(frozen=True)
class WorkoutCoachReview:
    athlete_id: int
    activity: ActivityReview
    plan: PlannedExecutionContext
    heart_rate: WorkoutHeartRateContext
    prediction: PredictionContribution
    next_direction: NextCoachingDirection
    correction_recommended: bool
    model_version: int = MODEL_VERSION


def _date(value: str | None) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _review_family(review: ActivityReview) -> str:
    purpose = str(review.purpose or "").lower()
    if review.session_type == "race" or purpose == "race":
        return "race"
    if purpose == "long":
        return "long"
    if purpose in {"threshold", "continuous_tempo"}:
        return "threshold"
    if purpose in {"vo2", "hills", "fartlek"}:
        return "quality"
    if review.session_type == "structured_workout":
        return "quality"
    if purpose == "recovery":
        return "recovery"
    return "easy"


def _families_align(planned: str | None, performed: str | None) -> tuple[str, str]:
    if planned is None or performed is None:
        return "unplanned", "No plan comparison"
    if planned == performed:
        return "matched", "Purpose delivered"
    compatible = (
        {planned, performed} <= {"easy", "recovery"}
        or {planned, performed} <= {"quality", "threshold"}
        or {planned, performed} <= {"easy", "long"}
    )
    if compatible:
        return "compatible", "Broad purpose delivered"
    if planned == "rest":
        return "extra", "Additional run"
    return "different", "Different stimulus"


def _plan_context(review: ActivityReview) -> PlannedExecutionContext:
    performed_family = _review_family(review)
    activity_date = _date(review.activity_date)
    if activity_date is None:
        return PlannedExecutionContext(
            available=False,
            block_name=None,
            week_label=None,
            planned_title="No dated plan available",
            planned_detail="The activity date cannot be matched to an approved block.",
            planned_family=None,
            performed_title=review.purpose_label,
            performed_family=performed_family,
            alignment="unplanned",
            alignment_label="Completed evidence retained",
            detail="The run still contributes to the athlete history.",
        )

    operational = build_operational_block_week(
        review.athlete_id,
        today=activity_date,
    )
    if operational is None:
        return PlannedExecutionContext(
            available=False,
            block_name=None,
            week_label=None,
            planned_title="Outside an approved block",
            planned_detail="No saved Training Block covered this activity date.",
            planned_family=None,
            performed_title=review.purpose_label,
            performed_family=performed_family,
            alignment="unplanned",
            alignment_label="Completed evidence retained",
            detail="Workout Coach reviews the run without pretending it was planned.",
        )

    day = next(
        (item for item in operational.days if item.date == activity_date.isoformat()),
        None,
    )
    if day is None:
        return PlannedExecutionContext(
            available=False,
            block_name=operational.block_name,
            week_label=f"Week {operational.week_number} of {operational.total_weeks}",
            planned_title="Plan day unavailable",
            planned_detail="The block exists, but this date is not present in its week.",
            planned_family=None,
            performed_title=review.purpose_label,
            performed_family=performed_family,
            alignment="unplanned",
            alignment_label="Completed evidence retained",
            detail="The imported activity remains valid evidence.",
        )

    performed = next(
        (item for item in day.activities if item.activity_id == review.activity_id),
        None,
    )
    actual_family = performed.family if performed is not None else performed_family
    actual_title = performed.family_label if performed is not None else review.purpose_label
    alignment, alignment_label = _families_align(day.planned_family, actual_family)
    detail = day.match_summary
    if alignment == "different":
        detail = (
            f"The plan asked for {day.planned_type}, while recognition found "
            f"{actual_title}. Review the classification if that is not what happened."
        )
    elif alignment == "extra":
        detail = (
            "A run was recorded on a planned rest day. It is retained as training "
            "evidence rather than silently treated as the planned session."
        )

    return PlannedExecutionContext(
        available=True,
        block_name=operational.block_name,
        week_label=f"Week {operational.week_number} of {operational.total_weeks}",
        planned_title=day.planned_type,
        planned_detail=day.planned_detail,
        planned_family=day.planned_family,
        performed_title=actual_title,
        performed_family=actual_family,
        alignment=alignment,
        alignment_label=alignment_label,
        detail=detail,
    )


def _heart_rate_context(review: ActivityReview) -> WorkoutHeartRateContext:
    thresholds = get_effective_athlete_thresholds(review.athlete_id)
    lt1 = thresholds.get("lt1_hr")
    lt2 = thresholds.get("lt2_hr")
    maximum = thresholds.get("athlete_max_hr")
    source = str(thresholds.get("source") or "Not set")
    average = review.avg_hr
    if not lt1 or not lt2:
        return WorkoutHeartRateContext(
            available=False,
            current_label="Zones still building",
            current_detail="Set or estimate LT1 and LT2 in the athlete profile to add effort context.",
            average_hr=average,
            lt1_hr=lt1,
            lt2_hr=lt2,
            max_hr=maximum,
            source=source,
            zones=(),
        )

    if average is None:
        current = None
        current_label = "Recorded heart rate unavailable"
        current_detail = "Pace, structure and perceived effort remain the better evidence for this run."
    elif average < lt1:
        current = "below_lt1"
        current_label = "Average below LT1"
        current_detail = "The whole-run average sits in the athlete's lower aerobic range."
    elif average < lt2:
        current = "between"
        current_label = "Average between LT1 and LT2"
        current_detail = "The whole-run average sits between the aerobic and threshold boundaries."
    else:
        current = "above_lt2"
        current_label = "Average at or above LT2"
        current_detail = "The whole-run average reached the athlete's higher-intensity range."

    if review.session_type == "structured_workout":
        current_detail += (
            " For intervals, whole-run average HR is context only because recoveries "
            "and heart-rate lag can conceal the work phases."
        )

    zones = (
        WorkoutHeartRateZone(
            key="below_lt1",
            label="Below LT1",
            range_text=f"Below {int(lt1)} bpm",
            purpose="Recovery and easy aerobic running",
            is_current=current == "below_lt1",
        ),
        WorkoutHeartRateZone(
            key="between",
            label="LT1 to LT2",
            range_text=f"{int(lt1)}–{int(lt2) - 1} bpm",
            purpose="Steady through threshold development",
            is_current=current == "between",
        ),
        WorkoutHeartRateZone(
            key="above_lt2",
            label="At/above LT2",
            range_text=(
                f"{int(lt2)}–{int(maximum)} bpm"
                if maximum and maximum >= lt2 else f"{int(lt2)}+ bpm"
            ),
            purpose="Higher-intensity and race-specific work",
            is_current=current == "above_lt2",
        ),
    )
    return WorkoutHeartRateContext(
        available=True,
        current_label=current_label,
        current_detail=current_detail,
        average_hr=average,
        lt1_hr=int(lt1),
        lt2_hr=int(lt2),
        max_hr=int(maximum) if maximum else None,
        source=source,
        zones=zones,
    )


def _decoded_workout(review: ActivityReview):
    connection = get_connection()
    row = connection.execute(
        """
        SELECT workout_signature, execution_score, recognition_confidence,
               phase_confidence
        FROM workout_library
        WHERE athlete_id = ? AND activity_id = ?
        """,
        (review.athlete_id, review.activity_id),
    ).fetchone()
    connection.close()
    return row


def _prediction_contribution(review: ActivityReview) -> PredictionContribution:
    decoded = _decoded_workout(review)
    purpose = str(review.purpose or "").lower()
    if review.session_type == "race" and review.classification_confidence >= 0.70:
        return PredictionContribution(
            status="eligible",
            headline="Direct Race Coach evidence",
            detail=(
                "A confidently recognised race can update distance-specific capability. "
                "Course, weather and evidence quality still affect its weight."
            ),
            coaches=("Race Coach",),
            confidence=review.classification_confidence,
        )

    # Shared live classification outranks a stale library row. In particular,
    # an easy run with finishing strides must never re-enter prediction evidence
    # simply because an older decoder once cached it as a workout.
    family = _review_family(review)
    if family in {"easy", "recovery", "long"}:
        return PredictionContribution(
            status="context",
            headline="Supports the training picture",
            detail=(
                "This run supports aerobic, endurance or recovery context. It does not "
                "directly create a faster race prediction from its average pace."
            ),
            coaches=("Lead Coach", "Recovery Coach"),
            confidence=review.classification_confidence,
        )

    if decoded is not None:
        signature, execution, recognition_confidence, phase_confidence = decoded
        recognition_confidence = float(recognition_confidence or 0.0)
        phase_confidence = float(phase_confidence or 0.0)
        confidence = min(recognition_confidence, phase_confidence)
        coaches = ["Workout Coach"]
        if purpose in {"threshold", "continuous_tempo"} or "threshold" in str(signature).lower():
            coaches.append("Threshold Coach")
        if recognition_confidence >= 0.65 and phase_confidence >= 0.70:
            return PredictionContribution(
                status="eligible",
                headline="Trusted workout evidence",
                detail=(
                    f"{signature} has reliable recognition and phase structure. It may "
                    "support the named coaches, but one workout cannot reset capability alone."
                ),
                coaches=tuple(coaches),
                confidence=confidence,
                execution_score=float(execution) if execution is not None else None,
            )
        return PredictionContribution(
            status="limited",
            headline="Workout recorded; prediction weight limited",
            detail=(
                "The session is in the workout library, but recognition or phase confidence "
                "is below the trusted evidence gate."
            ),
            coaches=tuple(coaches),
            confidence=confidence,
            execution_score=float(execution) if execution is not None else None,
        )

    return PredictionContribution(
        status="review",
        headline="Classification review before prediction use",
        detail=(
            "The run remains useful history, but it will not be promoted to prediction "
            "evidence until its session purpose and structure are trustworthy."
        ),
        coaches=("Workout Coach",),
        confidence=review.classification_confidence,
    )


def _next_direction(
    athlete_id: int,
    *,
    today: datetime.date,
) -> NextCoachingDirection:
    operational = build_operational_block_week(athlete_id, today=today)
    if operational is not None:
        next_run = operational.next_run
        confidence = 0.84 if operational.state == "Active" else 0.76
        return NextCoachingDirection(
            available=True,
            timing=next_run.timing,
            title=next_run.session_type,
            detail=next_run.detail,
            confidence=confidence,
            confidence_label="Good" if confidence >= 0.80 else "Moderate",
            caveat=(
                "Open Training Coach for the full live prescription. Pain, illness or "
                "unusual fatigue takes precedence over the planned session."
            ),
        )

    recommendation = build_next_run_recommendation(athlete_id, today=today)
    if recommendation is not None:
        return NextCoachingDirection(
            available=True,
            timing=recommendation.earliest_timing,
            title=recommendation.session_family,
            detail=recommendation.headline,
            confidence=recommendation.confidence,
            confidence_label=recommendation.confidence_label,
            caveat=(
                "Open Training Coach for the full live prescription. The athlete's "
                "own feeling, pain, illness or unusual fatigue takes precedence."
            ),
        )

    return NextCoachingDirection(
        available=False,
        timing="Next direction building",
        title="Return to normal recovery",
        detail="Training Coach does not yet have enough evidence for a specific next run.",
        confidence=0.0,
        confidence_label="Building",
        caveat="How the athlete feels takes precedence over an incomplete data picture.",
    )


def build_workout_coach_review(
    athlete_id: int,
    activity_id: int,
    *,
    today: datetime.date | None = None,
) -> WorkoutCoachReview | None:
    """Build one completed-run review without mutating imported evidence."""
    review = build_activity_review(athlete_id, activity_id)
    if review is None:
        return None
    return WorkoutCoachReview(
        athlete_id=athlete_id,
        activity=review,
        plan=_plan_context(review),
        heart_rate=_heart_rate_context(review),
        prediction=_prediction_contribution(review),
        next_direction=_next_direction(
            athlete_id,
            today=today or datetime.date.today(),
        ),
        correction_recommended=(
            review.classification_confidence < 0.70
            or review.session_type == "unknown"
        ),
    )

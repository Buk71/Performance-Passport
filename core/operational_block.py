"""Operational coaching for an athlete-approved Training Block.

This module answers three deliberately separate questions:

1. What did the saved block ask for this week?
2. What has the athlete actually completed?
3. What is the safest useful next step without silently rewriting the block?

The matcher prefers the athlete-relative Performance Recognition evidence and
falls back to the shared session classifier. Reliable distance contributes to
mileage; treadmill/indoor time may complete a training day without inventing
distance. Adaptations are advice only and never mutate the persisted design.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import datetime
import re
from typing import Any

from core.activity_reliability import has_reliable_distance_and_pace
from core.block_review import (
    BlockReviewProposal,
    apply_accepted_block_reviews,
    build_recovery_review,
)
from core.database import (
    get_athlete_sport_roles,
    get_connection,
    get_effective_athlete_thresholds,
)
from core.session import SessionPurpose, SessionType
from core.session_intelligence import ActivityFacts, classify_session
from core.home_latest_run import load_activity_runs
from core.performance_recognition import build_recognition_index, recognition_key
from core.training_blocks import (
    get_active_training_block,
    get_training_block_design,
)


WEEKDAYS = (
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
)


@dataclass(frozen=True)
class OperationalActivity:
    activity_id: int
    activity_date: str
    title: str
    family: str
    family_label: str
    distance_miles: float | None
    moving_time_s: float | None
    confidence: float
    distance_reliable: bool


@dataclass(frozen=True)
class DayExecution:
    day: str
    date: str
    planned_type: str
    planned_detail: str
    planned_family: str
    planned_miles: float | None
    is_hard: bool
    status: str
    completed_miles: float
    completed_time_s: float
    activities: tuple[OperationalActivity, ...]
    match_summary: str


@dataclass(frozen=True)
class AdaptationSuggestion:
    kind: str
    title: str
    detail: str
    changes_saved_plan: bool = False


@dataclass(frozen=True)
class OperationalNextRun:
    day: str | None
    date: str | None
    timing: str
    session_type: str
    planned_type: str
    family: str
    detail: str
    adapted: bool
    reason: str


@dataclass(frozen=True)
class OperationalWeek:
    athlete_id: int
    training_block_id: int
    block_name: str
    week_number: int
    total_weeks: int
    start_date: str
    end_date: str
    phase: str
    emphasis: str
    state: str
    status: str
    planned_miles: float
    completed_miles: float
    remaining_miles: float
    planned_run_days: int
    completed_run_days: int
    planned_quality_sessions: int
    completed_quality_sessions: int
    long_run_planned: bool
    long_run_completed: bool
    unreliable_distance_count: int
    days: tuple[DayExecution, ...]
    suggestions: tuple[AdaptationSuggestion, ...]
    next_run: OperationalNextRun
    headline: str
    summary: str
    source: str = "Saved Training Block + real activities"
    model_version: int = 1
    review: BlockReviewProposal | None = None


def _date(value: Any) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _distance_km(value: Any) -> float | None:
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return None
    if distance <= 0:
        return None
    return distance / 1000.0 if distance > 250.0 else distance


def _planned_family(session_type: str, *, is_hard: bool = False) -> str:
    value = str(session_type or "").lower()
    if value in {"rest", "strength"}:
        return "rest"
    if "primary race" in value or "secondary race" in value:
        return "race"
    if "long run" in value:
        return "long"
    if "recovery" in value:
        return "recovery"
    if value == "easy":
        return "easy"
    if "threshold" in value:
        return "threshold"
    if any(token in value for token in (
        "interval", "repetition", "vo₂", "vo2", "speed", "hill",
        "race-rhythm", "race pace", "race-pace",
    )):
        return "quality"
    return "quality" if is_hard else "easy"


def _actual_family(session) -> tuple[str, str]:
    purpose = session.purpose
    session_type = session.session_type
    if session_type == SessionType.RACE or purpose == SessionPurpose.RACE:
        return "race", "Race"
    if purpose == SessionPurpose.LONG:
        return "long", "Long run"
    if purpose in {SessionPurpose.THRESHOLD, SessionPurpose.CONTINUOUS_TEMPO}:
        return "threshold", "Threshold"
    if purpose in {
        SessionPurpose.VO2,
        SessionPurpose.HILLS,
        SessionPurpose.FARTLEK,
    } or session_type == SessionType.STRUCTURED_WORKOUT:
        return "quality", "Quality session"
    if purpose == SessionPurpose.RECOVERY:
        return "recovery", "Recovery"
    return "easy", "Easy / aerobic"


def _recognition_family(category_key: str) -> tuple[str, str] | None:
    return {
        "recovery": ("recovery", "Recovery"),
        "easy": ("easy", "Easy / aerobic"),
        "steady": ("easy", "Steady aerobic"),
        "long_easy": ("long", "Long run"),
        "threshold": ("threshold", "Threshold"),
        "vo2": ("quality", "VO₂ session"),
        "speed": ("quality", "Speed session"),
        "workout": ("quality", "Structured workout"),
        "race": ("race", "Race"),
    }.get(str(category_key or "").lower())


def _families_match(planned: str, actual: str) -> bool:
    if planned == actual:
        return True
    if planned in {"easy", "recovery"} and actual in {"easy", "recovery"}:
        return True
    if planned in {"threshold", "quality"} and actual in {
        "threshold", "quality", "race"
    }:
        return True
    return False


def _parse_miles(detail: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*mi\b", str(detail or ""), re.I)
    return float(match.group(1)) if match else None


def _planned_mileages(week: dict[str, Any]) -> tuple[float | None, ...]:
    days = tuple(week.get("days") or ())
    target = float(week.get("target_miles") or 0.0)
    values: list[float | None] = []
    unknown_run_indexes: list[int] = []
    known = 0.0
    for index, day in enumerate(days):
        family = _planned_family(
            str(day.get("session_type") or ""),
            is_hard=bool(day.get("is_hard")),
        )
        parsed = _parse_miles(str(day.get("detail") or ""))
        if family == "rest":
            parsed = 0.0
        elif parsed is None:
            unknown_run_indexes.append(index)
        values.append(parsed)
        if parsed is not None:
            known += parsed
    allocation = max(target - known, 0.0) / max(len(unknown_run_indexes), 1)
    for index in unknown_run_indexes:
        values[index] = round(allocation, 1)
    return tuple(values)


def _select_week(
    plan: dict[str, Any],
    today: datetime.date,
) -> tuple[dict[str, Any], str] | None:
    weeks = list(plan.get("weeks") or ())
    if not weeks:
        return None
    for week in weeks:
        start = _date(week.get("start_date"))
        end = _date(week.get("end_date"))
        if start is not None and end is not None and start <= today <= end:
            return week, "Active"
    future = [week for week in weeks if (_date(week.get("start_date")) or today) > today]
    if future:
        return min(future, key=lambda item: _date(item.get("start_date"))), "Upcoming"
    return weeks[-1], "Complete"


def _timing(target: datetime.date | None, today: datetime.date) -> str:
    if target is None:
        return "Timing building"
    difference = (target - today).days
    if difference == 0:
        return "Today"
    if difference == 1:
        return "Tomorrow"
    if 1 < difference < 7:
        return WEEKDAYS[target.weekday()]
    if difference >= 7:
        return target.strftime("%-d %b")
    return "Next available run"


def _empty_next(state: str) -> OperationalNextRun:
    return OperationalNextRun(
        day=None,
        date=None,
        timing="Next week" if state == "Complete" else "Timing building",
        session_type="Week complete" if state == "Complete" else "Plan building",
        planned_type="None",
        family="rest",
        detail=(
            "This saved week has no remaining planned run."
            if state == "Complete"
            else "The saved week does not contain a runnable day."
        ),
        adapted=False,
        reason="No remaining planned run was found.",
    )


def _next_run(
    days: tuple[DayExecution, ...],
    *,
    state: str,
    today: datetime.date,
) -> OperationalNextRun:
    candidates = []
    for day in days:
        day_date = _date(day.date)
        if day.planned_family == "rest" or day.activities:
            continue
        if day_date is not None and day_date >= today:
            candidates.append(day)
    if not candidates:
        return _empty_next("Complete")
    selected = candidates[0]
    selected_date = _date(selected.date)
    previous_hard = [
        day for day in days
        if day.status in {"Complete", "Different", "Extra"}
        and any(activity.family in {"threshold", "quality", "race", "long"} for activity in day.activities)
        and _date(day.date) is not None
        and selected_date is not None
        and 0 <= (selected_date - _date(day.date)).days <= 1
    ]
    adapted = bool(previous_hard and selected.is_hard)
    if adapted:
        return OperationalNextRun(
            day=selected.day,
            date=selected.date,
            timing=_timing(selected_date, today),
            session_type="Recovery / easy running",
            planned_type=selected.planned_type,
            family="recovery",
            detail=(
                "Protect recovery after the completed demanding run. Review "
                f"when to place {selected.planned_type}; the saved block has not changed."
            ),
            adapted=True,
            reason="A demanding run was completed within one day of the next planned hard day.",
        )
    return OperationalNextRun(
        day=selected.day,
        date=selected.date,
        timing=_timing(selected_date, today),
        session_type=selected.planned_type,
        planned_type=selected.planned_type,
        family=selected.planned_family,
        detail=selected.planned_detail,
        adapted=False,
        reason="This is the next incomplete runnable day in the saved week.",
    )


def _suggestions(
    days: tuple[DayExecution, ...],
    *,
    state: str,
    planned_miles: float,
    completed_miles: float,
    next_run: OperationalNextRun,
) -> tuple[AdaptationSuggestion, ...]:
    if state == "Upcoming":
        return (
            AdaptationSuggestion(
                kind="keep",
                title="Start with the approved shape",
                detail="No adaptation is needed before the block begins. The saved weekdays and ceiling remain unchanged.",
            ),
        )
    suggestions: list[AdaptationSuggestion] = []
    missed_hard = [day for day in days if day.status == "Missed" and day.is_hard]
    if missed_hard:
        names = ", ".join(day.planned_type for day in missed_hard)
        suggestions.append(
            AdaptationSuggestion(
                kind="protect",
                title="Do not chase missed quality",
                detail=f"{names} was missed. Keep the next safe planned stimulus rather than stacking two demanding days.",
            )
        )
    different = [day for day in days if day.status == "Different"]
    if different:
        suggestions.append(
            AdaptationSuggestion(
                kind="review",
                title="The week changed in practice",
                detail="One or more runs served a different purpose from the saved day. The evidence is recorded; the saved plan remains intact for review.",
            )
        )
    if next_run.adapted:
        suggestions.append(
            AdaptationSuggestion(
                kind="recover",
                title="Protect the next hard day",
                detail=next_run.reason + " Recovery is recommended before deliberately rescheduling quality.",
            )
        )
    if planned_miles > 0 and completed_miles > planned_miles * 1.05:
        suggestions.append(
            AdaptationSuggestion(
                kind="recover",
                title="Weekly volume is already above plan",
                detail="Keep remaining running easy or rest. Extra mileage is recognised but does not increase next week's target.",
            )
        )
    if not suggestions:
        suggestions.append(
            AdaptationSuggestion(
                kind="keep",
                title="No change needed",
                detail="Execution is compatible with the saved week. Continue with the next incomplete planned day.",
            )
        )
    return tuple(suggestions)


def compose_operational_week(
    *,
    athlete_id: int,
    training_block_id: int,
    block_name: str,
    plan: dict[str, Any],
    activities: tuple[OperationalActivity, ...],
    today: datetime.date,
) -> OperationalWeek | None:
    selected = _select_week(plan, today)
    if selected is None:
        return None
    week, state = selected
    start = _date(week.get("start_date"))
    end = _date(week.get("end_date"))
    if start is None or end is None:
        return None
    planned_days = tuple(week.get("days") or ())
    mileages = _planned_mileages(week)
    executions: list[DayExecution] = []
    for index, day in enumerate(planned_days):
        day_date = start + datetime.timedelta(days=index)
        day_activities = tuple(
            activity for activity in activities
            if _date(activity.activity_date) == day_date
        )
        planned_type = str(day.get("session_type") or "Rest")
        planned_detail = str(day.get("detail") or "")
        planned_family = _planned_family(
            planned_type,
            is_hard=bool(day.get("is_hard")),
        )
        matches = [
            activity for activity in day_activities
            if _families_match(planned_family, activity.family)
        ]
        completed_miles = sum(
            activity.distance_miles or 0.0 for activity in day_activities
            if activity.distance_reliable
        )
        completed_time = sum(activity.moving_time_s or 0.0 for activity in day_activities)
        if planned_family == "rest":
            status = "Extra" if day_activities else "Rest"
            summary = (
                f"{len(day_activities)} unplanned run{'s' if len(day_activities) != 1 else ''} recorded."
                if day_activities else "No running planned."
            )
        elif matches:
            status = "Complete"
            summary = f"{', '.join(activity.family_label for activity in matches)} matched the planned purpose."
        elif day_activities:
            status = "Different"
            summary = (
                f"Completed {', '.join(activity.family_label for activity in day_activities)} rather than {planned_type}."
            )
        elif state == "Upcoming" or day_date > today:
            status = "Planned"
            summary = "Still ahead in the saved week."
        elif day_date == today:
            status = "Today"
            summary = "Planned for today; no completed run is recorded yet."
        else:
            status = "Missed"
            summary = "No completed run was found for this planned day."
        executions.append(
            DayExecution(
                day=str(day.get("day") or WEEKDAYS[index]),
                date=day_date.isoformat(),
                planned_type=planned_type,
                planned_detail=planned_detail,
                planned_family=planned_family,
                planned_miles=mileages[index] if index < len(mileages) else None,
                is_hard=bool(day.get("is_hard")),
                status=status,
                completed_miles=round(completed_miles, 2),
                completed_time_s=round(completed_time, 1),
                activities=day_activities,
                match_summary=summary,
            )
        )
    day_tuple = tuple(executions)
    planned_miles = float(week.get("target_miles") or 0.0)
    completed_miles = round(sum(day.completed_miles for day in day_tuple), 1)
    remaining = round(max(planned_miles - completed_miles, 0.0), 1)
    planned_runs = [day for day in day_tuple if day.planned_family != "rest"]
    completed_runs = [
        day for day in day_tuple
        if day.planned_family != "rest" and day.activities
    ]
    planned_quality = [
        day for day in day_tuple
        if day.planned_family in {"threshold", "quality", "race"}
    ]
    completed_quality_days = [
        day for day in day_tuple
        if any(
            activity.family in {"threshold", "quality", "race"}
            for activity in day.activities
        )
    ]
    completed_quality_count = min(
        len(completed_quality_days), len(planned_quality)
    )
    long_planned = any(day.planned_family == "long" for day in day_tuple)
    long_complete = any(
        activity.family == "long" for activity in activities
        if start <= (_date(activity.activity_date) or start) <= end
    )
    next_run = _next_run(day_tuple, state=state, today=today)
    suggestions = _suggestions(
        day_tuple,
        state=state,
        planned_miles=planned_miles,
        completed_miles=completed_miles,
        next_run=next_run,
    )
    has_review = any(item.kind in {"protect", "review", "recover"} for item in suggestions)
    if state == "Upcoming":
        status = "Ready to start"
        headline = f"Week {week.get('week_number')} begins {_timing(start, today).lower()}"
    elif state == "Complete":
        status = "Week complete"
        headline = f"{completed_miles:.1f} reliable miles recorded"
    elif has_review:
        status = "Review suggested"
        headline = f"{completed_miles:.1f} of {planned_miles:.1f} reliable miles complete"
    else:
        status = "On track"
        headline = f"{completed_miles:.1f} of {planned_miles:.1f} reliable miles complete"
    unreliable_count = sum(
        not activity.distance_reliable for activity in activities
        if start <= (_date(activity.activity_date) or start) <= end
    )
    summary = (
        f"{len(completed_runs)} of {len(planned_runs)} planned running days have activity evidence. "
        f"{completed_quality_count} of {len(planned_quality)} quality/event commitments are complete."
    )
    if unreliable_count:
        summary += f" {unreliable_count} run{'s' if unreliable_count != 1 else ''} count by time but not reliable distance."
    return OperationalWeek(
        athlete_id=athlete_id,
        training_block_id=training_block_id,
        block_name=block_name,
        week_number=int(week.get("week_number") or 1),
        total_weeks=len(plan.get("weeks") or ()),
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        phase=str(week.get("phase") or "Build"),
        emphasis=str(week.get("emphasis") or "Saved weekly direction"),
        state=state,
        status=status,
        planned_miles=round(planned_miles, 1),
        completed_miles=completed_miles,
        remaining_miles=remaining,
        planned_run_days=len(planned_runs),
        completed_run_days=len(completed_runs),
        planned_quality_sessions=len(planned_quality),
        completed_quality_sessions=completed_quality_count,
        long_run_planned=long_planned,
        long_run_completed=long_complete,
        unreliable_distance_count=unreliable_count,
        days=day_tuple,
        suggestions=suggestions,
        next_run=next_run,
        headline=headline,
        summary=summary,
    )


def _load_operational_activities(
    athlete_id: int,
    start: datetime.date,
    end: datetime.date,
) -> tuple[OperationalActivity, ...]:
    roles = get_athlete_sport_roles(athlete_id)
    thresholds = get_effective_athlete_thresholds(athlete_id)
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, activity_date, title, sport_id, distance_m,
               moving_time_s, elapsed_time_s, avg_hr, max_hr,
               elevation_up_m, temperature_c, humidity, wind_speed,
               route_name, raw_json
        FROM activities
        WHERE athlete_id = ? AND activity_date BETWEEN ? AND ?
        ORDER BY activity_date, id
        """,
        (athlete_id, start.isoformat(), end.isoformat()),
    ).fetchall()
    connection.close()
    activity_runs = load_activity_runs(athlete_id)
    recognition_index = build_recognition_index(
        (run for _activity_id, run in activity_runs),
        athlete_id=athlete_id,
        reference_date=end,
    )
    recognition_by_id = {
        activity_id: recognition_index.get(recognition_key(run))
        for activity_id, run in activity_runs
    }
    activities: list[OperationalActivity] = []
    for row in rows:
        if roles.get(str(row[3] or "")) != "running":
            continue
        distance_km = _distance_km(row[4])
        facts = ActivityFacts(
            activity_id=int(row[0]),
            athlete_id=athlete_id,
            activity_date=row[1],
            title=str(row[2] or "Untitled run"),
            sport_id=str(row[3]) if row[3] is not None else None,
            distance_km=distance_km,
            moving_time_s=float(row[5]) if row[5] is not None else None,
            elapsed_time_s=float(row[6]) if row[6] is not None else None,
            avg_hr=float(row[7]) if row[7] is not None else None,
            max_hr=float(row[8]) if row[8] is not None else None,
            elevation_up_m=float(row[9]) if row[9] is not None else None,
            temperature_c=float(row[10]) if row[10] is not None else None,
            humidity=float(row[11]) if row[11] is not None else None,
            wind_speed=float(row[12]) if row[12] is not None else None,
            route_name=row[13],
            raw_json_text=row[14],
            athlete_lt2_hr=thresholds.get("lt2_hr"),
            athlete_max_hr=thresholds.get("athlete_max_hr"),
        )
        session = classify_session(facts)
        recognition = recognition_by_id.get(int(row[0]))
        recognised_family = (
            _recognition_family(recognition.category_key)
            if recognition is not None else None
        )
        family, label = recognised_family or _actual_family(session)
        title_lower = str(row[2] or "").lower()
        if (
            family == "quality"
            and "easy" in title_lower
            and any(token in title_lower for token in ("stride", "pickup"))
        ):
            family, label = "easy", "Easy + strides"
        reliable = has_reliable_distance_and_pace(
            title=row[2],
            sport_id=str(row[3]) if row[3] is not None else None,
            route_name=row[13],
            raw_json_text=row[14],
        )
        activities.append(
            OperationalActivity(
                activity_id=int(row[0]),
                activity_date=str(row[1]),
                title=str(row[2] or "Untitled run"),
                family=family,
                family_label=label,
                distance_miles=(
                    round(distance_km / 1.609344, 2)
                    if reliable and distance_km is not None else None
                ),
                moving_time_s=float(row[5]) if row[5] is not None else None,
                confidence=(
                    recognition.confidence
                    if recognition is not None else session.confidence
                ),
                distance_reliable=reliable,
            )
        )
    return tuple(activities)


def build_operational_block_week(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> OperationalWeek | None:
    """Load the active saved design and compose its operational week."""
    today = today or datetime.date.today()
    block = get_active_training_block(athlete_id)
    if block is None:
        return None
    saved = get_training_block_design(block.id, athlete_id=athlete_id)
    if saved is None:
        return None
    selected = _select_week(saved.plan, today)
    if selected is None:
        return None
    week, _state = selected
    start = _date(week.get("start_date"))
    end = _date(week.get("end_date"))
    if start is None or end is None:
        return None
    activities = _load_operational_activities(athlete_id, start, end)
    original = compose_operational_week(
        athlete_id=athlete_id,
        training_block_id=block.id,
        block_name=block.name,
        plan=saved.plan,
        activities=activities,
        today=today,
    )
    if original is None:
        return None
    review = None
    if original.next_run.adapted and original.next_run.date is not None:
        original_day = next(
            (
                day for day in original.days
                if day.date == original.next_run.date
            ),
            None,
        )
        if original_day is not None:
            review = build_recovery_review(
                athlete_id=athlete_id,
                training_block_id=block.id,
                week_number=original.week_number,
                target_date=original.next_run.date,
                planned_type=original_day.planned_type,
                planned_detail=original_day.planned_detail,
                planned_family=original_day.planned_family,
                reason=original.next_run.reason,
            )
    if review is None or not review.is_accepted:
        return replace(original, review=review)
    effective_plan = apply_accepted_block_reviews(
        saved.plan,
        athlete_id=athlete_id,
        training_block_id=block.id,
    )
    effective = compose_operational_week(
        athlete_id=athlete_id,
        training_block_id=block.id,
        block_name=block.name,
        plan=effective_plan,
        activities=activities,
        today=today,
    )
    if effective is None:
        return replace(original, review=review)
    return replace(
        effective,
        review=review,
        source="Saved Training Block + accepted Block Review + real activities",
    )

"""Real-data summary for the first Performance Passport Home composition.

This module is deliberately an adapter: it reuses the existing goal, training
block, Adaptive Weekly Plan and Live Coach engines without changing any of
their calculations or writing anything to the database.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.adaptive_weekly_plan import build_adaptive_weekly_plan
from core.database import get_active_goal
from core.beginner_training_plan import build_couch_to_5k_plan
from core.five_to_ten_k_plan import build_five_to_ten_k_plan
from core.runner_journey import (
    COUCH_TO_5K,
    FIVE_TO_TEN_K,
    RunnerJourney,
    get_active_runner_journey,
    get_journey_current_week,
    get_five_to_ten_k_current_level,
)
from core.operational_block import OperationalWeek, build_operational_block_week
from core.training_blocks import (
    block_progress,
    get_active_training_block,  # compatibility for existing test/mocking contracts
    get_current_training_block,
)


@dataclass(frozen=True)
class HomeDay:
    day_name: str
    session_family: str
    title: str
    detail: str
    target: str | None
    is_today: bool


@dataclass(frozen=True)
class HomeSummary:
    athlete_id: int
    goal_name: str
    goal_context: str
    target_time_s: float | None
    target_date: str | None
    block_name: str
    block_context: str
    block_is_saved: bool
    week_days: tuple[HomeDay, ...]
    week_theme: str
    next_label: str
    next_timing: str
    next_detail: str
    next_source: str


def _format_goal_context(goal: dict | None) -> str:
    if not goal:
        return "No active goal yet"

    parts = []
    if goal.get("race_name"):
        parts.append(str(goal["race_name"]))
    if goal.get("target_date"):
        try:
            date_value = datetime.date.fromisoformat(
                str(goal["target_date"])[:10]
            )
            parts.append(date_value.strftime("%-d %b %Y"))
        except (TypeError, ValueError):
            parts.append(str(goal["target_date"]))
    return " · ".join(parts) or str(goal.get("goal_type") or "Active goal")


def _fallback_next(
    days: tuple[HomeDay, ...],
    today: datetime.date,
) -> tuple[str, str, str, str]:
    family_labels = {
        "easy": "Easy Aerobic",
        "recovery": "Recovery Run",
        "endurance": "Long Easy / Endurance",
        "long": "Long Easy / Endurance",
        "threshold": "Threshold Development",
        "vo2": "VO₂ / Speed Development",
        "speed": "Speed Development",
        "race_pace": "Race-Pace / Sharpening",
    }
    today_index = today.weekday()
    candidates = list(days[today_index:]) + list(days[:today_index])

    for offset, day in enumerate(candidates):
        if day.session_family in {"completed", "rest"}:
            continue
        timing = "Today" if offset == 0 else day.day_name
        detail = day.detail
        if day.target:
            detail = f"{detail} · {day.target}"
        label = family_labels.get(day.session_family, day.title)
        return label, timing, detail, "Adaptive weekly plan"

    return (
        "Recovery and reset",
        "This week",
        "The current week is complete; the next plan will build from the latest training evidence.",
        "Adaptive weekly plan",
    )


def _operational_days(
    operational: OperationalWeek,
    today: datetime.date,
) -> tuple[HomeDay, ...]:
    family_map = {
        "long": "long",
        "threshold": "threshold",
        "quality": "vo2",
        "race": "race_pace",
        "recovery": "recovery",
        "easy": "easy",
        "rest": "rest",
    }
    result = []
    for day in operational.days:
        family = (
            "completed"
            if day.status in {"Complete", "Different", "Extra"}
            and day.activities
            else family_map.get(day.planned_family, "easy")
        )
        detail = day.planned_detail
        if day.status in {"Complete", "Different", "Extra"} and day.activities:
            activity_labels = list(dict.fromkeys(
                activity.family_label for activity in day.activities
            ))
            detail = " + ".join(activity_labels)
            if day.completed_miles > 0:
                detail += f" · {day.completed_miles:.1f} mi"
            if day.status == "Different":
                detail += f" · planned {day.planned_type}"
            elif day.status == "Extra":
                detail += " · unplanned"
        elif day.status == "Missed":
            detail = day.match_summary
        target = (
            f"{day.planned_miles:.1f} mi"
            if day.planned_miles is not None and day.planned_miles > 0
            else None
        )
        result.append(
            HomeDay(
                day_name=day.day,
                session_family=family,
                title=day.planned_type,
                detail=detail,
                target=target,
                is_today=day.date == today.isoformat(),
            )
        )
    return tuple(result)



def _beginner_home_days(
    *,
    journey: RunnerJourney,
    today: datetime.date,
) -> tuple[HomeDay, ...]:
    """Build the seven-day Lead Coach strip from the active Runner Journey."""
    current_week = get_journey_current_week(journey)
    plan = build_couch_to_5k_plan(
        athlete_id=journey.athlete_id,
        sessions_per_week=journey.sessions_per_week,
        entry_stage=journey.entry_stage,
        current_week=current_week,
        reference_date=today,
    )
    plan_week = plan.weeks[current_week - 1]
    planned_by_day = {day.day: day for day in plan_week.sessions}
    names = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

    result = []
    for index, day_name in enumerate(names):
        planned = planned_by_day.get(day_name)
        if planned is None:
            result.append(
                HomeDay(
                    day_name=day_name,
                    session_family="rest",
                    title="Rest / recovery",
                    detail="No planned Couch → 5K session.",
                    target=None,
                    is_today=index == today.weekday(),
                )
            )
            continue

        result.append(
            HomeDay(
                day_name=day_name,
                session_family=(
                    "recovery" if not planned.counts_for_progression else "easy"
                ),
                title=planned.title,
                detail=planned.detail,
                target=(
                    "Counts for progression"
                    if planned.counts_for_progression
                    else "Support session"
                ),
                is_today=index == today.weekday(),
            )
        )
    return tuple(result)


def _beginner_next(
    days: tuple[HomeDay, ...],
    today: datetime.date,
) -> tuple[str, str, str, str]:
    """Choose the next journey session from the current seven-day strip."""
    start = today.weekday()
    ordered = list(days[start:]) + list(days[:start])
    for offset, day in enumerate(ordered):
        if day.session_family == "rest":
            continue
        timing = "Today" if offset == 0 else day.day_name
        return (
            day.title,
            timing,
            day.detail,
            "Couch → 5K Runner Journey",
        )
    return (
        "Recovery and reset",
        "This week",
        "No additional Couch → 5K session is planned in the current level.",
        "Couch → 5K Runner Journey",
    )


def _build_beginner_home_summary(
    athlete_id: int,
    goal: dict | None,
    journey: RunnerJourney,
    *,
    today: datetime.date,
) -> HomeSummary:
    current_week = get_journey_current_week(journey)
    plan = build_couch_to_5k_plan(
        athlete_id=athlete_id,
        sessions_per_week=journey.sessions_per_week,
        entry_stage=journey.entry_stage,
        current_week=current_week,
        reference_date=today,
    )
    current = plan.weeks[current_week - 1]
    days = _beginner_home_days(journey=journey, today=today)
    next_label, next_timing, next_detail, next_source = _beginner_next(days, today)

    goal_name = (
        str(goal.get("goal_name") or goal.get("race_name") or "Complete my first 5K")
        if goal
        else "Complete my first 5K"
    )

    return HomeSummary(
        athlete_id=athlete_id,
        goal_name=goal_name,
        goal_context=_format_goal_context(goal),
        target_time_s=(goal.get("target_time_s") if goal else None),
        target_date=(goal.get("target_date") if goal else None),
        block_name="Couch → 5K",
        block_context=f"Level {current_week} of 12 · {current.title}",
        block_is_saved=True,
        week_days=days,
        week_theme=f"Level {current_week}: {current.emphasis}",
        next_label=next_label,
        next_timing=next_timing,
        next_detail=next_detail,
        next_source=next_source,
    )



def _five_to_ten_home_days(
    *,
    journey: RunnerJourney,
    today: datetime.date,
) -> tuple[HomeDay, ...]:
    current_level = get_five_to_ten_k_current_level(journey)
    plan = build_five_to_ten_k_plan(
        athlete_id=journey.athlete_id,
        sessions_per_week=journey.sessions_per_week,
        entry_stage=journey.entry_stage,
        current_level=current_level,
        reference_date=today,
    )
    current = plan.levels[current_level - 1]
    by_day = {session.day: session for session in current.sessions}
    names = ("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")
    days = []
    for index, name in enumerate(names):
        session = by_day.get(name)
        if session is None:
            days.append(HomeDay(
                day_name=name, session_family="rest", title="Rest / recovery",
                detail="No planned 5K → 10K session.", target=None,
                is_today=index == today.weekday(),
            ))
            continue
        family = (
            "endurance" if session.role == "Long easy"
            else "recovery" if session.role == "Recovery"
            else "easy" if "Easy" in session.role
            else "threshold"
        )
        days.append(HomeDay(
            day_name=name, session_family=family, title=session.title,
            detail=session.detail,
            target=("Counts for progression" if session.counts_for_progression
                    else "Optional support"),
            is_today=index == today.weekday(),
        ))
    return tuple(days)


def _five_to_ten_next(
    days: tuple[HomeDay, ...],
    today: datetime.date,
) -> tuple[str, str, str, str]:
    ordered = list(days[today.weekday():]) + list(days[:today.weekday()])
    for offset, day in enumerate(ordered):
        if day.session_family == "rest":
            continue
        timing = "Today" if offset == 0 else ("Tomorrow" if offset == 1 else day.day_name)
        return day.title, timing, day.detail, "5K → 10K Runner Journey"
    return (
        "Recovery and reset", "This week",
        "No additional 5K → 10K session is planned in the current level.",
        "5K → 10K Runner Journey",
    )


def _build_five_to_ten_home_summary(
    athlete_id: int,
    goal: dict | None,
    journey: RunnerJourney,
    *,
    today: datetime.date,
) -> HomeSummary:
    current_level = get_five_to_ten_k_current_level(journey)
    plan = build_five_to_ten_k_plan(
        athlete_id=athlete_id,
        sessions_per_week=journey.sessions_per_week,
        entry_stage=journey.entry_stage,
        current_level=current_level,
        reference_date=today,
    )
    current = plan.levels[current_level - 1]
    days = _five_to_ten_home_days(journey=journey, today=today)
    next_label, next_timing, next_detail, next_source = _five_to_ten_next(days, today)

    goal_name = (
        str(goal.get("goal_name") or goal.get("race_name") or "Complete 10K")
        if goal else "Complete 10K"
    )
    return HomeSummary(
        athlete_id=athlete_id,
        goal_name=goal_name,
        goal_context=_format_goal_context(goal),
        target_time_s=(goal.get("target_time_s") if goal else None),
        target_date=(goal.get("target_date") if goal else None),
        block_name="5K → 10K",
        block_context=f"Level {current_level} of 10 · {current.title}",
        block_is_saved=True,
        week_days=days,
        week_theme=f"Level {current_level}: {current.emphasis}",
        next_label=next_label,
        next_timing=next_timing,
        next_detail=next_detail,
        next_source=next_source,
    )


def build_home_summary(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> HomeSummary:
    """Build the real-data summary used by the first Home preview."""
    today = today or datetime.date.today()
    goal = get_active_goal(athlete_id)
    journey = get_active_runner_journey(athlete_id)
    if journey is not None and journey.journey_type == COUCH_TO_5K:
        return _build_beginner_home_summary(
            athlete_id,
            goal,
            journey,
            today=today,
        )
    if journey is not None and journey.journey_type == FIVE_TO_TEN_K:
        return _build_five_to_ten_home_summary(
            athlete_id,
            goal,
            journey,
            today=today,
        )

    weekly = build_adaptive_weekly_plan(athlete_id, today=today)
    saved_block = get_current_training_block(athlete_id, today=today)
    operational = build_operational_block_week(athlete_id, today=today)

    goal_name = (
        str(goal.get("goal_name") or goal.get("race_name") or "Active goal")
        if goal
        else "Build your next goal"
    )

    if saved_block:
        progress = block_progress(saved_block, today=today)
        block_name = saved_block.name
        block_bits = [
            value
            for value in (
                saved_block.current_phase,
                (
                    "Upcoming"
                    if progress.week_number == 0
                    else f"Week {progress.week_number} of {progress.total_weeks}"
                    if progress.week_number is not None
                    and progress.total_weeks is not None
                    else None
                ),
            )
            if value
        ]
        block_context = " · ".join(block_bits) or "Active training block"
        block_is_saved = True
    elif weekly.available:
        distance = weekly.distance_label or "Goal"
        block_name = f"{distance} adaptive direction"
        weeks = weekly.weeks_remaining
        block_context = (
            f"Goal-led preview · {weeks} weeks to goal"
            if weeks is not None
            else "Goal-led preview"
        )
        block_is_saved = False
    else:
        block_name = "Current training context"
        block_context = "Building from recent training"
        block_is_saved = False

    if operational is not None and operational.state == "Active":
        days = _operational_days(operational, today)
        block_context = (
            f"{operational.phase} · Week {operational.week_number} of "
            f"{operational.total_weeks} · {operational.status}"
        )
        week_theme = f"{operational.status} · {operational.headline}"
        next_label = operational.next_run.session_type
        next_timing = operational.next_run.timing
        next_detail = operational.next_run.detail
        next_source = operational.source
    else:
        planned_days = weekly.weeks[0].days if weekly.available and weekly.weeks else ()
        days = tuple(
            HomeDay(
                day_name=day.day_name,
                session_family=day.session_family,
                title=day.title,
                detail=day.prescription or day.purpose,
                target=day.target,
                is_today=index == today.weekday(),
            )
            for index, day in enumerate(planned_days)
        )

        week_theme = (
            weekly.weeks[0].theme
            if weekly.available and weekly.weeks
            else weekly.summary
        )

        (
            next_label,
            next_timing,
            next_detail,
            next_source,
        ) = _fallback_next(days, today)

    return HomeSummary(
        athlete_id=athlete_id,
        goal_name=goal_name,
        goal_context=_format_goal_context(goal),
        target_time_s=(goal.get("target_time_s") if goal else None),
        target_date=(goal.get("target_date") if goal else None),
        block_name=block_name,
        block_context=block_context,
        block_is_saved=block_is_saved,
        week_days=days,
        week_theme=week_theme,
        next_label=str(next_label or "Building next run"),
        next_timing=str(next_timing or "Timing building"),
        next_detail=str(next_detail or "Coaching context is building."),
        next_source=str(next_source or "Performance Passport coaching"),
    )

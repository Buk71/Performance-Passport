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
from core.training_blocks import (
    block_progress,
    get_active_training_block,
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


def build_home_summary(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> HomeSummary:
    """Build the real-data summary used by the first Home preview."""
    today = today or datetime.date.today()
    goal = get_active_goal(athlete_id)
    weekly = build_adaptive_weekly_plan(athlete_id, today=today)
    saved_block = get_active_training_block(athlete_id)

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
                    f"Week {progress.week_number} of {progress.total_weeks}"
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

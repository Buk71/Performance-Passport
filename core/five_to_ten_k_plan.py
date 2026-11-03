"""Full adaptive 5K -> 10K plan.

The plan is visible from day one and uses progression levels rather than
fixed calendar weeks. It gradually transitions a 5K runner toward normal
training concepts: easy running, a longer easy run, strides, and later modest
controlled quality. Pace is deliberately secondary to completion/durability.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime


PLAN_LENGTH = 10

LEVEL_STAGE = {
    1: "5k_consistency",
    2: "build_6k",
    3: "build_6k",
    4: "build_7k",
    5: "build_7k",
    6: "build_8k",
    7: "build_8k",
    8: "build_9k",
    9: "build_9k",
    10: "10k_ready",
}

STAGE_ENTRY_LEVEL = {
    "5k_consistency": 1,
    "build_6k": 2,
    "build_7k": 4,
    "build_8k": 6,
    "build_9k": 8,
    "10k_ready": 10,
}

LEVEL_TITLES = {
    1: "Make 5K feel routine",
    2: "Extend the long easy run",
    3: "Add relaxed strides",
    4: "Build toward 7K",
    5: "Consolidate 7K durability",
    6: "Build toward 8K",
    7: "Introduce controlled quality",
    8: "Build toward 9K",
    9: "Consolidate 9K + quality",
    10: "10K ready",
}

LEVEL_LONG_RUN_KM = {
    1: 5.0,
    2: 6.0,
    3: 6.0,
    4: 7.0,
    5: 7.0,
    6: 8.0,
    7: 8.0,
    8: 9.0,
    9: 9.0,
    10: 10.0,
}

LEVEL_QUALITY = {
    1: None,
    2: None,
    3: "4 × 20 sec relaxed strides after an easy run",
    4: "4–6 × 20 sec relaxed strides after an easy run",
    5: "6 × 20 sec relaxed strides after an easy run",
    6: "6 × 20 sec relaxed strides after an easy run",
    7: "3 × 4 min comfortably hard, 2 min easy between",
    8: "4 × 4 min comfortably hard, 2 min easy between",
    9: "3 × 6 min comfortably hard, 2 min easy between",
    10: "Optional 4 × 20 sec strides only; keep the week controlled",
}

LEVEL_EMPHASIS = {
    1: "Consistency before distance",
    2: "A little more time on feet",
    3: "Relaxed leg speed without fatigue",
    4: "Durability to seven kilometres",
    5: "Make seven kilometres feel normal",
    6: "Durability to eight kilometres",
    7: "First taste of controlled quality",
    8: "Durability to nine kilometres",
    9: "Hold durability while sharpening gently",
    10: "Arrive fresh enough to complete 10K",
}


@dataclass(frozen=True)
class FiveToTenKPlanDay:
    day: str
    role: str
    title: str
    detail: str
    counts_for_progression: bool


@dataclass(frozen=True)
class FiveToTenKPlanLevel:
    level_number: int
    stage: str
    title: str
    emphasis: str
    status: str
    long_run_km: float
    sessions: tuple[FiveToTenKPlanDay, ...]
    projected_start_date: str | None
    progression_rule: str


@dataclass(frozen=True)
class FiveToTenKPlan:
    athlete_id: int
    sessions_per_week: int
    entry_level: int
    current_level: int
    levels: tuple[FiveToTenKPlanLevel, ...]
    headline: str
    summary: str
    timeline_note: str
    model_version: int = 1


def entry_level_for_stage(stage: str) -> int:
    try:
        return STAGE_ENTRY_LEVEL[stage]
    except KeyError as exc:
        raise ValueError(f"Unsupported 5K -> 10K stage: {stage}") from exc


def stage_for_level(level_number: int) -> str:
    if int(level_number) not in LEVEL_STAGE:
        raise ValueError("5K -> 10K plan level must be between 1 and 10.")
    return LEVEL_STAGE[int(level_number)]


def _training_days(sessions_per_week: int) -> tuple[str, ...]:
    if sessions_per_week == 2:
        return ("Wednesday", "Sunday")
    if sessions_per_week == 3:
        return ("Tuesday", "Thursday", "Sunday")
    if sessions_per_week == 4:
        return ("Tuesday", "Thursday", "Saturday", "Sunday")
    raise ValueError("5K -> 10K supports 2, 3 or 4 running days per week.")


def _sessions(level: int, sessions_per_week: int) -> tuple[FiveToTenKPlanDay, ...]:
    days = _training_days(sessions_per_week)
    long_run = LEVEL_LONG_RUN_KM[level]
    quality = LEVEL_QUALITY[level]

    if sessions_per_week == 2:
        first = quality or "Easy conversational run, 25–35 minutes"
        return (
            FiveToTenKPlanDay(
                day=days[0],
                role="Easy / quality",
                title="Controlled development run",
                detail=first,
                counts_for_progression=True,
            ),
            FiveToTenKPlanDay(
                day=days[1],
                role="Long easy",
                title=f"{long_run:g}K easy",
                detail="Comfortable effort. Finishing the distance matters more than pace.",
                counts_for_progression=True,
            ),
        )

    items = [
        FiveToTenKPlanDay(
            day=days[0],
            role="Easy",
            title="Easy run",
            detail="25–40 minutes conversational running.",
            counts_for_progression=True,
        ),
        FiveToTenKPlanDay(
            day=days[1],
            role="Quality" if quality else "Easy + strides",
            title="Controlled quality" if quality else "Easy run",
            detail=quality or "25–35 minutes easy; no pace target.",
            counts_for_progression=True,
        ),
    ]

    if sessions_per_week == 4:
        items.append(
            FiveToTenKPlanDay(
                day=days[2],
                role="Recovery",
                title="Short recovery run",
                detail="20–30 minutes very easy. Skip if unusually tired or sore.",
                counts_for_progression=False,
            )
        )

    items.append(
        FiveToTenKPlanDay(
            day=days[-1],
            role="Long easy",
            title=f"{long_run:g}K easy",
            detail="Comfortable effort. Finishing the distance matters more than pace.",
            counts_for_progression=True,
        )
    )
    return tuple(items)


def _status(level: int, entry_level: int, current_level: int) -> str:
    if level < entry_level:
        return "Skipped by entry assessment"
    if level < current_level:
        return "Completed / passed"
    if level == current_level:
        return "Current"
    return "Ahead"


def build_five_to_ten_k_plan(
    *,
    athlete_id: int,
    sessions_per_week: int,
    entry_stage: str,
    current_level: int | None = None,
    reference_date: datetime.date | None = None,
) -> FiveToTenKPlan:
    reference_date = reference_date or datetime.date.today()
    entry_level = entry_level_for_stage(entry_stage)
    current = int(current_level or entry_level)
    current = min(max(current, entry_level), PLAN_LENGTH)

    levels: list[FiveToTenKPlanLevel] = []
    for level in range(1, PLAN_LENGTH + 1):
        offset = level - current
        projected = (
            reference_date + datetime.timedelta(days=offset * 7)
            if level >= current
            else None
        )
        levels.append(
            FiveToTenKPlanLevel(
                level_number=level,
                stage=stage_for_level(level),
                title=LEVEL_TITLES[level],
                emphasis=LEVEL_EMPHASIS[level],
                status=_status(level, entry_level, current),
                long_run_km=LEVEL_LONG_RUN_KM[level],
                sessions=_sessions(level, sessions_per_week),
                projected_start_date=projected.isoformat() if projected else None,
                progression_rule=(
                    "Progress after controlled successful training. Repeat if the "
                    "level still feels hard; step back if completion is poor, pain "
                    "appears, or there has been a long break."
                ),
            )
        )

    return FiveToTenKPlan(
        athlete_id=int(athlete_id),
        sessions_per_week=int(sessions_per_week),
        entry_level=entry_level,
        current_level=current,
        levels=tuple(levels),
        headline="Your full 5K → 10K journey",
        summary=(
            f"10 progression levels are visible from the start. You begin at "
            f"level {entry_level} and are currently on level {current}."
        ),
        timeline_note=(
            "These are progression levels, not fixed calendar weeks. You can "
            "progress early, repeat a level, or step back while keeping the full "
            "journey visible."
        ),
    )

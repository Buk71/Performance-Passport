"""Full adaptive Couch -> 5K training plan.

The plan is intentionally visible in full from day one. Its 12 "weeks" are
progression levels rather than immovable calendar weeks: an athlete can
progress early, repeat a level, or step back without the plan pretending that
the calendar itself created fitness.

Each level uses duration and completion, never pace, threshold or mileage.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.beginner_sessions import (
    BeginnerSessionPrescription,
    build_couch_to_5k_session,
)


PLAN_LENGTH = 12

WEEK_STAGE = {
    1: "walking_foundation",
    2: "run_walk_short",
    3: "run_walk_build",
    4: "run_blocks_5",
    5: "run_blocks_8",
    6: "run_blocks_10",
    7: "continuous_15",
    8: "continuous_20",
    9: "continuous_25",
    10: "continuous_30",
    11: "continuous_30",
    12: "5k_ready",
}

STAGE_ENTRY_WEEK = {
    "walking_foundation": 1,
    "run_walk_short": 2,
    "run_walk_build": 3,
    "run_blocks_5": 4,
    "run_blocks_8": 5,
    "run_blocks_10": 6,
    "continuous_15": 7,
    "continuous_20": 8,
    "continuous_25": 9,
    "continuous_30": 10,
    "5k_ready": 12,
}

WEEK_TITLES = {
    1: "Build the walking foundation",
    2: "Introduce short run / walk",
    3: "Build longer running intervals",
    4: "Own five-minute running blocks",
    5: "Extend to eight-minute blocks",
    6: "Two controlled ten-minute runs",
    7: "First sustained 15-minute run",
    8: "Build to 20 minutes continuous",
    9: "Build to 25 minutes continuous",
    10: "Reach 30 minutes continuous",
    11: "Consolidate 30-minute running",
    12: "Complete your 5K",
}

WEEK_EMPHASIS = {
    1: "Comfortable time on feet",
    2: "Relaxed running with full walk recovery",
    3: "More running, still fully controlled",
    4: "Confidence in repeated running blocks",
    5: "Longer sustained running",
    6: "Controlled double-digit running duration",
    7: "Transition to continuous running",
    8: "Continuous aerobic confidence",
    9: "Durability without pace pressure",
    10: "Reach the continuous-running benchmark",
    11: "Make 30 minutes feel normal",
    12: "5K completion and graduation",
}


@dataclass(frozen=True)
class BeginnerPlanDay:
    day: str
    role: str
    title: str
    detail: str
    counts_for_progression: bool
    source_stage: str | None = None


@dataclass(frozen=True)
class BeginnerPlanWeek:
    week_number: int
    stage: str
    title: str
    emphasis: str
    status: str
    sessions: tuple[BeginnerPlanDay, ...]
    standard_session: BeginnerSessionPrescription
    projected_start_date: str | None
    progression_rule: str


@dataclass(frozen=True)
class CouchTo5KPlan:
    athlete_id: int
    sessions_per_week: int
    entry_week: int
    current_week: int
    weeks: tuple[BeginnerPlanWeek, ...]
    headline: str
    summary: str
    timeline_note: str
    model_version: int = 1


def entry_week_for_stage(stage: str) -> int:
    try:
        return STAGE_ENTRY_WEEK[stage]
    except KeyError as exc:
        raise ValueError(f"Unsupported Couch -> 5K stage: {stage}") from exc


def stage_for_week(week_number: int) -> str:
    if int(week_number) not in WEEK_STAGE:
        raise ValueError("Couch -> 5K plan week must be between 1 and 12.")
    return WEEK_STAGE[int(week_number)]


def _training_days(sessions_per_week: int) -> tuple[str, ...]:
    if sessions_per_week == 2:
        return ("Tuesday", "Saturday")
    if sessions_per_week == 3:
        return ("Tuesday", "Thursday", "Sunday")
    if sessions_per_week == 4:
        # Three progression sessions plus one deliberately easy support day.
        return ("Tuesday", "Thursday", "Saturday", "Sunday")
    raise ValueError("Couch -> 5K supports 2, 3 or 4 training days per week.")


def _session_days(
    week_number: int,
    sessions_per_week: int,
) -> tuple[BeginnerPlanDay, ...]:
    stage = stage_for_week(week_number)
    session = build_couch_to_5k_session(stage)
    days = _training_days(sessions_per_week)

    output: list[BeginnerPlanDay] = []
    progression_days = days if sessions_per_week <= 3 else days[:3]

    for day in progression_days:
        output.append(
            BeginnerPlanDay(
                day=day,
                role="Journey session",
                title=session.title,
                detail=session.pace_guidance,
                counts_for_progression=True,
                source_stage=stage,
            )
        )

    if sessions_per_week == 4:
        output.append(
            BeginnerPlanDay(
                day=days[3],
                role="Support day",
                title="Comfortable walk + mobility",
                detail=(
                    "20–30 minutes comfortable walking. This supports the habit "
                    "but does not have to be completed to progress the running level."
                ),
                counts_for_progression=False,
                source_stage=None,
            )
        )

    return tuple(output)


def _status(week_number: int, entry_week: int, current_week: int) -> str:
    if week_number < entry_week:
        return "Skipped by entry assessment"
    if week_number < current_week:
        return "Completed / passed"
    if week_number == current_week:
        return "Current"
    return "Ahead"


def build_couch_to_5k_plan(
    *,
    athlete_id: int,
    sessions_per_week: int,
    entry_stage: str,
    current_week: int | None = None,
    reference_date: datetime.date | None = None,
) -> CouchTo5KPlan:
    """Build the complete 12-level plan from the athlete's assessed entry point."""
    reference_date = reference_date or datetime.date.today()
    entry_week = entry_week_for_stage(entry_stage)
    current = int(current_week or entry_week)
    current = min(max(current, entry_week), PLAN_LENGTH)

    weeks: list[BeginnerPlanWeek] = []
    for week_number in range(1, PLAN_LENGTH + 1):
        # Dates are explicitly projections only. Repeat/early progression moves them.
        offset = week_number - current
        projected = (
            reference_date + datetime.timedelta(days=offset * 7)
            if week_number >= current
            else None
        )
        stage = stage_for_week(week_number)
        weeks.append(
            BeginnerPlanWeek(
                week_number=week_number,
                stage=stage,
                title=WEEK_TITLES[week_number],
                emphasis=WEEK_EMPHASIS[week_number],
                status=_status(week_number, entry_week, current),
                sessions=_session_days(week_number, sessions_per_week),
                standard_session=build_couch_to_5k_session(stage),
                projected_start_date=projected.isoformat() if projected else None,
                progression_rule=(
                    "Two controlled successful journey sessions can support "
                    "progression. Repeat the level if it still feels hard; step "
                    "back if completion is poor or returning after a long gap."
                ),
            )
        )

    return CouchTo5KPlan(
        athlete_id=int(athlete_id),
        sessions_per_week=int(sessions_per_week),
        entry_week=entry_week,
        current_week=current,
        weeks=tuple(weeks),
        headline="Your full Couch → 5K journey",
        summary=(
            f"12 progression levels are visible from the start. You begin at "
            f"level {entry_week} from your entry assessment and are currently "
            f"on level {current}."
        ),
        timeline_note=(
            "These are progression levels, not fixed calendar weeks. You may "
            "progress early, repeat a level, or step back; projected dates move "
            "with you."
        ),
    )

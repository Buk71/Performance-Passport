"""History-led, athlete-customisable Training Block design.

The engine starts from demonstrated rhythm rather than a generic race plan.
It proposes a safe weekly shape, honours the one Active Primary goal, can place
relevant Secondary races, and keeps every athlete choice explicit and
serialisable. It deliberately plans session *types*, not prescriptive workouts;
Next Run remains responsible for the next detailed session.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime
import math
import statistics
from typing import Any

from core.database import get_athlete_sport_roles, get_connection
from core.goals import GoalHierarchy, GoalHierarchyItem, build_goal_hierarchy
from core.progress import ProgressSummary, build_progress_summary


WEEKDAYS = (
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
)
MODEL_VERSION = 1


@dataclass(frozen=True)
class TrainingHistoryProfile:
    athlete_id: int
    athlete_name: str
    recent_days_per_week: float
    recent_miles_per_week: float
    prior_miles_per_week: float
    sustainable_miles_per_week: float
    recent_hours_per_week: float
    typical_long_run_miles: float | None
    recent_quality_miles_per_week: float
    supported_sessions_per_week: int
    inferred_running_days: tuple[str, ...]
    inferred_long_run_day: str
    evidence_weeks: int
    confidence: str


@dataclass(frozen=True)
class TrainingBlockPreferences:
    running_days: tuple[str, ...]
    long_run_day: str
    session_days: tuple[str, ...]
    strength_days: tuple[str, ...]
    max_weekly_miles: float
    race_replaces_session: bool = True
    recovery_note: str = ""


@dataclass(frozen=True)
class PlannedDay:
    day: str
    session_type: str
    detail: str
    is_hard: bool = False
    event_goal_id: int | None = None


@dataclass(frozen=True)
class BlockDesignWeek:
    week_number: int
    start_date: str
    end_date: str
    phase: str
    target_miles: float
    long_run_miles: float
    session_count: int
    emphasis: str
    is_cutback: bool
    event_name: str | None
    days: tuple[PlannedDay, ...]


@dataclass(frozen=True)
class TrainingBlockDesign:
    athlete_id: int
    athlete_name: str
    primary_goal_id: int
    primary_goal_name: str
    block_name: str
    block_type: str
    start_date: str
    end_date: str
    baseline_miles: float
    peak_miles: float
    weeks: tuple[BlockDesignWeek, ...]
    secondary_goal_ids: tuple[int, ...]
    warnings: tuple[str, ...]
    rationale: tuple[str, ...]
    model_version: int = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preferences_to_dict(
    preferences: TrainingBlockPreferences,
) -> dict[str, Any]:
    return asdict(preferences)


def preferences_from_dict(data: dict[str, Any]) -> TrainingBlockPreferences:
    return TrainingBlockPreferences(
        running_days=tuple(data.get("running_days") or ()),
        long_run_day=str(data.get("long_run_day") or "Sunday"),
        session_days=tuple(data.get("session_days") or ()),
        strength_days=tuple(data.get("strength_days") or ()),
        max_weekly_miles=float(data.get("max_weekly_miles") or 0.0),
        race_replaces_session=bool(data.get("race_replaces_session", True)),
        recovery_note=str(data.get("recovery_note") or ""),
    )


def history_to_dict(history: TrainingHistoryProfile) -> dict[str, Any]:
    return asdict(history)


def _parse_date(value: str | None) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _next_monday(reference_date: datetime.date) -> datetime.date:
    days = (7 - reference_date.weekday()) % 7
    return reference_date + datetime.timedelta(days=days or 7)


def _median(values: list[float], default: float) -> float:
    return float(statistics.median(values)) if values else default


def _weekday_history(
    athlete_id: int,
    reference_date: datetime.date,
) -> tuple[dict[str, int], dict[str, list[float]]]:
    running_ids = {
        str(sport_id)
        for sport_id, role in get_athlete_sport_roles(athlete_id).items()
        if role == "running"
    }
    cutoff = reference_date - datetime.timedelta(days=83)
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT activity_date, sport_id, distance_m
        FROM activities
        WHERE athlete_id = ? AND activity_date BETWEEN ? AND ?
        ORDER BY activity_date, id
        """,
        (athlete_id, cutoff.isoformat(), reference_date.isoformat()),
    ).fetchall()
    connection.close()
    per_date: dict[datetime.date, float] = {}
    for date_text, sport_id, distance_value in rows:
        if str(sport_id or "") not in running_ids:
            continue
        run_date = _parse_date(date_text)
        if run_date is None:
            continue
        try:
            distance_km = float(distance_value or 0.0)
        except (TypeError, ValueError):
            distance_km = 0.0
        if distance_km > 250.0:
            distance_km /= 1000.0
        # Multiple same-day activities are a real double day. For weekday
        # preference inference the day should count once; the longest run is
        # the clearest signal of which day historically carries the long run.
        per_date[run_date] = max(per_date.get(run_date, 0.0), distance_km)
    counts = {day: 0 for day in WEEKDAYS}
    distances = {day: [] for day in WEEKDAYS}
    for run_date, distance_km in per_date.items():
        day = WEEKDAYS[run_date.weekday()]
        counts[day] += 1
        if distance_km > 0:
            distances[day].append(distance_km / 1.609344)
    return counts, distances


def build_training_history_profile(
    athlete_id: int,
    *,
    reference_date: datetime.date | None = None,
    progress: ProgressSummary | None = None,
) -> TrainingHistoryProfile | None:
    progress = progress or build_progress_summary(
        athlete_id,
        reference_date=reference_date,
    )
    if progress is None:
        return None
    evidence_date = _parse_date(progress.reference_date) or datetime.date.today()
    counts, distances = _weekday_history(athlete_id, evidence_date)
    desired_days = min(max(int(round(progress.rhythm.active_days_per_week)), 3), 7)
    ranked_days = sorted(
        WEEKDAYS,
        key=lambda day: (-counts[day], WEEKDAYS.index(day)),
    )
    inferred_days = tuple(
        day for day in WEEKDAYS if day in set(ranked_days[:desired_days])
    )
    long_day = max(
        WEEKDAYS,
        key=lambda day: (
            _median(distances[day], 0.0),
            counts[day],
            -abs(WEEKDAYS.index(day) - 6),
        ),
    )
    long_values = [
        point.long_miles
        for point in progress.rhythm.points
        if point.long_miles > 0
    ]
    recent_points = progress.rhythm.points[-6:]
    quality = statistics.fmean(
        point.quality_miles for point in recent_points
    ) if recent_points else 0.0
    sessions = 2 if quality >= 7.0 else 1 if quality >= 2.0 else 0
    weekly_values = [
        point.reliable_miles
        for point in progress.rhythm.points
        if point.reliable_miles > 0
    ]
    historical_typical = _median(
        weekly_values,
        progress.rhythm.reliable_miles_per_week,
    )
    sustainable = max(
        min(
            max(historical_typical, progress.rhythm.reliable_miles_per_week),
            progress.rhythm.reliable_miles_per_week * 1.08,
        ),
        progress.rhythm.reliable_miles_per_week,
    )
    return TrainingHistoryProfile(
        athlete_id=athlete_id,
        athlete_name=progress.athlete_name,
        recent_days_per_week=progress.rhythm.active_days_per_week,
        recent_miles_per_week=progress.rhythm.reliable_miles_per_week,
        prior_miles_per_week=progress.rhythm.prior_reliable_miles_per_week,
        sustainable_miles_per_week=round(sustainable, 1),
        recent_hours_per_week=progress.rhythm.moving_hours_per_week,
        typical_long_run_miles=(
            round(_median(long_values, 0.0), 1) if long_values else None
        ),
        recent_quality_miles_per_week=round(quality, 1),
        supported_sessions_per_week=sessions,
        inferred_running_days=inferred_days,
        inferred_long_run_day=long_day,
        evidence_weeks=len(progress.rhythm.points),
        confidence=progress.rhythm.confidence,
    )


def _circular_gap(first: str, second: str) -> int:
    gap = abs(WEEKDAYS.index(first) - WEEKDAYS.index(second))
    return min(gap, 7 - gap)


def _recommended_session_days(
    running_days: tuple[str, ...],
    long_run_day: str,
    count: int,
) -> tuple[str, ...]:
    candidates = [day for day in running_days if day != long_run_day]
    selected: list[str] = []
    while candidates and len(selected) < count:
        candidate = max(
            candidates,
            key=lambda day: (
                min(
                    [_circular_gap(day, long_run_day)]
                    + [_circular_gap(day, chosen) for chosen in selected]
                ),
                -WEEKDAYS.index(day),
            ),
        )
        selected.append(candidate)
        candidates.remove(candidate)
    return tuple(day for day in WEEKDAYS if day in selected)


def recommend_preferences(
    history: TrainingHistoryProfile,
) -> TrainingBlockPreferences:
    running_days = history.inferred_running_days
    long_day = history.inferred_long_run_day
    if long_day not in running_days:
        running_days = tuple(
            day for day in WEEKDAYS
            if day in set((*running_days[:-1], long_day))
        )
    session_days = _recommended_session_days(
        running_days,
        long_day,
        history.supported_sessions_per_week,
    )
    max_miles = max(
        history.recent_miles_per_week,
        min(
            history.recent_miles_per_week * 1.12,
            history.sustainable_miles_per_week * 1.05,
        ),
    )
    return TrainingBlockPreferences(
        running_days=running_days,
        long_run_day=long_day,
        session_days=session_days,
        strength_days=(),
        max_weekly_miles=round(max_miles),
        race_replaces_session=True,
        recovery_note="",
    )


def validate_preferences(
    preferences: TrainingBlockPreferences,
    history: TrainingHistoryProfile,
) -> tuple[str, ...]:
    warnings: list[str] = []
    running = set(preferences.running_days)
    sessions = set(preferences.session_days)
    unknown = (running | sessions | set(preferences.strength_days)) - set(WEEKDAYS)
    if unknown:
        warnings.append("One or more selected days are not valid weekdays.")
    if len(running) < 3:
        warnings.append("Fewer than three running days leaves limited room for balanced development.")
    if preferences.long_run_day not in running:
        warnings.append("The long-run day must also be selected as a running day.")
    if not sessions.issubset(running):
        warnings.append("Every session day must also be selected as a running day.")
    hard_days = [day for day in preferences.session_days if day in WEEKDAYS]
    if preferences.long_run_day in WEEKDAYS:
        hard_days.append(preferences.long_run_day)
    for index, first in enumerate(hard_days):
        for second in hard_days[index + 1:]:
            if _circular_gap(first, second) == 1:
                warnings.append(
                    f"{first} and {second} place demanding days back to back."
                )
    if len(preferences.session_days) > history.supported_sessions_per_week:
        warnings.append(
            "The chosen session frequency is above the recent history-supported rhythm."
        )
    if preferences.max_weekly_miles < history.recent_miles_per_week * 0.9:
        warnings.append(
            "The volume ceiling is materially below the athlete's recent average; this becomes a reduced-volume block."
        )
    if preferences.max_weekly_miles > history.recent_miles_per_week * 1.20:
        warnings.append(
            "The volume ceiling is more than 20% above the recent average and will be limited by safe progression."
        )
    conflicts = set(preferences.strength_days) & (
        set(preferences.session_days) | {preferences.long_run_day}
    )
    if conflicts:
        warnings.append(
            "Strength overlaps a demanding run on "
            + ", ".join(day for day in WEEKDAYS if day in conflicts)
            + "; keep that work light or move it."
        )
    return tuple(dict.fromkeys(warnings))


def _goal_block_type(goal: GoalHierarchyItem) -> str:
    distance = goal.distance_m or 0.0
    if distance >= 40000:
        return "Marathon"
    if distance >= 20000:
        return "Half Marathon"
    if distance >= 9000:
        return "10K"
    if distance >= 4500:
        return "5K"
    return goal.goal_type if goal.goal_type else "General"


def _phase_for_week(index: int, total: int) -> str:
    remaining = total - index
    if remaining == 1:
        return "Race"
    if remaining <= 3:
        return "Taper"
    fraction = index / max(total, 1)
    if fraction < 0.25:
        return "Base"
    if fraction < 0.62:
        return "Build"
    return "Specific"


def _emphasis(phase: str, block_type: str) -> str:
    if phase == "Base":
        return "Aerobic support and durable routine"
    if phase == "Build":
        return "Threshold strength and controlled progression"
    if phase == "Specific":
        if block_type == "5K":
            return "5K rhythm, speed endurance and economy"
        if block_type == "10K":
            return "10K rhythm and threshold durability"
        return "Race-specific endurance and sustained control"
    if phase == "Taper":
        return "Freshness with small race-rhythm reminders"
    return "Primary race and recovery"


def _weekly_volume(
    week_index: int,
    total_weeks: int,
    baseline: float,
    peak: float,
    phase: str,
    *,
    has_secondary_race: bool,
) -> tuple[float, bool]:
    if phase == "Race":
        return round(max(baseline * 0.52, 12.0), 1), False
    if phase == "Taper":
        remaining = total_weeks - week_index
        factor = 0.74 if remaining == 2 else 0.86
        return round(max(baseline * factor, 12.0), 1), False
    progress = week_index / max(total_weeks - 3, 1)
    target = baseline + (peak - baseline) * min(max(progress, 0.0), 1.0)
    cutback = week_index > 0 and (week_index + 1) % 4 == 0
    if cutback:
        target *= 0.90
    if has_secondary_race:
        target *= 0.90
    return round(target, 1), cutback


def _session_label(phase: str, position: int, block_type: str) -> str:
    if phase == "Base":
        return "Controlled hills" if position else "Steady threshold introduction"
    if phase == "Build":
        return "Aerobic intervals" if position else "Threshold development"
    if phase == "Specific":
        if block_type == "5K":
            return "5K / VO₂ repetitions" if position else "Threshold maintenance"
        if block_type == "10K":
            return "10K repetitions" if position else "Threshold development"
        return "Race-pace intervals" if position else "Sustained threshold"
    if phase == "Taper":
        return "Race-rhythm reminder"
    return "Short race-rhythm reminder"


def _build_days(
    *,
    week_start: datetime.date,
    phase: str,
    block_type: str,
    target_miles: float,
    long_miles: float,
    preferences: TrainingBlockPreferences,
    event: GoalHierarchyItem | None,
    primary: GoalHierarchyItem,
) -> tuple[PlannedDay, ...]:
    run_days = set(preferences.running_days)
    session_days = list(preferences.session_days)
    event_date = _parse_date(event.target_date) if event else None
    primary_date = _parse_date(primary.target_date)
    race_date = primary_date if phase == "Race" else event_date
    race_goal = primary if phase == "Race" else event
    race_day = WEEKDAYS[race_date.weekday()] if race_date else None
    if race_day and preferences.race_replaces_session and session_days:
        session_days = sorted(
            session_days,
            key=lambda day: _circular_gap(day, race_day),
            reverse=True,
        )[:-1]
    easy_days = [
        day for day in preferences.running_days
        if day != preferences.long_run_day and day not in session_days
    ]
    allocated = long_miles
    allocated += len(session_days) * min(max(target_miles * 0.16, 4.0), 7.0)
    easy_distance = max(
        (target_miles - allocated) / max(len(easy_days), 1),
        2.0,
    )
    days: list[PlannedDay] = []
    for index, day in enumerate(WEEKDAYS):
        date = week_start + datetime.timedelta(days=index)
        strength = day in preferences.strength_days
        if race_date == date and race_goal is not None:
            distance = (race_goal.distance_m or 0.0) / 1609.344
            days.append(
                PlannedDay(
                    day=day,
                    session_type=(
                        "Primary race" if race_goal.id == primary.id else "Secondary race"
                    ),
                    detail=(
                        f"{race_goal.race_name or race_goal.name} · "
                        f"{distance:.1f} mi"
                    ),
                    is_hard=True,
                    event_goal_id=race_goal.id,
                )
            )
        elif day == preferences.long_run_day and day in run_days:
            follows_event = (
                event_date is not None
                and _circular_gap(day, WEEKDAYS[event_date.weekday()]) == 1
            )
            days.append(
                PlannedDay(
                    day=day,
                    session_type="Post-race recovery" if follows_event else "Long run",
                    detail=(
                        f"Up to {long_miles:.1f} mi very easy after the Secondary race"
                        if follows_event
                        else f"{long_miles:.1f} mi comfortable endurance"
                    ),
                    is_hard=not follows_event,
                )
            )
        elif day in session_days and day in run_days:
            session_index = session_days.index(day)
            days.append(
                PlannedDay(
                    day=day,
                    session_type=_session_label(phase, session_index, block_type),
                    detail="Controlled quality; Next Run sets the exact prescription",
                    is_hard=True,
                )
            )
        elif day in run_days:
            previous = WEEKDAYS[(index - 1) % 7]
            recovery = previous in set(session_days) | {preferences.long_run_day}
            days.append(
                PlannedDay(
                    day=day,
                    session_type="Recovery" if recovery else "Easy",
                    detail=f"{easy_distance:.1f} mi conversational" + (
                        " · strength" if strength else ""
                    ),
                )
            )
        else:
            days.append(
                PlannedDay(
                    day=day,
                    session_type="Strength" if strength else "Rest",
                    detail="Strength and mobility" if strength else "No running",
                )
            )
    return tuple(days)


def design_training_block(
    *,
    history: TrainingHistoryProfile,
    hierarchy: GoalHierarchy,
    preferences: TrainingBlockPreferences,
    reference_date: datetime.date | None = None,
) -> TrainingBlockDesign:
    if hierarchy.primary is None:
        raise ValueError("An Active Primary goal is required to design a block.")
    primary = hierarchy.primary
    reference_date = reference_date or datetime.date.today()
    goal_date = _parse_date(primary.target_date)
    if goal_date is None:
        raise ValueError("The Primary goal needs a target date.")
    start = _next_monday(reference_date)
    if goal_date < start:
        raise ValueError("The Primary goal date must be after the block starts.")
    total_weeks = max(1, math.ceil(((goal_date - start).days + 1) / 7))
    end = goal_date
    block_type = _goal_block_type(primary)
    baseline = min(
        history.recent_miles_per_week,
        max(preferences.max_weekly_miles, 1.0),
    )
    safe_peak = min(
        max(preferences.max_weekly_miles, baseline),
        max(history.sustainable_miles_per_week * 1.05, baseline),
        max(history.recent_miles_per_week * 1.15, baseline),
    )
    secondary = tuple(
        goal for goal in hierarchy.secondary
        if (_parse_date(goal.target_date) is not None)
        and start <= _parse_date(goal.target_date) <= goal_date
    )
    weeks: list[BlockDesignWeek] = []
    previous_long = history.typical_long_run_miles or max(baseline * 0.25, 6.0)
    for index in range(total_weeks):
        week_start = start + datetime.timedelta(days=index * 7)
        week_end = min(week_start + datetime.timedelta(days=6), goal_date)
        phase = _phase_for_week(index, total_weeks)
        event = next(
            (
                goal for goal in secondary
                if week_start <= _parse_date(goal.target_date) <= week_end
            ),
            None,
        )
        target, cutback = _weekly_volume(
            index,
            total_weeks,
            baseline,
            safe_peak,
            phase,
            has_secondary_race=event is not None,
        )
        goal_long_cap = {
            "5K": 12.0,
            "10K": 14.0,
            "Half Marathon": 17.0,
            "Marathon": 22.0,
        }.get(block_type, 14.0)
        typical_long = history.typical_long_run_miles or previous_long
        long_share = 0.27 if block_type in {"5K", "10K"} else 0.30
        long_target = min(
            max(target * long_share, min(typical_long, target * 0.38)),
            goal_long_cap,
            previous_long + 1.0,
        )
        if phase == "Taper":
            long_target = min(long_target, previous_long * 0.80)
        elif phase == "Race":
            long_target = 0.0 if primary.distance_m and primary.distance_m >= 8000 else min(long_target, 6.0)
        long_target = round(max(long_target, 0.0), 1)
        if event is not None:
            event_date = _parse_date(event.target_date)
            event_day = WEEKDAYS[event_date.weekday()]
            if event_day == preferences.long_run_day:
                long_target = 0.0
            elif _circular_gap(event_day, preferences.long_run_day) == 1:
                long_target = round(long_target * 0.55, 1)
        days = _build_days(
            week_start=week_start,
            phase=phase,
            block_type=block_type,
            target_miles=target,
            long_miles=long_target,
            preferences=preferences,
            event=event,
            primary=primary,
        )
        weeks.append(
            BlockDesignWeek(
                week_number=index + 1,
                start_date=week_start.isoformat(),
                end_date=week_end.isoformat(),
                phase=phase,
                target_miles=target,
                long_run_miles=long_target,
                session_count=sum(
                    day.is_hard
                    and day.session_type not in {
                        "Long run", "Primary race", "Secondary race"
                    }
                    for day in days
                ),
                emphasis=_emphasis(phase, block_type),
                is_cutback=cutback,
                event_name=(event.race_name or event.name) if event else None,
                days=days,
            )
        )
        if long_target > 0:
            previous_long = long_target
    warnings = list(validate_preferences(preferences, history))
    if total_weeks < 6:
        warnings.append(
            "There are fewer than six weeks to the Primary goal, so this is a short preparation block."
        )
    if preferences.recovery_note.strip():
        warnings.append(
            "A recovery constraint has been recorded; use it when reviewing every weekly adjustment."
        )
    rationale = (
        f"Starts from {history.recent_miles_per_week:.1f} recent reliable miles across {history.recent_days_per_week:.1f} days per week.",
        f"Caps planned volume at {safe_peak:.1f} miles, within both the chosen ceiling and demonstrated history.",
        f"Uses {len(preferences.session_days)} selected session day{'s' if len(preferences.session_days) != 1 else ''} and protects the {preferences.long_run_day} long-run pattern.",
        f"Builds toward {primary.name}; relevant Secondary races replace training load rather than adding hidden intensity.",
    )
    return TrainingBlockDesign(
        athlete_id=history.athlete_id,
        athlete_name=history.athlete_name,
        primary_goal_id=primary.id,
        primary_goal_name=primary.name,
        block_name=f"{primary.name} Training Block",
        block_type=block_type,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        baseline_miles=round(baseline, 1),
        peak_miles=round(max(week.target_miles for week in weeks), 1),
        weeks=tuple(weeks),
        secondary_goal_ids=tuple(goal.id for goal in secondary),
        warnings=tuple(dict.fromkeys(warnings)),
        rationale=rationale,
    )


def build_history_led_design(
    athlete_id: int,
    preferences: TrainingBlockPreferences | None = None,
    *,
    reference_date: datetime.date | None = None,
) -> tuple[TrainingHistoryProfile, GoalHierarchy, TrainingBlockPreferences, TrainingBlockDesign] | None:
    history = build_training_history_profile(
        athlete_id,
        reference_date=reference_date,
    )
    if history is None:
        return None
    hierarchy = build_goal_hierarchy(
        athlete_id,
        reference_date=reference_date,
    )
    selected = preferences or recommend_preferences(history)
    design = design_training_block(
        history=history,
        hierarchy=hierarchy,
        preferences=selected,
        reference_date=reference_date,
    )
    return history, hierarchy, selected, design

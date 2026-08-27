
"""
Adaptive Weekly Plan Preview v0.19.1.

Turns the Adaptive Training Block strategy into actual day-by-day weeks.
It remains preview-only: no live recommendation or saved training block is changed.

Personalisation comes from:
- active goal and time to race;
- athlete-specific successful-preparation evidence;
- athlete's recent weekly running rhythm;
- athlete's own historical workout structures where trustworthy;
- current personal pace/HR target logic from Session Designer.

The plan uses a small fallback library only when personal evidence is insufficient.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import re
from collections import Counter
from functools import lru_cache
from typing import Any

from core.adaptive_training_block import (
    AdaptiveBlockPreview,
    AdaptivePhase,
    build_adaptive_block_preview,
)
from core.database import get_active_goal, get_athlete_sport_roles, get_connection
from core.performance_backtracking import (
    _family_components,
    build_performance_backtracking_profile,
)
from core.session_designer import (
    _historical_candidates,
    _targets,
)


DAY_NAMES = ("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")


@dataclass(frozen=True)
class PlannedDay:
    day_name: str
    session_family: str
    title: str
    prescription: str
    target: str | None
    purpose: str
    evidence: str


@dataclass(frozen=True)
class PlannedWeek:
    week_number: int
    phase_name: str
    theme: str
    days: tuple[PlannedDay, ...]


@dataclass(frozen=True)
class AdaptiveWeeklyPlan:
    athlete_id: int
    available: bool
    goal_name: str | None
    distance_label: str | None
    weeks_remaining: int | None
    quality_days: tuple[str, ...]
    long_run_day: str | None
    rest_day: str | None
    weeks: tuple[PlannedWeek, ...]
    summary: str
    limitations: tuple[str, ...]
    model_version: int = 1


@lru_cache(maxsize=64)
def _goal_pace(athlete_id: int) -> float | None:
    goal = get_active_goal(athlete_id)
    if not goal:
        return None
    try:
        target=float(goal.get("target_time_s") or 0)
        distance=float(goal.get("distance_m") or 0)
    except (TypeError,ValueError):
        return None
    if target <= 0 or distance <= 0:
        return None
    return target / (distance / 1000.0)


def _pace_text(seconds_per_km: float | None) -> str | None:
    if seconds_per_km is None:
        return None
    total=int(round(seconds_per_km))
    minutes,seconds=divmod(total,60)
    per_mile=seconds_per_km*1.609344
    mile_total=int(round(per_mile))
    mile_min,mile_sec=divmod(mile_total,60)
    return f"{minutes}:{seconds:02d}/km · {mile_min}:{mile_sec:02d}/mi"


@lru_cache(maxsize=256)
def _target_text(athlete_id: int, family: str) -> str | None:
    evidence=_historical_candidates(athlete_id,family,limit=5)
    low,high,hr_low,hr_high,rpe_low,rpe_high=_targets(
        athlete_id,family,evidence,goal_pace_s_per_km=_goal_pace(athlete_id)
    )
    parts=[]
    if low is not None and high is not None:
        # Lower seconds = faster pace, so display faster–slower naturally.
        parts.append(f"{_pace_text(low)} to {_pace_text(high)}")
    if hr_low is not None and hr_high is not None:
        parts.append(f"HR {hr_low}–{hr_high}")
    parts.append(f"RPE {rpe_low:g}–{rpe_high:g}")
    return " · ".join(parts)


@lru_cache(maxsize=64)
def _training_rhythm(athlete_id: int) -> tuple[tuple[str,...],str,str]:
    """Infer likely quality, long-run and rest days from recent real history."""
    roles=get_athlete_sport_roles(athlete_id)
    running={str(k) for k,v in roles.items() if v=="running"}
    today=datetime.date.today()
    cutoff=(today-datetime.timedelta(days=180)).isoformat()

    conn=get_connection(); cur=conn.cursor()
    cur.execute("""
        SELECT activity_date,sport_id,distance_m
        FROM activities
        WHERE athlete_id=? AND activity_date>=?
    """,(athlete_id,cutoff))
    activities=cur.fetchall()

    cur.execute("""
        SELECT activity_date,phase_json
        FROM workout_library
        WHERE athlete_id=? AND activity_date>=?
          AND phase_confidence>=0.70 AND recognition_confidence>=0.65
    """,(athlete_id,cutoff))
    workouts=cur.fetchall()
    conn.close()

    run_days=Counter()
    long_days=Counter()
    quality_days=Counter()

    for date_text,sport_id,distance_value in activities:
        if str(sport_id or "") not in running:
            continue
        try:
            day=datetime.date.fromisoformat(str(date_text)[:10]).weekday()
            distance=float(distance_value or 0)
            if distance>250: distance/=1000
        except (TypeError,ValueError):
            continue
        run_days[day]+=1
        if distance>=14:
            long_days[day]+=1

    for date_text,phase_json in workouts:
        try:
            day=datetime.date.fromisoformat(str(date_text)[:10]).weekday()
        except (TypeError,ValueError):
            continue
        if phase_json and phase_json != "[]":
            quality_days[day]+=1

    quality=[DAY_NAMES[i] for i,_ in quality_days.most_common(2)]
    if len(quality)<2:
        # Conservative runner-friendly fallback.
        quality=["Wednesday","Saturday"]

    long_day=DAY_NAMES[long_days.most_common(1)[0][0]] if long_days else "Sunday"

    # Rest day = least frequently run recent weekday, avoiding primary quality/long days.
    candidates=[
        (run_days.get(i,0),DAY_NAMES[i])
        for i in range(7)
        if DAY_NAMES[i] not in set(quality) | {long_day}
    ]
    rest=min(candidates)[1] if candidates else "Friday"
    return tuple(quality[:2]),long_day,rest


RECOGNISABLE_REP_DISTANCES_M = (
    200, 300, 400, 500, 600, 800, 1000, 1200, 1600,
)


def _snap_rep_distance(metres: float | int) -> int:
    """
    Convert decoder averages into coach-friendly prescription distances.

    Historical sessions remain stored at their real measured value. Only the
    future prescription is normalised: e.g. 775m -> 800m, 525m -> 500m.
    """
    value = max(float(metres), 1.0)
    return min(
        RECOGNISABLE_REP_DISTANCES_M,
        key=lambda standard: abs(standard - value),
    )


def _humanise_signature(signature: str) -> str:
    text=str(signature or "").strip()
    m=re.fullmatch(
        r"(threshold|short_intervals|long_intervals|strides)_(\d+)x(\d+)m",
        text,
    )
    if m:
        family,count,metres=m.groups()
        snapped=_snap_rep_distance(int(metres))
        label={
            "threshold":"threshold",
            "short_intervals":"controlled intervals",
            "long_intervals":"long intervals",
            "strides":"strides",
        }[family]
        return f"{count} × {snapped}m {label}"

    m=re.fullmatch(r"threshold_(\d+)x(\d+)min",text)
    if m:
        return f"{m.group(1)} × {m.group(2)} min threshold"

    return text.replace("_"," ")


def _personal_signature(
    athlete_id: int,
    family: str,
    profile,
) -> tuple[str|None,str]:
    prefix={
        "threshold":"threshold_",
        "vo2":"short_intervals_",
        "speed":"short_intervals_",
    }.get(family)

    if prefix:
        for item in profile.signature_lifts:
            if item.workout_signature.startswith(prefix):
                return (
                    _humanise_signature(item.workout_signature),
                    "Successful-preparation history",
                )

        for signature,_count in profile.recurring_42d_signatures:
            if signature.startswith(prefix):
                return (
                    _humanise_signature(signature),
                    "Repeated before strong performances",
                )

    evidence=_historical_candidates(
        athlete_id,
        family,
        limit=1,
    )
    if evidence:
        item=evidence[0]
        if item.rep_count and item.average_rep_distance_km:
            metres=_snap_rep_distance(
                item.average_rep_distance_km*1000
            )
            return (
                f"{item.rep_count} × {metres}m",
                "Personal workout history",
            )
        if item.rep_count and item.average_rep_duration_s:
            minutes=max(
                1,
                round(item.average_rep_duration_s/60),
            )
            return (
                f"{item.rep_count} × {minutes} min",
                "Personal workout history",
            )

    return None,"Coaching fallback"


def _parse_rep_prescription(
    prescription: str,
) -> tuple[int,int] | None:
    match=re.search(
        r"(\d+)\s*×\s*(\d+)\s*m",
        prescription,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    return int(match.group(1)),_snap_rep_distance(int(match.group(2)))


def _progress_interval_session(
    base: str,
    week_in_phase: int,
) -> str:
    """
    Progress a personal interval pattern through recognisable rep distances.

    The loading is intentionally stepped rather than linear. The total work
    grows, then rep length increases, which makes the block visibly progress
    without turning every week into a bigger session than the last.
    """
    parsed=_parse_rep_prescription(base)

    if parsed is None:
        fallback=(
            "8 × 400m controlled intervals",
            "10 × 400m controlled intervals",
            "8 × 500m controlled intervals",
            "8 × 600m controlled intervals",
            "6 × 800m controlled intervals",
            "7 × 800m controlled intervals",
            "5 × 1000m controlled intervals",
            "6 × 1000m controlled intervals",
            "5 × 1200m controlled intervals",
            "4 × 1200m controlled intervals",
        )
        return fallback[
            min(max(week_in_phase-1,0),len(fallback)-1)
        ]

    base_count,base_distance=parsed
    standards=list(RECOGNISABLE_REP_DISTANCES_M)
    index=standards.index(base_distance)

    # Personal starting structure first, then progressive overload.
    patterns=(
        (0,0),
        (1,0),
        (0,1),
        (1,1),
        (0,2),
        (1,2),
        (0,3),
        (1,3),
        (0,4),
        (0,4),
    )
    rep_add,distance_add=patterns[
        min(max(week_in_phase-1,0),len(patterns)-1)
    ]
    new_distance=standards[
        min(index+distance_add,len(standards)-1)
    ]

    # As reps get longer, keep total work in a sensible range.
    base_total=base_count*base_distance
    desired_total=base_total*(
        1.0+0.06*min(max(week_in_phase-1,0),6)
    )
    calculated=max(
        3,
        round(desired_total/new_distance),
    )
    new_count=max(
        3,
        calculated+rep_add,
    )

    return f"{new_count} × {new_distance}m controlled intervals"


def _progress_threshold_session(
    base: str,
    week_in_phase: int,
) -> str:
    """
    Threshold progression prioritises recognisable, coach-like structures.

    Distance-based personal history is respected for the first weeks, then
    progression moves toward sustained threshold duration rather than endlessly
    increasing rep count.
    """
    parsed=_parse_rep_prescription(base)
    week=max(1,week_in_phase)

    if parsed is not None and week <= 3:
        count,distance=parsed
        distance=_snap_rep_distance(distance)

        if week==1:
            return f"{count} × {distance}m threshold"

        if week==2:
            next_distance=_snap_rep_distance(
                distance*1.20
            )
            total=count*distance
            new_count=max(
                3,
                round(total*1.06/next_distance),
            )
            return f"{new_count} × {next_distance}m threshold"

        next_distance=_snap_rep_distance(
            distance*1.45
        )
        total=count*distance
        new_count=max(
            3,
            round(total*1.12/next_distance),
        )
        return f"{new_count} × {next_distance}m threshold"

    progression=(
        "4 × 8 min threshold",
        "3 × 10 min threshold",
        "4 × 10 min threshold",
        "3 × 12 min threshold",
        "2 × 15 min threshold",
        "3 × 10 min threshold",
        "2 × 12 min threshold + 4 × 30 sec relaxed strides",
    )

    # After three personal-distance weeks, move through sustained work.
    index=max(0,week-4 if parsed is not None else week-1)
    return progression[
        min(index,len(progression)-1)
    ]


def _specific_prescription(
    distance: str,
    slot: int,
    week_in_phase: int,
) -> tuple[str,str]:
    week=max(1,week_in_phase)

    if distance=="5K":
        first=(
            "6 × 800m at controlled 5K effort",
            "5 × 1000m at controlled 5K effort",
            "4 × 1200m at 5K–10K effort",
            "3 × 1600m around 5K–10K effort",
        )
        second=(
            "3 × 10 min threshold",
            "3 × 12 min threshold",
            "2 × 15 min threshold",
            "2 × 10 min threshold + 4 × 200m relaxed",
        )
    elif distance=="10K":
        first=(
            "5 × 1000m at goal 10K pace",
            "4 × 1200m at goal 10K pace",
            "3 × 1600m at goal 10K pace",
            "3 × 2 km at goal 10K pace",
            "2 × 2 km + 4 × 400m at 10K-to-5K effort",
        )
        second=(
            "3 × 10 min threshold",
            "3 × 12 min threshold",
            "2 × 15 min threshold",
            "2 × 12 min threshold + 4 × 30 sec strides",
            "20 min controlled threshold",
        )
    elif distance=="Half Marathon":
        first=(
            "3 × 2 km at half-marathon effort",
            "3 × 3 km at half-marathon effort",
            "2 × 4 km at half-marathon effort",
            "3 × 3 km at goal half-marathon pace",
        )
        second=(
            "3 × 12 min threshold",
            "2 × 15 min threshold",
            "2 × 20 min threshold",
            "25 min controlled threshold",
        )
    else:
        first=(
            "4 × 1000m at goal race pace",
            "3 × 1600m at goal race pace",
            "3 × 2 km at goal race pace",
        )
        second=(
            "3 × 10 min threshold",
            "3 × 12 min threshold",
            "2 × 15 min threshold",
        )

    sequence=first if slot==1 else second
    return (
        "race_pace" if slot==1 else "threshold",
        sequence[min(week-1,len(sequence)-1)],
    )


def _quality_prescription(
    athlete_id: int,
    distance: str,
    phase: str,
    slot: int,
    week_in_phase: int,
    profile,
) -> tuple[str,str,str]:
    if phase.startswith("Taper"):
        if slot==1:
            return (
                "race_pace",
                "3 × 1 km at goal race pace",
                "Race-specific sharpening",
            )
        return (
            "speed",
            "6 × 200m relaxed and quick",
            "Freshness / leg speed",
        )

    if phase=="Specific":
        family,prescription=_specific_prescription(
            distance,
            slot,
            week_in_phase,
        )
        return (
            family,
            prescription,
            "Goal-specific progression",
        )

    family="vo2" if slot==1 else "threshold"
    personal,source=_personal_signature(
        athlete_id,
        family,
        profile,
    )

    if family=="vo2":
        base=personal or "8 × 400m controlled intervals"
        return (
            family,
            _progress_interval_session(
                base,
                week_in_phase,
            ),
            (
                source
                + " + progressive overload"
            ),
        )

    base=personal or "3 × 10 min threshold"
    return (
        family,
        _progress_threshold_session(
            base,
            week_in_phase,
        ),
        (
            source
            + " + progressive overload"
        ),
    )


def _phase_for_week(preview: AdaptiveBlockPreview, week: int) -> AdaptivePhase:
    for phase in preview.phases:
        if phase.start_week <= week <= phase.end_week:
            return phase
    return preview.phases[-1]



def _completed_family_today(
    athlete_id: int,
    today: datetime.date,
) -> tuple[str | None, str | None]:
    """
    Recognise the whole-session stimulus already completed today.

    Whole-activity context deliberately outranks split decoder fragments here.
    A titled 'SLR 12 miles' is a long-run stimulus even if mile splits resemble
    repetitions to the low-level decoder.
    """
    roles = get_athlete_sport_roles(athlete_id)
    running = {
        str(k)
        for k, v in roles.items()
        if v == "running"
    }

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, distance_m
        FROM activities
        WHERE athlete_id = ?
          AND activity_date = ?
        ORDER BY distance_m DESC
        """,
        (athlete_id, today.isoformat()),
    )
    rows = cursor.fetchall()

    for activity_id, title, distance_value in rows:
        cursor.execute(
            "SELECT sport_id FROM activities WHERE id = ?",
            (activity_id,),
        )
        sport_row = cursor.fetchone()

        if (
            not sport_row
            or str(sport_row[0] or "") not in running
        ):
            continue

        try:
            distance = float(distance_value or 0.0)
        except (TypeError, ValueError):
            distance = 0.0

        if distance > 250:
            distance /= 1000.0

        lower = str(title or "").lower()

        if (
            distance >= 14.0
            or "long run" in lower
            or "slr" in lower
        ):
            conn.close()
            return "endurance", str(title or "Completed long run")

        cursor.execute(
            """
            SELECT phase_json, recognition_confidence, phase_confidence
            FROM workout_library
            WHERE activity_id = ?
            """,
            (activity_id,),
        )
        workout = cursor.fetchone()

        if (
            workout
            and float(workout[1] or 0) >= 0.65
            and float(workout[2] or 0) >= 0.70
        ):
            components = _family_components(workout[0])

            if "threshold" in components:
                conn.close()
                return "threshold", str(title or "Completed threshold")
            if "short_intervals" in components:
                conn.close()
                return "vo2", str(title or "Completed intervals")

        if "threshold" in lower or "tempo" in lower:
            conn.close()
            return "threshold", str(title or "Completed threshold")
        if "interval" in lower or "reps" in lower or "session" in lower:
            conn.close()
            return "vo2", str(title or "Completed workout")

    conn.close()
    return None, None



def build_adaptive_weekly_plan(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> AdaptiveWeeklyPlan:
    today=today or datetime.date.today()
    block=build_adaptive_block_preview(athlete_id,today=today)
    if not block.available:
        return AdaptiveWeeklyPlan(
            athlete_id,False,None,None,None,(),None,None,(),block.summary,
            ("Preview only; no live recommendation has changed.",),
        )

    quality_days,long_day,rest_day=_training_rhythm(athlete_id)
    history_profile=build_performance_backtracking_profile(athlete_id)
    completed_family, completed_title = _completed_family_today(
        athlete_id,
        today,
    )
    weeks=[]
    phase_week_counter=Counter()

    total_weeks=int(block.weeks_remaining or 1)
    for week_number in range(1,total_weeks+1):
        phase=_phase_for_week(block,week_number)
        phase_week_counter[phase.name]+=1
        q1_family,q1,q1_source=_quality_prescription(
            athlete_id,block.distance_label or "General",phase.name,1,
            phase_week_counter[phase.name],history_profile
        )
        q2_family,q2,q2_source=_quality_prescription(
            athlete_id,block.distance_label or "General",phase.name,2,
            phase_week_counter[phase.name],history_profile
        )

        days=[]
        for day in DAY_NAMES:
            is_today = (
                week_number == 1
                and day == DAY_NAMES[today.weekday()]
            )

            planned_family_for_day = (
                "endurance"
                if day == long_day
                else q1_family
                if day == quality_days[0]
                else q2_family
                if day == quality_days[1]
                else None
            )

            if (
                is_today
                and completed_family is not None
                and (
                    completed_family == planned_family_for_day
                    or (
                        completed_family in {"vo2", "speed", "race_pace"}
                        and planned_family_for_day in {"vo2", "speed", "race_pace"}
                    )
                )
            ):
                days.append(
                    PlannedDay(
                        day,
                        "completed",
                        "Completed today",
                        completed_title or "Completed planned stimulus",
                        None,
                        "Today's completed run already supplied this stimulus.",
                        "Live activity reconciliation",
                    )
                )
            elif day==rest_day:
                days.append(PlannedDay(day,"rest","Rest / optional mobility","No running",None,
                    "Absorb training and protect quality.","Recent weekly rhythm"))
            elif day==quality_days[0]:
                days.append(PlannedDay(day,q1_family,"Key Session 1",q1,_target_text(athlete_id,q1_family),
                    phase.purpose,q1_source))
            elif day==quality_days[1]:
                days.append(PlannedDay(day,q2_family,"Key Session 2",q2,_target_text(athlete_id,q2_family),
                    phase.purpose,q2_source))
            elif day==long_day:
                long_minutes=75 if phase.name.startswith("Taper") else (95 if block.distance_label in {"10K","Half Marathon"} else 85)
                days.append(PlannedDay(day,"endurance","Long Easy",f"{long_minutes} min comfortable continuous running",
                    _target_text(athlete_id,"endurance"),
                    "Maintain aerobic durability without compromising key-session quality.",
                    "Successful-preparation + current goal"))
            else:
                family="recovery" if day in {
                    DAY_NAMES[(DAY_NAMES.index(quality_days[0])+1)%7],
                    DAY_NAMES[(DAY_NAMES.index(quality_days[1])+1)%7],
                } else "easy"
                title="Recovery Run" if family=="recovery" else "Easy Aerobic"
                prescription="30–40 min very easy" if family=="recovery" else "40–55 min conversational"
                days.append(PlannedDay(day,family,title,prescription,_target_text(athlete_id,family),
                    "Support adaptation without stealing freshness from the key work.",
                    "Current personal easy-run targets"))

        weeks.append(PlannedWeek(
            week_number=week_number,phase_name=phase.name,
            theme=f"{phase.primary_focus} · {phase.quality_emphasis}",
            days=tuple(days),
        ))

    return AdaptiveWeeklyPlan(
        athlete_id=athlete_id,available=True,goal_name=block.goal_name,
        distance_label=block.distance_label,weeks_remaining=block.weeks_remaining,
        quality_days=quality_days,long_run_day=long_day,rest_day=rest_day,
        weeks=tuple(weeks),
        summary=(
            f"PP translated the {block.distance_label} block into {len(weeks)} actual weeks. "
            f"The current rhythm inferred from real training places key sessions on "
            f"{quality_days[0]} and {quality_days[1]}, with the long run on {long_day}."
        ),
        limitations=(
            "Preview only: nothing here changes Recommended Next Run, Next Run or the saved Training Block.",
            "Future live versions must recalculate after each completed run and use readiness before preserving or changing the next workout.",
            "Descriptive activity titles and richer FIT data will progressively improve workout-intent recognition and personal historical matching.",
            "Fallback workouts are used only when trustworthy personal historical structures are not available.",
        ),
    )


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
from core.performance_backtracking import build_performance_backtracking_profile
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


def _humanise_signature(signature: str) -> str:
    text=str(signature or "").strip()
    m=re.fullmatch(r"(threshold|short_intervals|long_intervals|strides)_(\d+)x(\d+)m",text)
    if m:
        family,count,metres=m.groups()
        label={
            "threshold":"threshold",
            "short_intervals":"controlled intervals",
            "long_intervals":"long intervals",
            "strides":"strides",
        }[family]
        return f"{count} × {metres}m {label}"

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
                return _humanise_signature(item.workout_signature), "Successful-preparation history"

        for signature,_count in profile.recurring_42d_signatures:
            if signature.startswith(prefix):
                return _humanise_signature(signature), "Repeated before strong performances"

    # Session Designer personal history is the second source.
    evidence=_historical_candidates(athlete_id,family,limit=1)
    if evidence:
        item=evidence[0]
        if item.rep_count and item.average_rep_distance_km:
            metres=int(round(item.average_rep_distance_km*1000/25)*25)
            return f"{item.rep_count} × {metres}m", "Personal workout history"
        if item.rep_count and item.average_rep_duration_s:
            minutes=max(1,round(item.average_rep_duration_s/60))
            return f"{item.rep_count} × {minutes} min", "Personal workout history"

    return None,"Coaching fallback"


def _quality_prescription(
    athlete_id: int,
    distance: str,
    phase: str,
    slot: int,
    week_in_phase: int,
    profile,
) -> tuple[str,str,str]:
    """
    slot 1 = first weekly quality stimulus
    slot 2 = second weekly quality stimulus
    """
    if phase.startswith("Taper"):
        if slot==1:
            return "race_pace", "3 × 1 km at goal race pace", "Race-specific sharpening"
        return "speed", "6 × 200m relaxed and quick", "Freshness / leg speed"

    if phase=="Specific":
        if distance=="5K":
            prescriptions=[
                ("vo2","5 × 1 km at controlled 5K effort"),
                ("threshold","2 × 12 min threshold"),
            ]
        elif distance=="10K":
            prescriptions=[
                ("race_pace","5 × 1 km at goal 10K pace"),
                ("threshold","3 × 10 min threshold"),
            ]
        elif distance=="Half Marathon":
            prescriptions=[
                ("race_pace","3 × 3 km at goal HM effort"),
                ("threshold","3 × 12 min threshold"),
            ]
        else:
            prescriptions=[
                ("race_pace","3 × 2 km at goal race pace"),
                ("threshold","3 × 10 min threshold"),
            ]
        family,prescription=prescriptions[slot-1]
        return family,prescription,"Goal-specific progression"

    # Build: let personal history lead where possible.
    family="vo2" if slot==1 else "threshold"
    personal,source=_personal_signature(athlete_id,family,profile)
    if personal:
        return family,personal,source

    if family=="vo2":
        return family,"6 × 3 min strong and controlled","Coaching fallback"
    return family,"3 × 10 min threshold","Coaching fallback"


def _phase_for_week(preview: AdaptiveBlockPreview, week: int) -> AdaptivePhase:
    for phase in preview.phases:
        if phase.start_week <= week <= phase.end_week:
            return phase
    return preview.phases[-1]


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
            if day==rest_day:
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
            "Preview only: nothing here changes Recommended Next Run, Today's Session or the saved Training Block.",
            "Future live versions must recalculate after each completed run and use readiness before preserving or changing the next workout.",
            "Descriptive activity titles and richer FIT data will progressively improve workout-intent recognition and personal historical matching.",
            "Fallback workouts are used only when trustworthy personal historical structures are not available.",
        ),
    )

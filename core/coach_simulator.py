"""
Retrospective Coach Simulator v0.19.4.

A read-only driving test for Adaptive Coach.

The simulator walks through a completed historical build one day at a time.
At each simulated date it only queries activities/workouts ON OR BEFORE that
date. The target race/PB is supplied as the scenario endpoint, but the coach
does not use training or results after the simulated day.

v1 validates:
- sensible quality-session spacing;
- phase progression toward the target;
- race/hard-effort substitution for a planned quality stimulus;
- progression / repeat / reduce decisions from trusted execution evidence;
- taper behaviour;
- data-confidence gaps.

It does not modify the database or live coaching system.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
from collections import Counter
from typing import Any

from core.database import get_athlete_sport_roles, get_connection
from core.race_detection import (
    score_athlete_relative_race_effort,
    score_race_evidence,
)


@dataclass(frozen=True)
class SimulatedDecision:
    date: str
    weekday: str
    weeks_to_target: float
    planned_family: str
    planned_session: str
    actual_title: str | None
    actual_family: str | None
    actual_execution_score: float | None
    substitution_accepted: bool
    progression_action: str
    status: str
    explanation: tuple[str,...]


@dataclass(frozen=True)
class ValidationFlag:
    severity: str
    date: str
    message: str


@dataclass(frozen=True)
class CoachSimulation:
    athlete_id: int
    target_date: str
    target_label: str
    start_date: str
    end_date: str
    training_days: int
    coaching_decision_count: int
    sensible_decision_count: int
    review_decision_count: int
    decisions: tuple[SimulatedDecision,...]
    flags: tuple[ValidationFlag,...]
    pass_rate: float
    verdict: str
    summary: str
    limitations: tuple[str,...]
    model_version: int=1


def _family_from_phase_json(value: Any) -> str|None:
    try:
        phases=json.loads(value or "[]")
    except (TypeError,json.JSONDecodeError):
        return None
    if not isinstance(phases,list):
        return None
    types={str(p.get("phase_type") or "").lower() for p in phases}
    aliases={
        "short_interval":"short_intervals","short_reps":"short_intervals",
        "intervals":"long_intervals","mile_repetitions":"long_intervals",
        "continuous_threshold":"threshold","long_threshold":"threshold",
        "sustained_quality":"threshold",
    }
    types={aliases.get(t,t) for t in types}
    if "threshold" in types:
        return "threshold"
    if "short_intervals" in types or "vo2" in types:
        return "vo2"
    if "long_intervals" in types:
        return "vo2"
    if "strides" in types:
        return "speed"
    return None


def _phase(weeks_to_target: float) -> str:
    if weeks_to_target <= 1.0:
        return "Taper"
    if weeks_to_target <= 4.0:
        return "Specific"
    return "Build"


def _planned_quality(
    phase: str,
    slot: int,
    week_index: int,
) -> tuple[str,str]:
    if phase=="Taper":
        if slot==1:
            return "race_pace","3 × 1 km at 5K–10K effort"
        return "speed","6 × 200m relaxed and quick"

    if phase=="Specific":
        first=(
            "6 × 800m at controlled 5K effort",
            "5 × 1000m at controlled 5K effort",
            "4 × 1200m at 5K–10K effort",
        )
        second=(
            "3 × 10 min threshold",
            "2 × 15 min threshold",
            "2 × 10 min threshold + 4 × 200m relaxed",
        )
        seq=first if slot==1 else second
        return (
            "vo2" if slot==1 else "threshold",
            seq[min(max(week_index-1,0),len(seq)-1)],
        )

    first=(
        "8 × 400m controlled intervals",
        "10 × 400m controlled intervals",
        "8 × 500m controlled intervals",
        "8 × 600m controlled intervals",
        "6 × 800m controlled intervals",
        "7 × 800m controlled intervals",
    )
    second=(
        "4 × 8 min threshold",
        "3 × 10 min threshold",
        "4 × 10 min threshold",
        "3 × 12 min threshold",
        "2 × 15 min threshold",
        "3 × 10 min threshold",
    )
    seq=first if slot==1 else second
    return (
        "vo2" if slot==1 else "threshold",
        seq[min(max(week_index-1,0),len(seq)-1)],
    )


def _actual_on_date(
    athlete_id:int,
    date:datetime.date,
) -> dict[str,Any]|None:
    roles=get_athlete_sport_roles(athlete_id)
    running={str(k) for k,v in roles.items() if v=="running"}
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""
        SELECT id,title,distance_m,moving_time_s,elapsed_time_s,avg_hr,max_hr,
               raw_json,sport_id
        FROM activities
        WHERE athlete_id=? AND activity_date=?
        ORDER BY distance_m DESC
    """,(athlete_id,date.isoformat()))
    activities=cur.fetchall()

    cur.execute("SELECT lt2_hr,max_hr FROM athletes WHERE id=?",(athlete_id,))
    athlete=cur.fetchone() or (None,None)

    for row in activities:
        if str(row[8] or "") not in running:
            continue
        activity_id=int(row[0])
        cur.execute("""
            SELECT phase_json,execution_score,recognition_confidence,phase_confidence,
                   workout_signature
            FROM workout_library
            WHERE activity_id=?
        """,(activity_id,))
        workout=cur.fetchone()

        family=None; execution=None; signature=None
        if workout and float(workout[2] or 0)>=0.65 and float(workout[3] or 0)>=0.70:
            family=_family_from_phase_json(workout[0])
            execution=float(workout[1]) if workout[1] is not None else None
            signature=str(workout[4] or "")

        raw={}
        try:
            raw=json.loads(row[7] or "{}")
        except (TypeError,json.JSONDecodeError):
            pass

        distance=float(row[2] or 0)
        relative=score_athlete_relative_race_effort(
            athlete_id=athlete_id,title=row[1] or "",
            distance_km=distance,
            moving_time_s=float(row[3]) if row[3] is not None else None,
            elapsed_time_s=float(row[4]) if row[4] is not None else None,
        )
        signals=score_race_evidence(
            title=row[1] or "",distance_km=distance,
            moving_time_s=float(row[3]) if row[3] is not None else None,
            elapsed_time_s=float(row[4]) if row[4] is not None else None,
            avg_hr=float(row[5]) if row[5] is not None else None,
            max_hr=float(row[6]) if row[6] is not None else None,
            athlete_lt2_hr=float(athlete[0]) if athlete[0] is not None else None,
            athlete_max_hr=float(athlete[1]) if athlete[1] is not None else None,
            official_race_name=raw.get("race_name"),
            official_distance_m=raw.get("race_officialDistance"),
            official_time_s=raw.get("race_officialTime"),
            officially_measured=bool(raw.get("race_officiallyMeasured")),
        )
        if relative.is_race_quality or signals.classification in {"confirmed_race","race_quality_effort"}:
            family="race"

        conn.close()
        return {
            "id":activity_id,"title":str(row[1] or "Run"),"family":family or "easy",
            "execution":execution,"signature":signature,
        }

    conn.close()
    return None


def _prior_execution(
    athlete_id:int,
    family:str,
    date:datetime.date,
    *,
    limit:int=4,
) -> list[float]:
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""
        SELECT phase_json,execution_score
        FROM workout_library
        WHERE athlete_id=? AND activity_date<?
          AND execution_score IS NOT NULL
          AND recognition_confidence>=0.65 AND phase_confidence>=0.70
        ORDER BY activity_date DESC,id DESC
        LIMIT 12
    """,(athlete_id,date.isoformat()))
    rows=cur.fetchall(); conn.close()
    values=[]
    for pj,score in rows:
        f=_family_from_phase_json(pj)
        match=(family==f) or (family in {"vo2","speed","race_pace"} and f=="vo2")
        if match:
            values.append(float(score))
        if len(values)>=limit:
            break
    return values


def _action(
    planned_family:str,
    actual:dict[str,Any]|None,
    prior:list[float],
) -> tuple[str,bool,tuple[str,...]]:
    if actual is None:
        return "hold",False,("No run was recorded on the planned quality day.",)

    actual_family=actual["family"]
    accepted=(
        actual_family==planned_family
        or actual_family=="race"
        or (
            planned_family in {"vo2","speed","race_pace"}
            and actual_family=="vo2"
        )
    )

    if actual_family=="race":
        return (
            "recover",True,
            ("Race/hard effort accepted as the week's quality stimulus.",
             "Do not add the missed planned hard session on top of it."),
        )

    if not accepted:
        return (
            "hold",False,
            (f"Actual stimulus was {actual_family}; it should not automatically progress {planned_family}.",),
        )

    score=actual.get("execution")
    if score is None:
        return (
            "hold",True,
            ("Stimulus matched, but trusted execution evidence is unavailable; progression stays conservative.",),
        )

    prior_avg=sum(prior)/len(prior) if prior else None
    if prior_avg is not None and score<=prior_avg-10:
        return (
            "repeat" if score>=72 else "reduce",True,
            (f"Execution {score:.0f}/100 was materially below the prior {prior_avg:.0f}/100 family average.",),
        )
    if score>=90 and (prior_avg is None or prior_avg>=82):
        return "progress",True,(f"Execution {score:.0f}/100 supports progression.",)
    if score>=82:
        return "small_progress",True,(f"Execution {score:.0f}/100 supports only a modest progression.",)
    if score>=72:
        return "repeat",True,(f"Execution {score:.0f}/100 suggests repeating before overload.",)
    return "reduce",True,(f"Execution {score:.0f}/100 suggests reducing the next load.",)


def simulate_pb_build(
    athlete_id:int,
    *,
    target_date:datetime.date,
    target_label:str="5K PB",
    weeks:int=10,
) -> CoachSimulation:
    start=target_date-datetime.timedelta(weeks=weeks)
    end=target_date
    decisions=[]
    flags=[]
    sensible=0
    review=0

    quality_days={2:1,5:2}
    phase_counts=Counter()
    last_planned_quality=None

    current=start
    while current<end:
        if current.weekday() in quality_days:
            weeks_to=(target_date-current).days/7.0
            phase=_phase(weeks_to)
            slot=quality_days[current.weekday()]
            phase_counts[(phase,slot)]+=1
            family,prescription=_planned_quality(
                phase,slot,phase_counts[(phase,slot)]
            )
            actual=_actual_on_date(athlete_id,current)
            prior=_prior_execution(athlete_id,family,current)
            action,accepted,reasons=_action(family,actual,prior)

            status="sensible"
            if last_planned_quality is not None:
                gap=(current-last_planned_quality).days
                if gap<2:
                    status="review"
                    flags.append(ValidationFlag(
                        "warning",current.isoformat(),
                        f"Planned quality sessions only {gap} day apart."
                    ))
            last_planned_quality=current

            if phase=="Taper" and action=="progress":
                status="review"
                flags.append(ValidationFlag(
                    "warning",current.isoformat(),
                    "Simulator tried to progress during taper."
                ))

            if status=="sensible":
                sensible+=1
            else:
                review+=1

            decisions.append(SimulatedDecision(
                date=current.isoformat(),weekday=current.strftime("%A"),
                weeks_to_target=round(weeks_to,1),
                planned_family=family,planned_session=prescription,
                actual_title=actual["title"] if actual else None,
                actual_family=actual["family"] if actual else None,
                actual_execution_score=actual["execution"] if actual else None,
                substitution_accepted=accepted,
                progression_action=action,status=status,
                explanation=reasons,
            ))
        current+=datetime.timedelta(days=1)

    trusted=sum(
        d.actual_execution_score is not None
        for d in decisions
    )
    if trusted < max(3,len(decisions)//4):
        flags.append(ValidationFlag(
            "info",start.isoformat(),
            "Historical decoded-workout coverage is sparse; many decisions can validate sequencing but not execution-driven progression."
        ))

    count=len(decisions)
    pass_rate=sensible/count if count else 0.0
    if pass_rate>=0.95 and not any(f.severity=="warning" for f in flags):
        verdict="Pass"
    elif pass_rate>=0.85:
        verdict="Pass with review"
    else:
        verdict="Needs refinement"

    return CoachSimulation(
        athlete_id=athlete_id,target_date=target_date.isoformat(),
        target_label=target_label,start_date=start.isoformat(),end_date=end.isoformat(),
        training_days=(end-start).days,coaching_decision_count=count,
        sensible_decision_count=sensible,review_decision_count=review,
        decisions=tuple(decisions),flags=tuple(flags),pass_rate=round(pass_rate,4),
        verdict=verdict,
        summary=(
            f"PP replayed {weeks} weeks before {target_label} without using activities "
            "after each simulated date. The first validation focuses on quality spacing, "
            "race substitution, progression evidence and taper behaviour."
        ),
        limitations=(
            "v0.19.4 uses the established Wednesday/Saturday quality rhythm for this first scenario.",
            "Historical physiological thresholds are not versioned, so current stored thresholds are used when race evidence needs HR support.",
            "Older workout-decoder coverage is incomplete; missing execution evidence causes HOLD rather than invented progression.",
            "The simulator is read-only and does not alter the database or live plan.",
        ),
    )

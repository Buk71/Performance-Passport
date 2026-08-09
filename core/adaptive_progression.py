"""
Adaptive Progression Gate v0.19.3.

Closes the loop:
    planned workout -> completed workout -> execution response -> next progression.

This version is PREVIEW / advisory only. It never writes to the live plan.

Because Performance Passport does not yet have a connected physiological
readiness specialist, the gate uses only evidence it genuinely has:
- trusted workout execution score;
- whether the completed workout matches the planned session family;
- recency of that workout;
- recent trusted quality-work execution trend.

It will not invent HRV, sleep, soreness or recovery data.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
from typing import Any

from core.database import get_connection
from core.learning_engine import _canonical_phase_type


@dataclass(frozen=True)
class ProgressionDecision:
    athlete_id: int
    planned_family: str
    completed_activity_id: int | None
    completed_date: str | None
    completed_title: str | None
    completed_signature: str | None
    execution_score: float | None
    recent_execution_average: float | None
    family_match: bool
    action: str
    load_multiplier: float
    headline: str
    explanation: tuple[str, ...]
    confidence: float
    confidence_label: str
    model_version: int = 1


def _family_components(phase_json: Any) -> set[str]:
    try:
        phases=json.loads(phase_json or "[]")
    except (TypeError,json.JSONDecodeError):
        return set()
    if not isinstance(phases,list):
        return set()
    result=set()
    for phase in phases:
        p=_canonical_phase_type(phase.get("phase_type"))
        if p=="threshold": result.add("threshold")
        if p in {"short_intervals","vo2"}: result.add("vo2")
        if p=="long_intervals": result.add("long_intervals")
        if p=="strides": result.add("speed")
    return result


def _matches(planned_family: str, components: set[str]) -> bool:
    if planned_family=="threshold":
        return bool({"threshold","long_intervals"} & components)
    if planned_family in {"vo2","speed"}:
        return bool({"vo2","speed","long_intervals"} & components)
    if planned_family=="race_pace":
        return bool({"threshold","vo2","long_intervals"} & components)
    return True


def _trusted_recent_workouts(
    athlete_id: int,
    *,
    before_or_on: datetime.date,
    limit: int = 6,
) -> list[dict[str,Any]]:
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""
        SELECT activity_id,activity_date,workout_signature,phase_json,
               execution_score,recognition_confidence,phase_confidence
        FROM workout_library
        WHERE athlete_id=?
          AND activity_date<=?
          AND execution_score IS NOT NULL
          AND recognition_confidence>=0.65
          AND phase_confidence>=0.70
        ORDER BY activity_date DESC,id DESC
        LIMIT ?
    """,(athlete_id,before_or_on.isoformat(),limit))
    rows=cur.fetchall()

    result=[]
    for row in rows:
        cur.execute("SELECT title FROM activities WHERE id=?",(row[0],))
        title_row=cur.fetchone()
        result.append({
            "activity_id":int(row[0]),
            "date":str(row[1])[:10],
            "signature":str(row[2] or ""),
            "components":_family_components(row[3]),
            "execution":float(row[4]),
            "title":str(title_row[0] or "Completed workout") if title_row else "Completed workout",
        })
    conn.close()
    return result


def evaluate_progression(
    athlete_id: int,
    planned_family: str,
    *,
    as_of: datetime.date | None = None,
) -> ProgressionDecision:
    as_of=as_of or datetime.date.today()
    rows=_trusted_recent_workouts(athlete_id,before_or_on=as_of)

    if not rows:
        return ProgressionDecision(
            athlete_id,planned_family,None,None,None,None,None,None,False,
            "hold",1.0,
            "Hold progression until PP sees a trustworthy completed quality session",
            ("No recent high-confidence execution record is available.",),
            0.35,"Low",
        )

    latest=rows[0]
    match=_matches(planned_family,latest["components"])
    prior=[r["execution"] for r in rows[1:]]
    recent_avg=(sum(prior)/len(prior)) if prior else None

    reasons=[
        f"Latest trusted workout: {latest['title']} ({latest['signature']}).",
        f"Execution score: {latest['execution']:.0f}/100.",
    ]
    if recent_avg is not None:
        reasons.append(f"Previous trusted quality-work average: {recent_avg:.0f}/100.")

    if not match:
        action="hold"; multiplier=1.0
        headline="Hold the planned progression — the latest workout was a different stimulus"
        reasons.append("PP should not advance this workout family using an unrelated session as evidence.")
        confidence=0.62
    elif latest["execution"]>=90 and (recent_avg is None or recent_avg>=82):
        action="progress"; multiplier=1.06
        headline="Progress the next session"
        reasons.append("The planned stimulus was executed strongly and recent quality execution is stable.")
        confidence=0.82
    elif latest["execution"]>=82 and (recent_avg is None or recent_avg>=78):
        action="small_progress"; multiplier=1.03
        headline="Progress, but only slightly"
        reasons.append("Execution supports overload, but PP should make the next step modest.")
        confidence=0.76
    elif latest["execution"]>=72:
        action="repeat"; multiplier=1.0
        headline="Repeat the stimulus before progressing"
        reasons.append("Execution was adequate but not strong enough to justify automatic overload.")
        confidence=0.78
    else:
        action="reduce"; multiplier=0.92
        headline="Reduce the next progression"
        reasons.append("Execution was below the level PP wants before increasing the training load.")
        confidence=0.84

    # A sharp deterioration versus the athlete's own recent quality baseline
    # overrides automatic progression.
    if match and recent_avg is not None and latest["execution"] <= recent_avg-10:
        action="repeat" if latest["execution"]>=72 else "reduce"
        multiplier=1.0 if action=="repeat" else 0.92
        headline="Do not progress yet — execution dropped versus recent quality work"
        reasons.append(
            f"This session was {recent_avg-latest['execution']:.0f} points below the recent trusted-workout average."
        )
        confidence=max(confidence,0.82)

    return ProgressionDecision(
        athlete_id=athlete_id,planned_family=planned_family,
        completed_activity_id=latest["activity_id"],completed_date=latest["date"],
        completed_title=latest["title"],completed_signature=latest["signature"],
        execution_score=round(latest["execution"],1),
        recent_execution_average=round(recent_avg,1) if recent_avg is not None else None,
        family_match=match,action=action,load_multiplier=multiplier,
        headline=headline,explanation=tuple(reasons),
        confidence=round(confidence,2),
        confidence_label="High" if confidence>=0.80 else ("Good" if confidence>=0.65 else "Low"),
    )

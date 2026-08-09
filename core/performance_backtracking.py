"""
Performance Backtracking v1.

Starts with objective strong performances and looks BACKWARDS through the
athlete's real training to reconstruct preparation patterns.

This is observational evidence. It does not claim individual workouts caused
a performance and it does not yet alter prescriptions.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import math
import statistics
from collections import Counter
from typing import Any

from core.database import get_athlete_sport_roles, get_connection
from core.race_detection import (
    score_athlete_relative_race_effort,
    score_race_evidence,
)

WINDOWS = (14, 28, 42, 56)
STANDARD_DISTANCES = (5.0, 10.0, 21.0975)


@dataclass(frozen=True)
class PerformanceAnchor:
    activity_id: int
    activity_date: str
    title: str
    distance_km: float
    time_s: float
    pace_s_per_km: float
    distance_label: str
    is_pb: bool
    quality_percentile: float
    confidence: float
    anchor_reason: str


@dataclass(frozen=True)
class PreparationWindow:
    days: int
    run_count: int
    total_distance_km: float
    average_weekly_km: float
    quality_session_count: int
    threshold_session_count: int
    short_interval_session_count: int
    long_interval_session_count: int
    strides_session_count: int
    long_run_count: int
    average_execution_score: float | None
    signatures: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class BacktrackedPerformance:
    anchor: PerformanceAnchor
    windows: tuple[PreparationWindow, ...]


@dataclass(frozen=True)
class PerformanceBacktrackingProfile:
    athlete_id: int
    anchor_count: int
    pb_count: int
    performances: tuple[BacktrackedPerformance, ...]
    recurring_42d_signatures: tuple[tuple[str, int], ...]
    summary: str
    limitations: tuple[str, ...]
    model_version: int = 1


def _date(value: Any) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _json(value: Any) -> dict[str, Any]:
    try:
        decoded=json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded,dict) else {}


def _distance_km(value: Any) -> float | None:
    try:
        d=float(value)
    except (TypeError,ValueError):
        return None
    if d<=0: return None
    return d/1000.0 if d>250 else d


def _bucket(distance_km: float) -> float | None:
    closest=min(STANDARD_DISTANCES,key=lambda x:abs(x-distance_km))
    return closest if abs(distance_km-closest)/closest<=0.06 else None


def _label(distance: float) -> str:
    if abs(distance-5.0)<0.1: return "5K"
    if abs(distance-10.0)<0.2: return "10K"
    if abs(distance-21.0975)<0.3: return "Half Marathon"
    return f"{distance:g}K"


def _race_time(elapsed: Any, moving: Any, raw: dict[str,Any]) -> float | None:
    for value in (raw.get("race_officialTime"), elapsed, moving):
        try:
            v=float(value)
        except (TypeError,ValueError):
            continue
        if v>0: return v
    return None


def _family_components(phase_json: Any) -> set[str]:
    try:
        phases=json.loads(phase_json or "[]")
    except (TypeError,json.JSONDecodeError):
        return set()
    if not isinstance(phases,list): return set()
    aliases={
        "continuous_threshold":"threshold",
        "long_threshold":"threshold",
        "sustained_quality":"threshold",
        "intervals":"long_intervals",
        "mile_repetitions":"long_intervals",
        "short_interval":"short_intervals",
        "short_reps":"short_intervals",
    }
    types={aliases.get(str(p.get("phase_type") or "").lower(),str(p.get("phase_type") or "").lower()) for p in phases}
    return {x for x in ("threshold","short_intervals","long_intervals","strides") if x in types}


def build_performance_anchors(athlete_id:int) -> tuple[PerformanceAnchor,...]:
    roles=get_athlete_sport_roles(athlete_id)
    running={str(k) for k,v in roles.items() if v=="running"}
    if not running: return ()

    conn=get_connection()
    cur=conn.cursor()
    cur.execute("""
        SELECT a.id,a.activity_date,a.title,a.distance_m,a.moving_time_s,
               a.elapsed_time_s,a.avg_hr,a.max_hr,at.lt2_hr,at.max_hr,a.raw_json
        FROM activities a JOIN athletes at ON at.id=a.athlete_id
        WHERE a.athlete_id=? AND a.activity_date IS NOT NULL
          AND a.distance_m IS NOT NULL AND a.moving_time_s IS NOT NULL
        ORDER BY a.activity_date
    """,(athlete_id,))
    rows=cur.fetchall()
    conn.close()

    candidates=[]
    for r in rows:
        # sport_id is deliberately filtered in a second lightweight query-free way
        # through athlete role mapping by loading the row's activity below.
        pass

    # Need sport_id, so reload with it included.
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""
        SELECT a.id,a.activity_date,a.title,a.distance_m,a.moving_time_s,
               a.elapsed_time_s,a.avg_hr,a.max_hr,at.lt2_hr,at.max_hr,
               a.raw_json,a.sport_id
        FROM activities a JOIN athletes at ON at.id=a.athlete_id
        WHERE a.athlete_id=? AND a.activity_date IS NOT NULL
          AND a.distance_m IS NOT NULL AND a.moving_time_s IS NOT NULL
        ORDER BY a.activity_date
    """,(athlete_id,))
    rows=cur.fetchall(); conn.close()

    for r in rows:
        if str(r[11] or "") not in running: continue
        d=_distance_km(r[3])
        if d is None: continue
        standard=_bucket(d)
        if standard is None: continue
        raw=_json(r[10])
        time_s=_race_time(r[5],r[4],raw)
        if time_s is None: continue

        signals=score_race_evidence(
            title=r[2] or "",distance_km=d,moving_time_s=float(r[4]),
            elapsed_time_s=float(r[5]) if r[5] is not None else None,
            avg_hr=float(r[6]) if r[6] is not None else None,
            max_hr=float(r[7]) if r[7] is not None else None,
            athlete_lt2_hr=float(r[8]) if r[8] is not None else None,
            athlete_max_hr=float(r[9]) if r[9] is not None else None,
            official_race_name=raw.get("race_name"),
            official_distance_m=raw.get("race_officialDistance"),
            official_time_s=raw.get("race_officialTime"),
            officially_measured=bool(raw.get("race_officiallyMeasured")),
        )
        relative=score_athlete_relative_race_effort(
            athlete_id=athlete_id,title=r[2] or "",distance_km=d,
            moving_time_s=float(r[4]),
            elapsed_time_s=float(r[5]) if r[5] is not None else None,
        )
        confirmed=signals.classification in {"confirmed_race","race_quality_effort"}
        if not confirmed and not relative.is_race_quality: continue
        candidates.append({
            "id":int(r[0]),"date":str(r[1])[:10],"title":r[2] or "Race / hard effort",
            "distance":d,"standard":standard,"time":time_s,
            "confidence":max(signals.confidence,relative.confidence),
        })

    by_distance={}
    for c in candidates: by_distance.setdefault(c["standard"],[]).append(c)

    anchors=[]
    for standard,items in by_distance.items():
        items=sorted(items,key=lambda x:(x["date"],x["time"]))
        historical_best=math.inf
        times=sorted(x["time"] for x in items)
        for c in items:
            is_pb=c["time"]<historical_best
            historical_best=min(historical_best,c["time"])
            rank=sum(t<=c["time"] for t in times)/len(times)
            # Keep all PBs plus top quartile race-quality performances.
            if not is_pb and rank>0.25: continue
            reason="Historical PB at the time" if is_pb else f"Top {max(rank*100,1):.0f}% { _label(standard) } performance"
            anchors.append(PerformanceAnchor(
                activity_id=c["id"],activity_date=c["date"],title=c["title"],
                distance_km=round(c["distance"],3),time_s=round(c["time"],1),
                pace_s_per_km=round(c["time"]/c["distance"],2),
                distance_label=_label(standard),is_pb=is_pb,
                quality_percentile=round(rank,4),confidence=round(c["confidence"],4),
                anchor_reason=reason,
            ))
    anchors.sort(key=lambda x:x.activity_date,reverse=True)
    return tuple(anchors)


def _window(athlete_id:int,anchor:PerformanceAnchor,days:int) -> PreparationWindow:
    end=_date(anchor.activity_date)
    start=end-datetime.timedelta(days=days)
    roles=get_athlete_sport_roles(athlete_id)
    running={str(k) for k,v in roles.items() if v=="running"}
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""
        SELECT id,activity_date,distance_m,sport_id
        FROM activities
        WHERE athlete_id=? AND activity_date>=? AND activity_date<?
    """,(athlete_id,start.isoformat(),end.isoformat()))
    acts=cur.fetchall()
    run_acts=[r for r in acts if str(r[3] or "") in running]
    total=sum((_distance_km(r[2]) or 0.0) for r in run_acts)
    long_runs=sum(1 for r in run_acts if (_distance_km(r[2]) or 0)>=16.0)

    cur.execute("""
        SELECT workout_signature,phase_json,execution_score
        FROM workout_library
        WHERE athlete_id=? AND activity_date>=? AND activity_date<?
          AND phase_confidence>=0.70 AND recognition_confidence>=0.65
    """,(athlete_id,start.isoformat(),end.isoformat()))
    workouts=cur.fetchall(); conn.close()

    counts=Counter(); sigs=Counter(); executions=[]
    for sig,pj,score in workouts:
        components=_family_components(pj)
        for comp in components: counts[comp]+=1
        if components: sigs[str(sig or "workout")]+=1
        try:
            if score is not None: executions.append(float(score))
        except (TypeError,ValueError): pass

    return PreparationWindow(
        days=days,run_count=len(run_acts),total_distance_km=round(total,1),
        average_weekly_km=round(total/(days/7.0),1),
        quality_session_count=sum(1 for _,pj,_ in workouts if _family_components(pj)),
        threshold_session_count=counts["threshold"],
        short_interval_session_count=counts["short_intervals"],
        long_interval_session_count=counts["long_intervals"],
        strides_session_count=counts["strides"],long_run_count=long_runs,
        average_execution_score=round(statistics.fmean(executions),1) if executions else None,
        signatures=tuple(sigs.most_common(5)),
    )


def build_performance_backtracking_profile(athlete_id:int) -> PerformanceBacktrackingProfile:
    anchors=build_performance_anchors(athlete_id)
    performances=[]
    recurring=Counter()
    for anchor in anchors:
        windows=tuple(_window(athlete_id,anchor,d) for d in WINDOWS)
        performances.append(BacktrackedPerformance(anchor=anchor,windows=windows))
        w42=next((w for w in windows if w.days==42),None)
        if w42:
            # Count presence per successful block, not raw repetition.
            for sig,_ in w42.signatures: recurring[sig]+=1

    pb_count=sum(a.is_pb for a in anchors)
    if anchors:
        summary=(
            f"PP found {len(anchors)} strong performance anchors, including "
            f"{pb_count} historical PBs. It has reconstructed the 2, 4, 6 and "
            "8 weeks before each one so recurring successful preparation can be compared."
        )
    else:
        summary="PP has not yet found enough trustworthy PB or race-quality anchors for backtracking."

    return PerformanceBacktrackingProfile(
        athlete_id=athlete_id,anchor_count=len(anchors),pb_count=pb_count,
        performances=tuple(performances),
        recurring_42d_signatures=tuple(recurring.most_common(8)),
        summary=summary,
        limitations=(
            "Backtracking identifies training associated with strong performances; it does not prove causation.",
            "Historical PB means best performance recorded up to that date in the available Performance Passport history.",
            "Training windows overlap when strong performances are close together, so repeated patterns are evidence rather than independent experiments.",
            "v0.18.3 remains observation-only and does not alter session recommendations.",
        ),
    )

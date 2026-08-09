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
class PreparationContrast:
    metric_key: str
    metric_label: str
    successful_average: float
    normal_average: float
    difference: float
    relative_difference: float | None
    direction: str
    evidence_label: str


@dataclass(frozen=True)
class SignatureLift:
    workout_signature: str
    successful_block_rate: float
    normal_block_rate: float
    lift: float | None
    successful_blocks: int
    normal_blocks: int


@dataclass(frozen=True)
class PerformanceBacktrackingProfile:
    athlete_id: int
    anchor_count: int
    pb_count: int
    performances: tuple[BacktrackedPerformance, ...]
    recurring_42d_signatures: tuple[tuple[str, int], ...]
    normal_42d_block_count: int
    preparation_contrasts: tuple[PreparationContrast, ...]
    signature_lifts: tuple[SignatureLift, ...]
    summary: str
    limitations: tuple[str, ...]
    model_version: int = 2


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


def _window_ending(
    athlete_id: int,
    end: datetime.date,
    days: int,
) -> PreparationWindow:
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


def _window(
    athlete_id: int,
    anchor: PerformanceAnchor,
    days: int,
) -> PreparationWindow:
    end = _date(anchor.activity_date)

    if end is None:
        raise ValueError("Performance anchor has no usable date.")

    return _window_ending(
        athlete_id,
        end,
        days,
    )


def _normal_control_windows(
    athlete_id: int,
    anchors: tuple[PerformanceAnchor, ...],
    *,
    days: int = 42,
) -> tuple[PreparationWindow, ...]:
    """
    Build ordinary training blocks for comparison.

    Windows end every 14 days across the athlete's running history. End dates
    within 21 days of a strong-performance anchor are excluded, so the control
    group is less contaminated by the same successful preparation period.
    """
    roles = get_athlete_sport_roles(athlete_id)
    running = {
        str(k)
        for k, v in roles.items()
        if v == "running"
    }

    if not running:
        return ()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT activity_date, sport_id
        FROM activities
        WHERE athlete_id = ?
          AND activity_date IS NOT NULL
        ORDER BY activity_date
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    dates = [
        _date(row[0])
        for row in rows
        if str(row[1] or "") in running
    ]
    dates = [value for value in dates if value is not None]

    if not dates:
        return ()

    first = min(dates) + datetime.timedelta(days=days)
    last = max(dates)

    anchor_dates = [
        _date(anchor.activity_date)
        for anchor in anchors
    ]
    anchor_dates = [
        value
        for value in anchor_dates
        if value is not None
    ]

    controls = []
    current = first

    while current <= last:
        near_anchor = any(
            abs((current - anchor_date).days) <= 21
            for anchor_date in anchor_dates
        )

        if not near_anchor:
            window = _window_ending(
                athlete_id,
                current,
                days,
            )

            # Require enough running to represent a genuine training block.
            if window.run_count >= 8:
                controls.append(window)

        current += datetime.timedelta(days=14)

    return tuple(controls)


def _average_metric(
    windows: tuple[PreparationWindow, ...],
    attribute: str,
) -> float | None:
    values = [
        float(getattr(window, attribute))
        for window in windows
        if getattr(window, attribute) is not None
    ]

    if not values:
        return None

    return statistics.fmean(values)


def _contrast(
    metric_key: str,
    metric_label: str,
    successful_windows: tuple[PreparationWindow, ...],
    normal_windows: tuple[PreparationWindow, ...],
) -> PreparationContrast | None:
    successful = _average_metric(
        successful_windows,
        metric_key,
    )
    normal = _average_metric(
        normal_windows,
        metric_key,
    )

    if successful is None or normal is None:
        return None

    difference = successful - normal
    relative = (
        difference / normal
        if abs(normal) > 1e-9
        else None
    )

    if relative is not None:
        magnitude = abs(relative)
    else:
        magnitude = abs(difference)

    if magnitude >= 0.25:
        evidence = "Strong difference"
    elif magnitude >= 0.12:
        evidence = "Meaningful difference"
    elif magnitude >= 0.05:
        evidence = "Small difference"
    else:
        evidence = "Similar to normal"

    if difference > 0:
        direction = "higher"
    elif difference < 0:
        direction = "lower"
    else:
        direction = "similar"

    return PreparationContrast(
        metric_key=metric_key,
        metric_label=metric_label,
        successful_average=round(successful, 2),
        normal_average=round(normal, 2),
        difference=round(difference, 2),
        relative_difference=(
            round(relative, 4)
            if relative is not None
            else None
        ),
        direction=direction,
        evidence_label=evidence,
    )


def _signature_presence(
    windows: tuple[PreparationWindow, ...],
) -> Counter:
    counts = Counter()

    for window in windows:
        present = {
            signature
            for signature, _count
            in window.signatures
        }

        for signature in present:
            counts[signature] += 1

    return counts


def _signature_lifts(
    successful_windows: tuple[PreparationWindow, ...],
    normal_windows: tuple[PreparationWindow, ...],
) -> tuple[SignatureLift, ...]:
    if not successful_windows or not normal_windows:
        return ()

    successful_counts = _signature_presence(
        successful_windows
    )
    normal_counts = _signature_presence(
        normal_windows
    )

    signatures = set(successful_counts) | set(normal_counts)
    results = []

    for signature in signatures:
        successful_rate = (
            successful_counts[signature]
            / len(successful_windows)
        )
        normal_rate = (
            normal_counts[signature]
            / len(normal_windows)
        )

        if successful_counts[signature] < 2:
            continue

        lift = (
            successful_rate / normal_rate
            if normal_rate > 0
            else None
        )

        results.append(
            SignatureLift(
                workout_signature=signature,
                successful_block_rate=round(
                    successful_rate,
                    4,
                ),
                normal_block_rate=round(
                    normal_rate,
                    4,
                ),
                lift=(
                    round(lift, 2)
                    if lift is not None
                    else None
                ),
                successful_blocks=successful_counts[
                    signature
                ],
                normal_blocks=normal_counts[
                    signature
                ],
            )
        )

    results.sort(
        key=lambda item: (
            (
                item.lift
                if item.lift is not None
                else 999.0
            ),
            item.successful_block_rate,
            item.successful_blocks,
        ),
        reverse=True,
    )

    return tuple(results[:10])


def build_performance_backtracking_profile(
    athlete_id: int,
) -> PerformanceBacktrackingProfile:
    anchors = build_performance_anchors(
        athlete_id
    )
    performances = []
    recurring = Counter()

    for anchor in anchors:
        windows = tuple(
            _window(
                athlete_id,
                anchor,
                days,
            )
            for days in WINDOWS
        )
        performances.append(
            BacktrackedPerformance(
                anchor=anchor,
                windows=windows,
            )
        )

        w42 = next(
            (
                window
                for window in windows
                if window.days == 42
            ),
            None,
        )

        if w42:
            for signature, _ in w42.signatures:
                recurring[signature] += 1

    successful_42d = tuple(
        next(
            window
            for window in item.windows
            if window.days == 42
        )
        for item in performances
    )

    normal_42d = _normal_control_windows(
        athlete_id,
        anchors,
        days=42,
    )

    metrics = (
        ("average_weekly_km", "Weekly volume"),
        ("quality_session_count", "Quality sessions / 6 weeks"),
        ("threshold_session_count", "Threshold sessions / 6 weeks"),
        ("short_interval_session_count", "Short interval / VO₂ sessions / 6 weeks"),
        ("long_interval_session_count", "Long interval sessions / 6 weeks"),
        ("long_run_count", "Long runs / 6 weeks"),
        ("average_execution_score", "Average quality execution"),
    )

    contrasts = []

    for metric_key, metric_label in metrics:
        item = _contrast(
            metric_key,
            metric_label,
            successful_42d,
            normal_42d,
        )

        if item is not None:
            contrasts.append(item)

    contrasts.sort(
        key=lambda item: abs(
            item.relative_difference
            if item.relative_difference is not None
            else 0.0
        ),
        reverse=True,
    )

    lifts = _signature_lifts(
        successful_42d,
        normal_42d,
    )

    pb_count = sum(
        anchor.is_pb
        for anchor in anchors
    )

    if anchors:
        summary = (
            f"PP found {len(anchors)} strong performance anchors, including "
            f"{pb_count} historical PBs, and compared their 6-week preparation "
            f"with {len(normal_42d)} ordinary 6-week training blocks. "
            "This shows which patterns are unusually associated with running well, "
            "rather than merely common in the athlete's training."
        )
    else:
        summary = (
            "PP has not yet found enough trustworthy PB or race-quality "
            "anchors for backtracking."
        )

    return PerformanceBacktrackingProfile(
        athlete_id=athlete_id,
        anchor_count=len(anchors),
        pb_count=pb_count,
        performances=tuple(performances),
        recurring_42d_signatures=tuple(
            recurring.most_common(8)
        ),
        normal_42d_block_count=len(normal_42d),
        preparation_contrasts=tuple(
            contrasts
        ),
        signature_lifts=lifts,
        summary=summary,
        limitations=(
            "Successful preparation is compared with ordinary 6-week blocks from the same athlete.",
            "Control blocks ending within 21 days of a strong-performance anchor are excluded to reduce overlap.",
            "Backtracking identifies association, not causation.",
            "Historical PB means best performance recorded up to that date in the available Performance Passport history.",
            "Strong-performance windows can still overlap when races are close together, so evidence is not fully independent.",
            "v0.18.4 remains observation-only and does not alter session recommendations.",
        ),
    )

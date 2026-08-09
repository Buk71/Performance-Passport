"""
Adaptive Training Block Preview.

Combines:
- the athlete's active goal;
- time remaining to the goal;
- Performance Backtracking evidence;
- the existing Training Block model.

v0.19.0 is deliberately advisory. It previews the block a coach-like system
would choose, explains why, and DOES NOT write or override live prescriptions.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.database import get_active_goal
from core.performance_backtracking import (
    PerformanceBacktrackingProfile,
    build_performance_backtracking_profile,
)


@dataclass(frozen=True)
class AdaptivePhase:
    name: str
    start_week: int
    end_week: int
    primary_focus: str
    quality_emphasis: str
    purpose: str
    athlete_evidence: tuple[str, ...]


@dataclass(frozen=True)
class AdaptiveBlockPreview:
    athlete_id: int
    available: bool
    goal_name: str | None
    distance_label: str | None
    target_date: str | None
    weeks_remaining: int | None
    current_phase: str | None
    phases: tuple[AdaptivePhase, ...]
    learned_signals: tuple[str, ...]
    headline: str
    summary: str
    limitations: tuple[str, ...]
    model_version: int = 1


def _distance_label(goal: dict) -> str:
    try:
        distance=float(goal.get("distance_m") or 0)
    except (TypeError,ValueError):
        distance=0.0
    if abs(distance-5000)<300: return "5K"
    if abs(distance-10000)<500: return "10K"
    if abs(distance-21097.5)<800: return "Half Marathon"
    if abs(distance-42195)<1200: return "Marathon"
    gt=str(goal.get("goal_type") or "").lower()
    if "half" in gt: return "Half Marathon"
    if "marathon" in gt: return "Marathon"
    if "10k" in gt: return "10K"
    if "5k" in gt: return "5K"
    return "General"


def _weeks(goal: dict, today: datetime.date) -> tuple[int,str|None]:
    raw=goal.get("target_date")
    if not raw: return 12,None
    try:
        target=datetime.date.fromisoformat(str(raw)[:10])
    except (TypeError,ValueError):
        return 12,None
    days=max((target-today).days,0)
    return max(1,(days+6)//7),target.isoformat()


def _learned_signals(profile: PerformanceBacktrackingProfile) -> tuple[str,...]:
    signals=[]
    for item in profile.preparation_contrasts:
        rel=item.relative_difference
        if rel is None or abs(rel)<0.12:
            continue
        direction="more" if rel>0 else "less"
        signals.append(
            f"Strong-performance builds contained {direction} {item.metric_label.lower()} "
            f"than ordinary training ({rel:+.0%})."
        )
    for item in profile.signature_lifts[:3]:
        if item.lift is None:
            detail="appeared in successful builds but not the sampled normal blocks"
        else:
            detail=f"was {item.lift:.1f}× as common in successful builds"
        signals.append(f"{item.workout_signature} {detail}.")
    return tuple(signals[:6])


def _phase_evidence(
    profile: PerformanceBacktrackingProfile,
    focus_keys: tuple[str,...],
) -> tuple[str,...]:
    evidence=[]
    for item in profile.preparation_contrasts:
        if item.metric_key not in focus_keys:
            continue
        if item.relative_difference is None or abs(item.relative_difference)<0.12:
            continue
        evidence.append(
            f"{item.metric_label}: {item.successful_average:g} before strong performances "
            f"vs {item.normal_average:g} in normal 6-week blocks."
        )
    return tuple(evidence[:3])


def _phase_plan(
    distance: str,
    weeks: int,
    profile: PerformanceBacktrackingProfile,
) -> tuple[AdaptivePhase,...]:
    # Phase lengths flex to the actual time available. The philosophy stays
    # generic; athlete evidence changes the explanation/emphasis.
    if weeks <= 2:
        specs=[("Taper / Race",1,weeks,"Freshness","Race-specific sharpening",
                "Reduce fatigue while preserving a small dose of race-specific intensity.",
                ("average_weekly_km","quality_session_count"))]
    elif weeks <= 4:
        split=max(1,weeks-1)
        specs=[
            ("Specific",1,split,"Race Specific","Race-specific quality",
             "Convert current fitness into the demands of the goal race.",
             ("quality_session_count","threshold_session_count","short_interval_session_count")),
            ("Taper",split+1,weeks,"Freshness","Sharpen and freshen",
             "Reduce fatigue without removing intensity completely.",
             ("average_weekly_km","quality_session_count")),
        ]
    else:
        taper=1
        specific=max(2,round(weeks*0.30))
        build=weeks-specific-taper
        if build<2:
            build=2
            specific=max(1,weeks-build-taper)
        specs=[
            ("Build",1,build,
             "Threshold" if distance in {"10K","Half Marathon"} else "Aerobic + Speed",
             "Capacity development",
             "Build the systems required for the goal while preserving the athlete's proven successful ingredients.",
             ("average_weekly_km","threshold_session_count","short_interval_session_count","long_run_count")),
            ("Specific",build+1,build+specific,"Race Specific",
             f"{distance}-specific development",
             "Shift the successful base toward sessions that increasingly resemble the physiological demands of race day.",
             ("quality_session_count","threshold_session_count","short_interval_session_count")),
            ("Taper / Race",build+specific+1,weeks,"Freshness",
             "Sharpen and freshen",
             "Protect fitness, reduce accumulated fatigue and arrive ready to express it.",
             ("average_weekly_km","quality_session_count")),
        ]

    return tuple(
        AdaptivePhase(
            name=name,start_week=start,end_week=end,primary_focus=focus,
            quality_emphasis=emphasis,purpose=purpose,
            athlete_evidence=_phase_evidence(profile,keys),
        )
        for name,start,end,focus,emphasis,purpose,keys in specs
        if start<=end
    )


def build_adaptive_block_preview(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> AdaptiveBlockPreview:
    today=today or datetime.date.today()
    goal=get_active_goal(athlete_id)
    if not goal:
        return AdaptiveBlockPreview(
            athlete_id,False,None,None,None,None,None,(),(),
            "No active goal yet",
            "Set an active goal before PP builds an adaptive race-focused block.",
            ("Preview only; no training prescription has been changed.",),
        )

    distance=_distance_label(goal)
    weeks,target=_weeks(goal,today)
    profile=build_performance_backtracking_profile(athlete_id)
    phases=_phase_plan(distance,weeks,profile)
    current=phases[0].name if phases else None
    signals=_learned_signals(profile)

    return AdaptiveBlockPreview(
        athlete_id=athlete_id,available=True,
        goal_name=str(goal.get("goal_name") or goal.get("race_name") or distance),
        distance_label=distance,target_date=target,weeks_remaining=weeks,
        current_phase=current,phases=phases,learned_signals=signals,
        headline=f"{distance} adaptive block preview",
        summary=(
            f"PP has built a {weeks}-week preview around the active {distance} goal. "
            "The phase structure follows race demands; the emphasis and explanation "
            "are informed by this athlete's own successful preparation history."
        ),
        limitations=(
            "Preview mode only: this does not change Recommended Next Run, Next Run or the saved Training Block.",
            "Historical associations influence emphasis but are not treated as proof of causation.",
            "Readiness and the response to each newly completed run should be used before the future live engine changes the next prescription.",
        ),
    )

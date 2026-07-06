"""
Performance Passport Coaching Engine

Reusable deterministic coaching calculations.

No database logic.
No Streamlit logic.
No UI formatting beyond simple pace display helpers.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass


METRES_PER_MILE = 1609.344


@dataclass(frozen=True)
class RunProfile:
    title: str | None
    sport_id: str | int | None
    distance_km: float | None
    moving_time_seconds: float | None
    avg_hr: float | None = None
    run_max_hr: float | None = None
    activity_date: str | None = None
    elevation_m: float | None = None

    lt1_hr: float | None = None
    lt2_hr: float | None = None
    athlete_max_hr: float | None = None


@dataclass(frozen=True)
class AthleteBaseline:
    run_type: str
    baseline_name: str
    run_count: int
    avg_distance_km: float
    avg_pace_seconds_per_km: float
    avg_hr: float
    avg_elevation_m: float


@dataclass(frozen=True)
class ActivityEvidence:
    """
    Explain why an activity was classified in a particular way.

    This is the foundation of the Activity Intelligence Engine.
    """

    classification: str
    easy_baseline_candidate: bool
    evidence: list[str]


def metres_to_miles(metres: float) -> float:
    return metres / METRES_PER_MILE


def metres_to_km(metres: float) -> float:
    return metres / 1000


def seconds_to_pace(seconds_per_unit: float) -> str:
    minutes = int(seconds_per_unit // 60)
    seconds = int(round(seconds_per_unit % 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}"


def pace_seconds_per_km(
    distance_km: float | None,
    moving_time_seconds: float | None,
) -> float | None:
    if not distance_km or not moving_time_seconds:
        return None

    if distance_km <= 0 or moving_time_seconds <= 0:
        return None

    return moving_time_seconds / distance_km


def pace_per_mile(distance_metres: float, moving_time_seconds: float) -> str:
    miles = metres_to_miles(distance_metres)

    if miles <= 0:
        return "-"

    return seconds_to_pace(moving_time_seconds / miles)


def pace_per_km(distance_metres: float, moving_time_seconds: float) -> str:
    km = metres_to_km(distance_metres)

    if km <= 0:
        return "-"

    return seconds_to_pace(moving_time_seconds / km)


def parse_activity_date(activity_date: str | None) -> datetime.date | None:
    if not activity_date:
        return None

    try:
        return datetime.date.fromisoformat(activity_date[:10])
    except ValueError:
        return None


def assess_activity(run: RunProfile) -> ActivityEvidence:
    """
    Assess an activity using deterministic coaching evidence.

    Version 1 deliberately keeps the rules simple and explainable.
    """

    title = (run.title or "").lower()
    sport_id = str(run.sport_id or "")

    if sport_id != "965611":
        return ActivityEvidence(
            classification="Other",
            easy_baseline_candidate=False,
            evidence=["Not a running activity"],
        )

    evidence = []

    race_keywords = [
        "race",
        "parkrun",
        "5k",
        "10k",
        "half",
        "marathon",
    ]

    session_keywords = [
        "session",
        "threshold",
        "tempo",
        "interval",
        "intervals",
        "rep",
        "reps",
        "400",
        "800",
        "1000",
        "1200",
        "1k",
        "fartlek",
        "hill",
    ]

    if any(keyword in title for keyword in race_keywords):
        evidence.append("Race keywords detected")

        return ActivityEvidence(
            classification="🏁 Race",
            easy_baseline_candidate=False,
            evidence=evidence,
        )

    if run.distance_km and run.distance_km >= 16:
        evidence.append("Long run distance")

        return ActivityEvidence(
            classification="🔵 Long Run",
            easy_baseline_candidate=False,
            evidence=evidence,
        )

    if any(keyword in title for keyword in session_keywords):
        evidence.append("Session keywords detected")

    if (
        run.run_max_hr is not None
        and run.lt1_hr is not None
        and run.run_max_hr >= run.lt1_hr
    ):
        evidence.append("Maximum HR exceeded LT1")

    if (
        run.avg_hr is not None
        and run.lt1_hr is not None
        and run.avg_hr >= run.lt1_hr
    ):
        evidence.append("Average HR exceeded LT1")

    if evidence:
        return ActivityEvidence(
            classification="🔴 Session",
            easy_baseline_candidate=False,
            evidence=evidence,
        )

    evidence.append("Matches easy aerobic profile")

    return ActivityEvidence(
        classification="🟢 Run",
        easy_baseline_candidate=True,
        evidence=evidence,
    )


def classify_run(run: RunProfile) -> str | None:
    """
    Return the activity classification.

    The assessment logic lives in assess_activity().
    """
    return assess_activity(run).classification


def is_easy_baseline_candidate(run: RunProfile) -> bool:
    """
    Return True if this activity should be included in the easy baseline.
    """
    return assess_activity(run).easy_baseline_candidate


def build_baseline(
    runs: list[RunProfile],
    run_type: str,
    baseline_name: str | None = None,
    period_days: int | None = None,
    period: str | None = None,
) -> AthleteBaseline | None:
    name = baseline_name or period or "All Time"

    cutoff_date = None
    if period_days is not None:
        cutoff_date = datetime.date.today() - datetime.timedelta(days=period_days)

    matching_runs = []

    for run in runs:
        if run_type == "🟢 Run":
            if not is_easy_baseline_candidate(run):
                continue
        elif classify_run(run) != run_type:
            continue

        if cutoff_date is not None:
            activity_date = parse_activity_date(run.activity_date)
            if activity_date is None or activity_date < cutoff_date:
                continue

        pace = pace_seconds_per_km(
            run.distance_km,
            run.moving_time_seconds,
        )

        if pace is None:
            continue

        if run.avg_hr is None:
            continue

        matching_runs.append((run, pace))

    if not matching_runs:
        return None

    run_count = len(matching_runs)

    avg_distance_km = sum(
        run.distance_km or 0 for run, _pace in matching_runs
    ) / run_count

    avg_pace_seconds_per_km = sum(
        pace for _run, pace in matching_runs
    ) / run_count

    avg_hr = sum(
        run.avg_hr or 0 for run, _pace in matching_runs
    ) / run_count

    avg_elevation_m = sum(
        run.elevation_m or 0 for run, _pace in matching_runs
    ) / run_count

    return AthleteBaseline(
        run_type=run_type,
        baseline_name=name,
        run_count=run_count,
        avg_distance_km=avg_distance_km,
        avg_pace_seconds_per_km=avg_pace_seconds_per_km,
        avg_hr=avg_hr,
        avg_elevation_m=avg_elevation_m,
    )


def aerobic_efficiency(avg_hr: float | None, pace_seconds_per_mile: float | None):
    return None
"""Lightweight real-data adapter for the latest-run Home card.

The full Coach's Journal also builds race and decision intelligence.  Home
already calculates those separately, so this adapter deliberately reuses only
Performance Recognition.  It keeps the latest-run card quick while preserving
the athlete-relative rank, environmental context and genuine achievement.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.coaching import RunProfile
from core.database import get_connection, get_effective_athlete_thresholds
from core.performance_recognition import (
    Recognition,
    build_recognition_index,
    recognition_key,
)


@dataclass(frozen=True)
class HomeLatestRun:
    athlete_id: int
    available: bool
    activity_date: str | None
    title: str
    category: str | None
    distance_km: float | None
    moving_time_s: float | None
    actual_pace_s_per_km: float | None
    adjusted_pace_s_per_km: float | None
    avg_hr: float | None
    headline: str
    explanation: str
    benefit: str
    rank: int | None
    comparison_count: int | None
    top_percent: float | None
    rank_12m: int | None
    comparison_count_12m: int | None
    environment_factors: tuple[str, ...]
    environment_adjustment_s_per_km: float
    confidence: float


BENEFITS = {
    "recovery": "Supports recovery while maintaining running rhythm.",
    "easy": "Builds aerobic fitness without spending unnecessary intensity.",
    "long_easy": "Builds endurance and the ability to hold form late in longer races.",
    "steady": "Builds aerobic strength between easy and threshold intensity.",
    "threshold": "Raises the sustainable pace you can hold near race effort.",
    "vo2": "Develops aerobic power so faster race pace feels more controlled.",
    "speed": "Improves running economy, leg speed and neuromuscular sharpness.",
    "workout": "Develops race-specific fitness through deliberate work and recovery.",
    "race": "Provides direct evidence of current race capability.",
}


def _load_runs(athlete_id: int) -> list[RunProfile]:
    thresholds = get_effective_athlete_thresholds(athlete_id)
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            activity_date,
            title,
            distance_m,
            moving_time_s,
            avg_hr,
            max_hr,
            sport_id,
            elevation_up_m,
            temperature_c,
            humidity
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_datetime DESC, id DESC
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    connection.close()

    runs = []
    for row in rows:
        try:
            distance_value = float(row[2] or 0.0)
        except (TypeError, ValueError):
            distance_value = 0.0
        distance_km = (
            distance_value / 1000.0
            if distance_value > 250.0
            else distance_value
        )
        runs.append(
            RunProfile(
                athlete_id=athlete_id,
                activity_date=row[0],
                title=row[1],
                distance_km=distance_km,
                moving_time_seconds=row[3],
                avg_hr=row[4],
                run_max_hr=row[5],
                sport_id=row[6],
                elevation_m=row[7],
                temperature_c=row[8],
                humidity=row[9],
                lt1_hr=thresholds.get("lt1_hr"),
                lt2_hr=thresholds.get("lt2_hr"),
                athlete_max_hr=thresholds.get("athlete_max_hr"),
            )
        )
    return runs


def _latest_recognised(
    runs: list[RunProfile],
    index: dict[str, Recognition],
) -> tuple[RunProfile | None, Recognition | None]:
    for run in runs:
        recognition = index.get(recognition_key(run))
        if recognition is not None:
            return run, recognition
    return None, None


def _empty(athlete_id: int) -> HomeLatestRun:
    return HomeLatestRun(
        athlete_id=athlete_id,
        available=False,
        activity_date=None,
        title="Latest run is still building",
        category=None,
        distance_km=None,
        moving_time_s=None,
        actual_pace_s_per_km=None,
        adjusted_pace_s_per_km=None,
        avg_hr=None,
        headline="No recognised run yet",
        explanation="Import a running activity to unlock its coaching value.",
        benefit="Every recognised run will explain what it contributed.",
        rank=None,
        comparison_count=None,
        top_percent=None,
        rank_12m=None,
        comparison_count_12m=None,
        environment_factors=(),
        environment_adjustment_s_per_km=0.0,
        confidence=0.0,
    )


def build_home_latest_run(athlete_id: int) -> HomeLatestRun:
    runs = _load_runs(athlete_id)
    if not runs:
        return _empty(athlete_id)

    recognition_index = build_recognition_index(
        runs,
        athlete_id=athlete_id,
    )
    run, recognition = _latest_recognised(runs, recognition_index)
    if run is None or recognition is None:
        return _empty(athlete_id)

    benefit = BENEFITS.get(
        recognition.category_key,
        "Adds another useful piece of evidence to your coaching picture.",
    )

    return HomeLatestRun(
        athlete_id=athlete_id,
        available=True,
        activity_date=run.activity_date,
        title=str(run.title or recognition.category_label),
        category=recognition.category_label,
        distance_km=run.distance_km,
        moving_time_s=run.moving_time_seconds,
        actual_pace_s_per_km=recognition.actual_pace_s_per_km,
        adjusted_pace_s_per_km=recognition.adjusted_pace_s_per_km,
        avg_hr=run.avg_hr,
        headline=recognition.celebration,
        explanation=recognition.positive_detail,
        benefit=benefit,
        rank=recognition.rank,
        comparison_count=recognition.total,
        top_percent=recognition.top_percent,
        rank_12m=recognition.rank_12m,
        comparison_count_12m=recognition.total_12m,
        environment_factors=recognition.environment_factors,
        environment_adjustment_s_per_km=(
            recognition.environment_adjustment_s_per_km
        ),
        confidence=recognition.confidence,
    )

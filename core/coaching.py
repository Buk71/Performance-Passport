"""
Performance Passport Coaching Engine

Reusable coaching calculations.

These functions are deterministic and contain no database or UI logic.
They provide the foundation for future coaching features including:

- Best Ever Easy Run
- Heat adjustment
- Fatigue
- Durability
- Passport Score
"""

from __future__ import annotations

from dataclasses import dataclass


METRES_PER_MILE = 1609.344


@dataclass(frozen=True)
class RunProfile:
    """
    Lightweight coaching profile for an activity.

    This is not a database model.
    It is a simple object used by the coaching engine.
    """

    title: str | None
    sport_id: str | int | None
    distance_km: float | None
    moving_time_seconds: float | None
    avg_hr: float | None = None


def metres_to_miles(metres: float) -> float:
    """Convert metres to miles."""
    return metres / METRES_PER_MILE


def metres_to_km(metres: float) -> float:
    """Convert metres to kilometres."""
    return metres / 1000


def seconds_to_pace(seconds_per_unit: float) -> str:
    """
    Convert seconds per mile/km into mm:ss pace.
    """
    minutes = int(seconds_per_unit // 60)
    seconds = int(round(seconds_per_unit % 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}"


def pace_per_mile(distance_metres: float, moving_time_seconds: float) -> str:
    """Return pace formatted as min/mile."""
    miles = metres_to_miles(distance_metres)

    if miles <= 0:
        return "-"

    return seconds_to_pace(moving_time_seconds / miles)


def pace_per_km(distance_metres: float, moving_time_seconds: float) -> str:
    """Return pace formatted as min/km."""
    km = metres_to_km(distance_metres)

    if km <= 0:
        return "-"

    return seconds_to_pace(moving_time_seconds / km)


def classify_run(run: RunProfile) -> str | None:
    """
    Classify a running activity using simple deterministic rules.

    This is intentionally conservative.
    It avoids calling something an Easy Run until we have stronger evidence.
    """
    title = (run.title or "").lower()
    sport_id = str(run.sport_id or "")

    if sport_id != "965611":
        return None

    race_keywords = [
        "race",
        "parkrun",
        "5k",
        "10k",
        "half",
        "marathon",
    ]

    interval_keywords = [
        "interval",
        "intervals",
        "rep",
        "reps",
        "400",
        "800",
        "1k",
        "1000",
        "1200",
        "fartlek",
    ]

    if any(keyword in title for keyword in race_keywords):
        return "🏁 Race"

    if any(keyword in title for keyword in interval_keywords):
        return "🔴 Interval Session"

    if run.distance_km and run.distance_km >= 16:
        return "🔵 Long Run"

    return "🟢 Run"


def aerobic_efficiency(avg_hr: float | None, pace_seconds_per_mile: float | None):
    """
    Placeholder for the future Aerobic Efficiency calculation.

    Sprint 3.2 intentionally returns None until we design the
    complete coaching model in a later sprint.
    """
    return None
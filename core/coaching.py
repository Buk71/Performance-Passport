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


METRES_PER_MILE = 1609.344


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


def aerobic_efficiency(avg_hr: float | None, pace_seconds_per_mile: float | None):
    """
    Placeholder for the future Aerobic Efficiency calculation.

    Sprint 3.2 intentionally returns None until we design the
    complete coaching model in a later sprint.
    """
    return None
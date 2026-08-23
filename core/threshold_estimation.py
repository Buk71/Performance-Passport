"""Explainable personal LT1/LT2 heart-rate estimates from training history.

These are field estimates, not laboratory measurements. The estimator uses
robust distributions across many sustained runs, honours activity heart-rate
corrections, and refuses to create precise-looking values from weak evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
from functools import lru_cache
import math
from statistics import median

from core.activity_reliability import has_reliable_distance_and_pace
from core.database import (
    get_activity_overrides,
    get_athlete_sport_roles,
    get_connection,
    get_effective_activity_heart_rate,
)


QUALITY_WORDS = (
    "race", "parkrun", "threshold", "tempo", "interval", "reps",
    "fartlek", "track", "vo2", "5k", "10k", "half marathon",
)


@dataclass(frozen=True)
class ThresholdPointEstimate:
    value_bpm: int | None
    low_bpm: int | None
    high_bpm: int | None
    confidence: str
    sample_size: int
    method: str


@dataclass(frozen=True)
class AthleteThresholdEstimate:
    athlete_id: int
    lt1: ThresholdPointEstimate
    lt2: ThresholdPointEstimate
    max_hr_basis: int | None
    reliable_run_count: int
    latest_evidence_date: str | None
    limitations: tuple[str, ...]

    @property
    def available(self) -> bool:
        return self.lt1.value_bpm is not None or self.lt2.value_bpm is not None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _distance_km(value) -> float | None:
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return None
    if distance <= 0:
        return None
    return distance / 1000.0 if distance > 250.0 else distance


def _confidence(sample_size: int, high_effort_size: int) -> str:
    if sample_size >= 80 and high_effort_size >= 12:
        return "Strong"
    if sample_size >= 25 and high_effort_size >= 6:
        return "Moderate"
    if sample_size >= 10 and high_effort_size >= 3:
        return "Limited"
    return "Insufficient"


def _empty(athlete_id: int, reason: str) -> AthleteThresholdEstimate:
    unavailable = ThresholdPointEstimate(
        value_bpm=None,
        low_bpm=None,
        high_bpm=None,
        confidence="Insufficient",
        sample_size=0,
        method="Not enough reliable personal heart-rate evidence.",
    )
    return AthleteThresholdEstimate(
        athlete_id=athlete_id,
        lt1=unavailable,
        lt2=unavailable,
        max_hr_basis=None,
        reliable_run_count=0,
        latest_evidence_date=None,
        limitations=(reason,),
    )


def estimate_athlete_thresholds(athlete_id: int) -> AthleteThresholdEstimate:
    """Return a cache-safe estimate that refreshes when activities change."""
    connection = get_connection()
    try:
        version = connection.execute(
            """SELECT COUNT(*), COALESCE(MAX(id), 0),
                      COALESCE(MAX(activity_datetime), '')
               FROM activities WHERE athlete_id = ?""",
            (athlete_id,),
        ).fetchone()
        athlete = connection.execute(
            """SELECT resting_hr, max_hr FROM athletes WHERE id = ?""",
            (athlete_id,),
        ).fetchone()
    except Exception:
        connection.close()
        return _empty(athlete_id, "The athlete or activity evidence is unavailable.")
    connection.close()
    if athlete is None:
        return _empty(athlete_id, "The athlete profile was not found.")
    override_signature = tuple(
        sorted(
            (activity_id, item.get("heart_rate_reliable"), item.get("corrected_avg_hr"))
            for activity_id, item in get_activity_overrides(athlete_id).items()
        )
    )
    return _estimate_cached(
        int(athlete_id), int(version[0]), int(version[1]), str(version[2]),
        int(athlete[0]) if athlete[0] else None,
        int(athlete[1]) if athlete[1] else None,
        override_signature,
    )


@lru_cache(maxsize=128)
def _estimate_cached(
    athlete_id: int,
    activity_count: int,
    latest_activity_id: int,
    latest_activity_datetime: str,
    resting_hr: int | None,
    profile_max_hr: int | None,
    override_signature: tuple,
) -> AthleteThresholdEstimate:
    del activity_count, latest_activity_id, latest_activity_datetime, override_signature
    roles = get_athlete_sport_roles(athlete_id)
    running_ids = {str(key) for key, role in roles.items() if role == "running"}
    if not running_ids:
        return _empty(athlete_id, "No running sport is mapped for this athlete.")

    connection = get_connection()
    placeholders = ",".join("?" for _ in running_ids)
    try:
        rows = connection.execute(
            f"""SELECT id, activity_date, title, sport_id, distance_m,
                       moving_time_s, avg_hr, max_hr, route_name, raw_json
                FROM activities
                WHERE athlete_id = ?
                  AND CAST(sport_id AS TEXT) IN ({placeholders})
                ORDER BY activity_datetime""",
            (athlete_id, *sorted(running_ids)),
        ).fetchall()
    except Exception:
        connection.close()
        return _empty(athlete_id, "Running heart-rate evidence could not be loaded.")
    connection.close()

    reliable = []
    minimum_hr = max((resting_hr or 45) + 22, 85)
    for row in rows:
        distance = _distance_km(row[4])
        try:
            duration = float(row[5] or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        effective_hr = get_effective_activity_heart_rate(athlete_id, row[0], row[6])
        try:
            avg_hr = float(effective_hr)
        except (TypeError, ValueError):
            continue
        try:
            run_max_hr = float(row[7]) if row[7] is not None else None
        except (TypeError, ValueError):
            run_max_hr = None
        if (
            distance is None or distance < 3.0
            or duration < 1_200 or duration > 9_000
            or avg_hr < minimum_hr or avg_hr > 220
            or (run_max_hr is not None and run_max_hr + 2 < avg_hr)
            or not has_reliable_distance_and_pace(
                title=row[2], sport_id=str(row[3] or ""),
                route_name=row[8], raw_json_text=row[9],
            )
        ):
            continue
        reliable.append(
            {
                "date": str(row[1])[:10] if row[1] else None,
                "title": str(row[2] or "").lower(),
                "avg_hr": avg_hr,
                "max_hr": run_max_hr,
                "duration": duration,
            }
        )

    if len(reliable) < 10:
        return _empty(
            athlete_id,
            f"Only {len(reliable)} reliable sustained runs were available; at least 10 are needed.",
        )

    average_values = [item["avg_hr"] for item in reliable]
    aerobic_values = [
        item["avg_hr"] for item in reliable
        if not any(word in item["title"] for word in QUALITY_WORDS)
    ]
    if len(aerobic_values) < 10:
        aerobic_values = average_values

    observed_max_values = [
        item["max_hr"] for item in reliable
        if item["max_hr"] is not None
        and item["max_hr"] >= item["avg_hr"]
        and item["max_hr"] <= 220
    ]
    observed_max = _percentile(observed_max_values, 0.95)
    max_basis = float(profile_max_hr) if profile_max_hr else observed_max
    if max_basis is None:
        high_average = _percentile(average_values, 0.98)
        max_basis = high_average / 0.92 if high_average else None
    if max_basis is None:
        return _empty(athlete_id, "No credible maximum-heart-rate basis was available.")

    aerobic_ceiling = _percentile(aerobic_values, 0.85)
    sustained_ceiling = _percentile(average_values, 0.98)
    if aerobic_ceiling is None or sustained_ceiling is None:
        return _empty(athlete_id, "The sustained heart-rate distribution was incomplete.")

    lt1_value = round(aerobic_ceiling * 0.65 + max_basis * 0.86 * 0.35)
    lt2_value = round(sustained_ceiling * 0.65 + max_basis * 0.92 * 0.35)
    lt1_value = max(lt1_value, (resting_hr or 40) + 35)
    lt2_value = max(lt2_value, lt1_value + 7)
    lt2_value = min(lt2_value, round(max_basis - 2))
    lt1_value = min(lt1_value, lt2_value - 7)

    high_effort_count = sum(
        1 for value in average_values if value >= sustained_ceiling * 0.97
    )
    confidence = _confidence(len(reliable), high_effort_count)
    uncertainty = {"Strong": 2, "Moderate": 4, "Limited": 6}.get(confidence, 8)
    latest_date = max(
        (item["date"] for item in reliable if item["date"]),
        default=None,
    )
    limitations = (
        "Field estimates can differ from laboratory lactate or ventilatory thresholds.",
        "Activity-average heart rate includes warm-up and cooldown and is treated conservatively.",
    )
    return AthleteThresholdEstimate(
        athlete_id=athlete_id,
        lt1=ThresholdPointEstimate(
            value_bpm=int(lt1_value),
            low_bpm=int(lt1_value - uncertainty),
            high_bpm=int(lt1_value + uncertainty),
            confidence=confidence,
            sample_size=len(aerobic_values),
            method="Upper aerobic boundary from the athlete's reliable sustained-run distribution.",
        ),
        lt2=ThresholdPointEstimate(
            value_bpm=int(lt2_value),
            low_bpm=int(lt2_value - uncertainty),
            high_bpm=int(lt2_value + uncertainty),
            confidence=confidence,
            sample_size=high_effort_count,
            method="Sustainable high-effort boundary from the athlete's strongest reliable sustained runs.",
        ),
        max_hr_basis=int(round(max_basis)),
        reliable_run_count=len(reliable),
        latest_evidence_date=latest_date,
        limitations=limitations,
    )


def clear_threshold_estimation_cache() -> None:
    _estimate_cached.cache_clear()

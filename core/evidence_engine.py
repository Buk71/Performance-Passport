"""
Evidence Engine foundation.

The Evidence Engine inspects what activity evidence is genuinely available
for one athlete before any coach makes a recommendation.

It is deliberately conservative:
- it never claims a metric exists without finding it;
- it supports database columns and Runalyze raw_json aliases;
- it reports coverage and sample sizes;
- it separates "available now" from "requires FIT/lap data";
- it does not invent first-kilometre pace, cardiac drift or stop metrics from
  summary-only activities.

This foundation prepares Actionable Coaching, Hall of Fame and Coach Mode.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any


@dataclass(frozen=True)
class EvidenceMetric:
    key: str
    label: str
    available_count: int
    activity_count: int
    coverage: float
    status: str
    source: str
    coaching_use: str
    note: str


@dataclass(frozen=True)
class AthleteEvidenceProfile:
    athlete_id: int
    activity_count: int
    run_count: int
    raw_json_count: int
    metrics: tuple[EvidenceMetric, ...]
    available_metric_count: int
    developing_metric_count: int
    unavailable_metric_count: int
    overall_coverage: float
    headline: str
    summary: str


COLUMN_ALIASES = {
    "temperature": (
        "temperature_c",
        "temperature",
        "weather_temperature",
    ),
    "humidity": (
        "humidity",
        "humidity_percent",
        "weather_humidity",
    ),
    "wind_speed": (
        "wind_speed",
        "wind_speed_kmh",
        "windspeed",
        "weather_wind_speed",
    ),
    "elevation": (
        "elevation_up_m",
        "elevation_gain_m",
        "elevation_m",
    ),
    "moving_time": (
        "moving_time_s",
        "moving_time_seconds",
    ),
    "elapsed_time": (
        "elapsed_time_s",
        "elapsed_time_seconds",
        "duration_s",
    ),
    "average_hr": (
        "avg_hr",
        "average_hr",
        "heart_rate_avg",
    ),
    "max_hr": (
        "max_hr",
        "maximum_hr",
        "heart_rate_max",
    ),
    "cadence": (
        "avg_cadence",
        "cadence",
        "average_cadence",
    ),
    "first_km_pace": (
        "first_km_pace_s",
        "first_km_pace_s_per_km",
    ),
    "last_km_pace": (
        "last_km_pace_s",
        "last_km_pace_s_per_km",
    ),
    "pace_variability": (
        "pace_variability",
        "pace_cv",
        "pace_stddev",
    ),
    "stop_count": (
        "stop_count",
        "stops",
        "pause_count",
    ),
    "longest_stop": (
        "longest_stop_s",
        "longest_pause_s",
    ),
    "moving_percent": (
        "moving_percent",
        "moving_percentage",
    ),
    "hr_drift": (
        "hr_drift",
        "cardiac_drift",
        "decoupling_percent",
    ),
}

RAW_JSON_ALIASES = {
    "wind_speed": (
        "wind_speed",
        "windspeed",
        "windSpeed",
        "weather.wind_speed",
        "weather.windspeed",
    ),
    "temperature": (
        "temperature",
        "temperature_c",
        "weather.temperature",
    ),
    "humidity": (
        "humidity",
        "weather.humidity",
    ),
    "cadence": (
        "cadence",
        "avg_cadence",
        "average_cadence",
    ),
    "first_km_pace": (
        "first_km_pace",
        "first_km_pace_s",
    ),
    "last_km_pace": (
        "last_km_pace",
        "last_km_pace_s",
    ),
    "pace_variability": (
        "pace_variability",
        "pace_cv",
    ),
    "stop_count": (
        "stop_count",
        "pause_count",
    ),
    "longest_stop": (
        "longest_stop_s",
        "longest_pause_s",
    ),
    "moving_percent": (
        "moving_percent",
        "moving_percentage",
    ),
    "hr_drift": (
        "hr_drift",
        "cardiac_drift",
        "decoupling_percent",
    ),
}

METRIC_DEFINITIONS = (
    (
        "average_hr",
        "Average heart rate",
        "Easy intensity, threshold control and aerobic efficiency",
        "Summary activity data",
    ),
    (
        "moving_time",
        "Moving time",
        "Training duration, pace and continuity",
        "Summary activity data",
    ),
    (
        "elapsed_time",
        "Elapsed time",
        "PB timing and interruption analysis",
        "Summary activity data",
    ),
    (
        "temperature",
        "Temperature",
        "Heat adjustment and Environmental Profile",
        "Runalyze weather data",
    ),
    (
        "humidity",
        "Humidity",
        "Heat-stress context",
        "Runalyze weather data",
    ),
    (
        "wind_speed",
        "Wind speed",
        "Wind forecasts and future personal wind response",
        "Runalyze weather data",
    ),
    (
        "elevation",
        "Elevation gain",
        "Hill adjustment and terrain context",
        "Summary activity data",
    ),
    (
        "cadence",
        "Cadence",
        "Running-economy evidence where appropriate",
        "FIT or enriched activity data",
    ),
    (
        "first_km_pace",
        "First-kilometre pace",
        "Evidence for conservative or aggressive starts",
        "Lap/FIT-derived metric",
    ),
    (
        "last_km_pace",
        "Last-kilometre pace",
        "Finish strength and progression evidence",
        "Lap/FIT-derived metric",
    ),
    (
        "pace_variability",
        "Pace variability",
        "Session execution and smoothness",
        "Lap/FIT-derived metric",
    ),
    (
        "stop_count",
        "Stop count",
        "Training continuity and execution advice",
        "FIT/GPS-derived metric",
    ),
    (
        "longest_stop",
        "Longest stop",
        "Interruption severity",
        "FIT/GPS-derived metric",
    ),
    (
        "moving_percent",
        "Moving percentage",
        "Continuous-running quality",
        "Moving versus elapsed time",
    ),
    (
        "hr_drift",
        "Cardiac drift",
        "Aerobic durability and Easy Run Coach",
        "Split/FIT-derived metric",
    ),
)


def _safe_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if not value:
        return {}

    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}

    return decoded if isinstance(decoded, dict) else {}


def _nested_value(data: dict[str, Any], path: str) -> Any:
    value: Any = data

    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)

    return value


def _usable(value: Any) -> bool:
    if value is None or value == "":
        return False

    if isinstance(value, bool):
        return True

    if isinstance(value, (int, float)):
        return math.isfinite(float(value))

    return True


def _table_columns(cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cursor.fetchall()}


def _column_count(
    cursor,
    *,
    athlete_id: int,
    column: str,
) -> int:
    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM activities
        WHERE athlete_id = ?
          AND {column} IS NOT NULL
          AND CAST({column} AS TEXT) != ''
        """,
        (athlete_id,),
    )
    return int(cursor.fetchone()[0] or 0)


def _raw_json_counts(
    rows: list[Any],
) -> dict[str, int]:
    counts = {
        key: 0
        for key in RAW_JSON_ALIASES
    }

    for row in rows:
        data = _safe_json(row)

        if not data:
            continue

        for key, aliases in RAW_JSON_ALIASES.items():
            if any(
                _usable(_nested_value(data, alias))
                for alias in aliases
            ):
                counts[key] += 1

    return counts


def _status(
    *,
    count: int,
    total: int,
) -> str:
    if total <= 0 or count <= 0:
        return "unavailable"

    coverage = count / total

    if coverage >= 0.65:
        return "available"
    if coverage >= 0.10:
        return "developing"
    return "limited"


def build_athlete_evidence_profile(
    conn,
    *,
    athlete_id: int,
) -> AthleteEvidenceProfile:
    cursor = conn.cursor()
    columns = _table_columns(cursor, "activities")

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM activities
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )
    activity_count = int(cursor.fetchone()[0] or 0)

    if "sport_id" in columns:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM activities
            WHERE athlete_id = ?
              AND CAST(sport_id AS TEXT) IN (
                  '965611',
                  'running',
                  'run'
              )
            """,
            (athlete_id,),
        )
        run_count = int(cursor.fetchone()[0] or 0)
    else:
        run_count = activity_count

    raw_json_rows = []

    if "raw_json" in columns:
        cursor.execute(
            """
            SELECT raw_json
            FROM activities
            WHERE athlete_id = ?
              AND raw_json IS NOT NULL
              AND CAST(raw_json AS TEXT) != ''
            """,
            (athlete_id,),
        )
        raw_json_rows = [
            row[0]
            for row in cursor.fetchall()
        ]

    raw_counts = _raw_json_counts(raw_json_rows)
    raw_json_count = len(raw_json_rows)
    denominator = max(run_count, activity_count, 1)
    metrics = []

    for key, label, coaching_use, preferred_source in METRIC_DEFINITIONS:
        count = 0
        source_parts = []

        for alias in COLUMN_ALIASES.get(key, ()):
            if alias in columns:
                alias_count = _column_count(
                    cursor,
                    athlete_id=athlete_id,
                    column=alias,
                )

                if alias_count > count:
                    count = alias_count

                if alias_count:
                    source_parts.append(f"activities.{alias}")

        raw_count = raw_counts.get(key, 0)

        if raw_count > count:
            count = raw_count

        if raw_count:
            source_parts.append("activities.raw_json")

        status = _status(
            count=count,
            total=denominator,
        )
        coverage = min(count / denominator, 1.0)

        if status == "available":
            note = "Ready for evidence-based coaching."
        elif status == "developing":
            note = (
                "Usable for cautious coaching with clear confidence labels."
            )
        elif status == "limited":
            note = (
                "Present in too few activities for reliable recommendations."
            )
        else:
            note = (
                f"Not currently available; expected from {preferred_source}."
            )

        metrics.append(
            EvidenceMetric(
                key=key,
                label=label,
                available_count=count,
                activity_count=denominator,
                coverage=round(coverage, 4),
                status=status,
                source=(
                    ", ".join(dict.fromkeys(source_parts))
                    if source_parts
                    else preferred_source
                ),
                coaching_use=coaching_use,
                note=note,
            )
        )

    available_count = sum(
        metric.status == "available"
        for metric in metrics
    )
    developing_count = sum(
        metric.status in {"developing", "limited"}
        for metric in metrics
    )
    unavailable_count = sum(
        metric.status == "unavailable"
        for metric in metrics
    )
    overall_coverage = (
        sum(metric.coverage for metric in metrics)
        / len(metrics)
        if metrics
        else 0.0
    )

    if available_count >= 8:
        headline = "Strong evidence foundation"
    elif available_count >= 5:
        headline = "Useful evidence foundation"
    else:
        headline = "Evidence foundation is still developing"

    summary = (
        f"{available_count} coaching metrics are ready, "
        f"{developing_count} are developing and "
        f"{unavailable_count} require additional data. "
        "Coaches should only make recommendations supported by the available "
        "evidence."
    )

    return AthleteEvidenceProfile(
        athlete_id=athlete_id,
        activity_count=activity_count,
        run_count=run_count,
        raw_json_count=raw_json_count,
        metrics=tuple(metrics),
        available_metric_count=available_count,
        developing_metric_count=developing_count,
        unavailable_metric_count=unavailable_count,
        overall_coverage=round(overall_coverage, 4),
        headline=headline,
        summary=summary,
    )

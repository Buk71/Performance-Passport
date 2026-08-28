"""Parse and persist Runalyze health exports without inventing physiology.

The combined Runalyze health export is preferred because it keeps nightly HRV,
resting heart rate and sleep on the same date.  The standalone HRV export is
also accepted.  Imports are athlete-scoped, idempotent and preserve the raw
source row for audit.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import math
from typing import Any, Iterable, Mapping

from core.database import create_athlete_health_daily_table, get_connection


RUNALYZE_HEALTH_SOURCE = "runalyze_health_csv"
GARMIN_CONNECT_HEALTH_SOURCE = "garmin_connect_health"


@dataclass(frozen=True)
class RunalyzeHealthRecord:
    health_date: str
    file_kind: str
    hrv_value: float | None = None
    hrv_metric_code: str | None = None
    hrv_measurement_type: str | None = None
    hrv_source_code: str | None = None
    hrv_source_id: str | None = None
    resting_hr: float | None = None
    resting_hr_source_id: str | None = None
    sleep_source_id: str | None = None
    sleep_start_time: str | None = None
    sleep_end_time: str | None = None
    sleep_duration_min: float | None = None
    sleep_rem_min: float | None = None
    sleep_awake_min: float | None = None
    sleep_deep_min: float | None = None
    sleep_light_min: float | None = None
    sleep_unknown_min: float | None = None
    sleep_quality: float | None = None
    sleep_quality_100: float | None = None
    weight_kg: float | None = None
    raw_json: str = "{}"


@dataclass(frozen=True)
class RunalyzeHealthParseResult:
    file_kind: str
    records: tuple[RunalyzeHealthRecord, ...]
    skipped: int
    issues: tuple[str, ...]


@dataclass(frozen=True)
class RunalyzeHealthImportResult:
    imported: int
    enriched: int
    duplicates: int
    errors: tuple[str, ...]


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() in {"", "nan", "NaN", "None", "null", "<NA>"}


def _text(value: Any) -> str | None:
    if _missing(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _number(value: Any) -> float | None:
    if _missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _date(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return datetime.date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _raw_payload(row: Mapping[str, Any], file_kind: str) -> str:
    clean = {
        str(key): None if _missing(value) else value
        for key, value in row.items()
    }
    return json.dumps({file_kind: clean}, default=str, sort_keys=True)


def _has_recovery_value(record: RunalyzeHealthRecord) -> bool:
    return any(
        value is not None
        for value in (
            record.hrv_value,
            record.resting_hr,
            record.sleep_duration_min,
            record.sleep_quality_100,
            record.weight_kg,
        )
    )


def _combined_record(row: Mapping[str, Any]) -> RunalyzeHealthRecord | None:
    health_date = _date(row.get("date"))
    if health_date is None:
        return None
    record = RunalyzeHealthRecord(
        health_date=health_date,
        file_kind="combined_health",
        hrv_value=_number(row.get("hrv.hrv")),
        hrv_metric_code=_text(row.get("hrv.metric")),
        hrv_measurement_type=_text(row.get("hrv.measurementType")),
        hrv_source_code=_text(row.get("hrv.source")),
        hrv_source_id=_text(row.get("hrv.id")),
        resting_hr=_number(row.get("restingHeartRate.heartRate")),
        resting_hr_source_id=_text(row.get("restingHeartRate.id")),
        sleep_source_id=_text(row.get("sleep.id")),
        sleep_start_time=_text(row.get("sleep.startTime")),
        sleep_end_time=_text(row.get("sleep.endTime")),
        sleep_duration_min=_number(row.get("sleep.duration")),
        sleep_rem_min=_number(row.get("sleep.remDuration")),
        sleep_awake_min=_number(row.get("sleep.awakeDuration")),
        sleep_deep_min=_number(row.get("sleep.deepSleepDuration")),
        sleep_light_min=_number(row.get("sleep.lightSleepDuration")),
        sleep_unknown_min=_number(row.get("sleep.unknownSleepDuration")),
        sleep_quality=_number(row.get("sleep.quality")),
        sleep_quality_100=_number(row.get("sleep.quality100")),
        weight_kg=_number(row.get("bodyComposition.weight")),
        raw_json=_raw_payload(row, "combined_health"),
    )
    return record if _has_recovery_value(record) else None


def _hrv_record(row: Mapping[str, Any]) -> RunalyzeHealthRecord | None:
    health_date = _date(row.get("date"))
    if health_date is None:
        return None
    record = RunalyzeHealthRecord(
        health_date=health_date,
        file_kind="hrv_only",
        hrv_value=_number(row.get("hrv")),
        hrv_metric_code=_text(row.get("metric")),
        hrv_measurement_type=_text(row.get("measurementType")),
        hrv_source_code=_text(row.get("source")),
        hrv_source_id=_text(row.get("id")),
        raw_json=_raw_payload(row, "hrv_only"),
    )
    return record if record.hrv_value is not None else None


def parse_runalyze_health_rows(
    rows: Iterable[Mapping[str, Any]],
) -> RunalyzeHealthParseResult:
    """Return typed health records from either supported Runalyze CSV shape."""
    row_list = list(rows)
    if not row_list:
        return RunalyzeHealthParseResult("unknown", (), 0, ("The CSV is empty.",))
    columns = set(row_list[0])
    if {"date", "hrv.hrv", "restingHeartRate.heartRate"} & columns and (
        "hrv.hrv" in columns or "sleep.duration" in columns
    ):
        file_kind = "combined_health"
        parser = _combined_record
    elif {"id", "date", "hrv", "metric", "measurementType", "source"}.issubset(columns):
        file_kind = "hrv_only"
        parser = _hrv_record
    else:
        return RunalyzeHealthParseResult(
            "unknown",
            (),
            len(row_list),
            (
                "This is not a recognised Runalyze combined-health or HRV CSV export.",
            ),
        )

    records = []
    issues = []
    skipped = 0
    for index, row in enumerate(row_list, start=2):
        record = parser(row)
        if record is None:
            skipped += 1
            if _date(row.get("date")) is None:
                issues.append(f"Row {index} has no valid health date.")
            continue
        records.append(record)
    records.sort(key=lambda item: item.health_date)
    return RunalyzeHealthParseResult(
        file_kind=file_kind,
        records=tuple(records),
        skipped=skipped,
        issues=tuple(issues),
    )


_UPDATE_FIELDS = (
    "hrv_value",
    "hrv_metric_code",
    "hrv_measurement_type",
    "hrv_source_code",
    "hrv_source_id",
    "resting_hr",
    "resting_hr_source_id",
    "sleep_source_id",
    "sleep_start_time",
    "sleep_end_time",
    "sleep_duration_min",
    "sleep_rem_min",
    "sleep_awake_min",
    "sleep_deep_min",
    "sleep_light_min",
    "sleep_unknown_min",
    "sleep_quality",
    "sleep_quality_100",
    "weight_kg",
)


def _merged_raw(existing: str | None, incoming: str) -> str:
    try:
        current = json.loads(existing or "{}")
    except (TypeError, json.JSONDecodeError):
        current = {"legacy": existing}
    try:
        new = json.loads(incoming or "{}")
    except (TypeError, json.JSONDecodeError):
        new = {"incoming": incoming}
    if not isinstance(current, dict):
        current = {"legacy": current}
    if isinstance(new, dict):
        current.update(new)
    return json.dumps(current, default=str, sort_keys=True)


def import_runalyze_health_records(
    records: Iterable[RunalyzeHealthRecord],
    *,
    athlete_id: int,
) -> RunalyzeHealthImportResult:
    """Insert or enrich one athlete's daily health rows idempotently."""
    return import_health_records(
        records,
        athlete_id=athlete_id,
        source=RUNALYZE_HEALTH_SOURCE,
    )


def import_health_records(
    records: Iterable[RunalyzeHealthRecord],
    *,
    athlete_id: int,
    source: str,
) -> RunalyzeHealthImportResult:
    """Insert or enrich source-labelled health evidence for one athlete."""
    clean_source = str(source or "").strip()
    if not clean_source:
        raise ValueError("Health source is required.")
    connection = get_connection()
    cursor = connection.cursor()
    create_athlete_health_daily_table(cursor)
    owner = cursor.execute(
        "SELECT id FROM athletes WHERE id = ?", (int(athlete_id),)
    ).fetchone()
    if owner is None:
        connection.close()
        raise ValueError("Athlete not found.")

    imported = enriched = duplicates = 0
    errors = []
    select_fields = ", ".join(_UPDATE_FIELDS) + ", raw_json"
    for record in records:
        try:
            existing = cursor.execute(
                f"""
                SELECT {select_fields}
                FROM athlete_health_daily
                WHERE athlete_id = ? AND health_date = ? AND source = ?
                """,
                (int(athlete_id), record.health_date, clean_source),
            ).fetchone()
            values = [getattr(record, field) for field in _UPDATE_FIELDS]
            if existing is None:
                columns = ", ".join(_UPDATE_FIELDS)
                placeholders = ", ".join("?" for _ in _UPDATE_FIELDS)
                cursor.execute(
                    f"""
                    INSERT INTO athlete_health_daily (
                        athlete_id, health_date, source, {columns}, raw_json
                    ) VALUES (?, ?, ?, {placeholders}, ?)
                    """,
                    (
                        int(athlete_id),
                        record.health_date,
                        clean_source,
                        *values,
                        record.raw_json,
                    ),
                )
                imported += 1
                continue

            existing_values = existing[:-1]
            merged_values = [
                incoming if incoming is not None else stored
                for stored, incoming in zip(existing_values, values)
            ]
            changed = any(
                incoming is not None and incoming != stored
                for stored, incoming in zip(existing_values, values)
            )
            if not changed:
                duplicates += 1
                continue
            assignments = ", ".join(f"{field} = ?" for field in _UPDATE_FIELDS)
            cursor.execute(
                f"""
                UPDATE athlete_health_daily
                SET {assignments}, raw_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE athlete_id = ? AND health_date = ? AND source = ?
                """,
                (
                    *merged_values,
                    _merged_raw(existing[-1], record.raw_json),
                    int(athlete_id),
                    record.health_date,
                    clean_source,
                ),
            )
            enriched += 1
        except Exception as error:  # keep a bad row from hiding the rest
            errors.append(f"{record.health_date}: {error}")
    connection.commit()
    connection.close()
    return RunalyzeHealthImportResult(
        imported=imported,
        enriched=enriched,
        duplicates=duplicates,
        errors=tuple(errors),
    )


def get_athlete_health_count(athlete_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor()
    create_athlete_health_daily_table(cursor)
    count = cursor.execute(
        "SELECT COUNT(*) FROM athlete_health_daily WHERE athlete_id = ?",
        (int(athlete_id),),
    ).fetchone()[0]
    connection.close()
    return int(count)

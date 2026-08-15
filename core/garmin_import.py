"""Garmin FIT activity discovery, parsing and athlete-safe persistence.

The importer deliberately keeps Garmin transport separate from coaching logic:

* FIT binaries remain the immutable source of truth in ``uploads/garmin``;
* the existing ``activities`` row receives only canonical summary fields;
* lap and device evidence is normalised into ``raw_json`` for current and
  future deterministic engines;
* a matching Runalyze activity is enriched rather than duplicated.

Garmin Connect OAuth is a later transport.  It can feed the same functions
once commercial API access is available.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path, PurePosixPath
import re
import sqlite3
from typing import Any, Iterable, Sequence
from zipfile import BadZipFile, ZipFile

from core.database import (
    _merge_duplicate_activity_children,
    get_connection,
    refresh_athlete_sport_mappings,
)


GARMIN_UPLOAD_ROOT = Path("uploads") / "garmin"
MAX_ARCHIVE_DEPTH = 4
MAX_DISCOVERED_FIT_FILES = 20_000
MAX_SINGLE_FIT_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 256 * 1024 * 1024


class GarminImportError(ValueError):
    """A user-facing FIT discovery or decoding failure."""


@dataclass(frozen=True)
class FitPayload:
    name: str
    data: bytes

    @property
    def file_hash(self) -> str:
        return sha256(self.data).hexdigest()


@dataclass(frozen=True)
class FitDiscovery:
    payloads: tuple[FitPayload, ...]
    issues: tuple[str, ...]
    repeated_files: int = 0


@dataclass(frozen=True)
class GarminFitActivity:
    file_name: str
    file_bytes: bytes
    file_hash: str
    garmin_activity_id: str | None
    source_activity_id: str
    activity_datetime: str
    activity_date: str
    sport: str
    sub_sport: str | None
    title: str
    distance_m: float | None
    moving_time_s: float | None
    elapsed_time_s: float | None
    elevation_up_m: float | None
    elevation_down_m: float | None
    avg_hr: float | None
    max_hr: float | None
    avg_power: float | None
    cadence: float | None
    calories: float | None
    temperature_c: float | None
    equipment_ids: str | None
    raw_fit: dict[str, Any]

    @property
    def is_running(self) -> bool:
        values = f"{self.sport} {self.sub_sport or ''}".lower()
        return self.sport.lower() == "running" or "run" in values


@dataclass(frozen=True)
class GarminParseResult:
    activities: tuple[GarminFitActivity, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class GarminImportResult:
    imported: int
    enriched: int
    duplicates: int
    skipped_non_running: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class ActivityMatch:
    activity_id: int
    source: str
    action: str
    duplicate_activity_id: int | None = None


def _safe_member_name(name: str) -> str:
    parts = [part for part in PurePosixPath(str(name).replace("\\", "/")).parts
             if part not in {"", ".", ".."}]
    return "/".join(parts) or "activity.fit"


def _garmin_activity_id(file_name: str) -> str | None:
    """Read Garmin Connect's stable activity ID from its export filename."""
    matches = re.findall(r"(?<!\d)(\d{9,})(?!\d)", str(file_name))
    return matches[-1] if matches else None


def discover_fit_payloads(
    uploads: Sequence[tuple[str, bytes]],
) -> FitDiscovery:
    """Find FIT files in direct uploads and nested Garmin export archives."""
    found: list[FitPayload] = []
    issues: list[str] = []
    seen_hashes: set[str] = set()
    repeated = 0

    def add_fit(name: str, data: bytes) -> None:
        nonlocal repeated
        if len(found) >= MAX_DISCOVERED_FIT_FILES:
            raise GarminImportError(
                f"The upload contains more than {MAX_DISCOVERED_FIT_FILES:,} "
                "FIT files. Import the Garmin archive in smaller batches."
            )
        if not data:
            issues.append(f"{name}: empty FIT file")
            return
        if len(data) > MAX_SINGLE_FIT_BYTES:
            issues.append(f"{name}: FIT file is larger than 64 MB")
            return
        digest = sha256(data).hexdigest()
        if digest in seen_hashes:
            repeated += 1
            return
        seen_hashes.add(digest)
        found.append(FitPayload(_safe_member_name(name), data))

    def inspect(name: str, data: bytes, depth: int) -> None:
        suffix = Path(name).suffix.lower()
        if suffix == ".fit":
            add_fit(name, data)
            return
        if suffix != ".zip":
            return
        if depth > MAX_ARCHIVE_DEPTH:
            issues.append(f"{name}: nested ZIP depth exceeds {MAX_ARCHIVE_DEPTH}")
            return
        try:
            with ZipFile(BytesIO(data)) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    member_name = _safe_member_name(member.filename)
                    member_suffix = Path(member_name).suffix.lower()
                    if member_suffix not in {".fit", ".zip"}:
                        continue
                    if member.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                        issues.append(
                            f"{name}/{member_name}: archive member is too large"
                        )
                        continue
                    child = archive.read(member)
                    inspect(f"{name}/{member_name}", child, depth + 1)
        except (BadZipFile, OSError, RuntimeError) as error:
            issues.append(f"{name}: ZIP could not be read ({error})")

    for upload_name, upload_data in uploads:
        try:
            inspect(_safe_member_name(upload_name), bytes(upload_data), 0)
        except GarminImportError as error:
            issues.append(str(error))
            break

    return FitDiscovery(tuple(found), tuple(issues), repeated)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    enum_name = getattr(value, "name", None)
    if enum_name is not None:
        return str(enum_name).lower()
    return str(value)


def _message_values(message: Any) -> dict[str, Any]:
    try:
        values = message.get_values()
    except Exception:
        values = {
            getattr(field, "name", "field"): getattr(field, "value", None)
            for field in message
        }
    return {
        str(key): _json_value(value)
        for key, value in values.items()
        if value is not None
    }


def _messages(fit_file: Any, name: str) -> list[dict[str, Any]]:
    return [_message_values(message) for message in fit_file.get_messages(name)]


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip().lower().replace(" ", "_")
    return result or None


def _timestamp(value: Any) -> str | None:
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _activity_date(timestamp: str) -> str:
    cleaned = timestamp.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(cleaned).date().isoformat()
    except ValueError:
        return timestamp[:10]


def _duration_text(seconds: float) -> str:
    total = max(int(round(seconds)), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _normalise_laps(laps: Iterable[dict[str, Any]]) -> tuple[list[dict], str | None]:
    normalised = []
    tokens = []
    for index, lap in enumerate(laps, start=1):
        distance_m = _number(lap.get("total_distance"))
        timer_s = _number(lap.get("total_timer_time"))
        elapsed_s = _number(lap.get("total_elapsed_time"))
        if not distance_m or distance_m <= 0 or not timer_s or timer_s <= 0:
            continue
        distance_km = distance_m / 1000.0
        item = {
            "index": index,
            "distance_km": round(distance_km, 5),
            "duration_s": round(timer_s, 3),
            "elapsed_time_s": round(elapsed_s, 3) if elapsed_s else None,
            "avg_hr": _number(lap.get("avg_heart_rate")),
            "max_hr": _number(lap.get("max_heart_rate")),
            "avg_cadence": _number(
                lap.get("avg_running_cadence", lap.get("avg_cadence"))
            ),
            "avg_power": _number(lap.get("avg_power")),
            "total_ascent_m": _number(lap.get("total_ascent")),
            "total_descent_m": _number(lap.get("total_descent")),
            "intensity": _text(lap.get("intensity")),
            "lap_trigger": _text(lap.get("lap_trigger")),
            "start_time": _timestamp(lap.get("start_time")),
        }
        normalised.append({key: value for key, value in item.items() if value is not None})
        tokens.append(f"F{distance_km:.5f}|{_duration_text(timer_s)}")
    return normalised, "-".join(tokens) or None


def _record_summary(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    record_list = list(records)
    fields = (
        "position_lat", "position_long", "heart_rate", "cadence", "power",
        "speed", "enhanced_speed", "altitude", "enhanced_altitude",
        "temperature",
    )
    coverage = {
        field: sum(1 for record in record_list if record.get(field) is not None)
        for field in fields
    }
    first = next((record.get("timestamp") for record in record_list
                  if record.get("timestamp") is not None), None)
    last = next((record.get("timestamp") for record in reversed(record_list)
                 if record.get("timestamp") is not None), None)
    return {
        "record_count": len(record_list),
        "first_timestamp": _timestamp(first),
        "last_timestamp": _timestamp(last),
        "field_coverage": coverage,
    }


def _title_for(sport: str, sub_sport: str | None) -> str:
    labels = {
        "trail": "Trail Running",
        "treadmill": "Treadmill Running",
        "track": "Track Running",
        "street": "Road Running",
        "virtual_activity": "Virtual Running",
    }
    if sport == "running":
        return labels.get(sub_sport or "", "Running")
    return (sub_sport or sport or "Garmin Activity").replace("_", " ").title()


def _source_id(
    timestamp: str,
    sport: str,
    serial_number: Any,
    distance_m: float | None,
    timer_s: float | None,
) -> str:
    identity = "|".join(
        (
            timestamp,
            sport,
            str(serial_number or "unknown"),
            f"{distance_m or 0:.1f}",
            f"{timer_s or 0:.1f}",
        )
    )
    return f"fit_{sha256(identity.encode('utf-8')).hexdigest()[:32]}"


def parse_fit_payload(payload: FitPayload) -> GarminFitActivity:
    """Decode one Garmin activity FIT into the canonical activity contract."""
    try:
        from fitparse import FitFile
    except ImportError as error:  # pragma: no cover - environment safeguard
        raise GarminImportError(
            "FIT support is not installed. Run pip install -r requirements.txt."
        ) from error

    try:
        fit_file = FitFile(BytesIO(payload.data), check_crc=True)
        fit_file.parse()
        file_ids = _messages(fit_file, "file_id")
        sessions = _messages(fit_file, "session")
        activities = _messages(fit_file, "activity")
        laps = _messages(fit_file, "lap")
        records = _messages(fit_file, "record")
        devices = _messages(fit_file, "device_info")
        events = _messages(fit_file, "event")
        workouts = _messages(fit_file, "workout")
        workout_steps = _messages(fit_file, "workout_step")
    except Exception as error:
        raise GarminImportError(f"FIT could not be decoded ({error})") from error

    file_id = file_ids[0] if file_ids else {}
    file_type = _text(file_id.get("type"))
    if file_type and file_type != "activity":
        raise GarminImportError(f"FIT type is {file_type}, not an activity")
    if not sessions:
        raise GarminImportError("FIT contains no activity session")

    session = sessions[0]
    sport = _text(session.get("sport")) or "unknown"
    sub_sport = _text(session.get("sub_sport"))
    timestamp = (
        _timestamp(session.get("start_time"))
        or _timestamp(file_id.get("time_created"))
        or _timestamp((activities[0] if activities else {}).get("timestamp"))
    )
    if timestamp is None:
        raise GarminImportError("FIT contains no usable start timestamp")

    distance_m = _number(session.get("total_distance"))
    moving_time_s = _number(session.get("total_timer_time"))
    elapsed_time_s = _number(session.get("total_elapsed_time"))
    serial_number = file_id.get("serial_number")
    if serial_number is None and devices:
        serial_number = devices[0].get("serial_number")
    garmin_activity_id = _garmin_activity_id(payload.name)

    normalised_laps, split_text = _normalise_laps(laps)
    equipment = {
        "serial_number": _json_value(serial_number),
        "manufacturer": file_id.get("manufacturer"),
        "product": file_id.get("product"),
        "devices": devices,
    }
    equipment_ids = json.dumps(equipment, sort_keys=True, default=str)
    raw_fit = {
        "format": "garmin_fit",
        "file_name": payload.name,
        "file_hash": payload.file_hash,
        "garmin_activity_id": garmin_activity_id,
        "file_id": file_id,
        "session": session,
        "activity": activities,
        "laps": normalised_laps,
        "record_summary": _record_summary(records),
        "devices": devices,
        "events": events,
        "workouts": workouts,
        "workout_steps": workout_steps,
    }
    if split_text:
        raw_fit["split_text"] = split_text

    return GarminFitActivity(
        file_name=payload.name,
        file_bytes=payload.data,
        file_hash=payload.file_hash,
        garmin_activity_id=garmin_activity_id,
        source_activity_id=(
            f"garmin_{garmin_activity_id}"
            if garmin_activity_id
            else _source_id(
                timestamp, sport, serial_number, distance_m, moving_time_s
            )
        ),
        activity_datetime=timestamp,
        activity_date=_activity_date(timestamp),
        sport=sport,
        sub_sport=sub_sport,
        title=_title_for(sport, sub_sport),
        distance_m=distance_m,
        moving_time_s=moving_time_s,
        elapsed_time_s=elapsed_time_s,
        elevation_up_m=_number(session.get("total_ascent")),
        elevation_down_m=_number(session.get("total_descent")),
        avg_hr=_number(session.get("avg_heart_rate")),
        max_hr=_number(session.get("max_heart_rate")),
        avg_power=_number(session.get("avg_power")),
        cadence=_number(
            session.get("avg_running_cadence", session.get("avg_cadence"))
        ),
        calories=_number(session.get("total_calories")),
        temperature_c=_number(session.get("avg_temperature")),
        equipment_ids=equipment_ids,
        raw_fit=raw_fit,
    )


def parse_fit_payloads(payloads: Sequence[FitPayload]) -> GarminParseResult:
    activities = []
    issues = []
    for payload in payloads:
        try:
            activities.append(parse_fit_payload(payload))
        except GarminImportError as error:
            issues.append(f"{payload.name}: {error}")
    return GarminParseResult(tuple(activities), tuple(issues))


def _parse_datetime(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return parsed


def _metres(value: Any) -> float | None:
    result = _number(value)
    if result is None or result <= 0:
        return None
    return result * 1000.0 if result <= 250.0 else result


def _raw_identity(
    raw_json_text: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    if not raw_json_text:
        return None, None, None, None
    try:
        raw = json.loads(raw_json_text)
    except (TypeError, json.JSONDecodeError):
        return None, None, None, None
    if not isinstance(raw, dict):
        return None, None, None, None
    runalyze_external_id = raw.get("externalId")
    fit = raw.get("garmin_fit")
    if not isinstance(fit, dict):
        return (
            None,
            None,
            None,
            str(runalyze_external_id) if runalyze_external_id is not None else None,
        )
    return (
        fit.get("file_hash"),
        fit.get("source_activity_id"),
        (
            str(fit.get("garmin_activity_id"))
            if fit.get("garmin_activity_id") is not None
            else None
        ),
        str(runalyze_external_id) if runalyze_external_id is not None else None,
    )


def _runalyze_environment(raw_json_text: str | None) -> dict[str, float]:
    """Return weather-adjusted environment values retained by Runalyze.

    A Garmin FIT session can contain device temperature and uncorrected
    barometric ascent. Those are useful evidence in ``garmin_fit`` but must
    not replace the weather and corrected elevation already chosen for an
    existing Runalyze activity.
    """
    if not raw_json_text:
        return {}
    try:
        raw = json.loads(raw_json_text)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    values = {}
    for column, key in (
        ("elevation_up_m", "elevationUp"),
        ("elevation_down_m", "elevationDown"),
        ("temperature_c", "temperature"),
    ):
        value = _number(raw.get(key))
        if value is not None:
            values[column] = value
    return values


def _restore_runalyze_environment(
    cursor: sqlite3.Cursor,
    activity_id: int,
) -> None:
    """Repair environmental summary fields after an earlier FIT enrichment."""
    cursor.execute(
        "SELECT source, raw_json FROM activities WHERE id = ?",
        (activity_id,),
    )
    row = cursor.fetchone()
    if row is None or row[0] != "runalyze_csv":
        return
    environment = _runalyze_environment(row[1])
    if not environment:
        return
    cursor.execute(
        """
        UPDATE activities
        SET elevation_up_m = COALESCE(?, elevation_up_m),
            elevation_down_m = COALESCE(?, elevation_down_m),
            temperature_c = COALESCE(?, temperature_c)
        WHERE id = ?
        """,
        (
            environment.get("elevation_up_m"),
            environment.get("elevation_down_m"),
            environment.get("temperature_c"),
            activity_id,
        ),
    )


def _candidate_date_bounds(activity_date: str) -> tuple[str, str]:
    try:
        value = dt.date.fromisoformat(activity_date)
    except ValueError:
        return activity_date, activity_date
    return (
        (value - dt.timedelta(days=1)).isoformat(),
        (value + dt.timedelta(days=1)).isoformat(),
    )


def _matching_activity(
    cursor: sqlite3.Cursor,
    athlete_id: int,
    activity: GarminFitActivity,
) -> ActivityMatch | None:
    first_date, last_date = _candidate_date_bounds(activity.activity_date)
    cursor.execute(
        """
        SELECT id, source, activity_hash, source_activity_id,
               activity_datetime, distance_m, moving_time_s, elapsed_time_s,
               raw_json
        FROM activities
        WHERE athlete_id = ? AND activity_date BETWEEN ? AND ?
        ORDER BY id
        """,
        (athlete_id, first_date, last_date),
    )
    target_time = _parse_datetime(activity.activity_datetime)
    target_distance = _metres(activity.distance_m)
    target_duration = activity.moving_time_s or activity.elapsed_time_s
    candidates = []
    external_match = None
    fit_duplicate = None
    for row in cursor.fetchall():
        (
            row_id, source, activity_hash, source_activity_id, activity_datetime,
            distance_value, moving_time, elapsed_time, raw_json_text,
        ) = row
        (
            stored_hash,
            stored_source_id,
            stored_garmin_id,
            runalyze_external_id,
        ) = _raw_identity(raw_json_text)
        if (
            activity.garmin_activity_id
            and activity.garmin_activity_id
            in {stored_garmin_id, runalyze_external_id}
        ):
            if source == "runalyze_csv":
                external_match = (int(row_id), str(source))
                if (
                    activity_hash == activity.file_hash
                    or stored_hash == activity.file_hash
                    or stored_source_id == activity.source_activity_id
                ):
                    fit_duplicate = (int(row_id), str(source))
            else:
                fit_duplicate = (int(row_id), str(source))
            continue
        if (
            activity_hash == activity.file_hash
            or stored_hash == activity.file_hash
            or (source == "garmin_fit" and source_activity_id == activity.source_activity_id)
            or stored_source_id == activity.source_activity_id
        ):
            fit_duplicate = (int(row_id), str(source))
            continue

        row_time = _parse_datetime(activity_datetime)
        if target_time is None or row_time is None:
            continue
        time_delta = abs((row_time - target_time).total_seconds())
        row_distance = _metres(distance_value)
        distance_close = False
        distance_delta = 0.0
        if target_distance is not None and row_distance is not None:
            distance_delta = abs(row_distance - target_distance)
            distance_close = distance_delta <= max(250.0, target_distance * 0.03)

        row_duration = _number(moving_time) or _number(elapsed_time)
        duration_close = False
        duration_delta = 0.0
        if target_duration is not None and row_duration is not None:
            duration_delta = abs(row_duration - target_duration)
            duration_close = duration_delta <= 180

        normal_time_match = time_delta <= 180
        timezone_time_match = (
            time_delta <= 14 * 3600
            and min(
                abs(time_delta - hours * 3600)
                for hours in range(1, 15)
            ) <= 120
            and target_distance is not None
            and row_distance is not None
            and distance_delta <= max(50.0, target_distance * 0.005)
            and target_duration is not None
            and row_duration is not None
            and duration_delta <= 10
        )
        if not (normal_time_match or timezone_time_match):
            continue
        if not (distance_close or duration_close):
            continue
        score = time_delta + distance_delta / 10.0 + duration_delta
        candidates.append((score, int(row_id), str(source)))

    if external_match is not None:
        if fit_duplicate is not None and fit_duplicate[0] == external_match[0]:
            return ActivityMatch(
                external_match[0], external_match[1], "duplicate"
            )
        duplicate_id = (
            fit_duplicate[0]
            if fit_duplicate is not None
            and fit_duplicate[0] != external_match[0]
            else None
        )
        return ActivityMatch(
            external_match[0], external_match[1], "enrich", duplicate_id
        )
    if fit_duplicate is not None:
        return ActivityMatch(fit_duplicate[0], fit_duplicate[1], "duplicate")
    if not candidates:
        return None
    _, row_id, source = min(candidates)
    return ActivityMatch(row_id, source, "enrich")


def _merged_raw_json(
    existing_raw: str | None,
    activity: GarminFitActivity,
) -> str:
    try:
        raw = json.loads(existing_raw) if existing_raw else {}
    except (TypeError, json.JSONDecodeError):
        raw = {"preserved_raw_text": existing_raw}
    if not isinstance(raw, dict):
        raw = {"preserved_raw_value": raw}
    split_text = activity.raw_fit.get("split_text")
    if split_text and raw.get("splits") and "runalyze_splits" not in raw:
        raw["runalyze_splits"] = raw["splits"]
    raw["garmin_fit"] = {
        **activity.raw_fit,
        "source_activity_id": activity.source_activity_id,
    }
    if split_text:
        raw["fit_splits"] = activity.raw_fit.get("laps", [])
        raw["splits"] = split_text
    return json.dumps(raw, sort_keys=True, default=str)


def _store_original(activity: GarminFitActivity, athlete_id: int) -> str:
    athlete_root = GARMIN_UPLOAD_ROOT / str(athlete_id)
    athlete_root.mkdir(parents=True, exist_ok=True)
    stamp = "".join(
        character
        for character in activity.activity_datetime.replace("+00:00", "Z")
        if character.isalnum()
    )[:16] or "activity"
    path = athlete_root / f"{stamp}_{activity.file_hash[:16]}.fit"
    if not path.exists():
        path.write_bytes(activity.file_bytes)
    return path.as_posix()


def import_garmin_activities(
    activities: Sequence[GarminFitActivity],
    *,
    athlete_id: int,
    athlete_name: str,
    running_only: bool = True,
) -> GarminImportResult:
    """Persist parsed FIT activities, enriching same-run Runalyze rows."""
    imported = 0
    enriched = 0
    duplicates = 0
    skipped = 0
    errors = []
    connection = get_connection()
    cursor = connection.cursor()

    try:
        for activity in activities:
            if running_only and not activity.is_running:
                skipped += 1
                continue
            try:
                match = _matching_activity(cursor, athlete_id, activity)
                if match is not None and match.action == "duplicate":
                    _restore_runalyze_environment(cursor, match.activity_id)
                    duplicates += 1
                    continue

                original_file = _store_original(activity, athlete_id)
                if match is not None:
                    row_id = match.activity_id
                    cursor.execute(
                        "SELECT raw_json FROM activities WHERE id = ?",
                        (row_id,),
                    )
                    existing_raw = cursor.fetchone()[0]
                    runalyze_environment = (
                        _runalyze_environment(existing_raw)
                        if match.source == "runalyze_csv"
                        else {}
                    )
                    cursor.execute(
                        """
                        UPDATE activities
                        SET distance_m = COALESCE(?, distance_m),
                            moving_time_s = COALESCE(?, moving_time_s),
                            elapsed_time_s = COALESCE(?, elapsed_time_s),
                            elevation_up_m = COALESCE(?, elevation_up_m),
                            elevation_down_m = COALESCE(?, elevation_down_m),
                            avg_hr = COALESCE(?, avg_hr),
                            max_hr = COALESCE(?, max_hr),
                            avg_power = COALESCE(?, avg_power),
                            cadence = COALESCE(?, cadence),
                            calories = COALESCE(?, calories),
                            temperature_c = COALESCE(?, temperature_c),
                            equipment_ids = COALESCE(?, equipment_ids),
                            original_file = ?,
                            raw_json = ?
                        WHERE id = ? AND athlete_id = ?
                        """,
                        (
                            activity.distance_m, activity.moving_time_s,
                            activity.elapsed_time_s,
                            runalyze_environment.get(
                                "elevation_up_m", activity.elevation_up_m
                            ),
                            runalyze_environment.get(
                                "elevation_down_m", activity.elevation_down_m
                            ),
                            activity.avg_hr,
                            activity.max_hr, activity.avg_power,
                            activity.cadence, activity.calories,
                            runalyze_environment.get(
                                "temperature_c", activity.temperature_c
                            ),
                            activity.equipment_ids,
                            original_file,
                            _merged_raw_json(existing_raw, activity),
                            row_id, athlete_id,
                        ),
                    )
                    if match.duplicate_activity_id is not None:
                        _merge_duplicate_activity_children(
                            cursor,
                            row_id,
                            match.duplicate_activity_id,
                        )
                        cursor.execute(
                            "DELETE FROM activities WHERE id = ? AND athlete_id = ?",
                            (match.duplicate_activity_id, athlete_id),
                        )
                    enriched += 1
                    continue

                cursor.execute(
                    """
                    INSERT INTO activities (
                        athlete_name, athlete_id, source, source_activity_id,
                        activity_hash, activity_datetime, activity_date, title,
                        sport_id, type_id, distance_m, moving_time_s,
                        elapsed_time_s, elevation_up_m, elevation_down_m, avg_hr,
                        max_hr, avg_power, cadence, calories, temperature_c,
                        humidity, wind_speed, route_name, equipment_ids,
                        original_file, raw_json
                    ) VALUES (
                        ?, ?, 'garmin_fit', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?
                    )
                    """,
                    (
                        athlete_name, athlete_id, activity.source_activity_id,
                        activity.file_hash, activity.activity_datetime,
                        activity.activity_date, activity.title, activity.sport,
                        activity.sub_sport, activity.distance_m,
                        activity.moving_time_s, activity.elapsed_time_s,
                        activity.elevation_up_m, activity.elevation_down_m,
                        activity.avg_hr, activity.max_hr, activity.avg_power,
                        activity.cadence, activity.calories,
                        activity.temperature_c, activity.equipment_ids,
                        original_file, _merged_raw_json(None, activity),
                    ),
                )
                imported += 1
            except sqlite3.IntegrityError:
                duplicates += 1
            except Exception as error:
                errors.append(f"{activity.file_name}: {error}")
        connection.commit()
    finally:
        connection.close()

    if imported or enriched:
        refresh_athlete_sport_mappings()

    return GarminImportResult(
        imported=imported,
        enriched=enriched,
        duplicates=duplicates,
        skipped_non_running=skipped,
        errors=tuple(errors),
    )

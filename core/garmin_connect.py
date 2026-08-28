"""Read-only experimental transport from Garmin Connect.

This module deliberately stops at transport and normalisation. Original FIT
archives are handed to :mod:`core.garmin_import`, while nightly recovery data
is handed to the source-labelled health importer. The unofficial connector is
appropriate for a private prototype, not the eventual commercial OAuth path.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from core.garmin_import import known_garmin_activity_ids
from core.runalyze_health import RunalyzeHealthRecord


GARMIN_TOKEN_ROOT = Path(os.getenv("PP_GARMIN_TOKEN_ROOT", ".garmin_tokens"))
GARMIN_HEALTH_HISTORY_DAYS = 35
MAX_ACTIVITY_LOOKBACK_DAYS = 366
MAX_ACTIVITY_DOWNLOADS = 250


class GarminConnectPrototypeError(RuntimeError):
    """A safe user-facing failure from the experimental connector."""


@dataclass(frozen=True)
class GarminLoginResult:
    client: Any
    needs_mfa: bool
    account_name: str | None


@dataclass(frozen=True)
class GarminActivityPreview:
    activity_id: str
    activity_date: str
    start_time: str | None
    title: str
    activity_type: str
    distance_m: float | None
    duration_s: float | None
    already_imported: bool


@dataclass(frozen=True)
class GarminHealthFetchResult:
    records: tuple[RunalyzeHealthRecord, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class GarminConnectPreview:
    account_name: str
    start_date: str
    end_date: str
    activities: tuple[GarminActivityPreview, ...]
    health_records: tuple[RunalyzeHealthRecord, ...]
    issues: tuple[str, ...]

    @property
    def new_activities(self) -> tuple[GarminActivityPreview, ...]:
        return tuple(item for item in self.activities if not item.already_imported)


@dataclass(frozen=True)
class GarminDownloadResult:
    uploads: tuple[tuple[str, bytes], ...]
    issues: tuple[str, ...]


def _library():
    try:
        from garminconnect import Garmin
    except ImportError as error:
        raise GarminConnectPrototypeError(
            "Garmin Connect support is not installed. Run "
            "python -m pip install -r requirements.txt, then restart the app."
        ) from error
    return Garmin


def dependency_available() -> bool:
    try:
        _library()
    except GarminConnectPrototypeError:
        return False
    return True


def token_store_path(athlete_id: int) -> Path:
    owner = int(athlete_id)
    if owner <= 0:
        raise ValueError("Athlete ID must be positive.")
    return GARMIN_TOKEN_ROOT / f"athlete_{owner}"


def _prepare_token_store(athlete_id: int) -> Path:
    path = token_store_path(athlete_id)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    with contextlib.suppress(OSError):
        path.chmod(0o700)
    return path


def has_saved_connection(athlete_id: int) -> bool:
    return (token_store_path(athlete_id) / "garmin_tokens.json").is_file()


def _account_name(client: Any) -> str:
    try:
        value = client.get_full_name()
    except Exception:
        value = None
    return str(value or getattr(client, "display_name", None) or "Garmin account")


def begin_login(email: str, password: str, *, athlete_id: int) -> GarminLoginResult:
    """Authenticate once without persisting the password."""
    clean_email = str(email or "").strip()
    if not clean_email or not password:
        raise GarminConnectPrototypeError("Garmin email and password are required.")
    Garmin = _library()
    store = _prepare_token_store(athlete_id)
    try:
        client = Garmin(
            clean_email,
            str(password),
            return_on_mfa=True,
            retry_attempts=1,
        )
        status, _ = client.login(str(store))
        if status == "needs_mfa":
            # v0.3.11 does not attach the token store on its MFA early return.
            client.client._tokenstore_path = str(store)
            client.password = None
            return GarminLoginResult(client, True, None)
        return GarminLoginResult(client, False, _account_name(client))
    except Exception as error:
        raise GarminConnectPrototypeError(str(error)) from error


def complete_mfa(client: Any, code: str, *, athlete_id: int) -> GarminLoginResult:
    clean_code = str(code or "").strip().replace(" ", "")
    if not 4 <= len(clean_code) <= 10 or not clean_code.isalnum():
        raise GarminConnectPrototypeError("Enter the Garmin verification code.")
    store = _prepare_token_store(athlete_id)
    try:
        client.client._tokenstore_path = str(store)
        client.resume_login(None, clean_code)
        client.client.dump(str(store))
        client.password = None
        token_file = store / "garmin_tokens.json"
        with contextlib.suppress(OSError):
            token_file.chmod(0o600)
        return GarminLoginResult(client, False, _account_name(client))
    except Exception as error:
        raise GarminConnectPrototypeError(str(error)) from error


def connect_with_saved_tokens(*, athlete_id: int) -> GarminLoginResult:
    store = token_store_path(athlete_id)
    if not has_saved_connection(athlete_id):
        raise GarminConnectPrototypeError("No saved Garmin connection was found.")
    Garmin = _library()
    try:
        client = Garmin(retry_attempts=1)
        client.login(str(store))
        return GarminLoginResult(client, False, _account_name(client))
    except Exception as error:
        raise GarminConnectPrototypeError(str(error)) from error


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    try:
        return dt.date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _activity_type(row: Mapping[str, Any]) -> str:
    nested = row.get("activityType")
    if isinstance(nested, Mapping):
        value = nested.get("typeKey") or nested.get("typeId")
    else:
        value = row.get("activityTypeDTO") or nested
    return str(value or "running").replace("_", " ").title()


def _activity_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("activities", "activityList", "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, Mapping)]
    return []


def _activity_preview(
    row: Mapping[str, Any], known_ids: set[str]
) -> GarminActivityPreview | None:
    activity_id = row.get("activityId") or row.get("activityID") or row.get("id")
    start = row.get("startTimeLocal") or row.get("startTimeGMT") or row.get("startTime")
    activity_date = _iso_date(start or row.get("calendarDate"))
    if activity_id is None or activity_date is None:
        return None
    clean_id = str(activity_id)
    return GarminActivityPreview(
        activity_id=clean_id,
        activity_date=activity_date,
        start_time=str(start) if start else None,
        title=str(row.get("activityName") or row.get("name") or _activity_type(row)),
        activity_type=_activity_type(row),
        distance_m=_number(row.get("distance")),
        duration_s=_number(row.get("duration") or row.get("elapsedDuration")),
        already_imported=clean_id in known_ids,
    )


def _walk_dicts(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_dicts(child)


def _hrv_by_date(payload: Any) -> dict[str, Mapping[str, Any]]:
    result = {}
    for row in _walk_dicts(payload):
        health_date = _iso_date(row.get("calendarDate"))
        if health_date and row.get("lastNightAvg") is not None:
            result[health_date] = row
    return result


def _rhr_by_date(payload: Any) -> dict[str, Mapping[str, Any]]:
    result = {}
    for row in _walk_dicts(payload):
        health_date = _iso_date(row.get("calendarDate"))
        value = row.get("value")
        if health_date and value is not None:
            result[health_date] = row
    return result


def _milliseconds_to_iso(value: Any) -> str | None:
    number = _number(value)
    if number is None:
        return None
    try:
        return dt.datetime.fromtimestamp(
            number / 1000.0, tz=dt.timezone.utc
        ).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _nested_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _minutes(seconds: Any) -> float | None:
    value = _number(seconds)
    return round(value / 60.0, 2) if value is not None else None


def _health_record(
    health_date: str,
    *,
    hrv: Mapping[str, Any] | None,
    resting: Mapping[str, Any] | None,
    sleep_payload: Any,
) -> RunalyzeHealthRecord | None:
    sleep = (
        sleep_payload.get("dailySleepDTO")
        if isinstance(sleep_payload, Mapping)
        and isinstance(sleep_payload.get("dailySleepDTO"), Mapping)
        else {}
    )
    hrv_value = _number((hrv or {}).get("lastNightAvg"))
    resting_hr = _number((resting or {}).get("value"))
    sleep_seconds = sleep.get("sleepTimeSeconds") or sleep.get("totalSleepTimeInSeconds")
    sleep_minutes = _minutes(sleep_seconds)
    sleep_score = _number(_nested_value(sleep, "sleepScores", "overall", "value"))
    if hrv_value is None and resting_hr is None and sleep_minutes is None:
        return None
    raw = {
        "garmin_connect_health": {
            "hrvSummary": dict(hrv or {}),
            "restingHeartRate": dict(resting or {}),
            "dailySleepDTO": dict(sleep),
        }
    }
    return RunalyzeHealthRecord(
        health_date=health_date,
        file_kind="garmin_connect_health",
        hrv_value=hrv_value,
        hrv_metric_code="RMSSD" if hrv_value is not None else None,
        hrv_measurement_type="nightly_average" if hrv_value is not None else None,
        hrv_source_code="garmin_connect" if hrv_value is not None else None,
        hrv_source_id=health_date if hrv_value is not None else None,
        resting_hr=resting_hr,
        resting_hr_source_id=health_date if resting_hr is not None else None,
        sleep_source_id=health_date if sleep_minutes is not None else None,
        sleep_start_time=_milliseconds_to_iso(
            sleep.get("sleepStartTimestampGMT")
            or sleep.get("sleepStartTimestampLocal")
        ),
        sleep_end_time=_milliseconds_to_iso(
            sleep.get("sleepEndTimestampGMT")
            or sleep.get("sleepEndTimestampLocal")
        ),
        sleep_duration_min=sleep_minutes,
        sleep_rem_min=_minutes(sleep.get("remSleepSeconds")),
        sleep_awake_min=_minutes(sleep.get("awakeSleepSeconds")),
        sleep_deep_min=_minutes(sleep.get("deepSleepSeconds")),
        sleep_light_min=_minutes(sleep.get("lightSleepSeconds")),
        sleep_quality_100=sleep_score,
        raw_json=json.dumps(raw, default=str, sort_keys=True),
    )


def _dates(start_date: dt.date, end_date: dt.date) -> Iterable[dt.date]:
    current = start_date
    while current <= end_date:
        yield current
        current += dt.timedelta(days=1)


def fetch_garmin_health_records(
    client: Any,
    *,
    start_date: dt.date,
    end_date: dt.date,
) -> GarminHealthFetchResult:
    """Fetch a bounded personal baseline using read-only calls."""
    if end_date < start_date:
        raise ValueError("Health start date cannot be after end date.")
    if (end_date - start_date).days + 1 > GARMIN_HEALTH_HISTORY_DAYS:
        start_date = end_date - dt.timedelta(days=GARMIN_HEALTH_HISTORY_DAYS - 1)
    start_text, end_text = start_date.isoformat(), end_date.isoformat()
    issues = []
    try:
        hrv_rows = _hrv_by_date(client.get_hrv_data_range(start_text, end_text))
    except Exception as error:
        hrv_rows = {}
        issues.append(f"HRV could not be read: {error}")
    try:
        resting_rows = _rhr_by_date(client.get_rhr_daily(start_text, end_text))
    except Exception as error:
        resting_rows = {}
        issues.append(f"Resting heart rate could not be read: {error}")

    records = []
    sleep_failures = 0
    for day in _dates(start_date, end_date):
        day_text = day.isoformat()
        try:
            sleep_payload = client.get_sleep_data(day_text)
        except Exception:
            sleep_payload = {}
            sleep_failures += 1
        record = _health_record(
            day_text,
            hrv=hrv_rows.get(day_text),
            resting=resting_rows.get(day_text),
            sleep_payload=sleep_payload,
        )
        if record is not None:
            records.append(record)
    if sleep_failures:
        issues.append(
            f"Sleep was unavailable for {sleep_failures} of "
            f"{(end_date - start_date).days + 1} requested day(s)."
        )
    return GarminHealthFetchResult(tuple(records), tuple(issues))


def fetch_garmin_preview(
    client: Any,
    *,
    athlete_id: int,
    start_date: dt.date,
    end_date: dt.date,
) -> GarminConnectPreview:
    if end_date < start_date:
        raise ValueError("Activity start date cannot be after end date.")
    if (end_date - start_date).days > MAX_ACTIVITY_LOOKBACK_DAYS:
        raise ValueError("The prototype preview is limited to one year.")
    try:
        payload = client.get_activities_by_date(
            start_date.isoformat(),
            end_date.isoformat(),
            activitytype="running",
            sortorder="desc",
        )
    except Exception as error:
        raise GarminConnectPrototypeError(
            f"Garmin activities could not be previewed: {error}"
        ) from error
    known = known_garmin_activity_ids(int(athlete_id))
    activities = []
    issues = []
    for row in _activity_rows(payload):
        item = _activity_preview(row, known)
        if item is None:
            issues.append("One Garmin activity had no usable ID or date.")
        else:
            activities.append(item)
    health_start = end_date - dt.timedelta(days=GARMIN_HEALTH_HISTORY_DAYS - 1)
    health = fetch_garmin_health_records(
        client,
        start_date=health_start,
        end_date=end_date,
    )
    activities.sort(
        key=lambda item: (item.activity_date, item.start_time or ""),
        reverse=True,
    )
    return GarminConnectPreview(
        account_name=_account_name(client),
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        activities=tuple(activities),
        health_records=health.records,
        issues=tuple((*issues, *health.issues)),
    )


def download_original_activities(
    client: Any,
    activities: Sequence[GarminActivityPreview],
) -> GarminDownloadResult:
    ready = [item for item in activities if not item.already_imported]
    if len(ready) > MAX_ACTIVITY_DOWNLOADS:
        raise GarminConnectPrototypeError(
            f"Import no more than {MAX_ACTIVITY_DOWNLOADS} new activities at once."
        )
    uploads = []
    issues = []
    for activity in ready:
        try:
            data = client.download_activity(
                activity.activity_id,
                dl_fmt=client.ActivityDownloadFormat.ORIGINAL,
            )
            if not isinstance(data, (bytes, bytearray)) or not data:
                raise ValueError("Garmin returned no original activity bytes")
            uploads.append((f"garmin_{activity.activity_id}.zip", bytes(data)))
        except Exception as error:
            issues.append(f"{activity.activity_date} · {activity.title}: {error}")
    return GarminDownloadResult(tuple(uploads), tuple(issues))

from __future__ import annotations

import datetime
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import core.database as database
import core.garmin_connect as garmin_connect
from core.garmin_connect import (
    GarminActivityPreview,
    begin_login,
    download_original_activities,
    fetch_garmin_health_records,
    fetch_garmin_preview,
    has_saved_connection,
    token_store_path,
)
from core.recovery_coach import build_recovery_health_signal
from core.runalyze_health import (
    GARMIN_CONNECT_HEALTH_SOURCE,
    RUNALYZE_HEALTH_SOURCE,
    RunalyzeHealthRecord,
    get_athlete_health_count,
    import_health_records,
)


ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.date(2026, 8, 27)


def _database(tmp_path, monkeypatch):
    path = tmp_path / "garmin-connect.db"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    database.initialise_database()
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO athletes (id, first_name, last_name) VALUES (?, ?, ?)",
            ((1, "Richard", "Burke"), (4, "Paul", "Farrell")),
        )
    return path


def test_saved_tokens_are_local_and_scoped_to_exactly_one_athlete(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(garmin_connect, "GARMIN_TOKEN_ROOT", tmp_path / "tokens")

    richard = token_store_path(1)
    paul = token_store_path(4)
    paul.mkdir(parents=True)
    (paul / "garmin_tokens.json").write_text("{}", encoding="utf-8")

    assert richard != paul
    assert richard.name == "athlete_1"
    assert has_saved_connection(1) is False
    assert has_saved_connection(4) is True


def test_initial_login_supports_mfa_without_persisting_password(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(garmin_connect, "GARMIN_TOKEN_ROOT", tmp_path / "tokens")

    class FakeGarmin:
        def __init__(self, email, password, **kwargs):
            self.email = email
            self.password = password
            self.kwargs = kwargs
            self.client = SimpleNamespace(_tokenstore_path=None)

        def login(self, tokenstore):
            self.tokenstore = tokenstore
            return "needs_mfa", None

    monkeypatch.setattr(garmin_connect, "_library", lambda: FakeGarmin)

    result = begin_login("runner@example.com", "secret", athlete_id=4)

    assert result.needs_mfa is True
    assert result.account_name is None
    assert result.client.kwargs["return_on_mfa"] is True
    assert result.client.client._tokenstore_path.endswith("athlete_4")
    assert result.client.password is None
    assert not (token_store_path(4) / "garmin_tokens.json").exists()


def test_health_transport_maps_nightly_hrv_resting_hr_and_sleep():
    class Client:
        def get_hrv_data_range(self, _start, _end):
            return {"hrvSummaries": [{"calendarDate": "2026-08-27", "lastNightAvg": 67}]}

        def get_rhr_daily(self, _start, _end):
            return {"allMetrics": [{"calendarDate": "2026-08-27", "value": 51}]}

        def get_sleep_data(self, day):
            if day != "2026-08-27":
                return {}
            return {
                "dailySleepDTO": {
                    "sleepTimeSeconds": 28_800,
                    "deepSleepSeconds": 5_400,
                    "lightSleepSeconds": 16_200,
                    "remSleepSeconds": 7_200,
                    "sleepScores": {"overall": {"value": 84}},
                }
            }

    fetched = fetch_garmin_health_records(
        Client(), start_date=TODAY, end_date=TODAY
    )

    assert fetched.issues == ()
    assert len(fetched.records) == 1
    record = fetched.records[0]
    assert record.hrv_value == 67
    assert record.hrv_metric_code == "RMSSD"
    assert record.resting_hr == 51
    assert record.sleep_duration_min == 480
    assert record.sleep_quality_100 == 84


def test_health_transport_stops_repeating_a_rejected_sleep_request():
    calls = []

    class Client:
        def get_hrv_data_range(self, _start, _end):
            return {
                "hrvSummaries": [
                    {"calendarDate": "2026-08-27", "lastNightAvg": 67}
                ]
            }

        def get_rhr_daily(self, _start, _end):
            return {}

        def get_sleep_data(self, day):
            calls.append(day)
            raise RuntimeError("Display name is not set")

    fetched = fetch_garmin_health_records(
        Client(),
        start_date=TODAY - datetime.timedelta(days=9),
        end_date=TODAY,
    )

    assert len(calls) == garmin_connect.MAX_CONSECUTIVE_SLEEP_FAILURES
    assert fetched.records[0].health_date == TODAY.isoformat()
    assert "Sleep was unavailable for 10 of 10 requested day(s)." in fetched.issues


def test_preview_marks_only_the_selected_athletes_existing_garmin_ids(
    tmp_path, monkeypatch
):
    path = _database(tmp_path, monkeypatch)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO activities (
                athlete_name, athlete_id, source, source_activity_id,
                activity_date, raw_json
            ) VALUES ('Paul Farrell', 4, 'runalyze_csv', 'paul-run', ?, ?)
            """,
            ("2026-08-27", json.dumps({"externalId": 12345})),
        )

    class Client:
        display_name = "Paul Garmin"

        def get_full_name(self):
            return self.display_name

        def get_activities_by_date(self, *_args, **_kwargs):
            return [
                {
                    "activityId": 12345,
                    "startTimeLocal": "2026-08-27 09:00:00",
                    "activityName": "Fast 5K",
                    "distance": 5000,
                    "duration": 1156,
                    "activityType": {"typeKey": "running"},
                }
            ]

        def get_hrv_data_range(self, *_args):
            return {}

        def get_rhr_daily(self, *_args):
            return {}

        def get_sleep_data(self, _day):
            return {}

    paul = fetch_garmin_preview(
        Client(), athlete_id=4, start_date=TODAY, end_date=TODAY
    )
    richard = fetch_garmin_preview(
        Client(), athlete_id=1, start_date=TODAY, end_date=TODAY
    )

    assert paul.activities[0].already_imported is True
    assert richard.activities[0].already_imported is False
    assert paul.new_activities == ()
    assert richard.new_activities[0].activity_id == "12345"


def test_original_download_ignores_already_imported_activities():
    calls = []

    class Client:
        ActivityDownloadFormat = SimpleNamespace(ORIGINAL="original")

        def download_activity(self, activity_id, *, dl_fmt):
            calls.append((activity_id, dl_fmt))
            return b"original archive"

    existing = GarminActivityPreview(
        "1", "2026-08-26", None, "Existing", "Running", 5000, 1200, True
    )
    new = GarminActivityPreview(
        "2", "2026-08-27", None, "New", "Running", 5000, 1190, False
    )

    result = download_original_activities(Client(), (existing, new))

    assert calls == [("2", "original")]
    assert result.uploads == (("garmin_2.zip", b"original archive"),)


def test_direct_health_import_is_idempotent_and_athlete_scoped(
    tmp_path, monkeypatch
):
    _database(tmp_path, monkeypatch)
    record = RunalyzeHealthRecord(
        health_date=TODAY.isoformat(),
        file_kind="garmin_connect_health",
        hrv_value=67,
        hrv_metric_code="RMSSD",
        resting_hr=51,
        sleep_duration_min=480,
    )

    first = import_health_records(
        (record,), athlete_id=4, source=GARMIN_CONNECT_HEALTH_SOURCE
    )
    repeated = import_health_records(
        (record,), athlete_id=4, source=GARMIN_CONNECT_HEALTH_SOURCE
    )

    assert first.imported == 1
    assert repeated.duplicates == 1
    assert get_athlete_health_count(4) == 1
    assert get_athlete_health_count(1) == 0


def test_recovery_baseline_counts_one_night_once_across_two_connectors(
    tmp_path, monkeypatch
):
    _database(tmp_path, monkeypatch)
    for offset in range(35):
        day = TODAY - datetime.timedelta(days=offset)
        runalyze = RunalyzeHealthRecord(
            health_date=day.isoformat(),
            file_kind="combined_health",
            hrv_value=65,
            hrv_metric_code="RMSSD",
            hrv_measurement_type="nightly_average",
            hrv_source_code="garmin_connect",
            resting_hr=52,
            sleep_duration_min=470,
        )
        direct = RunalyzeHealthRecord(
            health_date=day.isoformat(),
            file_kind="garmin_connect_health",
            hrv_value=65,
            hrv_metric_code="RMSSD",
            hrv_measurement_type="nightly_average",
            hrv_source_code="garmin_connect",
            resting_hr=52,
            sleep_duration_min=470,
        )
        import_health_records(
            (runalyze,), athlete_id=4, source=RUNALYZE_HEALTH_SOURCE
        )
        import_health_records(
            (direct,), athlete_id=4, source=GARMIN_CONNECT_HEALTH_SOURCE
        )

    signal = build_recovery_health_signal(4, today=TODAY)

    assert signal.hrv_recent_count == 7
    assert signal.hrv_baseline_count == 28
    assert signal.source == "Garmin Connect Health"
    assert signal.confidence == "Strong"


def test_ui_and_dependency_contracts_keep_the_prototype_explicit_and_private():
    source = (ROOT / "ui" / "import_page.py").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "Garmin Connect (Experimental)" in source
    assert "Connect read-only" in source
    assert "I confirm Garmin account" in source
    assert 'st.text_input("Garmin password", type="password")' in source
    assert "garminconnect==0.3.11" in requirements
    assert ".garmin_tokens/" in gitignore

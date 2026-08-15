from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from zipfile import ZipFile

import core.database as database
import core.garmin_import as garmin_import
from core.garmin_import import (
    FitPayload,
    GarminFitActivity,
    discover_fit_payloads,
    import_garmin_activities,
    parse_fit_payload,
)


ROOT = Path(__file__).resolve().parent.parent


def _database(tmp_path, monkeypatch):
    path = tmp_path / "performance_passport.db"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    monkeypatch.setattr(garmin_import, "GARMIN_UPLOAD_ROOT", tmp_path / "uploads")
    database.initialise_database()
    with sqlite3.connect(path) as connection:
        athlete_id = connection.execute(
            """
            INSERT INTO athletes (first_name, last_name, date_of_birth, sex)
            VALUES ('Paul', 'Tester', '1980-01-01', 'Male')
            """
        ).lastrowid
    return path, athlete_id


def _activity(
    *, sport="running", file_hash="fit-hash", source_id="garmin_23865797605"
):
    return GarminFitActivity(
        file_name="activity.fit",
        file_bytes=b"FIT binary source",
        file_hash=file_hash,
        garmin_activity_id="23865797605",
        source_activity_id=source_id,
        activity_datetime="2026-08-15T09:00:00",
        activity_date="2026-08-15",
        sport=sport,
        sub_sport="street" if sport == "running" else "road",
        title="Road Running" if sport == "running" else "Road Cycling",
        distance_m=10_000.0,
        moving_time_s=2_400.0,
        elapsed_time_s=2_425.0,
        elevation_up_m=52.0,
        elevation_down_m=50.0,
        avg_hr=151.0,
        max_hr=166.0,
        avg_power=300.0,
        cadence=188.0,
        calories=700.0,
        temperature_c=18.0,
        equipment_ids='{"serial_number": "watch-1"}',
        raw_fit={
            "file_hash": file_hash,
            "split_text": "F1.00000|4:00-F1.00000|3:58",
            "laps": [{"index": 1, "distance_km": 1.0, "duration_s": 240}],
        },
    )


def test_discovers_direct_and_nested_garmin_fit_files_once():
    inner = BytesIO()
    with ZipFile(inner, "w") as archive:
        archive.writestr("activity.fit", b"second-fit")

    outer = BytesIO()
    with ZipFile(outer, "w") as archive:
        archive.writestr("DI_CONNECT/one.fit", b"first-fit")
        archive.writestr("DI_CONNECT/repeat.fit", b"first-fit")
        archive.writestr("DI_CONNECT/uploaded.zip", inner.getvalue())
        archive.writestr("DI_CONNECT/readme.txt", "ignored")

    result = discover_fit_payloads((("garmin-export.zip", outer.getvalue()),))

    assert [payload.data for payload in result.payloads] == [
        b"first-fit",
        b"second-fit",
    ]
    assert result.repeated_files == 1
    assert result.issues == ()


def test_fit_parser_maps_session_laps_and_record_coverage(monkeypatch):
    messages = {
        "file_id": [{
            "type": "activity", "time_created": "2026-08-15T09:00:00",
            "serial_number": 1234, "manufacturer": "garmin", "product": 999,
        }],
        "session": [{
            "start_time": "2026-08-15T09:00:00", "sport": "running",
            "sub_sport": "trail", "total_distance": 10_000.0,
            "total_timer_time": 2_500.0, "total_elapsed_time": 2_540.0,
            "total_ascent": 120.0, "avg_heart_rate": 149,
            "max_heart_rate": 165, "avg_running_cadence": 186,
        }],
        "activity": [{"timestamp": "2026-08-15T09:42:20"}],
        "lap": [{
            "total_distance": 1_000.0, "total_timer_time": 250.0,
            "total_elapsed_time": 252.0, "avg_heart_rate": 145,
            "intensity": "active",
        }],
        "record": [
            {"timestamp": "2026-08-15T09:00:00", "heart_rate": 120},
            {"timestamp": "2026-08-15T09:00:01", "heart_rate": 121,
             "position_lat": 1, "position_long": 2},
        ],
        "device_info": [{"serial_number": 1234, "product": 999}],
        "event": [], "workout": [], "workout_step": [],
    }

    class Message:
        def __init__(self, values):
            self.values = values

        def get_values(self):
            return self.values

    class FitFile:
        def __init__(self, _stream, check_crc=True):
            assert check_crc is True

        def parse(self):
            return None

        def get_messages(self, name):
            return [Message(values) for values in messages.get(name, [])]

    monkeypatch.setitem(sys.modules, "fitparse", SimpleNamespace(FitFile=FitFile))

    parsed = parse_fit_payload(
        FitPayload("23865797605.zip/23865797605.fit", b"binary")
    )

    assert parsed.is_running is True
    assert parsed.title == "Trail Running"
    assert parsed.garmin_activity_id == "23865797605"
    assert parsed.source_activity_id == "garmin_23865797605"
    assert parsed.distance_m == 10_000.0
    assert parsed.raw_fit["split_text"] == "F1.00000|4:10"
    assert parsed.raw_fit["record_summary"]["record_count"] == 2
    assert parsed.raw_fit["record_summary"]["field_coverage"]["heart_rate"] == 2


def test_import_is_athlete_scoped_and_exact_reimport_is_duplicate(
    tmp_path, monkeypatch
):
    path, athlete_id = _database(tmp_path, monkeypatch)
    activity = _activity()

    first = import_garmin_activities(
        (activity,), athlete_id=athlete_id, athlete_name="Paul Tester"
    )
    second = import_garmin_activities(
        (activity,), athlete_id=athlete_id, athlete_name="Paul Tester"
    )

    assert (first.imported, first.enriched, first.duplicates) == (1, 0, 0)
    assert (second.imported, second.enriched, second.duplicates) == (0, 0, 1)
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT athlete_id, source, sport_id, distance_m, original_file,
                   raw_json
            FROM activities WHERE athlete_id = ?
            """,
            (athlete_id,),
        ).fetchone()
    assert row[:4] == (athlete_id, "garmin_fit", "running", 10_000.0)
    assert Path(row[4]).exists()
    assert (
        json.loads(row[5])["garmin_fit"]["source_activity_id"]
        == "garmin_23865797605"
    )


def test_fit_enriches_matching_runalyze_row_without_losing_title_or_raw_splits(
    tmp_path, monkeypatch
):
    path, athlete_id = _database(tmp_path, monkeypatch)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO activities (
                athlete_name, athlete_id, source, source_activity_id,
                activity_datetime, activity_date, title, sport_id, distance_m,
                moving_time_s, elapsed_time_s, elevation_up_m,
                elevation_down_m, temperature_c, raw_json
            ) VALUES (?, ?, 'runalyze_csv', 'runalyze-42', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Paul Tester", athlete_id, "2026-08-15T10:00:00",
                "2026-08-15", "Paul's threshold session", "965611", 10.0,
                2_400.0, 2_425.0, 18.0, 17.0, 20.0, json.dumps({
                    "externalId": 23865797605,
                    "splits": "I1.000|4:00||0",
                    "elevationUp": 18.0,
                    "elevationDown": 17.0,
                    "temperature": 20.0,
                }),
            ),
        )

    result = import_garmin_activities(
        (_activity(),), athlete_id=athlete_id, athlete_name="Paul Tester"
    )
    repeated = import_garmin_activities(
        (_activity(),), athlete_id=athlete_id, athlete_name="Paul Tester"
    )

    assert (result.imported, result.enriched, result.duplicates) == (0, 1, 0)
    assert (repeated.imported, repeated.enriched, repeated.duplicates) == (0, 0, 1)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """
            SELECT source, title, distance_m, avg_hr, elevation_up_m,
                   elevation_down_m, temperature_c, raw_json
            FROM activities WHERE athlete_id = ?
            """,
            (athlete_id,),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][:7] == (
        "runalyze_csv", "Paul's threshold session", 10_000.0, 151.0,
        18.0, 17.0, 20.0,
    )
    raw = json.loads(rows[0][7])
    assert raw["runalyze_splits"] == "I1.000|4:00||0"
    assert raw["splits"].startswith("F1.00000|4:00")
    assert raw["garmin_fit"]["source_activity_id"] == "garmin_23865797605"

    # An exact repeat also repairs environmental fields written by v0.37.1.
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE activities
            SET elevation_up_m = 52.0, elevation_down_m = 50.0,
                temperature_c = 29.0
            WHERE athlete_id = ?
            """,
            (athlete_id,),
        )
    repaired = import_garmin_activities(
        (_activity(),), athlete_id=athlete_id, athlete_name="Paul Tester"
    )
    assert (repaired.imported, repaired.enriched, repaired.duplicates) == (0, 0, 1)
    with sqlite3.connect(path) as connection:
        environment = connection.execute(
            """
            SELECT elevation_up_m, elevation_down_m, temperature_c
            FROM activities WHERE athlete_id = ?
            """,
            (athlete_id,),
        ).fetchone()
    assert environment == (18.0, 17.0, 20.0)


def test_reimport_repairs_pre_hotfix_garmin_duplicate(tmp_path, monkeypatch):
    path, athlete_id = _database(tmp_path, monkeypatch)
    with sqlite3.connect(path) as connection:
        runalyze_id = connection.execute(
            """
            INSERT INTO activities (
                athlete_name, athlete_id, source, source_activity_id,
                activity_datetime, activity_date, title, sport_id, distance_m,
                moving_time_s, elapsed_time_s, raw_json
            ) VALUES (?, ?, 'runalyze_csv', 'runalyze-42', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Paul Tester", athlete_id, "2026-08-15T10:00:00",
                "2026-08-15", "Original Runalyze title", "965611", 10.0,
                2_400.0, 2_425.0,
                json.dumps({"externalId": 23865797605}),
            ),
        ).lastrowid
        duplicate_id = connection.execute(
            """
            INSERT INTO activities (
                athlete_name, athlete_id, source, source_activity_id,
                activity_hash, activity_datetime, activity_date, title,
                sport_id, distance_m, moving_time_s, elapsed_time_s, raw_json
            ) VALUES (?, ?, 'garmin_fit', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Paul Tester", athlete_id, "fit-id-before-hotfix", "fit-hash",
                "2026-08-15T09:00:00", "2026-08-15", "Road Running",
                "running", 10_000.0, 2_400.0, 2_425.0,
                json.dumps({
                    "garmin_fit": {
                        "file_hash": "fit-hash",
                        "source_activity_id": "fit-id-before-hotfix",
                    }
                }),
            ),
        ).lastrowid
        connection.execute(
            "INSERT INTO derived_metrics(activity_id, metric_name, metric_value) "
            "VALUES (?, 'test_metric', 1.0)",
            (duplicate_id,),
        )

    result = import_garmin_activities(
        (_activity(),), athlete_id=athlete_id, athlete_name="Paul Tester"
    )

    assert (result.imported, result.enriched, result.duplicates) == (0, 1, 0)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT id, source, title FROM activities WHERE athlete_id = ?",
            (athlete_id,),
        ).fetchall()
        metric_activity_id = connection.execute(
            "SELECT activity_id FROM derived_metrics WHERE metric_name='test_metric'"
        ).fetchone()[0]
    assert rows == [(runalyze_id, "runalyze_csv", "Original Runalyze title")]
    assert metric_activity_id == runalyze_id


def test_running_only_does_not_import_other_garmin_sports(tmp_path, monkeypatch):
    path, athlete_id = _database(tmp_path, monkeypatch)
    result = import_garmin_activities(
        (_activity(sport="cycling"),),
        athlete_id=athlete_id,
        athlete_name="Paul Tester",
        running_only=True,
    )
    assert result.skipped_non_running == 1
    with sqlite3.connect(path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM activities WHERE athlete_id = ?", (athlete_id,)
        ).fetchone()[0]
    assert count == 0


def test_import_page_exposes_real_garmin_fit_and_zip_flow():
    source = (ROOT / "ui" / "import_page.py").read_text(encoding="utf-8")
    assert '"Garmin FIT / ZIP"' in source
    assert "accept_multiple_files=True" in source
    assert "import_garmin_activities(" in source
    assert "FIT import will be added later" not in source

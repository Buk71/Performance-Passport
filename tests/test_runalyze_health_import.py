from pathlib import Path

import core.database as database
from core.runalyze_health import (
    RunalyzeHealthRecord,
    get_athlete_health_count,
    import_runalyze_health_records,
    parse_runalyze_health_rows,
)


ROOT = Path(__file__).resolve().parent.parent


def _database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "health-import.db")
    connection = database.get_connection()
    cursor = connection.cursor()
    database.create_base_tables(cursor)
    database.create_athlete_health_daily_table(cursor)
    cursor.executemany(
        "INSERT INTO athletes (id, first_name, last_name) VALUES (?, ?, ?)",
        ((1, "Richard", "Burke"), (4, "Paul", "Farrell")),
    )
    connection.commit()
    connection.close()


def test_combined_health_export_extracts_recovery_values_and_skips_empty_rows():
    parsed = parse_runalyze_health_rows(
        (
            {
                "date": "2026-08-27",
                "hrv.hrv": "67",
                "hrv.metric": "2",
                "hrv.measurementType": "2",
                "hrv.source": "3",
                "hrv.id": "79300169",
                "restingHeartRate.heartRate": "51",
                "sleep.duration": "501",
                "sleep.quality100": "83",
            },
            {"date": "2023-04-02", "maximumHeartRate.heartRate": "182"},
        )
    )

    assert parsed.file_kind == "combined_health"
    assert parsed.skipped == 1
    assert len(parsed.records) == 1
    record = parsed.records[0]
    assert record.hrv_value == 67
    assert record.hrv_metric_code == "2"
    assert record.resting_hr == 51
    assert record.sleep_duration_min == 501


def test_standalone_hrv_export_is_supported_without_inventing_other_health_values():
    parsed = parse_runalyze_health_rows(
        ({
            "id": "79300169", "date": "2026-08-27", "time": "",
            "hrv": "67", "metric": "2", "measurementType": "2", "source": "3",
        },)
    )

    assert parsed.file_kind == "hrv_only"
    assert parsed.records[0].hrv_value == 67
    assert parsed.records[0].resting_hr is None
    assert parsed.records[0].sleep_duration_min is None


def test_unrecognised_csv_shape_is_rejected_with_an_explainable_issue():
    parsed = parse_runalyze_health_rows(({"date": "2026-08-27", "pace": "4:00"},))
    assert parsed.file_kind == "unknown"
    assert parsed.records == ()
    assert "not a recognised" in parsed.issues[0]


def test_health_import_is_idempotent_enriches_missing_values_and_isolates_athletes(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    hrv_only = RunalyzeHealthRecord(
        health_date="2026-08-27",
        file_kind="hrv_only",
        hrv_value=67,
        hrv_metric_code="2",
        hrv_measurement_type="2",
        hrv_source_code="3",
        raw_json='{"hrv_only":{"hrv":67}}',
    )
    first = import_runalyze_health_records((hrv_only,), athlete_id=1)
    repeated = import_runalyze_health_records((hrv_only,), athlete_id=1)
    combined = RunalyzeHealthRecord(
        health_date="2026-08-27",
        file_kind="combined_health",
        hrv_value=67,
        hrv_metric_code="2",
        hrv_measurement_type="2",
        hrv_source_code="3",
        resting_hr=51,
        sleep_duration_min=501,
        raw_json='{"combined_health":{"hrv.hrv":67}}',
    )
    enriched = import_runalyze_health_records((combined,), athlete_id=1)

    assert first.imported == 1
    assert repeated.duplicates == 1
    assert enriched.enriched == 1
    assert get_athlete_health_count(1) == 1
    assert get_athlete_health_count(4) == 0


def test_import_page_exposes_health_csv_without_replacing_activity_import():
    source = (ROOT / "ui" / "import_page.py").read_text(encoding="utf-8")

    assert '["Runalyze CSV", "Runalyze Health CSV", "Garmin FIT / ZIP"]' in source
    assert "Repeated uploads are safe" in source

import datetime as dt
import json

import core.database as database
from core.intelligence_store import (
    delete_intelligence,
    history_horizon,
    load_intelligence,
    save_intelligence,
)


def test_history_horizons_have_explicit_boundaries():
    today = dt.date(2026, 9, 3)
    assert history_horizon("2026-09-03", today=today) == "recent"
    assert history_horizon("2026-06-05", today=today) == "recent"  # 90 days
    assert history_horizon("2026-06-04", today=today) == "current"
    assert history_horizon("2025-09-03", today=today) == "current"  # 365 days
    assert history_horizon("2025-09-02", today=today) == "archive"


def test_intelligence_store_round_trip_and_version_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "performance_passport.db")
    database.initialise_database()

    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO athletes
            (id, first_name, last_name, date_of_birth, sex)
        VALUES (1, 'Test', 'Runner', '1980-01-01', 'Male')
        """
    )
    conn.commit()
    conn.close()

    save_intelligence(
        1,
        "race.capability.v1",
        {"5k_seconds": 1200, "confidence": 0.8},
        source_version=("activities", 42),
        horizon="current",
    )

    record = load_intelligence(
        1,
        "race.capability.v1",
        source_version=("activities", 42),
    )
    assert record is not None
    assert record.horizon == "current"
    assert record.payload["5k_seconds"] == 1200

    assert (
        load_intelligence(
            1,
            "race.capability.v1",
            source_version=("activities", 43),
        )
        is None
    )

    assert delete_intelligence(1, "race.capability.v1") == 1
    assert load_intelligence(1, "race.capability.v1") is None


def test_schema_v16_creates_intelligence_table(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "performance_passport.db")
    database.initialise_database()
    conn = database.get_connection()
    try:
        version = conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert version == 16
    assert "athlete_intelligence" in tables

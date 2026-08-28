import datetime

import pytest

import core.database as database
from core.recovery_coach import get_recovery_checkin, save_recovery_checkin


def _database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        tmp_path / "recovery-checkins.db",
    )
    connection = database.get_connection()
    cursor = connection.cursor()
    database.create_base_tables(cursor)
    database.create_recovery_checkins_table(cursor)
    cursor.executemany(
        "INSERT INTO athletes (id, first_name, last_name) VALUES (?, ?, ?)",
        ((1, "Richard", "Burke"), (3, "Joanne", "Burke")),
    )
    connection.commit()
    connection.close()


def test_daily_checkin_upserts_one_explicit_report_and_preserves_athlete_isolation(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    day = datetime.date(2026, 8, 27)
    save_recovery_checkin(
        1, day, sleep_quality=4, fatigue=2, soreness=2, motivation=5,
        notes="First report",
    )
    save_recovery_checkin(
        1, day, sleep_quality=3, fatigue=3, soreness=2, motivation=4,
        notes="Updated report",
    )

    saved = get_recovery_checkin(1, day)
    assert saved is not None
    assert saved.sleep_quality == 3
    assert saved.notes == "Updated report"
    assert get_recovery_checkin(3, day) is None


def test_checkin_rejects_values_outside_the_explained_scale(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Fatigue must be between 1 and 5"):
        save_recovery_checkin(
            1,
            "2026-08-27",
            sleep_quality=3,
            fatigue=6,
            soreness=2,
            motivation=4,
        )

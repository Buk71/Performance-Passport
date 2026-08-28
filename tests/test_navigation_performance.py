from __future__ import annotations

from pathlib import Path
import sqlite3

import core.database as database
from core.cache_version import (
    NAVIGATION_CACHE_TTL_SECONDS,
    get_athlete_cache_version,
)


ROOT = Path(__file__).resolve().parent.parent


def _athletes(tmp_path, monkeypatch) -> tuple[int, int]:
    database_path = tmp_path / "navigation-cache.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    database.initialise_database()
    with sqlite3.connect(database_path) as connection:
        first = connection.execute(
            """
            INSERT INTO athletes (first_name, last_name, date_of_birth, sex)
            VALUES ('First', 'Runner', '1980-01-01', 'Male')
            """
        ).lastrowid
        second = connection.execute(
            """
            INSERT INTO athletes (first_name, last_name, date_of_birth, sex)
            VALUES ('Second', 'Runner', '1985-01-01', 'Female')
            """
        ).lastrowid
    return int(first), int(second)


def test_athlete_cache_version_changes_only_for_changed_athlete(
    tmp_path, monkeypatch
):
    first, second = _athletes(tmp_path, monkeypatch)
    first_before = get_athlete_cache_version(first)
    second_before = get_athlete_cache_version(second)

    with sqlite3.connect(database.DATABASE_PATH) as connection:
        connection.execute(
            """
            INSERT INTO activities (
                athlete_name, athlete_id, source, source_activity_id,
                activity_datetime, activity_date, title, sport_id,
                distance_m, moving_time_s
            ) VALUES (?, ?, 'garmin_fit', 'garmin_new_run', ?, ?, ?, ?, ?, ?)
            """,
            (
                "First Runner",
                first,
                "2026-08-28T08:00:00",
                "2026-08-28",
                "Easy run",
                "running",
                8_000.0,
                2_400.0,
            ),
        )

    assert get_athlete_cache_version(first) != first_before
    assert get_athlete_cache_version(second) == second_before


def test_profile_and_sport_mapping_changes_invalidate_navigation_cache(
    tmp_path, monkeypatch
):
    first, _ = _athletes(tmp_path, monkeypatch)
    before = get_athlete_cache_version(first)

    with sqlite3.connect(database.DATABASE_PATH) as connection:
        connection.execute(
            "UPDATE athletes SET lt1_hr = 135, lt2_hr = 158 WHERE id = ?",
            (first,),
        )
    profile_changed = get_athlete_cache_version(first)
    assert profile_changed != before

    with sqlite3.connect(database.DATABASE_PATH) as connection:
        connection.execute(
            """
            INSERT INTO athlete_sport_mappings (
                athlete_id, sport_id, sport_role, confidence, source
            ) VALUES (?, 'running', 'running', 1.0, 'explicit')
            """,
            (first,),
        )
    assert get_athlete_cache_version(first) != profile_changed


def test_navigation_cache_contract_is_long_lived_and_data_versioned():
    assert NAVIGATION_CACHE_TTL_SECONDS >= 3_600

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "@st.cache_resource" in app_source
    assert "_initialise_database_once" in app_source

    for relative_path in (
        "ui/lead_coach_home.py",
        "ui/coaching_team.py",
        "ui/next_run.py",
        "ui/goals.py",
        "ui/fuel_planner.py",
        "ui/recovery_coach.py",
        "ui/progress.py",
        "ui/passport.py",
        "ui/training_blocks.py",
        "ui/race_outlook.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "NAVIGATION_CACHE_TTL_SECONDS" in source
        assert "get_athlete_cache_version" in source

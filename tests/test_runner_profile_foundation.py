import sqlite3
import pytest
import core.database as database
from core import runner_profile


@pytest.fixture
def profile_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "profile.db")
    database.initialise_database()
    with database.get_connection() as conn:
        conn.execute("INSERT INTO athletes (id, first_name) VALUES (1, 'Example')")
    return database.DATABASE_PATH


def test_profile_optional_and_editable(profile_db):
    assert runner_profile.get_runner_profile(1) is None
    result = runner_profile.save_runner_profile(1, experience="experienced", training_status="returning", sessions_per_week=3)
    assert result == {"experience": "experienced", "training_status": "returning", "sessions_per_week": 3}
    result = runner_profile.save_runner_profile(1, training_status="training")
    assert result["experience"] == "experienced"
    assert result["training_status"] == "training"


def test_invalid_values_and_unknown_athlete(profile_db):
    with pytest.raises(ValueError):
        runner_profile.save_runner_profile(1, experience="elite")
    with pytest.raises(ValueError):
        runner_profile.save_runner_profile(1, sessions_per_week=True)
    with pytest.raises(sqlite3.IntegrityError):
        runner_profile.save_runner_profile(99, experience="developing")


def test_schema_migration_and_delete_cascade(profile_db):
    with database.get_connection() as conn:
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 18
    runner_profile.save_runner_profile(1, experience="getting_started")
    with database.get_connection() as conn:
        conn.execute("DELETE FROM athletes WHERE id=1")
    assert runner_profile.get_runner_profile(1) is None

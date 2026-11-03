from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_database_schema_is_v17():
    source = (ROOT / "core" / "database.py").read_text(encoding="utf-8")
    assert "CURRENT_SCHEMA_VERSION = 17" in source
    assert "def migrate_to_schema_v17(" in source
    assert "create_runner_journey_tables(cursor)" in source


def test_runner_journey_tables_are_auditable():
    source = (ROOT / "core" / "database.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS athlete_runner_journeys" in source
    assert "CREATE TABLE IF NOT EXISTS runner_journey_events" in source
    assert "idx_runner_journeys_one_active" in source

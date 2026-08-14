import sqlite3

from core.training_blocks import (
    get_training_block_design,
    save_training_block_design,
)


def _database(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE athletes (id INTEGER PRIMARY KEY);
        CREATE TABLE goals (id INTEGER PRIMARY KEY, athlete_id INTEGER);
        CREATE TABLE training_blocks (id INTEGER PRIMARY KEY, athlete_id INTEGER);
        INSERT INTO athletes VALUES (1);
        INSERT INTO goals VALUES (7, 1);
        INSERT INTO training_blocks VALUES (9, 1);
        """
    )
    connection.commit()
    connection.close()


def test_block_design_round_trips_json_and_updates_in_place(monkeypatch, tmp_path):
    path = tmp_path / "design.db"
    _database(path)
    monkeypatch.setattr(
        "core.training_blocks.get_connection",
        lambda: sqlite3.connect(path),
    )
    first = save_training_block_design(
        athlete_id=1,
        training_block_id=9,
        primary_goal_id=7,
        preferences={"running_days": ["Tuesday", "Sunday"]},
        evidence={"recent_miles_per_week": 40},
        plan={"weeks": [{"week_number": 1}]},
    )
    second = save_training_block_design(
        athlete_id=1,
        training_block_id=9,
        primary_goal_id=7,
        preferences={"running_days": ["Wednesday", "Sunday"]},
        evidence={"recent_miles_per_week": 41},
        plan={"weeks": [{"week_number": 2}]},
    )
    saved = get_training_block_design(9, athlete_id=1)

    assert first == second
    assert saved.preferences["running_days"] == ["Wednesday", "Sunday"]
    assert saved.evidence["recent_miles_per_week"] == 41
    assert saved.plan["weeks"][0]["week_number"] == 2


def test_block_design_cannot_leak_across_athletes(monkeypatch, tmp_path):
    path = tmp_path / "design.db"
    _database(path)
    monkeypatch.setattr(
        "core.training_blocks.get_connection",
        lambda: sqlite3.connect(path),
    )
    save_training_block_design(
        athlete_id=1,
        training_block_id=9,
        primary_goal_id=7,
        preferences={}, evidence={}, plan={},
    )

    assert get_training_block_design(9, athlete_id=2) is None

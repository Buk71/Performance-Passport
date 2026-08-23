import datetime
import sqlite3

from core.database import get_active_goal, save_goal
from core.goals import (
    build_goal_hierarchy,
    build_goal_hierarchy_from_records,
    remove_goal,
    set_primary_goal,
)
from core.training_blocks import get_active_training_block


REFERENCE_DATE = datetime.date(2026, 8, 14)


def _record(
    goal_id,
    name,
    priority,
    status,
    target_date,
    *,
    block_id=None,
):
    return {
        "id": goal_id,
        "athlete_id": 1,
        "training_block_id": block_id,
        "goal_name": name,
        "goal_type": "10K",
        "distance_m": 10000.0,
        "target_time_s": 2400,
        "target_date": target_date,
        "race_name": name,
        "priority": priority,
        "status": status,
        "motivation": None,
    }


def _temporary_goal_database(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            training_block_id INTEGER,
            goal_name TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            distance_m REAL,
            target_time_s INTEGER,
            target_date TEXT,
            race_name TEXT,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            motivation TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.commit()
    connection.close()


def test_hierarchy_keeps_primary_secondary_future_and_past_distinct():
    hierarchy = build_goal_hierarchy_from_records(
        1,
        [
            _record(1, "Main 10K", "Primary", "Active", "2026-11-29"),
            _record(2, "Tune-up 5K", "Secondary", "Active", "2026-10-10"),
            _record(3, "Spring half", "Future", "Planned", "2027-04-04"),
            _record(4, "Summer 10K", "Primary", "Complete", "2026-06-01"),
        ],
        reference_date=REFERENCE_DATE,
    )

    assert hierarchy.primary.name == "Main 10K"
    assert hierarchy.secondary[0].influence_title == "Tune-up / benchmark"
    assert hierarchy.future[0].influence_title == "Parked for later"
    assert hierarchy.future[0].block_relationship == "No current block influence"
    assert hierarchy.past[0].role == "Past"
    assert "Main 10K leads your coaching" == hierarchy.headline


def test_real_richard_and_jo_keep_independent_primary_goals():
    richard = build_goal_hierarchy(1, reference_date=REFERENCE_DATE)
    jo = build_goal_hierarchy(3, reference_date=REFERENCE_DATE)
    richard_block = get_active_training_block(1)
    jo_block = get_active_training_block(3)

    assert richard.primary.name == "Sub 39:00"
    assert jo.primary.name == "Sub 45"
    assert richard.primary.athlete_id == 1
    assert jo.primary.athlete_id == 3

    for hierarchy, block in ((richard, richard_block), (jo, jo_block)):
        if block is None:
            assert hierarchy.active_block_name is None
            assert hierarchy.primary.block_relationship == "Training block not created"
        else:
            assert hierarchy.active_block_id == block.id
            assert hierarchy.active_block_name == block.name
            expected = (
                f"Drives {block.name}"
                if hierarchy.primary.training_block_id == block.id
                else "Current block needs review"
            )
            assert hierarchy.primary.block_relationship == expected


def test_promoting_goal_preserves_previous_primary_as_secondary(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "goals.db"
    _temporary_goal_database(path)
    connection = sqlite3.connect(path)
    connection.executemany(
        """
        INSERT INTO goals (
            id, athlete_id, goal_name, goal_type, priority, status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 1, "Old Primary", "10K", "Primary", "Active"),
            (2, 1, "New Primary", "5K", "Secondary", "Active"),
        ],
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(
        "core.goals.get_connection",
        lambda: sqlite3.connect(path),
    )

    set_primary_goal(1, 2)

    connection = sqlite3.connect(path)
    rows = connection.execute(
        "SELECT id, priority, status FROM goals ORDER BY id"
    ).fetchall()
    connection.close()
    assert rows == [
        (1, "Secondary", "Active"),
        (2, "Primary", "Active"),
    ]


def test_active_goal_never_falls_back_to_an_active_secondary(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "goals.db"
    _temporary_goal_database(path)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        INSERT INTO goals (
            athlete_id, goal_name, goal_type, priority, status
        ) VALUES (1, 'Tune-up', '5K', 'Secondary', 'Active')
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(
        "core.database.get_connection",
        lambda: sqlite3.connect(path),
    )

    assert get_active_goal(1) is None


def test_saving_a_new_primary_demotes_the_previous_one(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "goals.db"
    _temporary_goal_database(path)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        INSERT INTO goals (
            athlete_id, goal_name, goal_type, priority, status
        ) VALUES (1, 'Old Primary', '10K', 'Primary', 'Active')
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(
        "core.database.get_connection",
        lambda: sqlite3.connect(path),
    )

    save_goal(
        athlete_id=1,
        goal_name="New Primary",
        goal_type="5K",
        priority="Primary",
        status="Planned",
    )

    connection = sqlite3.connect(path)
    rows = connection.execute(
        "SELECT goal_name, priority, status FROM goals ORDER BY id"
    ).fetchall()
    connection.close()
    assert rows == [
        ("Old Primary", "Secondary", "Active"),
        ("New Primary", "Primary", "Active"),
    ]


def test_removing_primary_restores_block_linked_secondary_without_deleting_it(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "goals.db"
    _temporary_goal_database(path)
    connection = sqlite3.connect(path)
    connection.executemany(
        """
        INSERT INTO goals (
            id, athlete_id, training_block_id, goal_name, goal_type,
            priority, status, target_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 1, 2, "Sub 39:00", "10K", "Secondary", "Active", "2026-11-29"),
            (2, 1, None, "Nearer tune-up", "5K", "Secondary", "Active", "2026-09-01"),
            (3, 1, None, "Test half marathon", "Half", "Primary", "Active", "2026-10-11"),
            (4, 3, 7, "Jo's goal", "10K", "Primary", "Active", "2026-11-29"),
        ],
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr("core.goals.get_connection", lambda: sqlite3.connect(path))

    result = remove_goal(1, 3)

    connection = sqlite3.connect(path)
    rows = connection.execute(
        "SELECT id, priority, status, training_block_id FROM goals ORDER BY id"
    ).fetchall()
    connection.close()
    assert rows == [
        (1, "Primary", "Active", 2),
        (2, "Secondary", "Active", None),
        (3, "Primary", "Archived", None),
        (4, "Primary", "Active", 7),
    ]
    assert result.was_primary is True
    assert result.replacement_goal_id == 1
    assert result.replacement_goal_name == "Sub 39:00"


def test_removing_secondary_archives_it_without_changing_primary(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "goals.db"
    _temporary_goal_database(path)
    connection = sqlite3.connect(path)
    connection.executemany(
        """
        INSERT INTO goals (
            id, athlete_id, training_block_id, goal_name, goal_type,
            priority, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 1, 2, "Main target", "10K", "Primary", "Active"),
            (2, 1, 2, "Test goal", "Half", "Secondary", "Active"),
        ],
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr("core.goals.get_connection", lambda: sqlite3.connect(path))

    result = remove_goal(1, 2)

    connection = sqlite3.connect(path)
    rows = connection.execute(
        "SELECT id, priority, status, training_block_id FROM goals ORDER BY id"
    ).fetchall()
    connection.close()
    assert rows == [
        (1, "Primary", "Active", 2),
        (2, "Secondary", "Archived", None),
    ]
    assert result.was_primary is False
    assert result.was_linked_to_block is True
    assert result.replacement_goal_id is None


def test_removing_goal_cannot_change_another_athletes_goal(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "goals.db"
    _temporary_goal_database(path)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        INSERT INTO goals (
            id, athlete_id, goal_name, goal_type, priority, status
        ) VALUES (7, 3, 'Jo target', '10K', 'Primary', 'Active')
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr("core.goals.get_connection", lambda: sqlite3.connect(path))

    try:
        remove_goal(1, 7)
    except ValueError as error:
        assert "does not belong" in str(error)
    else:
        raise AssertionError("Another athlete's goal must never be removed")

    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT priority, status FROM goals WHERE id = 7"
    ).fetchone()
    connection.close()
    assert row == ("Primary", "Active")

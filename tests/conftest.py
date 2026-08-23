"""Keep real-athlete regression tests isolated from the live application."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3

import pytest

import core.database as database


@pytest.fixture(scope="session", autouse=True)
def isolated_real_athlete_database(tmp_path_factory):
    """Run the historical golden tests against a disposable database copy.

    The application database is intentionally allowed to evolve: athletes can
    switch goals, import sessions and adjust their plans. Existing real-data
    regressions, however, were written against Richard's original Sub-39 10K
    goal. Restore that reference goal only in a temporary snapshot, never in
    the athlete's live database.
    """
    original_path = Path(database.DATABASE_PATH).resolve()
    conventional_path = (Path("database") / "performance_passport.db").resolve()
    if not original_path.is_file():
        yield
        return

    original_connect = sqlite3.connect
    snapshot_path = (
        tmp_path_factory.mktemp("performance-passport-tests")
        / "performance_passport.db"
    )

    with original_connect(original_path) as source:
        with original_connect(snapshot_path) as snapshot:
            source.backup(snapshot)

    with original_connect(snapshot_path) as snapshot:
        late_richard_activities = """
            SELECT id FROM activities
            WHERE athlete_id IN (1, 3)
              AND date(activity_date) > date('2026-08-09')
        """
        snapshot.execute(
            f"""
            DELETE FROM workout_race_links
            WHERE race_activity_id IN ({late_richard_activities})
               OR workout_id IN (
                    SELECT id FROM workout_library
                    WHERE activity_id IN ({late_richard_activities})
               )
            """
        )
        for table in (
            "derived_metrics", "benchmarks", "decoded_workouts",
            "workout_library",
        ):
            snapshot.execute(
                f"DELETE FROM {table} "
                f"WHERE activity_id IN ({late_richard_activities})"
            )
        snapshot.execute(
            f"DELETE FROM activities WHERE id IN ({late_richard_activities})"
        )

        for table in (
            "training_block_designs", "block_review_actions",
            "nutrition_week_selections",
        ):
            snapshot.execute(f"DELETE FROM {table} WHERE athlete_id = 1")
        snapshot.execute("DELETE FROM training_blocks WHERE athlete_id = 1")
        snapshot.execute(
            "UPDATE goals SET training_block_id = NULL WHERE athlete_id = 1"
        )

        old_primary = snapshot.execute(
            """
            SELECT id FROM goals
            WHERE athlete_id = 1
              AND goal_name = 'Sub 39:00'
              AND status = 'Active'
            """
        ).fetchone()
        if old_primary is not None:
            snapshot.execute(
                """
                UPDATE goals
                SET priority = CASE
                    WHEN id = ? THEN 'Primary'
                    ELSE 'Secondary'
                END
                WHERE athlete_id = 1 AND status = 'Active'
                """,
                (old_primary[0],),
            )

    database.DATABASE_PATH = snapshot_path

    def connect_to_test_database(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)):
            path_text = os.fsdecode(path)
            if path_text != ":memory:" and not path_text.startswith("file:"):
                if Path(path_text).resolve() in (original_path, conventional_path):
                    path = snapshot_path
        return original_connect(path, *args, **kwargs)

    sqlite3.connect = connect_to_test_database
    try:
        yield
    finally:
        sqlite3.connect = original_connect
        database.DATABASE_PATH = original_path

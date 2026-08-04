"""
Workout Intelligence Library persistence service.

This module only stores and retrieves workout knowledge. It does not decide
which activities are workouts and does not generate predictions. Those jobs
remain with the phase engine, linker and similarity engine.

Raw activities always remain the source of truth. Library records are
rebuildable derived intelligence.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from core.database import (
    create_workout_library_tables,
    get_connection,
)


@dataclass(frozen=True)
class WorkoutLibraryRecord:
    id: int
    activity_id: int
    athlete_id: int
    activity_date: str | None
    session_type: str
    workout_signature: str
    phases: tuple[dict[str, Any], ...]
    execution_score: float | None
    recognition_confidence: float
    phase_confidence: float
    source: str
    decoder_version: int
    created_at: str
    updated_at: str


def _normalise_phases(phases: list[dict[str, Any]] | tuple[dict[str, Any], ...]):
    return json.dumps(
        list(phases),
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def _row_to_record(row) -> WorkoutLibraryRecord:
    try:
        phases = json.loads(row[6]) if row[6] else []
    except (TypeError, json.JSONDecodeError):
        phases = []

    return WorkoutLibraryRecord(
        id=int(row[0]),
        activity_id=int(row[1]),
        athlete_id=int(row[2]),
        activity_date=row[3],
        session_type=row[4],
        workout_signature=row[5],
        phases=tuple(phases),
        execution_score=(
            float(row[7]) if row[7] is not None else None
        ),
        recognition_confidence=float(row[8] or 0.0),
        phase_confidence=float(row[9] or 0.0),
        source=row[10],
        decoder_version=int(row[11]),
        created_at=row[12],
        updated_at=row[13],
    )


def upsert_workout(
    *,
    activity_id: int,
    athlete_id: int,
    activity_date: str | None,
    session_type: str,
    workout_signature: str,
    phases: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    execution_score: float | None,
    recognition_confidence: float,
    phase_confidence: float,
    source: str,
    decoder_version: int,
) -> int:
    """
    Insert or refresh one derived workout record.

    activity_id is unique, so re-decoding an activity updates the existing
    library entry instead of creating duplicates.
    """
    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    cursor.execute(
        """
        INSERT INTO workout_library (
            activity_id,
            athlete_id,
            activity_date,
            session_type,
            workout_signature,
            phase_json,
            execution_score,
            recognition_confidence,
            phase_confidence,
            source,
            decoder_version,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
            athlete_id = excluded.athlete_id,
            activity_date = excluded.activity_date,
            session_type = excluded.session_type,
            workout_signature = excluded.workout_signature,
            phase_json = excluded.phase_json,
            execution_score = excluded.execution_score,
            recognition_confidence = excluded.recognition_confidence,
            phase_confidence = excluded.phase_confidence,
            source = excluded.source,
            decoder_version = excluded.decoder_version,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            activity_id,
            athlete_id,
            activity_date,
            session_type,
            workout_signature,
            _normalise_phases(phases),
            execution_score,
            max(0.0, min(float(recognition_confidence), 1.0)),
            max(0.0, min(float(phase_confidence), 1.0)),
            source,
            int(decoder_version),
        ),
    )

    cursor.execute(
        "SELECT id FROM workout_library WHERE activity_id = ?",
        (activity_id,),
    )
    library_id = int(cursor.fetchone()[0])

    conn.commit()
    conn.close()

    return library_id


def get_workout_by_activity(activity_id: int) -> WorkoutLibraryRecord | None:
    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    cursor.execute(
        """
        SELECT
            id,
            activity_id,
            athlete_id,
            activity_date,
            session_type,
            workout_signature,
            phase_json,
            execution_score,
            recognition_confidence,
            phase_confidence,
            source,
            decoder_version,
            created_at,
            updated_at
        FROM workout_library
        WHERE activity_id = ?
        """,
        (activity_id,),
    )

    row = cursor.fetchone()
    conn.close()

    return _row_to_record(row) if row else None


def get_athlete_workouts(
    athlete_id: int,
    *,
    limit: int | None = None,
) -> list[WorkoutLibraryRecord]:
    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    sql = """
        SELECT
            id,
            activity_id,
            athlete_id,
            activity_date,
            session_type,
            workout_signature,
            phase_json,
            execution_score,
            recognition_confidence,
            phase_confidence,
            source,
            decoder_version,
            created_at,
            updated_at
        FROM workout_library
        WHERE athlete_id = ?
        ORDER BY activity_date DESC, id DESC
    """
    parameters: list[Any] = [athlete_id]

    if limit is not None:
        sql += " LIMIT ?"
        parameters.append(max(int(limit), 0))

    cursor.execute(sql, tuple(parameters))
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_record(row) for row in rows]


def count_athlete_workouts(athlete_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM workout_library
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )

    count = int(cursor.fetchone()[0])
    conn.close()

    return count


def delete_workout_by_activity(activity_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    cursor.execute(
        "DELETE FROM workout_library WHERE activity_id = ?",
        (activity_id,),
    )
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted

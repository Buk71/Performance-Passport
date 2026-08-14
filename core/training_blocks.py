"""
Training Blocks Engine.

A Training Block is the organising unit for coaching direction.

A block answers:
- What are we trying to develop?
- Over what period?
- Which phase are we in?
- Which goals belong to this block?
- What week are we in?

This first version is intentionally deterministic and lightweight. It provides
the data model and calculations that Goal Centre, Recommended Next Run, Dynamic
Plan, Block Review and Coach Mode will build upon.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
from typing import Any

from core.database import create_training_block_designs_table, get_connection


BLOCK_STATUSES = (
    "Planned",
    "Active",
    "Complete",
    "Archived",
)

BLOCK_TYPES = (
    "Base",
    "5K",
    "10K",
    "Half Marathon",
    "Marathon",
    "Speed Development",
    "Return to Running",
    "Recovery",
    "General",
)

BLOCK_PHASES = (
    "Base",
    "Build",
    "Specific",
    "Peak",
    "Taper",
    "Race",
    "Recovery",
)

BLOCK_FOCUSES = (
    "Aerobic",
    "Threshold",
    "Speed / VO₂",
    "Endurance",
    "Race Specific",
    "Recovery",
    "Balanced",
)


@dataclass(frozen=True)
class TrainingBlock:
    id: int
    athlete_id: int
    name: str
    block_type: str
    purpose: str | None
    start_date: str | None
    end_date: str | None
    status: str
    primary_focus: str | None
    current_phase: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class BlockGoal:
    id: int
    athlete_id: int
    training_block_id: int | None
    goal_name: str
    goal_type: str
    distance_m: float | None
    target_time_s: int | None
    target_date: str | None
    race_name: str | None
    priority: str
    status: str
    motivation: str | None


@dataclass(frozen=True)
class BlockProgress:
    week_number: int | None
    total_weeks: int | None
    progress_fraction: float | None
    days_remaining: int | None
    date_status: str


@dataclass(frozen=True)
class SavedBlockDesign:
    id: int
    athlete_id: int
    training_block_id: int
    primary_goal_id: int
    preferences: dict[str, Any]
    evidence: dict[str, Any]
    plan: dict[str, Any]
    model_version: int
    updated_at: str | None


def _date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _block_from_row(row) -> TrainingBlock:
    return TrainingBlock(
        id=row[0],
        athlete_id=row[1],
        name=row[2],
        block_type=row[3],
        purpose=row[4],
        start_date=row[5],
        end_date=row[6],
        status=row[7],
        primary_focus=row[8],
        current_phase=row[9],
        notes=row[10],
        created_at=row[11],
        updated_at=row[12],
    )


def list_training_blocks(
    athlete_id: int,
) -> tuple[TrainingBlock, ...]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id,
            athlete_id,
            name,
            block_type,
            purpose,
            start_date,
            end_date,
            status,
            primary_focus,
            current_phase,
            notes,
            created_at,
            updated_at
        FROM training_blocks
        WHERE athlete_id = ?
        ORDER BY
            CASE status
                WHEN 'Active' THEN 0
                WHEN 'Planned' THEN 1
                WHEN 'Complete' THEN 2
                ELSE 3
            END,
            start_date DESC,
            id DESC
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return tuple(_block_from_row(row) for row in rows)


def get_training_block(
    block_id: int,
    *,
    athlete_id: int | None = None,
) -> TrainingBlock | None:
    conn = get_connection()
    cursor = conn.cursor()

    if athlete_id is None:
        cursor.execute(
            """
            SELECT
                id, athlete_id, name, block_type, purpose,
                start_date, end_date, status, primary_focus,
                current_phase, notes, created_at, updated_at
            FROM training_blocks
            WHERE id = ?
            """,
            (block_id,),
        )
    else:
        cursor.execute(
            """
            SELECT
                id, athlete_id, name, block_type, purpose,
                start_date, end_date, status, primary_focus,
                current_phase, notes, created_at, updated_at
            FROM training_blocks
            WHERE id = ? AND athlete_id = ?
            """,
            (block_id, athlete_id),
        )

    row = cursor.fetchone()
    conn.close()
    return _block_from_row(row) if row else None


def get_active_training_block(
    athlete_id: int,
) -> TrainingBlock | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id, athlete_id, name, block_type, purpose,
            start_date, end_date, status, primary_focus,
            current_phase, notes, created_at, updated_at
        FROM training_blocks
        WHERE athlete_id = ? AND status = 'Active'
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (athlete_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return _block_from_row(row) if row else None


def save_training_block(
    *,
    athlete_id: int,
    name: str,
    block_type: str,
    purpose: str | None,
    start_date: str | None,
    end_date: str | None,
    status: str,
    primary_focus: str | None,
    current_phase: str | None,
    notes: str | None,
    block_id: int | None = None,
) -> int:
    if status not in BLOCK_STATUSES:
        raise ValueError(f"Unsupported block status: {status}")

    conn = get_connection()
    cursor = conn.cursor()

    if status == "Active":
        cursor.execute(
            """
            UPDATE training_blocks
            SET status = 'Complete',
                updated_at = CURRENT_TIMESTAMP
            WHERE athlete_id = ?
              AND status = 'Active'
              AND (? IS NULL OR id != ?)
            """,
            (athlete_id, block_id, block_id),
        )

    if block_id is None:
        cursor.execute(
            """
            INSERT INTO training_blocks (
                athlete_id,
                name,
                block_type,
                purpose,
                start_date,
                end_date,
                status,
                primary_focus,
                current_phase,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                athlete_id,
                name,
                block_type,
                purpose,
                start_date,
                end_date,
                status,
                primary_focus,
                current_phase,
                notes,
            ),
        )
        block_id = int(cursor.lastrowid)
    else:
        cursor.execute(
            """
            UPDATE training_blocks
            SET
                name = ?,
                block_type = ?,
                purpose = ?,
                start_date = ?,
                end_date = ?,
                status = ?,
                primary_focus = ?,
                current_phase = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND athlete_id = ?
            """,
            (
                name,
                block_type,
                purpose,
                start_date,
                end_date,
                status,
                primary_focus,
                current_phase,
                notes,
                block_id,
                athlete_id,
            ),
        )

    conn.commit()
    conn.close()
    return block_id


def set_active_training_block(
    athlete_id: int,
    block_id: int,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE training_blocks
        SET status = 'Complete',
            updated_at = CURRENT_TIMESTAMP
        WHERE athlete_id = ?
          AND status = 'Active'
          AND id != ?
        """,
        (athlete_id, block_id),
    )

    cursor.execute(
        """
        UPDATE training_blocks
        SET status = 'Active',
            updated_at = CURRENT_TIMESTAMP
        WHERE athlete_id = ? AND id = ?
        """,
        (athlete_id, block_id),
    )

    conn.commit()
    conn.close()


def block_progress(
    block: TrainingBlock,
    *,
    today: datetime.date | None = None,
) -> BlockProgress:
    today = today or datetime.date.today()
    start = _date(block.start_date)
    end = _date(block.end_date)

    if start is None or end is None or end < start:
        return BlockProgress(
            week_number=None,
            total_weeks=None,
            progress_fraction=None,
            days_remaining=None,
            date_status="Dates not fully configured",
        )

    total_days = (end - start).days + 1
    total_weeks = max(1, (total_days + 6) // 7)

    if today < start:
        return BlockProgress(
            week_number=0,
            total_weeks=total_weeks,
            progress_fraction=0.0,
            days_remaining=(end - today).days,
            date_status="Upcoming",
        )

    elapsed_days = (today - start).days

    if today > end:
        return BlockProgress(
            week_number=total_weeks,
            total_weeks=total_weeks,
            progress_fraction=1.0,
            days_remaining=0,
            date_status="Block dates complete",
        )

    week_number = min(
        (elapsed_days // 7) + 1,
        total_weeks,
    )
    progress_fraction = min(
        max((elapsed_days + 1) / total_days, 0.0),
        1.0,
    )

    return BlockProgress(
        week_number=week_number,
        total_weeks=total_weeks,
        progress_fraction=round(progress_fraction, 4),
        days_remaining=max((end - today).days, 0),
        date_status="Active dates",
    )


def list_goals_for_block(
    athlete_id: int,
    block_id: int,
) -> tuple[BlockGoal, ...]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id,
            athlete_id,
            training_block_id,
            goal_name,
            goal_type,
            distance_m,
            target_time_s,
            target_date,
            race_name,
            priority,
            status,
            motivation
        FROM goals
        WHERE athlete_id = ?
          AND training_block_id = ?
        ORDER BY
            CASE priority
                WHEN 'Primary' THEN 0
                WHEN 'Secondary' THEN 1
                ELSE 2
            END,
            target_date,
            id
        """,
        (athlete_id, block_id),
    )
    rows = cursor.fetchall()
    conn.close()

    return tuple(
        BlockGoal(
            id=row[0],
            athlete_id=row[1],
            training_block_id=row[2],
            goal_name=row[3],
            goal_type=row[4],
            distance_m=row[5],
            target_time_s=row[6],
            target_date=row[7],
            race_name=row[8],
            priority=row[9],
            status=row[10],
            motivation=row[11],
        )
        for row in rows
    )


def list_unassigned_goals(
    athlete_id: int,
) -> tuple[BlockGoal, ...]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id,
            athlete_id,
            training_block_id,
            goal_name,
            goal_type,
            distance_m,
            target_time_s,
            target_date,
            race_name,
            priority,
            status,
            motivation
        FROM goals
        WHERE athlete_id = ?
          AND training_block_id IS NULL
          AND status IN ('Active', 'Planned')
        ORDER BY
            CASE priority
                WHEN 'Primary' THEN 0
                WHEN 'Secondary' THEN 1
                ELSE 2
            END,
            target_date,
            id
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return tuple(
        BlockGoal(
            id=row[0],
            athlete_id=row[1],
            training_block_id=row[2],
            goal_name=row[3],
            goal_type=row[4],
            distance_m=row[5],
            target_time_s=row[6],
            target_date=row[7],
            race_name=row[8],
            priority=row[9],
            status=row[10],
            motivation=row[11],
        )
        for row in rows
    )


def assign_goal_to_block(
    *,
    athlete_id: int,
    goal_id: int,
    block_id: int,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE goals
        SET training_block_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND athlete_id = ?
        """,
        (block_id, goal_id, athlete_id),
    )
    conn.commit()
    conn.close()


def save_training_block_design(
    *,
    athlete_id: int,
    training_block_id: int,
    primary_goal_id: int,
    preferences: dict[str, Any],
    evidence: dict[str, Any],
    plan: dict[str, Any],
    model_version: int = 1,
) -> int:
    """Save the athlete-approved generator inputs and resulting plan."""
    conn = get_connection()
    cursor = conn.cursor()
    create_training_block_designs_table(cursor)
    cursor.execute(
        """
        INSERT INTO training_block_designs (
            athlete_id, training_block_id, primary_goal_id,
            preferences_json, evidence_json, plan_json, model_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(training_block_id) DO UPDATE SET
            athlete_id = excluded.athlete_id,
            primary_goal_id = excluded.primary_goal_id,
            preferences_json = excluded.preferences_json,
            evidence_json = excluded.evidence_json,
            plan_json = excluded.plan_json,
            model_version = excluded.model_version,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            athlete_id,
            training_block_id,
            primary_goal_id,
            json.dumps(preferences, sort_keys=True),
            json.dumps(evidence, sort_keys=True),
            json.dumps(plan, sort_keys=True),
            model_version,
        ),
    )
    cursor.execute(
        "SELECT id FROM training_block_designs WHERE training_block_id = ?",
        (training_block_id,),
    )
    design_id = int(cursor.fetchone()[0])
    conn.commit()
    conn.close()
    return design_id


def get_training_block_design(
    training_block_id: int,
    *,
    athlete_id: int | None = None,
) -> SavedBlockDesign | None:
    conn = get_connection()
    cursor = conn.cursor()
    create_training_block_designs_table(cursor)
    if athlete_id is None:
        cursor.execute(
            """
            SELECT id, athlete_id, training_block_id, primary_goal_id,
                   preferences_json, evidence_json, plan_json,
                   model_version, updated_at
            FROM training_block_designs
            WHERE training_block_id = ?
            """,
            (training_block_id,),
        )
    else:
        cursor.execute(
            """
            SELECT id, athlete_id, training_block_id, primary_goal_id,
                   preferences_json, evidence_json, plan_json,
                   model_version, updated_at
            FROM training_block_designs
            WHERE training_block_id = ? AND athlete_id = ?
            """,
            (training_block_id, athlete_id),
        )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return SavedBlockDesign(
        id=int(row[0]),
        athlete_id=int(row[1]),
        training_block_id=int(row[2]),
        primary_goal_id=int(row[3]),
        preferences=json.loads(row[4]),
        evidence=json.loads(row[5]),
        plan=json.loads(row[6]),
        model_version=int(row[7]),
        updated_at=row[8],
    )

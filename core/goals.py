"""Goal hierarchy and lifecycle rules for Performance Passport.

Goals answer what the athlete is targeting. Exactly one Active Primary goal
may drive coaching. Secondary goals can support the current journey, while
Future goals remain parked until deliberately promoted.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.database import get_connection, get_goals_for_athlete
from core.training_blocks import TrainingBlock, get_active_training_block


GOAL_ROLES = ("Primary", "Secondary", "Future")
GOAL_STATUSES = ("Active", "Planned", "Complete", "Archived")
PAST_STATUSES = {"Complete", "Archived"}


@dataclass(frozen=True)
class GoalHierarchyItem:
    id: int
    athlete_id: int
    name: str
    goal_type: str
    distance_m: float | None
    target_time_s: float | None
    target_date: str | None
    race_name: str | None
    priority: str
    status: str
    motivation: str | None
    training_block_id: int | None
    role: str
    influence_title: str
    influence_summary: str
    block_relationship: str
    timing_label: str
    days_to_goal: int | None


@dataclass(frozen=True)
class GoalHierarchy:
    athlete_id: int
    primary: GoalHierarchyItem | None
    secondary: tuple[GoalHierarchyItem, ...]
    future: tuple[GoalHierarchyItem, ...]
    past: tuple[GoalHierarchyItem, ...]
    active_block_id: int | None
    active_block_name: str | None
    headline: str
    summary: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class GoalRemovalResult:
    """Describe a reversible removal without changing saved block designs."""

    goal_id: int
    goal_name: str
    was_primary: bool
    replacement_goal_id: int | None
    replacement_goal_name: str | None
    was_linked_to_block: bool


def _date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _timing(
    target_date: str | None,
    reference_date: datetime.date,
) -> tuple[str, int | None]:
    parsed = _date(target_date)
    if parsed is None:
        return "Date not set", None
    days = (parsed - reference_date).days
    if days < 0:
        return f"Date passed {abs(days)} days ago", days
    if days == 0:
        return "Goal day is today", 0
    if days == 1:
        return "Tomorrow", 1
    weeks = days // 7
    if weeks >= 2:
        return f"{weeks} weeks away", days
    return f"{days} days away", days


def _item(
    goal: dict,
    *,
    role: str,
    reference_date: datetime.date,
    primary_date: datetime.date | None,
    active_block: TrainingBlock | None,
) -> GoalHierarchyItem:
    timing_label, days_to_goal = _timing(
        goal.get("target_date"),
        reference_date,
    )
    goal_date = _date(goal.get("target_date"))

    if role == "Primary":
        influence_title = "Drives current coaching"
        influence_summary = (
            "Sets the direction for Home, Next Run and the active Training Block."
        )
        if active_block is None:
            block_relationship = "Training block not created"
        elif goal.get("training_block_id") == active_block.id:
            block_relationship = f"Drives {active_block.name}"
        else:
            block_relationship = "Current block needs review"
    elif role == "Secondary":
        is_tune_up = (
            primary_date is not None
            and goal_date is not None
            and reference_date <= goal_date <= primary_date
        )
        influence_title = (
            "Tune-up / benchmark"
            if is_tune_up
            else "Supporting goal"
        )
        influence_summary = (
            "Can shape sequencing and race practice without replacing the Primary goal."
        )
        if (
            active_block is not None
            and goal.get("training_block_id") == active_block.id
        ):
            block_relationship = f"Included in {active_block.name}"
        elif active_block is not None:
            block_relationship = "Available to include in current block"
        else:
            block_relationship = "Available when a block is created"
    elif role == "Future":
        influence_title = "Parked for later"
        influence_summary = (
            "Visible for planning, but has no effect on current coaching."
        )
        block_relationship = "No current block influence"
    else:
        influence_title = "Historical outcome"
        influence_summary = (
            "Retained as part of the athlete's goal history."
        )
        block_relationship = "Historical record"

    return GoalHierarchyItem(
        id=int(goal["id"]),
        athlete_id=int(goal["athlete_id"]),
        name=str(goal.get("goal_name") or "Goal"),
        goal_type=str(goal.get("goal_type") or "Goal"),
        distance_m=(
            float(goal["distance_m"])
            if goal.get("distance_m") is not None
            else None
        ),
        target_time_s=(
            float(goal["target_time_s"])
            if goal.get("target_time_s") is not None
            else None
        ),
        target_date=goal.get("target_date"),
        race_name=goal.get("race_name"),
        priority=str(goal.get("priority") or role),
        status=str(goal.get("status") or "Planned"),
        motivation=goal.get("motivation"),
        training_block_id=goal.get("training_block_id"),
        role=role,
        influence_title=influence_title,
        influence_summary=influence_summary,
        block_relationship=block_relationship,
        timing_label=timing_label,
        days_to_goal=days_to_goal,
    )


def build_goal_hierarchy_from_records(
    athlete_id: int,
    goals: list[dict],
    *,
    active_block: TrainingBlock | None = None,
    reference_date: datetime.date | None = None,
) -> GoalHierarchy:
    """Compose a deterministic hierarchy from persisted goal records."""
    reference_date = reference_date or datetime.date.today()
    current = [
        goal for goal in goals
        if str(goal.get("status") or "") not in PAST_STATUSES
    ]
    past_records = [
        goal for goal in goals
        if str(goal.get("status") or "") in PAST_STATUSES
    ]
    active_primary = [
        goal for goal in current
        if goal.get("priority") == "Primary"
        and goal.get("status") == "Active"
    ]
    primary_record = active_primary[0] if active_primary else None
    primary_date = _date(
        primary_record.get("target_date") if primary_record else None
    )
    warnings: list[str] = []
    if len(active_primary) > 1:
        warnings.append(
            "More than one Active Primary goal was found; only the first can drive coaching."
        )

    primary = (
        _item(
            primary_record,
            role="Primary",
            reference_date=reference_date,
            primary_date=primary_date,
            active_block=active_block,
        )
        if primary_record is not None
        else None
    )

    secondary_records = [
        goal for goal in current
        if goal is not primary_record
        and (
            goal.get("priority") == "Secondary"
            or (
                goal.get("priority") == "Primary"
                and goal.get("status") != "Active"
            )
            or goal in active_primary[1:]
        )
    ]
    future_records = [
        goal for goal in current
        if goal.get("priority") == "Future"
    ]

    secondary = tuple(
        _item(
            goal,
            role="Secondary",
            reference_date=reference_date,
            primary_date=primary_date,
            active_block=active_block,
        )
        for goal in secondary_records
    )
    future = tuple(
        _item(
            goal,
            role="Future",
            reference_date=reference_date,
            primary_date=primary_date,
            active_block=active_block,
        )
        for goal in future_records
    )
    past = tuple(
        _item(
            goal,
            role="Past",
            reference_date=reference_date,
            primary_date=primary_date,
            active_block=active_block,
        )
        for goal in past_records
    )

    if primary is None:
        headline = "Choose one goal to lead your coaching"
        summary = (
            "Secondary and Future goals stay saved, but Home and planning need "
            "one Active Primary goal."
        )
    else:
        headline = f"{primary.name} leads your coaching"
        supporting = len(secondary)
        future_count = len(future)
        summary = (
            f"One Primary goal sets direction. {supporting} Secondary goal"
            f"{'s' if supporting != 1 else ''} can support it and "
            f"{future_count} Future goal{'s' if future_count != 1 else ''} "
            "remain parked."
        )

    return GoalHierarchy(
        athlete_id=athlete_id,
        primary=primary,
        secondary=secondary,
        future=future,
        past=past,
        active_block_id=active_block.id if active_block else None,
        active_block_name=active_block.name if active_block else None,
        headline=headline,
        summary=summary,
        warnings=tuple(warnings),
    )


def build_goal_hierarchy(
    athlete_id: int,
    *,
    reference_date: datetime.date | None = None,
) -> GoalHierarchy:
    return build_goal_hierarchy_from_records(
        athlete_id,
        get_goals_for_athlete(athlete_id),
        active_block=get_active_training_block(athlete_id),
        reference_date=reference_date,
    )


def set_primary_goal(athlete_id: int, goal_id: int) -> None:
    """Promote one goal and preserve the previous Primary as Secondary."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT status
        FROM goals
        WHERE id = ? AND athlete_id = ?
        """,
        (goal_id, athlete_id),
    )
    row = cursor.fetchone()
    if row is None:
        connection.close()
        raise ValueError("Goal does not belong to this athlete.")
    if row[0] in PAST_STATUSES:
        connection.close()
        raise ValueError("Restore a completed goal before making it Primary.")

    cursor.execute(
        """
        UPDATE goals
        SET priority = 'Secondary',
            updated_at = CURRENT_TIMESTAMP
        WHERE athlete_id = ?
          AND priority = 'Primary'
          AND status = 'Active'
          AND id != ?
        """,
        (athlete_id, goal_id),
    )
    cursor.execute(
        """
        UPDATE goals
        SET priority = 'Primary',
            status = 'Active',
            updated_at = CURRENT_TIMESTAMP
        WHERE athlete_id = ? AND id = ?
        """,
        (athlete_id, goal_id),
    )
    connection.commit()
    connection.close()


def set_goal_role(athlete_id: int, goal_id: int, role: str) -> None:
    if role not in GOAL_ROLES:
        raise ValueError(f"Unsupported goal role: {role}")
    if role == "Primary":
        set_primary_goal(athlete_id, goal_id)
        return

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT priority, status
        FROM goals
        WHERE id = ? AND athlete_id = ?
        """,
        (goal_id, athlete_id),
    )
    row = cursor.fetchone()
    if row is None:
        connection.close()
        raise ValueError("Goal does not belong to this athlete.")
    if row[0] == "Primary" and row[1] == "Active":
        connection.close()
        raise ValueError("Choose another Primary before moving this goal.")
    status = "Planned" if role == "Future" else row[1]
    cursor.execute(
        """
        UPDATE goals
        SET priority = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND athlete_id = ?
        """,
        (role, status, goal_id, athlete_id),
    )
    connection.commit()
    connection.close()


def set_goal_status(athlete_id: int, goal_id: int, status: str) -> None:
    if status not in GOAL_STATUSES:
        raise ValueError(f"Unsupported goal status: {status}")
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE goals
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND athlete_id = ?
        """,
        (status, goal_id, athlete_id),
    )
    if cursor.rowcount != 1:
        connection.close()
        raise ValueError("Goal does not belong to this athlete.")
    connection.commit()
    connection.close()


def remove_goal(athlete_id: int, goal_id: int) -> GoalRemovalResult:
    """Archive an unwanted goal and restore the best existing Primary.

    Removal is deliberately recoverable: race history remains available under
    Past goals, and no active training block or approved block design is
    deleted. When the removed goal was Primary, an existing Active Secondary
    already connected to a block takes priority over an unrelated goal.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT goal_name, priority, status, training_block_id
        FROM goals
        WHERE id = ? AND athlete_id = ?
        """,
        (goal_id, athlete_id),
    )
    selected = cursor.fetchone()
    if selected is None:
        connection.close()
        raise ValueError("Goal does not belong to this athlete.")
    if selected[2] == "Archived":
        connection.close()
        raise ValueError("This goal has already been removed.")

    goal_name = str(selected[0] or "Goal")
    was_primary = selected[1] == "Primary" and selected[2] == "Active"
    replacement = None

    if was_primary:
        cursor.execute(
            """
            SELECT id, goal_name
            FROM goals
            WHERE athlete_id = ?
              AND id != ?
              AND priority = 'Secondary'
              AND status = 'Active'
            ORDER BY
                CASE WHEN training_block_id IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN target_date IS NULL THEN 1 ELSE 0 END,
                target_date ASC,
                id ASC
            LIMIT 1
            """,
            (athlete_id, goal_id),
        )
        replacement = cursor.fetchone()

    cursor.execute(
        """
        UPDATE goals
        SET status = 'Archived',
            training_block_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND athlete_id = ?
        """,
        (goal_id, athlete_id),
    )
    if replacement is not None:
        cursor.execute(
            """
            UPDATE goals
            SET priority = 'Primary',
                status = 'Active',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND athlete_id = ?
            """,
            (replacement[0], athlete_id),
        )

    connection.commit()
    connection.close()
    return GoalRemovalResult(
        goal_id=goal_id,
        goal_name=goal_name,
        was_primary=was_primary,
        replacement_goal_id=int(replacement[0]) if replacement else None,
        replacement_goal_name=str(replacement[1]) if replacement else None,
        was_linked_to_block=selected[3] is not None,
    )


def restore_goal_as_future(athlete_id: int, goal_id: int) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE goals
        SET priority = 'Future', status = 'Planned',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND athlete_id = ?
        """,
        (goal_id, athlete_id),
    )
    if cursor.rowcount != 1:
        connection.close()
        raise ValueError("Goal does not belong to this athlete.")
    connection.commit()
    connection.close()

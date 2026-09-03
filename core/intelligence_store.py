"""Persistent materialised athlete intelligence for Performance Passport v0.64.

The store is intentionally page-agnostic. Coaches should eventually consume
reusable intelligence artifacts rather than repeatedly rebuilding the same
history-derived evidence on every navigation action.

History horizons:
- recent: 0-90 days, kept at high resolution for current coaching decisions;
- current: 91-365 days, retained as current-season evidence;
- archive: >365 days, progressively represented by durable summaries plus
  explicitly preserved significant evidence (PBs, races, benchmark sessions).

This module establishes persistence and horizon rules only. v0.64.1 does not
change any coach output yet.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any, Iterable

from core.database import get_connection


RECENT_DAYS = 90
CURRENT_DAYS = 365
VALID_HORIZONS = {"recent", "current", "archive", "all"}


@dataclass(frozen=True)
class IntelligenceRecord:
    athlete_id: int
    intelligence_key: str
    horizon: str
    source_version: tuple[Any, ...]
    payload: Any
    generated_at: str | None = None


def history_horizon(activity_date: str | dt.date, *, today: dt.date | None = None) -> str:
    """Classify an activity date into recent/current/archive."""
    if isinstance(activity_date, str):
        activity_date = dt.date.fromisoformat(activity_date[:10])
    today = today or dt.date.today()
    age_days = (today - activity_date).days
    if age_days <= RECENT_DAYS:
        return "recent"
    if age_days <= CURRENT_DAYS:
        return "current"
    return "archive"


def get_activity_horizon_counts(
    athlete_id: int,
    *,
    today: dt.date | None = None,
) -> dict[str, int]:
    """Return raw activity counts in the three v0.64 history horizons."""
    today = today or dt.date.today()
    recent_cutoff = (today - dt.timedelta(days=RECENT_DAYS)).isoformat()
    current_cutoff = (today - dt.timedelta(days=CURRENT_DAYS)).isoformat()

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN activity_date >= ? THEN 1 ELSE 0 END),
                SUM(CASE WHEN activity_date < ? AND activity_date >= ? THEN 1 ELSE 0 END),
                SUM(CASE WHEN activity_date < ? THEN 1 ELSE 0 END)
            FROM activities
            WHERE athlete_id = ?
              AND activity_date IS NOT NULL
              AND activity_date <> ''
            """,
            (
                recent_cutoff,
                recent_cutoff,
                current_cutoff,
                current_cutoff,
                int(athlete_id),
            ),
        ).fetchone()
    finally:
        conn.close()

    return {
        "recent": int((row or (0, 0, 0))[0] or 0),
        "current": int((row or (0, 0, 0))[1] or 0),
        "archive": int((row or (0, 0, 0))[2] or 0),
    }


def save_intelligence(
    athlete_id: int,
    intelligence_key: str,
    payload: Any,
    *,
    source_version: Iterable[Any],
    horizon: str = "current",
) -> None:
    """Upsert one reusable intelligence artifact."""
    if horizon not in VALID_HORIZONS:
        raise ValueError(f"Unsupported intelligence horizon: {horizon}")
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO athlete_intelligence
                (athlete_id, intelligence_key, horizon,
                 source_version_json, payload_json, generated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(athlete_id, intelligence_key) DO UPDATE SET
                horizon=excluded.horizon,
                source_version_json=excluded.source_version_json,
                payload_json=excluded.payload_json,
                generated_at=CURRENT_TIMESTAMP
            """,
            (
                int(athlete_id),
                str(intelligence_key),
                horizon,
                json.dumps(list(source_version), separators=(",", ":"), default=str),
                json.dumps(payload, separators=(",", ":"), default=str),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def load_intelligence(
    athlete_id: int,
    intelligence_key: str,
    *,
    source_version: Iterable[Any] | None = None,
) -> IntelligenceRecord | None:
    """Load a materialised artifact, optionally requiring an exact source version."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT horizon, source_version_json, payload_json, generated_at
            FROM athlete_intelligence
            WHERE athlete_id = ? AND intelligence_key = ?
            """,
            (int(athlete_id), str(intelligence_key)),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    stored_version = tuple(json.loads(row[1]))
    if source_version is not None and stored_version != tuple(source_version):
        return None

    return IntelligenceRecord(
        athlete_id=int(athlete_id),
        intelligence_key=str(intelligence_key),
        horizon=str(row[0]),
        source_version=stored_version,
        payload=json.loads(row[2]),
        generated_at=row[3],
    )


def delete_intelligence(
    athlete_id: int,
    intelligence_key: str | None = None,
) -> int:
    """Invalidate one artifact or all materialised intelligence for an athlete."""
    conn = get_connection()
    try:
        if intelligence_key is None:
            cursor = conn.execute(
                "DELETE FROM athlete_intelligence WHERE athlete_id = ?",
                (int(athlete_id),),
            )
        else:
            cursor = conn.execute(
                """
                DELETE FROM athlete_intelligence
                WHERE athlete_id = ? AND intelligence_key = ?
                """,
                (int(athlete_id), str(intelligence_key)),
            )
        conn.commit()
        return int(cursor.rowcount)
    finally:
        conn.close()

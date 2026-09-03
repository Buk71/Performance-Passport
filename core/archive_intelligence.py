"""Archive intelligence foundation for Performance Passport v0.64.9.

This module separates athlete history into:
- recent: 0–90 days
- current: 91–365 days
- archive: >365 days

It does NOT yet change coach outputs. Its purpose is to build a compact,
persistent archive summary that future rebuilds can reuse instead of repeatedly
scanning thousands of old activities.

Significant PB evidence remains handled separately and is never discarded by
the archive boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import datetime as dt
from typing import Any

from core.database import get_connection, get_athlete_sport_roles
from core.intelligence_store import load_intelligence, save_intelligence
from core.cache_version import get_race_intelligence_version

RECENT_DAYS = 90
CURRENT_DAYS = 365
ARCHIVE_KEY = "archive.history_summary.v1"


@dataclass(frozen=True)
class ArchiveHistorySummary:
    athlete_id: int
    as_of_date: str
    archive_cutoff_date: str
    activity_count: int
    running_activity_count: int
    earliest_activity_date: str | None
    latest_archive_activity_date: str | None
    total_distance_km: float
    total_duration_s: float
    best_5k_like_s: float | None
    best_10k_like_s: float | None
    best_half_like_s: float | None
    best_marathon_like_s: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _activity_window_counts(athlete_id: int, *, as_of: dt.date) -> dict[str, int]:
    recent_cutoff = as_of - dt.timedelta(days=RECENT_DAYS)
    current_cutoff = as_of - dt.timedelta(days=CURRENT_DAYS)

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT activity_date
            FROM activities
            WHERE athlete_id = ?
              AND activity_date IS NOT NULL
              AND TRIM(activity_date) <> ''
            """,
            (int(athlete_id),),
        ).fetchall()
    finally:
        conn.close()

    counts = {"recent": 0, "current": 0, "archive": 0}
    for row in rows:
        raw = row[0]
        try:
            date_value = dt.date.fromisoformat(str(raw)[:10])
        except Exception:
            continue
        if date_value >= recent_cutoff:
            counts["recent"] += 1
        elif date_value >= current_cutoff:
            counts["current"] += 1
        else:
            counts["archive"] += 1
    return counts


def build_archive_history_summary(
    athlete_id: int,
    *,
    as_of: dt.date | None = None,
) -> ArchiveHistorySummary:
    """Build a compact summary from activities older than 365 days.

    Uses the real Performance Passport activities schema.

    Historical note: despite its legacy name, activities.distance_m is stored
    in kilometres throughout the existing coaching engines.
    """
    athlete_id = int(athlete_id)
    as_of = as_of or dt.date.today()
    archive_cutoff = as_of - dt.timedelta(days=CURRENT_DAYS)

    sport_roles = get_athlete_sport_roles(athlete_id)
    running_ids = {
        str(sport_id)
        for sport_id, role in sport_roles.items()
        if str(role).lower() == "running"
    }

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*),
                MIN(activity_date),
                MAX(activity_date),
                COALESCE(SUM(COALESCE(distance_m, 0)), 0),
                COALESCE(SUM(COALESCE(moving_time_s, elapsed_time_s, 0)), 0)
            FROM activities
            WHERE athlete_id = ?
              AND activity_date IS NOT NULL
              AND DATE(activity_date) < DATE(?)
            """,
            (athlete_id, archive_cutoff.isoformat()),
        ).fetchone()

        running_count = 0
        if running_ids:
            placeholders = ",".join("?" for _ in running_ids)
            running_count = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM activities
                WHERE athlete_id = ?
                  AND activity_date IS NOT NULL
                  AND DATE(activity_date) < DATE(?)
                  AND CAST(sport_id AS TEXT) IN ({placeholders})
                """,
                (athlete_id, archive_cutoff.isoformat(), *sorted(running_ids)),
            ).fetchone()[0]

        # Lightweight best-distance-like evidence. These are supporting archive
        # summaries, not replacements for verified PB detection.
        # Elapsed time is used here to stay aligned with PB/race timing rules.
        def best_like(distance_km: float, tolerance: float):
            """Return lightweight archived RUNNING evidence near a distance.

            This is deliberately only supporting evidence. Verified PB logic
            remains separate. Non-running sports must never enter this summary.
            """
            if not running_ids:
                return None

            target_km = float(distance_km)
            placeholders = ",".join("?" for _ in running_ids)
            result = conn.execute(
                f"""
                SELECT MIN(elapsed_time_s)
                FROM activities
                WHERE athlete_id = ?
                  AND activity_date IS NOT NULL
                  AND DATE(activity_date) < DATE(?)
                  AND CAST(sport_id AS TEXT) IN ({placeholders})
                  AND distance_m BETWEEN ? AND ?
                  AND elapsed_time_s IS NOT NULL
                  AND elapsed_time_s > 0
                """,
                (
                    athlete_id,
                    archive_cutoff.isoformat(),
                    *sorted(running_ids),
                    target_km * (1.0 - tolerance),
                    target_km * (1.0 + tolerance),
                ),
            ).fetchone()
            value = result[0] if result else None
            return float(value) if value is not None else None

        return ArchiveHistorySummary(
            athlete_id=athlete_id,
            as_of_date=as_of.isoformat(),
            archive_cutoff_date=archive_cutoff.isoformat(),
            activity_count=int(row[0] or 0),
            running_activity_count=int(running_count or 0),
            earliest_activity_date=str(row[1])[:10] if row and row[1] else None,
            latest_archive_activity_date=str(row[2])[:10] if row and row[2] else None,
            total_distance_km=float(row[3] or 0.0),
            total_duration_s=float(row[4] or 0.0),
            best_5k_like_s=best_like(5.0, 0.03),
            best_10k_like_s=best_like(10.0, 0.03),
            best_half_like_s=best_like(21.0975, 0.03),
            best_marathon_like_s=best_like(42.195, 0.03),
        )
    finally:
        conn.close()


def refresh_archive_history_summary(
    athlete_id: int,
    *,
    as_of: dt.date | None = None,
) -> ArchiveHistorySummary:
    """Rebuild and persist the compact archive summary."""
    athlete_id = int(athlete_id)
    as_of = as_of or dt.date.today()
    summary = build_archive_history_summary(athlete_id, as_of=as_of)

    # Race-source version is intentionally used here because it tracks the
    # historical evidence that can change this summary without being affected
    # by derived coach-output tables.
    source_version = tuple(get_race_intelligence_version(athlete_id))
    save_intelligence(
        athlete_id,
        ARCHIVE_KEY,
        summary.to_dict(),
        source_version=source_version,
        horizon="archive",
    )
    return summary


def load_archive_history_summary(
    athlete_id: int,
) -> ArchiveHistorySummary | None:
    athlete_id = int(athlete_id)
    source_version = tuple(get_race_intelligence_version(athlete_id))
    record = load_intelligence(
        athlete_id,
        ARCHIVE_KEY,
        source_version=source_version,
    )
    if record is None:
        return None
    payload = record.payload
    return ArchiveHistorySummary(**payload)


def inspect_history_horizons(
    athlete_id: int,
    *,
    as_of: dt.date | None = None,
) -> dict[str, int]:
    return _activity_window_counts(
        int(athlete_id),
        as_of=as_of or dt.date.today(),
    )

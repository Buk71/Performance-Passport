"""
Automatic Workout-to-Race Linker.

The linker connects stored workouts to subsequent race outcomes for the same
athlete. These links are the evidence foundation for future historical
matching and athlete-calibrated workout predictions.

A workout is linked to confirmed race evidence occurring 3-35 days later.
Race-quality efforts may also be linked, but at lower confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
from typing import Any

from core.database import (
    create_workout_library_tables,
    get_athlete_sport_roles,
    get_connection,
)
from core.race_detection import score_race_evidence


MIN_DAYS_AFTER = 3
MAX_DAYS_AFTER = 35


@dataclass(frozen=True)
class WorkoutRaceLinkSummary:
    athlete_id: int
    workout_count: int
    race_candidate_count: int
    links_written: int
    links_deleted: int
    errors: int


def _as_date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}

    return decoded if isinstance(decoded, dict) else {}


def _race_time_seconds(
    elapsed_time_s: float | None,
    moving_time_s: float | None,
    raw: dict[str, Any],
) -> float | None:
    official = raw.get("race_officialTime")

    try:
        if official is not None and float(official) > 0:
            return float(official)
    except (TypeError, ValueError):
        pass

    if elapsed_time_s is not None and elapsed_time_s > 0:
        return elapsed_time_s

    if moving_time_s is not None and moving_time_s > 0:
        return moving_time_s

    return None


def _link_confidence(
    *,
    race_classification: str,
    race_confidence: float,
    days_after: int,
    workout_recognition: float,
    workout_phase_confidence: float,
) -> float:
    if race_classification == "confirmed_race":
        race_quality = 1.0
    else:
        race_quality = 0.72

    # The most useful pre-race window is roughly 7-21 days.
    if 7 <= days_after <= 21:
        timing_quality = 1.0
    elif 4 <= days_after <= 28:
        timing_quality = 0.85
    else:
        timing_quality = 0.65

    confidence = (
        race_quality * 0.25
        + race_confidence * 0.25
        + timing_quality * 0.20
        + workout_recognition * 0.15
        + workout_phase_confidence * 0.15
    )

    return max(0.0, min(confidence, 1.0))


def refresh_workout_race_links(
    athlete_id: int,
) -> WorkoutRaceLinkSummary:
    """
    Rebuild all workout-to-race links for one athlete.

    The operation is idempotent. Existing links for the athlete are removed
    and regenerated from the current Workout Library and activity history.
    """
    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    cursor.execute(
        """
        SELECT
            id,
            activity_id,
            activity_date,
            recognition_confidence,
            phase_confidence
        FROM workout_library
        WHERE athlete_id = ?
          AND activity_date IS NOT NULL
        ORDER BY activity_date
        """,
        (athlete_id,),
    )
    workout_rows = cursor.fetchall()

    sport_roles = get_athlete_sport_roles(athlete_id)
    running_ids = [
        sport_id
        for sport_id, role in sport_roles.items()
        if role == "running"
    ]

    if not running_ids:
        conn.close()
        return WorkoutRaceLinkSummary(
            athlete_id=athlete_id,
            workout_count=len(workout_rows),
            race_candidate_count=0,
            links_written=0,
            links_deleted=0,
            errors=0,
        )

    placeholders = ",".join("?" for _ in running_ids)

    cursor.execute(
        f"""
        SELECT
            a.id,
            a.activity_date,
            a.title,
            a.distance_m,
            a.moving_time_s,
            a.elapsed_time_s,
            a.avg_hr,
            a.max_hr,
            at.lt2_hr,
            at.max_hr,
            a.raw_json
        FROM activities a
        JOIN athletes at ON at.id = a.athlete_id
        WHERE a.athlete_id = ?
          AND CAST(a.sport_id AS TEXT) IN ({placeholders})
          AND a.activity_date IS NOT NULL
          AND a.distance_m IS NOT NULL
          AND COALESCE(a.elapsed_time_s, a.moving_time_s) IS NOT NULL
        ORDER BY a.activity_date
        """,
        (athlete_id, *running_ids),
    )
    activity_rows = cursor.fetchall()

    race_candidates = []

    for row in activity_rows:
        raw = _safe_json(row[10])

        signals = score_race_evidence(
            title=row[2] or "",
            distance_km=(
                float(row[3]) if row[3] is not None else None
            ),
            moving_time_s=(
                float(row[4]) if row[4] is not None else None
            ),
            elapsed_time_s=(
                float(row[5]) if row[5] is not None else None
            ),
            avg_hr=float(row[6]) if row[6] is not None else None,
            max_hr=float(row[7]) if row[7] is not None else None,
            athlete_lt2_hr=(
                float(row[8]) if row[8] is not None else None
            ),
            athlete_max_hr=(
                float(row[9]) if row[9] is not None else None
            ),
            official_race_name=raw.get("race_name"),
            official_distance_m=raw.get("race_officialDistance"),
            official_time_s=raw.get("race_officialTime"),
            officially_measured=bool(
                raw.get("race_officiallyMeasured")
            ),
        )

        if signals.classification not in {
            "confirmed_race",
            "race_quality_effort",
        }:
            continue

        race_date = _as_date(row[1])
        race_time_s = _race_time_seconds(
            float(row[5]) if row[5] is not None else None,
            float(row[4]) if row[4] is not None else None,
            raw,
        )

        if race_date is None or race_time_s is None:
            continue

        race_candidates.append(
            {
                "activity_id": int(row[0]),
                "date": race_date,
                "distance_km": float(row[3]),
                "time_s": float(race_time_s),
                "classification": signals.classification,
                "confidence": signals.confidence,
            }
        )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM workout_race_links
        WHERE workout_id IN (
            SELECT id
            FROM workout_library
            WHERE athlete_id = ?
        )
        """,
        (athlete_id,),
    )
    links_deleted = int(cursor.fetchone()[0])

    cursor.execute(
        """
        DELETE FROM workout_race_links
        WHERE workout_id IN (
            SELECT id
            FROM workout_library
            WHERE athlete_id = ?
        )
        """,
        (athlete_id,),
    )

    links_written = 0
    errors = 0

    for workout_row in workout_rows:
        workout_id = int(workout_row[0])
        workout_activity_id = int(workout_row[1])
        workout_date = _as_date(workout_row[2])
        recognition_confidence = float(workout_row[3] or 0.0)
        phase_confidence = float(workout_row[4] or 0.0)

        if workout_date is None:
            continue

        for race in race_candidates:
            if race["activity_id"] == workout_activity_id:
                continue

            days_after = (race["date"] - workout_date).days

            if not MIN_DAYS_AFTER <= days_after <= MAX_DAYS_AFTER:
                continue

            confidence = _link_confidence(
                race_classification=race["classification"],
                race_confidence=race["confidence"],
                days_after=days_after,
                workout_recognition=recognition_confidence,
                workout_phase_confidence=phase_confidence,
            )

            try:
                cursor.execute(
                    """
                    INSERT INTO workout_race_links (
                        workout_id,
                        race_activity_id,
                        days_after,
                        race_distance_km,
                        race_time_s,
                        link_confidence,
                        similarity_score,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP)
                    ON CONFLICT(workout_id, race_activity_id)
                    DO UPDATE SET
                        days_after = excluded.days_after,
                        race_distance_km = excluded.race_distance_km,
                        race_time_s = excluded.race_time_s,
                        link_confidence = excluded.link_confidence,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        workout_id,
                        race["activity_id"],
                        days_after,
                        race["distance_km"],
                        race["time_s"],
                        confidence,
                    ),
                )
                links_written += 1
            except Exception:
                errors += 1

    conn.commit()
    conn.close()

    return WorkoutRaceLinkSummary(
        athlete_id=athlete_id,
        workout_count=len(workout_rows),
        race_candidate_count=len(race_candidates),
        links_written=links_written,
        links_deleted=links_deleted,
        errors=errors,
    )


def get_workout_race_links(
    athlete_id: int,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    sql = """
        SELECT
            wrl.id,
            wl.activity_id AS workout_activity_id,
            wl.activity_date AS workout_date,
            wl.workout_signature,
            wrl.race_activity_id,
            race.activity_date AS race_date,
            race.title AS race_title,
            wrl.days_after,
            wrl.race_distance_km,
            wrl.race_time_s,
            wrl.link_confidence,
            wrl.similarity_score
        FROM workout_race_links wrl
        JOIN workout_library wl
          ON wl.id = wrl.workout_id
        JOIN activities race
          ON race.id = wrl.race_activity_id
        WHERE wl.athlete_id = ?
        ORDER BY race.activity_date DESC,
                 wrl.link_confidence DESC
    """
    parameters: list[Any] = [athlete_id]

    if limit is not None:
        sql += " LIMIT ?"
        parameters.append(max(int(limit), 0))

    cursor.execute(sql, tuple(parameters))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": int(row[0]),
            "workout_activity_id": int(row[1]),
            "workout_date": row[2],
            "workout_signature": row[3],
            "race_activity_id": int(row[4]),
            "race_date": row[5],
            "race_title": row[6] or "Race effort",
            "days_after": int(row[7]),
            "race_distance_km": float(row[8]),
            "race_time_s": float(row[9]),
            "link_confidence": float(row[10]),
            "similarity_score": (
                float(row[11]) if row[11] is not None else None
            ),
        }
        for row in rows
    ]

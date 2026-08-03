"""
Workout Coach core service.

Decodes Runalyze split strings once, stores the structured result, and gives
all specialist coaches one shared description of the session.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

from core.database import get_connection
from core.splits import (
    detect_split_format,
    parse_splits,
    recognise_workout,
    splits_to_dicts,
)


DECODER_VERSION = 3


@dataclass(frozen=True)
class DecodedWorkout:
    activity_id: int
    workout_type: str
    description: str
    confidence: float
    execution_score: float | None
    rep_count: int
    average_rep_distance_km: float | None
    average_rep_pace_s_per_km: float | None
    rep_pace_variation_percent: float | None
    recognition_json: dict[str, Any]
    decoder_version: int = DECODER_VERSION


def _execution_score(recognition) -> float | None:
    if not recognition.work_splits:
        return None

    score = 55.0
    score += recognition.confidence * 20.0

    variation = recognition.rep_pace_variation_percent
    if variation is not None:
        if variation <= 2:
            score += 20
        elif variation <= 5:
            score += 15
        elif variation <= 8:
            score += 8

    expected_recoveries = max(recognition.rep_count - 1, 0)
    if expected_recoveries:
        recovery_ratio = min(
            len(recognition.recovery_splits) / expected_recoveries,
            1.0,
        )
        score += recovery_ratio * 5.0

    return min(round(score, 1), 100.0)


def decode_workout(activity_id: int, raw_splits: str | None) -> DecodedWorkout:
    splits = parse_splits(raw_splits)
    recognition = recognise_workout(splits)

    payload = {
        "split_format": detect_split_format(raw_splits),
        "workout_type": recognition.workout_type,
        "description": recognition.description,
        "confidence": recognition.confidence,
        "reasons": list(recognition.reasons),
        "limitations": list(recognition.limitations),
        "work_splits": splits_to_dicts(recognition.work_splits),
        "recovery_splits": splits_to_dicts(recognition.recovery_splits),
        "warmup_splits": splits_to_dicts(recognition.warmup_splits),
        "cooldown_splits": splits_to_dicts(recognition.cooldown_splits),
        "boundary_splits": splits_to_dicts(recognition.boundary_splits),
        "unknown_recovery_count": recognition.unknown_recovery_count,
        "work_blocks": [
            {
                "kind": block.kind,
                "distance_km": round(block.distance_km, 4),
                "duration_s": block.duration_s,
                "pace_s_per_km": (
                    round(block.pace_s_per_km, 2)
                    if block.pace_s_per_km is not None
                    else None
                ),
                "splits": splits_to_dicts(block.splits),
            }
            for block in recognition.work_blocks
        ],
        "all_splits": splits_to_dicts(splits),
    }

    return DecodedWorkout(
        activity_id=activity_id,
        workout_type=recognition.workout_type,
        description=recognition.description,
        confidence=round(recognition.confidence, 4),
        execution_score=_execution_score(recognition),
        rep_count=recognition.rep_count,
        average_rep_distance_km=recognition.average_rep_distance_km,
        average_rep_pace_s_per_km=recognition.average_rep_pace_s_per_km,
        rep_pace_variation_percent=recognition.rep_pace_variation_percent,
        recognition_json=payload,
    )


def save_decoded_workout(workout: DecodedWorkout) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO decoded_workouts (
            activity_id,
            workout_type,
            description,
            confidence,
            execution_score,
            rep_count,
            average_rep_distance_km,
            average_rep_pace_s_per_km,
            rep_pace_variation_percent,
            workout_json,
            decoder_version,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
            workout_type = excluded.workout_type,
            description = excluded.description,
            confidence = excluded.confidence,
            execution_score = excluded.execution_score,
            rep_count = excluded.rep_count,
            average_rep_distance_km = excluded.average_rep_distance_km,
            average_rep_pace_s_per_km =
                excluded.average_rep_pace_s_per_km,
            rep_pace_variation_percent =
                excluded.rep_pace_variation_percent,
            workout_json = excluded.workout_json,
            decoder_version = excluded.decoder_version,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            workout.activity_id,
            workout.workout_type,
            workout.description,
            workout.confidence,
            workout.execution_score,
            workout.rep_count,
            workout.average_rep_distance_km,
            workout.average_rep_pace_s_per_km,
            workout.rep_pace_variation_percent,
            json.dumps(workout.recognition_json),
            workout.decoder_version,
        ),
    )
    conn.commit()
    conn.close()


def _extract_raw_splits(raw_json_text: str | None) -> str | None:
    if not raw_json_text:
        return None

    try:
        raw = json.loads(raw_json_text)
    except (TypeError, json.JSONDecodeError):
        return None

    return raw.get("splits") or raw.get("splitsCustom")


def get_or_decode_workout(
    activity_id: int,
    raw_json_text: str | None,
) -> DecodedWorkout:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            workout_type,
            description,
            confidence,
            execution_score,
            rep_count,
            average_rep_distance_km,
            average_rep_pace_s_per_km,
            rep_pace_variation_percent,
            workout_json,
            decoder_version
        FROM decoded_workouts
        WHERE activity_id = ?
        """,
        (activity_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is not None and row[9] == DECODER_VERSION:
        return DecodedWorkout(
            activity_id=activity_id,
            workout_type=row[0],
            description=row[1],
            confidence=row[2],
            execution_score=row[3],
            rep_count=row[4],
            average_rep_distance_km=row[5],
            average_rep_pace_s_per_km=row[6],
            rep_pace_variation_percent=row[7],
            recognition_json=json.loads(row[8] or "{}"),
            decoder_version=row[9],
        )

    workout = decode_workout(
        activity_id=activity_id,
        raw_splits=_extract_raw_splits(raw_json_text),
    )
    save_decoded_workout(workout)
    return workout


def rebuild_decoded_workouts(athlete_id: int | None = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    if athlete_id is None:
        cursor.execute(
            """
            SELECT id, raw_json
            FROM activities
            WHERE raw_json IS NOT NULL
            """
        )
    else:
        cursor.execute(
            """
            SELECT id, raw_json
            FROM activities
            WHERE athlete_id = ?
              AND raw_json IS NOT NULL
            """,
            (athlete_id,),
        )

    rows = cursor.fetchall()
    conn.close()

    count = 0
    for activity_id, raw_json_text in rows:
        workout = decode_workout(
            activity_id,
            _extract_raw_splits(raw_json_text),
        )
        save_decoded_workout(workout)
        count += 1

    return count


def get_recent_decoded_workouts(
    athlete_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            a.id,
            a.activity_date,
            a.title,
            dw.workout_type,
            dw.description,
            dw.confidence,
            dw.execution_score,
            dw.rep_count,
            dw.average_rep_distance_km,
            dw.average_rep_pace_s_per_km,
            dw.rep_pace_variation_percent,
            dw.workout_json
        FROM decoded_workouts dw
        JOIN activities a ON a.id = dw.activity_id
        WHERE a.athlete_id = ?
          AND dw.workout_type NOT IN ('No split data', 'Unclassified')
        ORDER BY a.activity_datetime DESC
        LIMIT ?
        """,
        (athlete_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()

    keys = [
        "activity_id",
        "activity_date",
        "title",
        "workout_type",
        "description",
        "confidence",
        "execution_score",
        "rep_count",
        "average_rep_distance_km",
        "average_rep_pace_s_per_km",
        "rep_pace_variation_percent",
        "workout_json",
    ]

    result = []
    for row in rows:
        item = dict(zip(keys, row))
        item["workout_json"] = json.loads(item["workout_json"] or "{}")
        result.append(item)

    return result

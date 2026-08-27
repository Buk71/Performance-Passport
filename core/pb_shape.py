"""
PB Shape Engine.

The engine answers a personal coaching question:

    How does current training compare with the athlete's training
    7-28 days before their best race at this distance?

It is athlete-scoped, device-independent and based on the permanent Workout
Library. It intentionally ignores the easy/taper week immediately before a PB.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import math
from typing import Any

from core.database import (
    create_workout_library_tables,
    get_athlete_sport_roles,
    get_connection,
)
from core.race_detection import score_race_evidence
from core.workout_similarity import compare_workout_phase_json


PB_WINDOW_START_DAYS = 7
PB_WINDOW_END_DAYS = 28
MAX_PB_WORKOUTS = 5


@dataclass(frozen=True)
class PBShapeResult:
    athlete_id: int
    current_activity_id: int
    goal_distance_km: float
    pb_activity_id: int | None
    pb_date: str | None
    pb_time_s: float | None
    pb_distance_km: float | None
    pb_title: str | None
    pb_classification: str | None
    pb_workout_count: int
    current_shape_percent: float | None
    central_seconds: float | None
    low_seconds: float | None
    high_seconds: float | None
    confidence: float
    status: str
    matches: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]


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


def _distance_tolerance(goal_distance_km: float) -> float:
    if goal_distance_km <= 10.5:
        return 0.04
    if goal_distance_km <= 22.0:
        return 0.035
    return 0.03


def _race_time(
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


def _find_pb(
    *,
    athlete_id: int,
    goal_distance_km: float,
) -> dict[str, Any] | None:
    sport_roles = get_athlete_sport_roles(athlete_id)
    running_ids = [
        sport_id
        for sport_id, role in sport_roles.items()
        if role == "running"
    ]

    if not running_ids:
        return None

    tolerance = _distance_tolerance(goal_distance_km)
    minimum_distance = goal_distance_km * (1.0 - tolerance)
    maximum_distance = goal_distance_km * (1.0 + tolerance)
    placeholders = ",".join("?" for _ in running_ids)

    conn = get_connection()
    cursor = conn.cursor()

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
          AND a.distance_m BETWEEN ? AND ?
          AND COALESCE(a.elapsed_time_s, a.moving_time_s) IS NOT NULL
        ORDER BY COALESCE(a.elapsed_time_s, a.moving_time_s) ASC
        """,
        (
            athlete_id,
            *running_ids,
            minimum_distance,
            maximum_distance,
        ),
    )
    rows = cursor.fetchall()
    conn.close()

    confirmed = []
    quality = []

    for row in rows:
        raw = _safe_json(row[10])
        elapsed = float(row[5]) if row[5] is not None else None
        moving = float(row[4]) if row[4] is not None else None
        race_time_s = _race_time(elapsed, moving, raw)

        if race_time_s is None:
            continue

        signals = score_race_evidence(
            title=row[2] or "",
            distance_km=float(row[3]),
            moving_time_s=moving,
            elapsed_time_s=elapsed,
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

        candidate = {
            "activity_id": int(row[0]),
            "date": row[1],
            "title": row[2] or "Race effort",
            "distance_km": float(row[3]),
            "time_s": float(race_time_s),
            "classification": signals.classification,
            "confidence": signals.confidence,
        }

        if signals.classification == "confirmed_race":
            confirmed.append(candidate)
        elif signals.classification == "race_quality_effort":
            quality.append(candidate)

    pool = confirmed or quality

    if not pool:
        return None

    return min(pool, key=lambda item: item["time_s"])


def find_race_pb(
    *,
    athlete_id: int,
    goal_distance_km: float,
) -> dict[str, Any] | None:
    """Public read-only access to the verified PB selected by PB Shape."""
    return _find_pb(
        athlete_id=athlete_id,
        goal_distance_km=goal_distance_km,
    )


def _empty_result(
    *,
    athlete_id: int,
    current_activity_id: int,
    goal_distance_km: float,
    status: str,
    limitation: str,
) -> PBShapeResult:
    return PBShapeResult(
        athlete_id=athlete_id,
        current_activity_id=current_activity_id,
        goal_distance_km=goal_distance_km,
        pb_activity_id=None,
        pb_date=None,
        pb_time_s=None,
        pb_distance_km=None,
        pb_title=None,
        pb_classification=None,
        pb_workout_count=0,
        current_shape_percent=None,
        central_seconds=None,
        low_seconds=None,
        high_seconds=None,
        confidence=0.0,
        status=status,
        matches=(),
        limitations=(limitation,),
    )


def build_pb_shape(
    *,
    athlete_id: int,
    current_activity_id: int,
    goal_distance_km: float,
) -> PBShapeResult:
    if goal_distance_km <= 0:
        return _empty_result(
            athlete_id=athlete_id,
            current_activity_id=current_activity_id,
            goal_distance_km=goal_distance_km,
            status="no_goal",
            limitation="No valid goal distance was available.",
        )

    pb = _find_pb(
        athlete_id=athlete_id,
        goal_distance_km=goal_distance_km,
    )

    if pb is None:
        return _empty_result(
            athlete_id=athlete_id,
            current_activity_id=current_activity_id,
            goal_distance_km=goal_distance_km,
            status="no_pb",
            limitation=(
                "No confirmed PB-quality race was found at this distance."
            ),
        )

    pb_date = _as_date(pb["date"])

    if pb_date is None:
        return _empty_result(
            athlete_id=athlete_id,
            current_activity_id=current_activity_id,
            goal_distance_km=goal_distance_km,
            status="invalid_pb_date",
            limitation="The PB date could not be read.",
        )

    conn = get_connection()
    cursor = conn.cursor()
    create_workout_library_tables(cursor)

    cursor.execute(
        """
        SELECT
            activity_id,
            activity_date,
            workout_signature,
            phase_json,
            execution_score,
            recognition_confidence,
            phase_confidence
        FROM workout_library
        WHERE athlete_id = ?
          AND activity_id = ?
        """,
        (athlete_id, current_activity_id),
    )
    current_row = cursor.fetchone()

    if current_row is None:
        conn.close()
        return PBShapeResult(
            athlete_id=athlete_id,
            current_activity_id=current_activity_id,
            goal_distance_km=goal_distance_km,
            pb_activity_id=pb["activity_id"],
            pb_date=pb["date"],
            pb_time_s=pb["time_s"],
            pb_distance_km=pb["distance_km"],
            pb_title=pb["title"],
            pb_classification=pb["classification"],
            pb_workout_count=0,
            current_shape_percent=None,
            central_seconds=None,
            low_seconds=None,
            high_seconds=None,
            confidence=0.0,
            status="current_workout_missing",
            matches=(),
            limitations=(
                "The selected current workout is not in the Workout Library.",
            ),
        )

    window_start = (
        pb_date - datetime.timedelta(days=PB_WINDOW_END_DAYS)
    ).isoformat()
    window_end = (
        pb_date - datetime.timedelta(days=PB_WINDOW_START_DAYS)
    ).isoformat()

    cursor.execute(
        """
        SELECT
            activity_id,
            activity_date,
            workout_signature,
            phase_json,
            execution_score,
            recognition_confidence,
            phase_confidence
        FROM workout_library
        WHERE athlete_id = ?
          AND activity_date BETWEEN ? AND ?
          AND activity_id <> ?
        ORDER BY activity_date DESC
        """,
        (
            athlete_id,
            window_start,
            window_end,
            current_activity_id,
        ),
    )
    pb_rows = cursor.fetchall()
    conn.close()

    if not pb_rows:
        return PBShapeResult(
            athlete_id=athlete_id,
            current_activity_id=current_activity_id,
            goal_distance_km=goal_distance_km,
            pb_activity_id=pb["activity_id"],
            pb_date=pb["date"],
            pb_time_s=pb["time_s"],
            pb_distance_km=pb["distance_km"],
            pb_title=pb["title"],
            pb_classification=pb["classification"],
            pb_workout_count=0,
            current_shape_percent=None,
            central_seconds=None,
            low_seconds=None,
            high_seconds=None,
            confidence=0.20,
            status="no_pb_workouts",
            matches=(),
            limitations=(
                "No recognised workouts were found 14-28 days before the PB.",
            ),
        )

    matches = []

    for row in pb_rows:
        comparison = compare_workout_phase_json(
            current_row[3],
            row[3],
            current_execution_score=current_row[4],
            candidate_execution_score=row[4],
        )

        similarity = float(comparison["similarity"])

        if similarity < 0.35:
            continue

        pace_ratio = comparison.get("pace_ratio")
        volume_ratio = comparison.get("volume_ratio")

        # Damp workout differences heavily. A 2% faster matched workout
        # should not claim a full 2% faster race without direct race evidence.
        pace_adjustment = (
            (float(pace_ratio) - 1.0) * 0.35
            if pace_ratio is not None
            else 0.0
        )
        volume_adjustment = (
            (1.0 - min(max(float(volume_ratio), 0.70), 1.30))
            * 0.08
            if volume_ratio is not None
            else 0.0
        )

        total_adjustment = max(
            min(pace_adjustment + volume_adjustment, 0.05),
            -0.05,
        )
        estimate = pb["time_s"] * (1.0 + total_adjustment)

        evidence_confidence = (
            similarity * 0.65
            + float(row[5] or 0.0) * 0.20
            + float(row[6] or 0.0) * 0.15
        )
        weight = math.pow(max(similarity, 0.01), 3.0)

        matches.append(
            {
                "activity_id": int(row[0]),
                "date": row[1],
                "signature": row[2],
                "similarity": round(similarity, 4),
                "pace_ratio": (
                    round(float(pace_ratio), 4)
                    if pace_ratio is not None
                    else None
                ),
                "volume_ratio": (
                    round(float(volume_ratio), 4)
                    if volume_ratio is not None
                    else None
                ),
                "estimated_seconds": round(estimate, 1),
                "confidence": round(evidence_confidence, 4),
                "weight": round(weight, 5),
                "reasons": list(comparison["reasons"]),
                "differences": list(comparison["differences"]),
            }
        )

    matches.sort(
        key=lambda item: (
            item["similarity"],
            item["confidence"],
        ),
        reverse=True,
    )
    matches = matches[:MAX_PB_WORKOUTS]

    if not matches:
        return PBShapeResult(
            athlete_id=athlete_id,
            current_activity_id=current_activity_id,
            goal_distance_km=goal_distance_km,
            pb_activity_id=pb["activity_id"],
            pb_date=pb["date"],
            pb_time_s=pb["time_s"],
            pb_distance_km=pb["distance_km"],
            pb_title=pb["title"],
            pb_classification=pb["classification"],
            pb_workout_count=0,
            current_shape_percent=None,
            central_seconds=None,
            low_seconds=None,
            high_seconds=None,
            confidence=0.25,
            status="no_similar_pb_workouts",
            matches=(),
            limitations=(
                "PB-window workouts existed, but none were sufficiently "
                "similar to the current representative workout.",
            ),
        )

    total_weight = sum(item["weight"] for item in matches)
    central = sum(
        item["estimated_seconds"] * item["weight"]
        for item in matches
    ) / total_weight

    average_similarity = sum(
        item["similarity"] * item["weight"]
        for item in matches
    ) / total_weight
    average_evidence = sum(
        item["confidence"] * item["weight"]
        for item in matches
    ) / total_weight
    sample_factor = min(len(matches) / 3.0, 1.0)

    confidence = min(
        average_similarity * 0.55
        + average_evidence * 0.25
        + sample_factor * 0.20,
        0.93,
    )

    uncertainty = max(
        central * (0.012 + (1.0 - confidence) * 0.035),
        8.0,
    )
    shape_percent = pb["time_s"] / central * 100.0

    if shape_percent >= 101.0:
        status = "ahead_of_pb_shape"
    elif shape_percent >= 98.5:
        status = "at_pb_shape"
    elif shape_percent >= 95.0:
        status = "close_to_pb_shape"
    else:
        status = "below_pb_shape"

    return PBShapeResult(
        athlete_id=athlete_id,
        current_activity_id=current_activity_id,
        goal_distance_km=goal_distance_km,
        pb_activity_id=pb["activity_id"],
        pb_date=pb["date"],
        pb_time_s=pb["time_s"],
        pb_distance_km=pb["distance_km"],
        pb_title=pb["title"],
        pb_classification=pb["classification"],
        pb_workout_count=len(matches),
        current_shape_percent=round(shape_percent, 1),
        central_seconds=round(central, 1),
        low_seconds=round(max(central - uncertainty, 1.0), 1),
        high_seconds=round(central + uncertainty, 1),
        confidence=round(confidence, 4),
        status=status,
        matches=tuple(matches),
        limitations=(
            "PB Shape compares the current representative workout with "
            "recognised workouts 7-28 days before the athlete's PB.",
            "The week immediately before the PB is deliberately excluded "
            "because it often contains taper or easier sessions.",
            "Weather, hills, trail surface and race intent are not yet "
            "normalised.",
        ),
    )


def pb_shape_to_dict(result: PBShapeResult) -> dict[str, Any]:
    return {
        "athlete_id": result.athlete_id,
        "current_activity_id": result.current_activity_id,
        "goal_distance_km": result.goal_distance_km,
        "pb_activity_id": result.pb_activity_id,
        "pb_date": result.pb_date,
        "pb_time_s": result.pb_time_s,
        "pb_distance_km": result.pb_distance_km,
        "pb_title": result.pb_title,
        "pb_classification": result.pb_classification,
        "pb_workout_count": result.pb_workout_count,
        "current_shape_percent": result.current_shape_percent,
        "central_seconds": result.central_seconds,
        "low_seconds": result.low_seconds,
        "high_seconds": result.high_seconds,
        "confidence": result.confidence,
        "status": result.status,
        "matches": list(result.matches),
        "limitations": list(result.limitations),
        "method": "PB Shape Engine",
        "model_version": 1,
    }

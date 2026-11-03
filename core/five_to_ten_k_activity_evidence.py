"""Imported running evidence for an active 5K -> 10K journey."""
from __future__ import annotations
from dataclasses import dataclass
import datetime, json
from core.database import get_athlete_sport_roles, get_connection
from core.runner_journey import FIVE_TO_TEN_K, get_active_runner_journey

@dataclass(frozen=True)
class FiveToTenKActivityEvidence:
    activity_id: int
    activity_date: str
    title: str
    distance_km: float
    moving_time_s: float
    likely_completed_as_planned: bool
    completed_10k: bool
    match_reason: str

def _distance_km(value) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return number / 1000.0 if number > 250.0 else number

def _reviewed_activity_ids(journey_id: int, athlete_id: int) -> set[int]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT evidence_json FROM runner_journey_events
               WHERE journey_id=? AND athlete_id=? AND event_type='progress_review'
               ORDER BY id DESC""",
            (int(journey_id), int(athlete_id)),
        ).fetchall()
    finally:
        conn.close()
    result = set()
    for (text,) in rows:
        try:
            value = int(json.loads(text or "{}").get("activity_id") or 0)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if value > 0:
            result.add(value)
    return result

def find_latest_five_to_ten_k_activity_evidence(
    athlete_id: int,
    *,
    planned_distance_km: float | None = None,
    today: datetime.date | None = None,
    max_age_days: int = 7,
) -> FiveToTenKActivityEvidence | None:
    today = today or datetime.date.today()
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None or journey.journey_type != FIVE_TO_TEN_K:
        return None
    try:
        started = datetime.date.fromisoformat(str(journey.started_at)[:10])
    except (TypeError, ValueError):
        started = today - datetime.timedelta(days=max_age_days)
    cutoff = max(started, today - datetime.timedelta(days=max_age_days))
    reviewed = _reviewed_activity_ids(journey.id, int(athlete_id))
    roles = get_athlete_sport_roles(int(athlete_id))

    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, activity_date, title, sport_id, type_id,
                      distance_m, moving_time_s, elapsed_time_s
               FROM activities
               WHERE athlete_id=? AND activity_date>=? AND activity_date<=?
               ORDER BY activity_datetime DESC, id DESC""",
            (int(athlete_id), cutoff.isoformat(), today.isoformat()),
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        activity_id, activity_date, title, sport_id, type_id, distance, moving, elapsed = row
        activity_id = int(activity_id)
        if activity_id in reviewed:
            continue
        sport = str(sport_id or "")
        role = str(roles.get(sport) or "").lower()
        text = f"{sport} {type_id or ''} {title or ''}".lower()
        if not (role == "running" or sport.lower() == "running" or "run" in text):
            continue
        km = _distance_km(distance)
        duration = float(moving or elapsed or 0.0)
        if km <= 0 and duration <= 0:
            continue
        planned = float(planned_distance_km or 0.0)
        likely = (km >= planned * 0.80) if planned > 0 else duration >= 20 * 60
        reason = (
            f"{km:.2f} km · {round(duration/60.0)} min recorded"
            + (" · consistent with the planned session" if likely else "")
        )
        return FiveToTenKActivityEvidence(
            activity_id=activity_id,
            activity_date=str(activity_date or ""),
            title=str(title or "Recorded run"),
            distance_km=km,
            moving_time_s=duration,
            likely_completed_as_planned=likely,
            completed_10k=km >= 9.95,
            match_reason=reason,
        )
    return None

"""Imported activity evidence for the adaptive Couch -> 5K journey.

This module is deliberately conservative. It can identify a recent, unreviewed
run/walk activity and pre-fill objective facts such as duration, distance and
whether 5K was completed. Subjective evidence (difficulty, pain) always remains
with the athlete.

An activity can only be suggested once: reviewed activity ids are stored in
runner_journey_events.evidence_json and excluded from future matching.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json

from core.database import get_athlete_sport_roles, get_connection
from core.runner_journey import COUCH_TO_5K, RunnerJourney, get_active_runner_journey


@dataclass(frozen=True)
class BeginnerActivityEvidence:
    activity_id: int
    activity_date: str
    title: str
    sport_id: str
    distance_km: float
    moving_time_s: float
    planned_duration_s: int
    likely_completed_as_planned: bool
    completed_5k: bool
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
            """SELECT evidence_json
               FROM runner_journey_events
               WHERE journey_id = ? AND athlete_id = ?
                 AND event_type = 'progress_review'
               ORDER BY id DESC""",
            (int(journey_id), int(athlete_id)),
        ).fetchall()
    finally:
        conn.close()

    reviewed: set[int] = set()
    for (payload_text,) in rows:
        try:
            payload = json.loads(payload_text or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        try:
            activity_id = int(payload.get("activity_id"))
        except (TypeError, ValueError):
            continue
        if activity_id > 0:
            reviewed.add(activity_id)
    return reviewed


def _eligible_sport(
    sport_id: str,
    type_id: str,
    title: str,
    *,
    stage: str,
    roles: dict[str, str],
) -> bool:
    sport = str(sport_id or "")
    role = str(roles.get(sport) or "").lower()
    text = f"{sport} {type_id or ''} {title or ''}".lower()

    if role == "running" or sport.lower() == "running":
        return True

    # Walking foundation legitimately may be recorded as a walk.
    if stage == "walking_foundation":
        return (
            role == "walking"
            or sport.lower() == "walking"
            or "walk" in text
        )

    return False


def find_latest_beginner_activity_evidence(
    athlete_id: int,
    *,
    planned_duration_s: int,
    today: datetime.date | None = None,
    max_age_days: int = 7,
) -> BeginnerActivityEvidence | None:
    """Return the newest plausible unreviewed activity for the active journey."""
    today = today or datetime.date.today()
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None or journey.journey_type != COUCH_TO_5K:
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
               WHERE athlete_id = ?
                 AND activity_date >= ?
                 AND activity_date <= ?
               ORDER BY activity_datetime DESC, id DESC""",
            (int(athlete_id), cutoff.isoformat(), today.isoformat()),
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        (
            activity_id,
            activity_date,
            title,
            sport_id,
            type_id,
            distance_value,
            moving_time,
            elapsed_time,
        ) = row

        activity_id = int(activity_id)
        if activity_id in reviewed:
            continue
        if not _eligible_sport(
            str(sport_id or ""),
            str(type_id or ""),
            str(title or ""),
            stage=journey.current_stage,
            roles=roles,
        ):
            continue

        duration = float(moving_time or elapsed_time or 0.0)
        if duration <= 0:
            continue

        distance = _distance_km(distance_value)
        planned = max(int(planned_duration_s or 0), 1)

        # A conservative completion suggestion. This only pre-fills the form;
        # the athlete still confirms before any progression decision.
        ratio = duration / planned
        likely_complete = ratio >= 0.80
        completed_5k = distance >= 4.95

        reason_bits = [
            f"{round(duration / 60.0)} min recorded",
            f"{distance:.2f} km" if distance > 0 else "distance unavailable",
        ]
        if likely_complete:
            reason_bits.append("duration is consistent with the planned session")
        else:
            reason_bits.append("shorter than the planned session")

        return BeginnerActivityEvidence(
            activity_id=activity_id,
            activity_date=str(activity_date or ""),
            title=str(title or "Recorded activity"),
            sport_id=str(sport_id or ""),
            distance_km=distance,
            moving_time_s=duration,
            planned_duration_s=planned,
            likely_completed_as_planned=likely_complete,
            completed_5k=completed_5k,
            match_reason=" · ".join(reason_bits),
        )

    return None

"""Real-data entry assessment for the 5K -> 10K Runner Journey."""
from __future__ import annotations
from dataclasses import dataclass
import datetime
from core.database import get_connection, get_athlete_sport_roles
from core.runner_journey import FiveToTenKAssessment

@dataclass(frozen=True)
class FiveToTenKRecentEvidence:
    recent_runs_per_week: int
    recent_weekly_km: float
    longest_recent_run_km: float
    recent_run_count: int
    lookback_days: int = 28

def _distance_km(value) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return number / 1000.0 if number > 250.0 else number

def build_five_to_ten_k_recent_evidence(athlete_id: int, *, today=None, lookback_days: int = 28):
    today = today or datetime.date.today()
    start = today - datetime.timedelta(days=max(int(lookback_days), 7) - 1)
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT activity_date, distance_m, sport_id, type_id, title
               FROM activities
               WHERE athlete_id=? AND activity_date>=? AND activity_date<=?
               ORDER BY activity_datetime DESC, id DESC""",
            (int(athlete_id), start.isoformat(), today.isoformat()),
        ).fetchall()
    finally:
        conn.close()
    roles = get_athlete_sport_roles(int(athlete_id))

    distances = []
    for _date, distance_m, sport_id, type_id, title in rows:
        sport = str(sport_id or "")
        role = str(roles.get(sport) or "").lower()
        text = f"{sport} {type_id or ''} {title or ''}".lower()

        is_running = (
            role == "running"
            or sport.lower() == "running"
            or " run" in f" {text}"
            or text.startswith("run")
        )
        if not is_running:
            continue

        km = _distance_km(distance_m)
        if km > 0:
            distances.append(km)
    weeks = max(lookback_days / 7.0, 1.0)
    return FiveToTenKRecentEvidence(
        recent_runs_per_week=round(len(distances) / weeks),
        recent_weekly_km=sum(distances) / weeks if distances else 0.0,
        longest_recent_run_km=max(distances, default=0.0),
        recent_run_count=len(distances),
        lookback_days=lookback_days,
    )

def build_five_to_ten_k_assessment(athlete_id: int, *, sessions_per_week: int,
                                   goal_mode: str = "complete_10k",
                                   target_date: str | None = None,
                                   today=None):
    evidence = build_five_to_ten_k_recent_evidence(athlete_id, today=today)
    assessment = FiveToTenKAssessment(
        can_complete_5k=evidence.longest_recent_run_km >= 4.95,
        recent_runs_per_week=evidence.recent_runs_per_week,
        recent_weekly_km=evidence.recent_weekly_km,
        longest_recent_run_km=evidence.longest_recent_run_km,
        sessions_per_week=int(sessions_per_week),
        goal_mode=goal_mode,
        target_date=target_date,
    )
    return assessment, evidence

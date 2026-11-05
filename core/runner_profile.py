"""User-declared running context; never infer injury or override capability."""
from core.database import get_connection, create_runner_profiles_table

EXPERIENCE = frozenset({"getting_started", "developing", "established", "experienced"})
TRAINING_STATUS = frozenset({"training", "returning", "rebuilding", "paused"})


def get_runner_profile(athlete_id):
    with get_connection() as conn:
        create_runner_profiles_table(conn.cursor())
        row = conn.execute(
            "SELECT experience, training_status, sessions_per_week FROM athlete_runner_profiles WHERE athlete_id = ?",
            (athlete_id,),
        ).fetchone()
    return None if row is None else dict(zip(("experience", "training_status", "sessions_per_week"), row))


def save_runner_profile(athlete_id, *, experience=None, training_status=None, sessions_per_week=None):
    if experience is not None and experience not in EXPERIENCE:
        raise ValueError("Invalid experience")
    if training_status is not None and training_status not in TRAINING_STATUS:
        raise ValueError("Invalid training status")
    if sessions_per_week is not None and (type(sessions_per_week) is not int or not 1 <= sessions_per_week <= 7):
        raise ValueError("Sessions per week must be an integer from 1 to 7")
    with get_connection() as conn:
        create_runner_profiles_table(conn.cursor())
        conn.execute(
            """INSERT INTO athlete_runner_profiles (athlete_id, experience, training_status, sessions_per_week)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(athlete_id) DO UPDATE SET
                 experience=COALESCE(excluded.experience, experience),
                 training_status=COALESCE(excluded.training_status, training_status),
                 sessions_per_week=COALESCE(excluded.sessions_per_week, sessions_per_week),
                 updated_at=CURRENT_TIMESTAMP""",
            (athlete_id, experience, training_status, sessions_per_week),
        )
    return get_runner_profile(athlete_id)

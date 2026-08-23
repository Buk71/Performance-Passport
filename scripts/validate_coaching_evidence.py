"""Inspect real-athlete coaching evidence without modifying source activities.

Run from the project root with ``python scripts/validate_coaching_evidence.py``.
The normal application database is used; decoded-workout caches may refresh.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_connection, initialise_database
from core.home_predictions import build_home_predictions
from core.splits import parse_splits, recognise_workout


def main() -> None:
    initialise_database()
    connection = get_connection()
    athletes = connection.execute(
        "SELECT id, first_name, last_name FROM athletes ORDER BY id"
    ).fetchall()
    for athlete_id, first_name, last_name in athletes:
        prediction = build_home_predictions(int(athlete_id))
        print(f"\n{first_name} {last_name} | {prediction.goal_name}", flush=True)
        for coach in prediction.coach_positions:
            print(f"  {coach.title}: {coach.predicted_seconds:.1f}s", flush=True)
        rows = connection.execute(
            """SELECT id, activity_date, title, raw_json FROM activities
               WHERE athlete_id=? ORDER BY activity_datetime DESC LIMIT 12""",
            (athlete_id,),
        ).fetchall()
        for activity_id, activity_date, title, payload in rows:
            if not payload:
                continue
            raw = json.loads(payload)
            workout = recognise_workout(
                parse_splits(raw.get("splits") or raw.get("splitsCustom"))
            )
            if workout.rep_count:
                print(
                    f"  {activity_date} #{activity_id} {title or 'Activity'}: "
                    f"{workout.rep_count} reps at "
                    f"{workout.average_rep_pace_s_per_km:.1f}s/km",
                    flush=True,
                )
    connection.close()


if __name__ == "__main__":
    main()

"""Print selected, recent, and excluded Workout Coach evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.coach_brain import CoachBrain


athlete_ids = tuple(map(int, sys.argv[1:])) if len(sys.argv) > 1 else (1, 3, 4)
for athlete_id in athlete_ids:
    brain = CoachBrain(athlete_id)
    evidence = brain.build_evidence(brain.get_goal())
    workout = next(item for item in evidence.items if item.key == "workout")
    metadata = workout.metadata
    print(f"\nAthlete {athlete_id}: {workout.predicted_seconds}", flush=True)
    for key in (
        "activity_id", "activity_date", "selected_title", "prediction_source",
        "session_counts", "latest_workout", "best_workout",
        "distance_relevant_prediction", "similarity_prediction",
    ):
        value = metadata.get(key)
        if value is not None:
            print(f"  {key}: {json.dumps(value, default=str)[:950]}", flush=True)

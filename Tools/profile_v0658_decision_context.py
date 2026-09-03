"""Profile Journal decision-context cold path.

This is diagnostic only. It times the internal evidence builders used by
journal._build_decision_context so we can identify which source should get the
next horizon-aware optimisation.

Run:
    python tools/profile_v0658_decision_context.py --athlete 1
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import initialise_database
from core.journal import _run_profiles
from core.performance_recognition import build_recognition_index
from core.home_summary import build_home_summary
from core.home_predictions import build_home_predictions
from core.distance_prediction_outlook import build_distance_prediction_outlook
from core.progress_coach import build_progress_coach_detail
from core.recovery_coach import build_recovery_coach_detail
from core.learning_coach import build_learning_coach_detail
from core.coaching_team import build_coaching_team_detail


def _time(label, fn):
    started = time.perf_counter()
    value = fn()
    elapsed = time.perf_counter() - started
    print(f"  {label:30s} {elapsed:8.2f}s")
    return value, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    args = parser.parse_args()

    initialise_database()
    athlete_id = int(args.athlete)

    print("Performance Passport v0.65.8 decision-context profile")
    print(f"Athlete: {athlete_id}")
    print("Diagnostic only; production behaviour is unchanged.\n")

    timings = {}

    runs, timings["run_profiles"] = _time(
        "run_profiles",
        lambda: _run_profiles(athlete_id),
    )

    recognition, timings["recognition_index"] = _time(
        "recognition_index",
        lambda: build_recognition_index(
            runs,
            athlete_id=athlete_id,
        ),
    )

    _, timings["home_summary"] = _time(
        "home_summary",
        lambda: build_home_summary(athlete_id),
    )

    predictions, timings["home_predictions"] = _time(
        "home_predictions",
        lambda: build_home_predictions(athlete_id),
    )

    _, timings["distance_outlook"] = _time(
        "distance_outlook",
        lambda: build_distance_prediction_outlook(
            athlete_id,
            active_predictions=predictions,
        ),
    )

    _, timings["progress_coach"] = _time(
        "progress_coach",
        lambda: build_progress_coach_detail(athlete_id),
    )

    _, timings["recovery_coach"] = _time(
        "recovery_coach",
        lambda: build_recovery_coach_detail(athlete_id),
    )

    _, timings["learning_coach"] = _time(
        "learning_coach",
        lambda: build_learning_coach_detail(athlete_id),
    )

    _, timings["coaching_summary"] = _time(
        "coaching_summary",
        lambda: build_coaching_team_detail(athlete_id),
    )

    print("\n=== Ranked decision-context dependencies ===")
    for key, seconds in sorted(
        timings.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {key:30s} {seconds:8.2f}s")

    print(f"\nRun profiles loaded: {len(runs):,}")
    print(f"Recognition records: {len(recognition):,}")
    print(
        "\nThe largest uncached dependency should be optimised next. "
        "Cached race/training objects may show near-zero here, which is useful: "
        "we are isolating the remaining raw-history work."
    )


if __name__ == "__main__":
    main()

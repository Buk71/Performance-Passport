"""Validate duplicate evidence removal in Journal decision context."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.coach_brain import CoachBrain
from core.database import initialise_database


def _snapshot(prediction):
    return (
        prediction.available,
        prediction.predicted_seconds,
        prediction.confidence,
        prediction.goal_id,
        prediction.gap_seconds,
        prediction.explanation,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    args = parser.parse_args()
    initialise_database()

    athlete_id = int(args.athlete)

    print("Performance Passport v0.65.9 shared-evidence validation")
    print(f"Athlete: {athlete_id}\n")

    old_brain = CoachBrain(athlete_id)
    started = time.perf_counter()
    old_bundle = old_brain.build_evidence()
    old_prediction = old_brain.goal_prediction()
    old_s = time.perf_counter() - started

    new_brain = CoachBrain(athlete_id)
    started = time.perf_counter()
    new_bundle = new_brain.build_evidence()
    new_prediction = new_brain.goal_prediction(evidence=new_bundle)
    new_s = time.perf_counter() - started

    parity = _snapshot(old_prediction) == _snapshot(new_prediction)

    print(f"Old duplicate path:  {old_s:.2f}s")
    print(f"Shared evidence path:{new_s:.2f}s")
    print(f"Speed-up:            {old_s / new_s:.2f}x" if new_s else "Speed-up: inf")
    print(f"Prediction parity:   {parity}")
    print(
        f"Evidence item count: old={len(old_bundle.items)} "
        f"new={len(new_bundle.items)}"
    )

    print("\nRESULT")
    print(
        "PASS — duplicate evidence build removed with identical prediction."
        if parity
        else "REVIEW — prediction changed; do not proceed."
    )


if __name__ == "__main__":
    main()

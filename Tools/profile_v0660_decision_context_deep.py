"""Deep-profile Journal decision context after v0.65.9 shared evidence."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.coach_brain import CoachBrain
from core.database import get_active_goal, get_connection, initialise_database
from core.evidence_providers import (
    RaceEvidenceProvider,
    ThresholdEvidenceProvider,
    WorkoutEvidenceProvider,
)
from core.evidence_providers.base import EvidenceContext
from core.easy_run_coach import build_easy_run_coach
from core.journal import _run_profiles
from core.evidence_engine import build_athlete_evidence_profile
from core.performance_dna import build_performance_dna
from core.coach_consensus import build_coach_consensus
from core.capability import build_capability


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
    goal = get_active_goal(athlete_id)
    context = EvidenceContext(athlete_id=athlete_id, goal=goal)

    print("Performance Passport v0.66.0a decision-context deep profile")
    print(f"Athlete: {athlete_id}")
    print("Diagnostic only; production behaviour is unchanged.\n")

    timings = {}

    runs, timings["run_profiles"] = _time(
        "run_profiles",
        lambda: _run_profiles(athlete_id),
    )

    conn = get_connection()
    try:
        evidence_profile, timings["athlete_evidence_profile"] = _time(
            "athlete_evidence_profile",
            lambda: build_athlete_evidence_profile(
                conn,
                athlete_id=athlete_id,
            ),
        )
    finally:
        conn.close()

    brain = CoachBrain(athlete_id, providers=())

    bundle, timings["foundation_evidence"] = _time(
        "foundation_evidence",
        brain.build_foundation_evidence,
    )

    workout, timings["workout_provider"] = _time(
        "workout_provider",
        lambda: WorkoutEvidenceProvider().build(context),
    )
    bundle = bundle.with_item(workout)

    race, timings["race_provider"] = _time(
        "race_provider",
        lambda: RaceEvidenceProvider().build(context),
    )
    bundle = bundle.with_item(race)

    threshold, timings["threshold_provider"] = _time(
        "threshold_provider",
        lambda: ThresholdEvidenceProvider().build(context),
    )
    bundle = bundle.with_item(threshold)

    prediction, timings["prediction_engine"] = _time(
        "prediction_engine",
        lambda: brain.prediction_engine.predict_goal(
            athlete_id=athlete_id,
            goal=goal,
            evidence=bundle,
        ),
    )

    easy, timings["easy_run_coach"] = _time(
        "easy_run_coach",
        lambda: build_easy_run_coach(
            runs,
            evidence_profile=evidence_profile,
        ),
    )

    predicted_seconds = (
        prediction.predicted_seconds if prediction.available else None
    )

    dna, timings["performance_dna"] = _time(
        "performance_dna",
        lambda: build_performance_dna(
            bundle,
            consensus_prediction_s=predicted_seconds,
            easy_run_coach=easy,
        ),
    )

    consensus, timings["coach_consensus"] = _time(
        "coach_consensus",
        lambda: build_coach_consensus(
            dna,
            consensus_prediction_s=predicted_seconds,
        ),
    )

    _, timings["capability"] = _time(
        "capability",
        lambda: build_capability(
            predicted_seconds=predicted_seconds,
            prediction_confidence=(
                prediction.confidence if prediction.available else 0.0
            ),
            performance_dna=dna,
            coach_consensus=consensus,
            target_seconds=(
                goal["target_time_s"] if goal is not None else None
            ),
        ),
    )

    print("\n=== Ranked decision-context internals ===")
    for key, seconds in sorted(
        timings.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {key:30s} {seconds:8.2f}s")

    print(f"\nRun profiles loaded: {len(runs):,}")


if __name__ == "__main__":
    main()

"""Shadow-validate a 365-day WorkoutEvidenceProvider horizon.

Production remains full history because WorkoutEvidenceProvider() defaults to
history_days=None. This tool compares the existing full-history provider with
the proposed 365-day raw scan.

It deliberately separates coaching-critical parity from historical bookkeeping
counts. Old recognised-workout totals/session-count diagnostics may differ
because the horizon avoids processing old raw activities; prediction and coach
selection must not differ.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_active_goal, initialise_database
from core.evidence_providers.base import EvidenceContext
from core.evidence_providers.workout import WorkoutEvidenceProvider


def _top_ids(item):
    return [
        int(row["activity_id"])
        for row in item.metadata.get("top_workouts", [])
    ]


def _snapshot(item):
    best = item.metadata.get("best_evidence") or {}
    latest = item.metadata.get("latest_workout") or {}
    prediction = item.metadata.get("workout_prediction") or {}
    trend = item.metadata.get("trend") or {}

    return {
        "status": str(item.status.value if hasattr(item.status, "value") else item.status),
        "summary": item.summary,
        "confidence": item.confidence,
        "predicted_seconds": item.predicted_seconds,
        "weight": item.weight,
        "prediction_source": item.metadata.get("prediction_source"),
        "prediction_confidence": item.metadata.get("prediction_confidence"),
        "recognition_confidence": item.metadata.get("recognition_confidence"),
        "latest_activity_id": item.metadata.get("activity_id"),
        "latest_title": latest.get("title"),
        "latest_representative": latest.get("representative"),
        "best_date": best.get("date"),
        "best_title": best.get("title"),
        "best_trust_score": best.get("trust_score"),
        "top_workout_ids": _top_ids(item),
        "prediction_central_seconds": prediction.get("central_seconds"),
        "prediction_low_seconds": prediction.get("low_seconds"),
        "prediction_high_seconds": prediction.get("high_seconds"),
        "prediction_confidence_inner": prediction.get("confidence"),
        "trend_label": trend.get("label"),
        "trend_change": trend.get("change_seconds_per_km"),
        "trend_sample_size": trend.get("sample_size"),
    }


def _run(provider, context):
    started = time.perf_counter()
    result = provider.build(context)
    return result, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    initialise_database()
    athlete_id = int(args.athlete)
    goal = get_active_goal(athlete_id)
    context = EvidenceContext(athlete_id=athlete_id, goal=goal)

    print("Performance Passport v0.66.1 Workout Horizon shadow validation")
    print(f"Athlete: {athlete_id}")
    print(f"Proposed horizon: {args.days} days")
    print("Production default remains full history.\n")

    full, full_s = _run(
        WorkoutEvidenceProvider(history_days=None),
        context,
    )
    horizon, horizon_s = _run(
        WorkoutEvidenceProvider(history_days=args.days),
        context,
    )

    full_snapshot = _snapshot(full)
    horizon_snapshot = _snapshot(horizon)
    parity = full_snapshot == horizon_snapshot

    full_h = full.metadata.get("history_horizon", {})
    horizon_h = horizon.metadata.get("history_horizon", {})

    print("=== TIMING ===")
    print(f"  Full history: {full_s:.2f}s")
    print(f"  Horizon:      {horizon_s:.2f}s")
    if horizon_s > 0:
        print(f"  Speed-up:     {full_s / horizon_s:.2f}x")

    print("\n=== RAW INPUT ===")
    print(f"  Full rows loaded:    {full_h.get('raw_rows_loaded')}")
    print(f"  Horizon rows loaded: {horizon_h.get('raw_rows_loaded')}")
    print(f"  Horizon cutoff:      {horizon_h.get('cutoff_date')}")

    print("\n=== COACHING PARITY ===")
    print(f"  Exact critical parity: {parity}")

    if not parity:
        print("\nDifferences:")
        for key in full_snapshot:
            if full_snapshot[key] != horizon_snapshot[key]:
                print(
                    f"  {key}: full={full_snapshot[key]!r} "
                    f"horizon={horizon_snapshot[key]!r}"
                )

    print("\n=== BOOKKEEPING (allowed to differ in shadow) ===")
    print(
        "  recognised_workout_count: "
        f"full={full.metadata.get('recognised_workout_count')} "
        f"horizon={horizon.metadata.get('recognised_workout_count')}"
    )
    print(
        "  sample_size: "
        f"full={full.sample_size} horizon={horizon.sample_size}"
    )

    print("\n=== RESULT ===")
    if parity:
        print(
            "PASS — 365-day raw horizon preserves coaching-critical Workout "
            "Coach output for this athlete."
        )
    else:
        print(
            "REVIEW — horizon changed coaching output. Do not make it the "
            "production default yet."
        )


if __name__ == "__main__":
    main()

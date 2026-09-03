"""Validate the production Workout Coach horizon.

Production default is now 365 days. This tool confirms:
1) default provider == explicit 365-day provider exactly;
2) full-history path remains available with history_days=None;
3) critical coaching fields still match full history for the athlete.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_active_goal, initialise_database
from core.evidence_providers.base import EvidenceContext
from core.evidence_providers.workout import WorkoutEvidenceProvider


def _snapshot(item):
    best = item.metadata.get("best_evidence") or {}
    latest = item.metadata.get("latest_workout") or {}
    prediction = item.metadata.get("workout_prediction") or {}
    trend = item.metadata.get("trend") or {}
    return {
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
        "top_workout_ids": [
            int(row["activity_id"])
            for row in item.metadata.get("top_workouts", [])
        ],
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
    args = parser.parse_args()

    initialise_database()
    athlete_id = int(args.athlete)
    context = EvidenceContext(
        athlete_id=athlete_id,
        goal=get_active_goal(athlete_id),
    )

    print("Performance Passport v0.66.2 production Workout Horizon validation")
    print(f"Athlete: {athlete_id}\n")

    default, default_s = _run(WorkoutEvidenceProvider(), context)
    explicit, explicit_s = _run(WorkoutEvidenceProvider(history_days=365), context)
    full, full_s = _run(WorkoutEvidenceProvider(history_days=None), context)

    default_snapshot = _snapshot(default)
    explicit_snapshot = _snapshot(explicit)
    full_snapshot = _snapshot(full)

    default_is_365 = default_snapshot == explicit_snapshot
    full_parity = default_snapshot == full_snapshot

    print("=== TIMING ===")
    print(f"  Production default: {default_s:.2f}s")
    print(f"  Explicit 365 days:  {explicit_s:.2f}s")
    print(f"  Full history:       {full_s:.2f}s")

    print("\n=== HORIZON ===")
    print(
        "  Default history_days: "
        f"{default.metadata.get('history_horizon', {}).get('history_days')}"
    )
    print(
        "  Default rows loaded:  "
        f"{default.metadata.get('history_horizon', {}).get('raw_rows_loaded')}"
    )
    print(
        "  Full rows loaded:     "
        f"{full.metadata.get('history_horizon', {}).get('raw_rows_loaded')}"
    )

    print("\n=== PARITY ===")
    print(f"  Default == explicit 365: {default_is_365}")
    print(f"  Default == full critical output: {full_parity}")

    print("\n=== RESULT ===")
    if default_is_365 and full_parity:
        print("PASS — production Workout horizon is live and output-identical.")
    else:
        print("REVIEW — do not treat production horizon as complete.")


if __name__ == "__main__":
    main()

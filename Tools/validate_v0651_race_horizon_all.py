"""Multi-athlete safety gate for horizon-aware race evidence.

Requires the v0.65.0 shadow-capable RaceEvidenceProvider.

For every athlete with activities, compare:
  full history
vs
  last N days + preserved verified PB activity IDs

No production coaching behaviour is changed.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_connection, initialise_database
from core.evidence_providers.base import EvidenceContext
from core.evidence_providers.race import RaceEvidenceProvider
from core.significant_evidence import refresh_significant_pb_index

DISTANCES = (
    ("5K", 5000.0),
    ("10K", 10000.0),
    ("Half", 21097.5),
    ("Marathon", 42195.0),
)


def _seconds(value):
    return None if value is None else round(float(value), 2)


def _athletes():
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT a.id, a.first_name, a.last_name, COUNT(ac.id)
            FROM athletes a
            LEFT JOIN activities ac ON ac.athlete_id = a.id
            GROUP BY a.id, a.first_name, a.last_name
            HAVING COUNT(ac.id) > 0
            ORDER BY a.id
            """
        ).fetchall()
    finally:
        conn.close()


def _time_build(provider, context):
    started = time.perf_counter()
    item = provider.build(context)
    return item, time.perf_counter() - started


def _parity(full, horizon):
    return (
        full.status == horizon.status
        and _seconds(full.predicted_seconds) == _seconds(horizon.predicted_seconds)
        and round(float(full.confidence), 6) == round(float(horizon.confidence), 6)
        and full.summary == horizon.summary
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    initialise_database()
    athletes = _athletes()

    print("Performance Passport v0.65.1 multi-athlete race-horizon safety gate")
    print(f"Raw horizon: {args.days} days")
    print("Production is NOT changed by this tool.\n")

    overall = True
    total_full = 0.0
    total_horizon = 0.0

    for athlete_id, first_name, last_name, activity_count in athletes:
        name = f"{first_name or ''} {last_name or ''}".strip() or f"Athlete {athlete_id}"

        # Refresh is deliberately done outside the measured race-provider timing.
        # It guarantees old verified PB activity IDs are preserved for this safety test.
        pb_index = refresh_significant_pb_index(int(athlete_id))
        preserved_ids = tuple(
            sorted({
                int(value["activity_id"])
                for value in pb_index.values()
                if value.get("activity_id") is not None
            })
        )

        print(f"=== {name} · athlete {athlete_id} · {activity_count:,} activities ===")
        print(f"Preserved PB activity IDs: {preserved_ids or '-'}")

        athlete_ok = True

        for label, distance_m in DISTANCES:
            goal = {"goal_name": f"Shadow {label}", "distance_m": distance_m}
            context = EvidenceContext(athlete_id=int(athlete_id), goal=goal)

            full, full_s = _time_build(RaceEvidenceProvider(), context)
            horizon, horizon_s = _time_build(
                RaceEvidenceProvider(
                    history_days=args.days,
                    preserved_activity_ids=preserved_ids,
                ),
                context,
            )

            parity = _parity(full, horizon)
            athlete_ok = athlete_ok and parity
            total_full += full_s
            total_horizon += horizon_s

            speedup = full_s / horizon_s if horizon_s > 0 else float("inf")
            print(
                f"  {label:8s} parity={str(parity):5s}  "
                f"full={full_s:6.2f}s  horizon={horizon_s:6.2f}s  "
                f"speed-up={speedup:4.1f}x  "
                f"prediction={_seconds(horizon.predicted_seconds)}  "
                f"confidence={horizon.confidence:.4f}"
            )

        overall = overall and athlete_ok
        print(f"  ATHLETE RESULT: {'PASS' if athlete_ok else 'REVIEW'}\n")

    print("=== OVERALL ===")
    if total_horizon > 0:
        print(f"Aggregate provider speed-up: {total_full / total_horizon:.2f}x")
    print(
        "RESULT: "
        + (
            "PASS — horizon path is output-identical across all athletes tested."
            if overall
            else "REVIEW — at least one athlete/distance changed. Do not wire production yet."
        )
    )


if __name__ == "__main__":
    main()

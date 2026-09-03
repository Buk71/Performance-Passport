"""Shadow-validate horizon-aware Race Coach candidate loading.

Production behaviour remains unchanged in v0.65.0. This tool compares:
  A) current full-history RaceEvidenceProvider
  B) 365-day raw history + preserved verified PB activity IDs

It reports timing and evidence parity for standard race distances.
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


def _selected_activity(item):
    debug = item.metadata.get("candidate_debug") or []
    if not debug:
        return None
    # candidate_debug is score-sorted in the provider.
    return debug[0].get("activity_id")


def _time_build(provider, context):
    started = time.perf_counter()
    item = provider.build(context)
    return item, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    initialise_database()

    conn = get_connection()
    try:
        athlete = conn.execute(
            "SELECT first_name, last_name FROM athletes WHERE id = ?",
            (args.athlete,),
        ).fetchone()
    finally:
        conn.close()

    name = (
        f"{athlete[0] or ''} {athlete[1] or ''}".strip()
        if athlete else f"Athlete {args.athlete}"
    )

    pb_index = refresh_significant_pb_index(args.athlete)
    preserved_ids = tuple(
        sorted({
            int(value["activity_id"])
            for value in pb_index.values()
            if value.get("activity_id") is not None
        })
    )

    print(f"Performance Passport v0.65.0 race-horizon shadow validation · {name}")
    print(f"Raw horizon: {args.days} days")
    print(f"Preserved PB activity IDs: {preserved_ids or '-'}")
    print("\nProduction is NOT changed by this tool.\n")

    all_equal = True

    for label, distance_m in DISTANCES:
        goal = {
            "goal_name": f"Shadow {label}",
            "distance_m": distance_m,
        }
        context = EvidenceContext(athlete_id=args.athlete, goal=goal)

        full_provider = RaceEvidenceProvider()
        horizon_provider = RaceEvidenceProvider(
            history_days=args.days,
            preserved_activity_ids=preserved_ids,
        )

        full, full_s = _time_build(full_provider, context)
        horizon, horizon_s = _time_build(horizon_provider, context)

        parity = (
            full.status == horizon.status
            and _seconds(full.predicted_seconds) == _seconds(horizon.predicted_seconds)
            and round(float(full.confidence), 6) == round(float(horizon.confidence), 6)
            and full.summary == horizon.summary
        )
        all_equal = all_equal and parity

        speedup = full_s / horizon_s if horizon_s > 0 else float("inf")
        print(f"{label}")
        print(f"  full history:  {full_s:7.3f}s  prediction={_seconds(full.predicted_seconds)}  confidence={full.confidence:.4f}")
        print(f"  horizon:       {horizon_s:7.3f}s  prediction={_seconds(horizon.predicted_seconds)}  confidence={horizon.confidence:.4f}")
        print(f"  speed-up:      {speedup:7.2f}x")
        print(f"  exact parity:  {parity}")
        print(f"  full sample:   {full.sample_size}")
        print(f"  horizon sample:{horizon.sample_size}")
        print()

    print("RESULT")
    if all_equal:
        print("  PASS: standard-distance Race Coach evidence is unchanged.")
        print("  This horizon is safe to consider for production wiring.")
    else:
        print("  REVIEW: at least one standard-distance result changed.")
        print("  Do not switch production to the horizon path yet.")


if __name__ == "__main__":
    main()

"""Inspect how much raw history sits in each proposed v0.64 horizon."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_connection, initialise_database
from core.intelligence_store import get_activity_horizon_counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, default=None)
    args = parser.parse_args()

    initialise_database()
    conn = get_connection()
    try:
        if args.athlete is None:
            athletes = conn.execute(
                "SELECT id, first_name, last_name FROM athletes ORDER BY id"
            ).fetchall()
        else:
            athletes = conn.execute(
                "SELECT id, first_name, last_name FROM athletes WHERE id = ?",
                (args.athlete,),
            ).fetchall()
    finally:
        conn.close()

    print("Performance Passport v0.64 history horizons")
    print("Recent = 0-90 days · Current = 91-365 days · Archive = >365 days")
    for athlete_id, first_name, last_name in athletes:
        counts = get_activity_horizon_counts(int(athlete_id))
        total = sum(counts.values())
        name = f"{first_name or ''} {last_name or ''}".strip()
        print(f"\n{name} (athlete {athlete_id}) · {total:,} dated activities")
        for key in ("recent", "current", "archive"):
            value = counts[key]
            share = (100.0 * value / total) if total else 0.0
            print(f"  {key:8s} {value:6,d}  {share:5.1f}%")


if __name__ == "__main__":
    main()

"""Build and inspect Performance Passport v0.64.9 archive intelligence."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.archive_intelligence import (
    inspect_history_horizons,
    refresh_archive_history_summary,
)
from core.database import get_connection, initialise_database


def fmt_time(seconds):
    if seconds is None:
        return "-"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
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
        if athlete is not None
        else f"Athlete {args.athlete}"
    )

    counts = inspect_history_horizons(args.athlete)
    summary = refresh_archive_history_summary(args.athlete)

    print(f"Performance Passport v0.64.9 archive intelligence · {name}")
    print("\nHistory horizons")
    total = sum(counts.values()) or 1
    for key in ("recent", "current", "archive"):
        count = counts[key]
        print(f"  {key:8s} {count:5d}  ({100*count/total:5.1f}%)")

    print("\nArchive summary")
    print(f"  cutoff:              before {summary.archive_cutoff_date}")
    print(f"  activities:          {summary.activity_count}")
    print(f"  running activities:  {summary.running_activity_count}")
    print(f"  earliest:            {summary.earliest_activity_date or '-'}")
    print(f"  latest archive:      {summary.latest_archive_activity_date or '-'}")
    print(f"  total distance:      {summary.total_distance_km:,.1f} km")
    print(f"  total duration:      {summary.total_duration_s/3600:,.1f} h")
    print("\nArchive supporting best-distance-like evidence")
    print(f"  5K-like:             {fmt_time(summary.best_5k_like_s)}")
    print(f"  10K-like:            {fmt_time(summary.best_10k_like_s)}")
    print(f"  Half-like:           {fmt_time(summary.best_half_like_s)}")
    print(f"  Marathon-like:       {fmt_time(summary.best_marathon_like_s)}")
    print(
        "\nThese are compact archive summaries only. Verified PB/official override "
        "logic remains separate and first-class."
    )


if __name__ == "__main__":
    main()

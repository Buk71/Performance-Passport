"""Build/inspect the v0.64 all-time significant PB index."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_connection, initialise_database
from core.significant_evidence import refresh_significant_pb_index


def _format_time(seconds):
    seconds = int(round(float(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


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

    if athlete is None:
        raise SystemExit(f"Athlete {args.athlete} not found.")

    name = f"{athlete[0] or ''} {athlete[1] or ''}".strip()
    print(f"Refreshing all-time significant PB index for {name} (athlete {args.athlete})...")
    index = refresh_significant_pb_index(args.athlete)

    if not index:
        print("No verified PB-quality race evidence found.")
        return

    print("\nPreserved PB evidence")
    for value in index.values():
        print(
            f"  {value['label']:14s}  {_format_time(value['time_s']):>8s}  "
            f"{value.get('activity_date') or '-'}  "
            f"activity {value.get('activity_id') if value.get('activity_id') is not None else '-'}  "
            f"{value.get('source', value.get('classification', ''))}"
        )

    print("\nThese PBs remain first-class evidence even when their activities move into the archive.")
    print("A new athlete-data version invalidates this stored index until it is refreshed.")


if __name__ == "__main__":
    main()

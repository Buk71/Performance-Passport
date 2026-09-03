"""Inspect broad vs race-specific intelligence dependency versions."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.cache_version import get_athlete_cache_version, get_race_intelligence_version
from core.database import get_connection, initialise_database


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    args = parser.parse_args()
    initialise_database()

    broad = tuple(get_athlete_cache_version(args.athlete))
    race = tuple(get_race_intelligence_version(args.athlete))

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

    print(f"Performance Passport v0.64.4 dependency versions · {name}")
    print(f"Broad athlete version fields: {len(broad)}")
    print(f"Race intelligence fields:     {len(race)}")
    print("Race intelligence excludes workout_library and other derived coach tables.")


if __name__ == "__main__":
    main()

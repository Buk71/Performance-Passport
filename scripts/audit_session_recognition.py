"""Print a safe recognition audit without changing athlete data or predictions.

Examples:
    python scripts/audit_session_recognition.py
    python scripts/audit_session_recognition.py --athlete 3 --days 180
    python scripts/audit_session_recognition.py --athlete 1 3 4 --limit 8
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_connection
from core.recognition_audit import build_recognition_audit


def _athlete_ids(selected: list[int] | None) -> tuple[int, ...]:
    if selected:
        return tuple(dict.fromkeys(selected))
    connection = get_connection()
    rows = connection.execute("SELECT id FROM athletes ORDER BY id").fetchall()
    connection.close()
    return tuple(int(row[0]) for row in rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Audit real historical run recognition without changing the app."
    )
    parser.add_argument("--athlete", nargs="+", type=int, help="One or more athlete IDs.")
    parser.add_argument("--days", type=int, help="Limit the audit to recent calendar days.")
    parser.add_argument("--limit", type=int, default=12, help="Maximum review items per athlete.")
    options = parser.parse_args(argv)

    for athlete_id in _athlete_ids(options.athlete):
        report = build_recognition_audit(athlete_id, recent_days=options.days)
        print(f"\n{report.athlete_name} · {report.total_running_activities:,} running activities")
        print(f"  Likely missed workouts: {report.likely_missed_workout_count:,}")
        print(f"  Likely false workouts: {report.likely_false_workout_count:,}")
        print(f"  Strides protected: {report.protected_strides_count:,}")
        print(f"  Easy runs with pickups protected: {report.protected_pickups_count:,}")
        print(f"  Races protected: {report.confirmed_race_count:,}")
        print(f"  Activities needing review: {report.reviewed_count:,}")
        print("  Live classifications and predictions changed: no")

        for entry in report.review_queue[: max(options.limit, 0)]:
            print(
                f"  [{entry.review_priority.upper()}] {entry.activity_date} "
                f"#{entry.activity_id} {entry.title}: {entry.current_label} "
                f"-> {entry.proposed_label} ({entry.current_confidence:.0%})"
            )
            print(f"    {entry.recommendation}")


if __name__ == "__main__":
    main()

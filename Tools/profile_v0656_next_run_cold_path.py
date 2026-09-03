"""Profile the cold Next Run recommendation path.

Each measured service starts from zero athlete_intelligence rows so persistent
materialisation from an earlier call cannot warm later measurements.

Only athlete_intelligence rows are temporarily removed and are restored in a
finally block.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_connection, initialise_database
from core.next_run import build_next_run_recommendation
from core.home_summary import build_home_summary
from core.home_latest_run import build_home_latest_run
from core.progress_coach import build_progress_coach_detail
from core.recovery_coach import build_recovery_coach_detail
from core.learning_coach import build_learning_coach_detail

BACKUP_DIR = ROOT / "benchmarks" / "cache_backups"


def _columns(conn: sqlite3.Connection):
    return [
        str(row[1])
        for row in conn.execute(
            "PRAGMA table_info(athlete_intelligence)"
        ).fetchall()
    ]


def _serialisable(value):
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    return value


def _deserialise(value):
    if isinstance(value, dict) and "__bytes_hex__" in value:
        return bytes.fromhex(value["__bytes_hex__"])
    return value


def _backup(athlete_id: int):
    conn = get_connection()
    try:
        columns = _columns(conn)
        rows = conn.execute(
            "SELECT * FROM athlete_intelligence WHERE athlete_id = ?",
            (athlete_id,),
        ).fetchall()
        return columns, [
            [_serialisable(value) for value in tuple(row)]
            for row in rows
        ]
    finally:
        conn.close()


def _write_backup(athlete_id: int, columns, rows) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = BACKUP_DIR / f"next-run-profile-{athlete_id}-{stamp}.json"
    path.write_text(
        json.dumps(
            {"athlete_id": athlete_id, "columns": columns, "rows": rows},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return path


def _clear(athlete_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM athlete_intelligence WHERE athlete_id = ?",
            (athlete_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _restore(athlete_id: int, columns, rows):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM athlete_intelligence WHERE athlete_id = ?",
            (athlete_id,),
        )
        if rows:
            column_sql = ",".join(f'"{c}"' for c in columns)
            placeholders = ",".join("?" for _ in columns)
            sql = (
                f"INSERT INTO athlete_intelligence ({column_sql}) "
                f"VALUES ({placeholders})"
            )
            conn.executemany(
                sql,
                [
                    tuple(_deserialise(v) for v in row)
                    for row in rows
                ],
            )
        conn.commit()
    finally:
        conn.close()


def _count(athlete_id: int) -> int:
    conn = get_connection()
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM athlete_intelligence WHERE athlete_id = ?",
                (athlete_id,),
            ).fetchone()[0]
            or 0
        )
    finally:
        conn.close()


def _name(athlete_id: int) -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT first_name, last_name FROM athletes WHERE id = ?",
            (athlete_id,),
        ).fetchone()
    finally:
        conn.close()
    return (
        f"{row[0] or ''} {row[1] or ''}".strip()
        if row
        else f"Athlete {athlete_id}"
    )


def _isolated(athlete_id: int, label: str, fn):
    _clear(athlete_id)
    started = time.perf_counter()
    try:
        result = fn()
        elapsed = time.perf_counter() - started
        print(
            f"  {label:28s} {elapsed:8.2f}s  "
            f"generated_rows={_count(athlete_id)}"
        )
        return result, elapsed
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(
            f"  {label:28s} {elapsed:8.2f}s  "
            f"ERROR {type(exc).__name__}: {exc}"
        )
        return None, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    parser.add_argument("--date", type=str, default=None)
    args = parser.parse_args()

    initialise_database()
    athlete_id = int(args.athlete)
    today = (
        dt.date.fromisoformat(args.date)
        if args.date
        else dt.date.today()
    )

    columns, rows = _backup(athlete_id)
    backup_path = _write_backup(athlete_id, columns, rows)

    print("Performance Passport v0.65.6 Next Run cold-path profile")
    print(f"Athlete: {_name(athlete_id)} ({athlete_id})")
    print(f"Date: {today.isoformat()}")
    print(f"Original intelligence rows: {len(rows)}")
    print(f"Safety backup: {backup_path}")
    print("\nEvery measurement starts cold.\n")

    timings = {}

    try:
        _, timings["home_summary"] = _isolated(
            athlete_id,
            "home_summary",
            lambda: build_home_summary(athlete_id, today=today),
        )

        _, timings["latest_run"] = _isolated(
            athlete_id,
            "latest_run",
            lambda: build_home_latest_run(athlete_id),
        )

        _, timings["progress_coach"] = _isolated(
            athlete_id,
            "progress_coach",
            lambda: build_progress_coach_detail(athlete_id),
        )

        _, timings["recovery_coach"] = _isolated(
            athlete_id,
            "recovery_coach",
            lambda: build_recovery_coach_detail(athlete_id),
        )

        _, timings["learning_coach"] = _isolated(
            athlete_id,
            "learning_coach",
            lambda: build_learning_coach_detail(athlete_id),
        )

        _, timings["next_run"] = _isolated(
            athlete_id,
            "next_run_recommendation",
            lambda: build_next_run_recommendation(
                athlete_id,
                today=today,
            ),
        )

    finally:
        print("\n=== RESTORING ORIGINAL INTELLIGENCE ===")
        _restore(athlete_id, columns, rows)
        restored = _count(athlete_id)
        print(f"  Restored rows: {restored} (expected {len(rows)})")
        print("  Restore check: " + ("PASS" if restored == len(rows) else "WARNING"))

    print("\n=== ISOLATED COLD RANKING ===")
    for key, seconds in sorted(
        timings.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {key:28s} {seconds:8.2f}s")

    print(
        "\nThis tells us which already-visible coaching services account for "
        "the 14s Next Run cold cost before we alter production logic."
    )


if __name__ == "__main__":
    main()

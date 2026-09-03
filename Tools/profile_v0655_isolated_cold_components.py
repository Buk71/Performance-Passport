"""Isolated cold-component profile for Training Coach.

Each component is measured from the SAME genuinely cold athlete_intelligence
state. Generated cache rows are removed before the next component, so an
earlier measurement cannot warm a later one.

Original intelligence rows are backed up and restored in a finally block.
Only athlete_intelligence rows are temporarily changed.
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
from core.operational_block import build_operational_block_week
from core.live_integration import build_adaptive_coach_proposal
from core.coaching_arbitration import build_coaching_arbitration
from core.adaptive_coach_live import build_live_coach_decision
from core.training_coach import build_training_coach_detail

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
            [_serialisable(v) for v in tuple(row)]
            for row in rows
        ]
    finally:
        conn.close()


def _write_backup(athlete_id: int, columns, rows) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = BACKUP_DIR / (
        f"isolated-cold-intelligence-{athlete_id}-{stamp}.json"
    )
    path.write_text(
        json.dumps(
            {
                "athlete_id": athlete_id,
                "columns": columns,
                "rows": rows,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return path


def _clear(athlete_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM athlete_intelligence WHERE athlete_id = ?",
            (athlete_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _restore(athlete_id: int, columns, rows) -> None:
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
            values = [
                tuple(_deserialise(v) for v in row)
                for row in rows
            ]
            conn.executemany(sql, values)
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


def _time_isolated(athlete_id: int, label: str, fn):
    _clear(athlete_id)
    if _count(athlete_id) != 0:
        raise RuntimeError("Could not establish cold intelligence state")

    started = time.perf_counter()
    value = fn()
    elapsed = time.perf_counter() - started
    generated = _count(athlete_id)

    print(
        f"  {label:30s} {elapsed:8.2f}s  "
        f"generated_rows={generated}"
    )
    return value, elapsed


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

    columns, original_rows = _backup(athlete_id)
    backup_path = _write_backup(
        athlete_id,
        columns,
        original_rows,
    )

    print("Performance Passport v0.65.5 isolated cold-component profile")
    print(f"Athlete: {_name(athlete_id)} ({athlete_id})")
    print(f"Date: {today.isoformat()}")
    print(f"Original intelligence rows: {len(original_rows)}")
    print(f"Safety backup: {backup_path}")
    print(
        "\nEvery measurement starts with zero athlete_intelligence rows. "
        "No component can warm the next one.\n"
    )

    timings = {}

    try:
        established, timings["next_run"] = _time_isolated(
            athlete_id,
            "next_run_recommendation",
            lambda: build_next_run_recommendation(
                athlete_id,
                today=today,
            ),
        )

        _, timings["operational_block"] = _time_isolated(
            athlete_id,
            "operational_block_week",
            lambda: build_operational_block_week(
                athlete_id,
                today=today,
            ),
        )

        # Next-run itself is essentially free, so resolving it outside the
        # adaptive measurement does not materially warm persistent intelligence.
        existing_label = None
        if established is not None:
            existing_label = (
                established.next_key_session_family
                or established.session_family
            )

        _, timings["adaptive_proposal"] = _time_isolated(
            athlete_id,
            "adaptive_coach_proposal",
            lambda: build_adaptive_coach_proposal(
                athlete_id,
                today=today,
                existing_label=existing_label,
            ),
        )

        _, timings["arbitration"] = _time_isolated(
            athlete_id,
            "coaching_arbitration",
            lambda: build_coaching_arbitration(
                athlete_id,
                today=today,
                existing_recommendation=established,
            ),
        )

        _, timings["live_decision"] = _time_isolated(
            athlete_id,
            "live_coach_decision",
            lambda: build_live_coach_decision(
                athlete_id,
                today=today,
            ),
        )

        _, timings["training_coach"] = _time_isolated(
            athlete_id,
            "training_coach_full",
            lambda: build_training_coach_detail(
                athlete_id,
                today=today,
            ),
        )

    finally:
        print("\n=== RESTORING ORIGINAL INTELLIGENCE ===")
        _restore(
            athlete_id,
            columns,
            original_rows,
        )
        restored = _count(athlete_id)
        print(
            f"  Restored rows: {restored} "
            f"(expected {len(original_rows)})"
        )
        print(
            "  Restore check: "
            + ("PASS" if restored == len(original_rows) else "WARNING")
        )

    print("\n=== ISOLATED COLD RANKING ===")
    for key, seconds in sorted(
        timings.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {key:30s} {seconds:8.2f}s")

    print(
        "\nThe dominant isolated component is the correct next optimisation "
        "target. These timings are not contaminated by earlier warm-cache calls."
    )


if __name__ == "__main__":
    main()

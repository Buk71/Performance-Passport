"""Cold cProfile of the real Live Coach decision path.

Built specifically to inspect the current adaptive_coach_live.py call tree
without guessing which nested builder is responsible.

Safety:
- backs up all athlete_intelligence rows for the athlete;
- clears only athlete_intelligence;
- profiles one cold build_live_coach_decision() call in a fresh process;
- restores the exact original rows in finally.

It reports the hottest core/* functions by cumulative and own time plus
repeated-call counts.
"""

from __future__ import annotations

import argparse
import cProfile
import datetime as dt
import io
import json
import pstats
import sqlite3
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adaptive_coach_live import build_live_coach_decision
from core.database import get_connection, initialise_database

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
        f"live-decision-cprofile-{athlete_id}-{stamp}.json"
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


def _core_rows(profile: cProfile.Profile):
    stats = pstats.Stats(profile)
    rows = []

    for func, stat in stats.stats.items():
        cc, nc, tt, ct, callers = stat
        filename, lineno, funcname = func
        normalized = filename.replace("\\", "/")

        if "/core/" not in normalized:
            continue

        try:
            rel = str(Path(filename).resolve().relative_to(ROOT))
        except Exception:
            rel = filename

        rows.append(
            {
                "file": rel,
                "line": lineno,
                "function": funcname,
                "primitive_calls": cc,
                "total_calls": nc,
                "own_time": tt,
                "cumulative_time": ct,
            }
        )

    return rows


def _print_table(title, rows, sort_key, limit=25):
    print(f"\n=== {title} ===")
    print(
        f"{'calls':>7}  {'own':>8}  {'cum':>8}  "
        f"{'function':40s}  file"
    )
    for row in sorted(
        rows,
        key=lambda item: item[sort_key],
        reverse=True,
    )[:limit]:
        print(
            f"{row['total_calls']:7d}  "
            f"{row['own_time']:8.2f}  "
            f"{row['cumulative_time']:8.2f}  "
            f"{row['function'][:40]:40s}  "
            f"{row['file']}:{row['line']}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--limit", type=int, default=25)
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

    print("Performance Passport v0.66.3 Live Decision cold cProfile")
    print(f"Athlete: {athlete_id}")
    print(f"Date: {today.isoformat()}")
    print(f"Original intelligence rows: {len(rows)}")
    print(f"Safety backup: {backup_path}")
    print("\nOnly athlete_intelligence is temporarily cleared.\n")

    profile = cProfile.Profile()
    result = None

    try:
        _clear(athlete_id)
        print(
            f"Cold setup rows remaining: {_count(athlete_id)}"
        )

        started = time.perf_counter()
        profile.enable()
        try:
            result = build_live_coach_decision(
                athlete_id,
                today=today,
            )
        finally:
            profile.disable()
        elapsed = time.perf_counter() - started

        generated = _count(athlete_id)
        print(f"Live decision wall time: {elapsed:.2f}s")
        print(f"Generated intelligence rows: {generated}")
        print(f"Result returned: {result is not None}")

        core_rows = _core_rows(profile)

        _print_table(
            "TOP CORE FUNCTIONS BY CUMULATIVE TIME",
            core_rows,
            "cumulative_time",
            args.limit,
        )
        _print_table(
            "TOP CORE FUNCTIONS BY OWN TIME",
            core_rows,
            "own_time",
            args.limit,
        )

        repeated = [
            row for row in core_rows
            if row["total_calls"] > 1
            and row["cumulative_time"] >= 0.25
        ]
        _print_table(
            "REPEATED CORE CALLS >= 0.25s CUMULATIVE",
            repeated,
            "cumulative_time",
            args.limit,
        )

    finally:
        print("\n=== RESTORING ORIGINAL INTELLIGENCE ===")
        _restore(athlete_id, columns, rows)
        restored = _count(athlete_id)
        print(
            f"  Restored rows: {restored} "
            f"(expected {len(rows)})"
        )
        print(
            "  Restore check: "
            + ("PASS" if restored == len(rows) else "WARNING")
        )

    print(
        "\nUse cumulative time to find expensive call trees, own time to find "
        "expensive leaf work, and call counts to identify duplicated builders."
    )


if __name__ == "__main__":
    main()

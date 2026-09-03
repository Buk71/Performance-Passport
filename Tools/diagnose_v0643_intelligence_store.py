"""Diagnose v0.64.3 persistent race intelligence reuse.

Run from the Performance-Passport project root:

    python tools/diagnose_v0643_intelligence_store.py --athlete 1

This is read-only. It does not modify athlete data or intelligence rows.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.cache_version import get_athlete_cache_version
from core.database import get_connection, initialise_database
from core.materialized_intelligence import load_typed_intelligence


def _short(value, limit=140):
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    args = parser.parse_args()
    athlete_id = int(args.athlete)

    initialise_database()

    conn = get_connection()
    try:
        athlete = conn.execute(
            "SELECT first_name, last_name FROM athletes WHERE id = ?",
            (athlete_id,),
        ).fetchone()
        table_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name='athlete_intelligence'
            """
        ).fetchone() is not None
    finally:
        conn.close()

    name = (
        f"{athlete[0] or ''} {athlete[1] or ''}".strip()
        if athlete is not None
        else f"Athlete {athlete_id}"
    )

    print("Performance Passport v0.64.3 intelligence-store diagnostic")
    print(f"Athlete: {name} ({athlete_id})")
    print(f"athlete_intelligence table exists: {table_exists}")

    started = time.perf_counter()
    version_1 = tuple(get_athlete_cache_version(athlete_id))
    t1 = time.perf_counter() - started
    time.sleep(0.05)
    started = time.perf_counter()
    version_2 = tuple(get_athlete_cache_version(athlete_id))
    t2 = time.perf_counter() - started

    print("\nSource-version stability")
    print(f"  call 1: {t1:.4f}s")
    print(f"  call 2: {t2:.4f}s")
    print(f"  equal:  {version_1 == version_2}")
    if version_1 != version_2:
        print("  differing fields:")
        width = max(len(version_1), len(version_2))
        for index in range(width):
            first = version_1[index] if index < len(version_1) else "<missing>"
            second = version_2[index] if index < len(version_2) else "<missing>"
            if first != second:
                print(f"    [{index}] {_short(first)} -> {_short(second)}")

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT intelligence_key, horizon, source_version_json,
                   length(payload_json), generated_at
            FROM athlete_intelligence
            WHERE athlete_id = ?
              AND (
                    intelligence_key LIKE 'race.%'
                 OR intelligence_key LIKE 'significant.%'
              )
            ORDER BY intelligence_key
            """,
            (athlete_id,),
        ).fetchall()
    finally:
        conn.close()

    print(f"\nStored race/significant intelligence rows: {len(rows)}")
    if not rows:
        print("  NONE")
        print("\nConclusion: v0.64.3 builders are not writing to the intelligence store.")
        return

    exact_matches = 0
    decode_ok = 0
    decode_fail = 0

    for row in rows:
        key, horizon, source_json, payload_size, generated_at = row
        try:
            stored_version = tuple(json.loads(source_json))
            version_match = stored_version == version_2
        except Exception as exc:
            stored_version = ()
            version_match = False
            print(f"\n{key}")
            print(f"  source-version JSON ERROR: {type(exc).__name__}: {exc}")
            continue

        if version_match:
            exact_matches += 1

        started = time.perf_counter()
        decoded = load_typed_intelligence(
            athlete_id,
            key,
            source_version=version_2,
        )
        elapsed = time.perf_counter() - started

        if decoded is None:
            decode_fail += 1
            decoded_status = "FAIL / MISS"
        else:
            decode_ok += 1
            decoded_status = f"OK ({type(decoded).__module__}.{type(decoded).__name__})"

        print(f"\n{key}")
        print(f"  horizon:       {horizon}")
        print(f"  generated_at:  {generated_at}")
        print(f"  payload bytes: {payload_size or 0}")
        print(f"  version match: {version_match}")
        print(f"  typed reload:  {decoded_status} in {elapsed:.4f}s")

        if not version_match:
            print("  version differences:")
            width = max(len(stored_version), len(version_2))
            for index in range(width):
                first = stored_version[index] if index < len(stored_version) else "<missing>"
                second = version_2[index] if index < len(version_2) else "<missing>"
                if first != second:
                    print(f"    [{index}] stored={_short(first)} current={_short(second)}")

    print("\nSummary")
    print(f"  rows:                 {len(rows)}")
    print(f"  exact version match:  {exact_matches}")
    print(f"  typed reload OK:      {decode_ok}")
    print(f"  typed reload miss:    {decode_fail}")

    if exact_matches == 0:
        print("\nLikely cause: source-version mismatch is invalidating every stored object.")
    elif decode_ok == 0:
        print("\nLikely cause: rows are stored, but typed JSON reconstruction is failing.")
    elif decode_ok < len(rows):
        print("\nLikely cause: mixed result — some materialised object types cannot reload.")
    else:
        print(
            "\nStore/read-back looks healthy. If the benchmark is still slow, "
            "the benchmark/build path is bypassing the materialised wrappers "
            "or is generating different intelligence keys on each call."
        )


if __name__ == "__main__":
    main()

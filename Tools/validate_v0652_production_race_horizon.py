"""Validate production RaceEvidenceProvider default against full history."""

from __future__ import annotations

import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_connection, initialise_database
from core.evidence_providers.base import EvidenceContext
from core.evidence_providers.race import RaceEvidenceProvider

DISTANCES = (
    ("5K", 5000.0),
    ("10K", 10000.0),
    ("Half", 21097.5),
    ("Marathon", 42195.0),
)


def _seconds(value):
    return None if value is None else round(float(value), 2)


def _athletes():
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT a.id, a.first_name, a.last_name, COUNT(ac.id)
            FROM athletes a
            LEFT JOIN activities ac ON ac.athlete_id = a.id
            GROUP BY a.id, a.first_name, a.last_name
            HAVING COUNT(ac.id) > 0
            ORDER BY a.id
            """
        ).fetchall()
    finally:
        conn.close()


def _build(provider, context):
    started = time.perf_counter()
    item = provider.build(context)
    return item, time.perf_counter() - started


def _same(a, b):
    return (
        a.status == b.status
        and _seconds(a.predicted_seconds) == _seconds(b.predicted_seconds)
        and round(float(a.confidence), 6) == round(float(b.confidence), 6)
        and a.summary == b.summary
    )


def main():
    initialise_database()
    overall = True
    full_total = 0.0
    prod_total = 0.0

    print("Performance Passport v0.65.2 production race-horizon validation")
    print("Default provider = 365 days + automatic preserved PB activity IDs\n")

    for athlete_id, first_name, last_name, activity_count in _athletes():
        name = f"{first_name or ''} {last_name or ''}".strip() or f"Athlete {athlete_id}"
        athlete_ok = True
        print(f"=== {name} · athlete {athlete_id} · {activity_count:,} activities ===")

        for label, distance_m in DISTANCES:
            goal = {"goal_name": f"Production validation {label}", "distance_m": distance_m}
            context = EvidenceContext(athlete_id=int(athlete_id), goal=goal)

            full, full_s = _build(
                RaceEvidenceProvider(history_days=None, preserved_activity_ids=()),
                context,
            )
            production, prod_s = _build(RaceEvidenceProvider(), context)

            parity = _same(full, production)
            athlete_ok = athlete_ok and parity
            overall = overall and parity
            full_total += full_s
            prod_total += prod_s

            speedup = full_s / prod_s if prod_s else float("inf")
            print(
                f"  {label:8s} parity={str(parity):5s}  "
                f"full={full_s:6.2f}s  production={prod_s:6.2f}s  "
                f"speed-up={speedup:4.1f}x"
            )

        print(f"  ATHLETE RESULT: {'PASS' if athlete_ok else 'REVIEW'}\n")

    print("=== OVERALL ===")
    if prod_total:
        print(f"Aggregate speed-up: {full_total / prod_total:.2f}x")
    print(
        "RESULT: "
        + (
            "PASS — production default is output-identical to full history."
            if overall
            else "REVIEW — production default changed at least one result."
        )
    )


if __name__ == "__main__":
    main()

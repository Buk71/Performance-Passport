"""Profile the cold Training Coach rebuild path.

Read-only diagnostic. It times the major services called by Training Coach so
we know where the ~70 second cold-build cost actually lives before changing
history horizons.

Run:
    python tools/profile_v0653_training_cold_build.py --athlete 1

This does not modify production coaching logic.
"""

from __future__ import annotations

import argparse
import datetime
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
from core.session_designer import build_designed_session
from core.training_coach import _designer_family


def _time(label, fn):
    started = time.perf_counter()
    try:
        value = fn()
        elapsed = time.perf_counter() - started
        print(f"  {label:30s} {elapsed:8.2f}s  ok")
        return value, elapsed
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(
            f"  {label:30s} {elapsed:8.2f}s  "
            f"ERROR {type(exc).__name__}: {exc}"
        )
        return None, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    parser.add_argument("--date", type=str, default=None)
    args = parser.parse_args()

    initialise_database()
    today = (
        datetime.date.fromisoformat(args.date)
        if args.date
        else datetime.date.today()
    )

    conn = get_connection()
    try:
        athlete = conn.execute(
            "SELECT first_name, last_name FROM athletes WHERE id = ?",
            (int(args.athlete),),
        ).fetchone()
    finally:
        conn.close()

    name = (
        f"{athlete[0] or ''} {athlete[1] or ''}".strip()
        if athlete else f"Athlete {args.athlete}"
    )

    print("Performance Passport v0.65.3 Training Coach cold-build profile")
    print(f"Athlete: {name} ({args.athlete})")
    print(f"Date: {today.isoformat()}")
    print("Read-only diagnostic; production behaviour is unchanged.\n")

    timings = {}

    established, timings["next_run"] = _time(
        "next_run_recommendation",
        lambda: build_next_run_recommendation(
            int(args.athlete),
            today=today,
        ),
    )

    operational, timings["operational_block"] = _time(
        "operational_block_week",
        lambda: build_operational_block_week(
            int(args.athlete),
            today=today,
        ),
    )

    existing_label = None
    if established is not None:
        existing_label = (
            established.next_key_session_family
            or established.session_family
        )

    proposal, timings["adaptive_proposal"] = _time(
        "adaptive_coach_proposal",
        lambda: build_adaptive_coach_proposal(
            int(args.athlete),
            today=today,
            existing_label=existing_label,
        ),
    )

    arbitration, timings["arbitration"] = _time(
        "coaching_arbitration",
        lambda: build_coaching_arbitration(
            int(args.athlete),
            today=today,
            existing_recommendation=established,
        ),
    )

    decision, timings["live_decision"] = _time(
        "live_coach_decision",
        lambda: build_live_coach_decision(
            int(args.athlete),
            today=today,
        ),
    )

    session = None
    if decision is not None:
        family = _designer_family(decision)
        main_set = (
            (decision.key_prescription,)
            if decision.key_prescription
            else None
        )
        session, timings["session_designer"] = _time(
            "session_designer",
            lambda: build_designed_session(
                int(args.athlete),
                family_override=family,
                main_set_override=main_set,
                timing_override=decision.key_day,
                confidence_override=decision.confidence,
                confidence_label_override=decision.confidence_label,
                why_override=decision.why,
            ),
        )

    print("\n=== Ranked cold-path components ===")
    for key, seconds in sorted(
        timings.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {key:30s} {seconds:8.2f}s")

    component_sum = sum(timings.values())
    print(f"\nMeasured component sum: {component_sum:.2f}s")
    print(
        "Note: live_coach_decision deliberately repeats some of the earlier "
        "services, so this sum is diagnostic rather than page wall-clock time."
    )
    print(
        "\nNext step: optimise the dominant SOURCE builder(s), then shadow-test "
        "their horizon-aware results before changing production."
    )


if __name__ == "__main__":
    main()

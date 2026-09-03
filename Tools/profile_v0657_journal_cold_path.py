"""Profile the cold Journal build path directly.

The v0.65.6 profile showed Next Run cold cost is ~13s. Reading next_run.py shows
that Next Run itself is lightweight: it calls build_latest_journal_entry() plus
the active training block. Therefore Journal is the real source dependency.

This tool times the Journal's major internal stages without changing production.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import initialise_database
from core.journal import (
    _run_profiles,
    _latest_recognised_run,
    _build_decision_context,
)
from core.performance_recognition import build_recognition_index
from core.training_blocks import get_active_training_block


def _time(label, fn):
    started = time.perf_counter()
    value = fn()
    elapsed = time.perf_counter() - started
    print(f"  {label:28s} {elapsed:8.2f}s")
    return value, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete", type=int, required=True)
    args = parser.parse_args()

    initialise_database()
    athlete_id = int(args.athlete)

    print("Performance Passport v0.65.7 Journal cold-path profile")
    print(f"Athlete: {athlete_id}")
    print("Diagnostic only; production behaviour is unchanged.\n")

    timings = {}

    runs, timings["run_profiles"] = _time(
        "run_profiles",
        lambda: _run_profiles(athlete_id),
    )

    recognition_index, timings["recognition_index"] = _time(
        "recognition_index",
        lambda: build_recognition_index(
            runs,
            athlete_id=athlete_id,
        ),
    )

    latest_pair, timings["latest_recognised_run"] = _time(
        "latest_recognised_run",
        lambda: _latest_recognised_run(
            runs,
            recognition_index,
        ),
    )

    decision, timings["decision_context"] = _time(
        "decision_context",
        lambda: _build_decision_context(
            athlete_id,
            runs,
            recognition_index,
        ),
    )

    block, timings["active_training_block"] = _time(
        "active_training_block",
        lambda: get_active_training_block(athlete_id),
    )

    print("\n=== Ranked Journal components ===")
    for key, seconds in sorted(
        timings.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {key:28s} {seconds:8.2f}s")

    total = sum(timings.values())
    print(f"\nMeasured component sum: {total:.2f}s")
    print(f"Run profiles loaded: {len(runs):,}")
    print(f"Recognition records: {len(recognition_index):,}")
    print(
        "\nThe dominant component is the right next target for horizon-aware "
        "first-build optimisation."
    )


if __name__ == "__main__":
    main()

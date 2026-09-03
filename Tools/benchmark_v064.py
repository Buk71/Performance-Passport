"""Performance Passport v0.64 baseline benchmark.

Run from the project root, for example:
    python tools/benchmark_v064.py --athlete 1
    python tools/benchmark_v064.py --athlete all

The benchmark is read-only. It times established coaching builders against the
real database and writes a CSV report under benchmarks/. No coaching logic is
changed.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import gc
from pathlib import Path
import statistics
import sys
import time
from typing import Callable, Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.activity_review import list_review_activities
from core.athlete_passport import build_athlete_passport
from core.coaching_team import build_coaching_team_detail
from core.database import get_active_goal, get_connection, initialise_database
from core.distance_prediction_outlook import build_distance_prediction_outlook
from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from core.journal import build_latest_journal_entry
from core.learning_coach import build_learning_coach_detail
from core.passport_detail import build_passport_detail
from core.progress_coach import build_progress_coach_detail
from core.race_coach import build_race_coach_detail
from core.recovery_coach import build_recovery_coach_detail
from core.training_coach import build_training_coach_detail
from core.workout_coach import build_workout_coach_review

OUT_DIR = ROOT / "benchmarks"
TODAY = datetime.date.today()


def athlete_rows() -> list[tuple[int, str]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, first_name, last_name FROM athletes ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return [
        (int(row[0]), f"{row[1] or ''} {row[2] or ''}".strip() or f"Athlete {row[0]}")
        for row in rows
    ]


def latest_activity_id(athlete_id: int) -> int | None:
    items = list_review_activities(athlete_id)
    return int(items[0].activity_id) if items else None


def timed_call(label: str, fn: Callable[[], Any]) -> tuple[float, str]:
    gc.collect()
    started = time.perf_counter()
    try:
        value = fn()
        elapsed = time.perf_counter() - started
        status = "ok" if value is not None else "none"
    except Exception as exc:  # benchmark should continue and report failures
        elapsed = time.perf_counter() - started
        status = f"ERROR: {type(exc).__name__}: {exc}"
    print(f"  {label:<28} {elapsed:8.2f}s  {status}")
    return elapsed, status


def benchmark_athlete(athlete_id: int, athlete_name: str, pass_number: int):
    records = []
    print(f"\n=== {athlete_name} (athlete {athlete_id}) · pass {pass_number} ===")

    shared = {}

    def run(label: str, fn: Callable[[], Any]):
        elapsed, status = timed_call(label, fn)
        records.append(
            {
                "athlete_id": athlete_id,
                "athlete_name": athlete_name,
                "pass": pass_number,
                "builder": label,
                "seconds": round(elapsed, 4),
                "status": status,
            }
        )

    run("athlete_passport", lambda: build_athlete_passport(athlete_id))
    run("home_summary", lambda: build_home_summary(athlete_id))

    def build_predictions():
        value = build_home_predictions(athlete_id)
        shared["predictions"] = value
        return value
    run("home_predictions", build_predictions)

    run("home_latest_run", lambda: build_home_latest_run(athlete_id))

    def build_outlook():
        predictions = shared.get("predictions") or build_home_predictions(athlete_id)
        return build_distance_prediction_outlook(
            athlete_id,
            active_predictions=predictions,
        )
    run("distance_outlook", build_outlook)

    run("training_coach", lambda: build_training_coach_detail(athlete_id))
    run("passport_detail", lambda: build_passport_detail(athlete_id))
    run("progress_coach", lambda: build_progress_coach_detail(athlete_id))
    run("coaching_summary", lambda: build_coaching_team_detail(athlete_id))
    run("journal", lambda: build_latest_journal_entry(athlete_id))
    run("learning_coach", lambda: build_learning_coach_detail(athlete_id, today=TODAY))
    run("recovery_coach", lambda: build_recovery_coach_detail(athlete_id, today=TODAY))

    activity_id = latest_activity_id(athlete_id)
    if activity_id is not None:
        run(
            f"workout_coach[{activity_id}]",
            lambda: build_workout_coach_review(athlete_id, activity_id, today=TODAY),
        )

    goal = get_active_goal(athlete_id)
    if goal and goal.get("distance_m"):
        run("race_coach", lambda: build_race_coach_detail(athlete_id, goal))

    return records


def print_summary(records):
    print("\n=== Slowest builders ===")
    good = [row for row in records if not row["status"].startswith("ERROR")]
    for row in sorted(good, key=lambda item: item["seconds"], reverse=True)[:15]:
        print(
            f"  {row['athlete_name']:<18} pass {row['pass']}  "
            f"{row['builder']:<28} {row['seconds']:8.2f}s"
        )

    by_builder = {}
    for row in good:
        by_builder.setdefault(row["builder"], []).append(row["seconds"])
    if by_builder:
        print("\n=== Median by builder ===")
        for builder, values in sorted(
            by_builder.items(),
            key=lambda item: statistics.median(item[1]),
            reverse=True,
        ):
            print(f"  {builder:<28} {statistics.median(values):8.2f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--athlete",
        default="1",
        help="Athlete id, or 'all'. Default: 1 (Richard).",
    )
    parser.add_argument(
        "--passes",
        type=int,
        default=2,
        choices=(1, 2),
        help="1 = cold-ish baseline only; 2 = repeat immediately to reveal reuse. Default: 2.",
    )
    args = parser.parse_args()

    initialise_database()
    athletes = athlete_rows()
    if args.athlete != "all":
        wanted = int(args.athlete)
        athletes = [row for row in athletes if row[0] == wanted]
        if not athletes:
            raise SystemExit(f"Athlete {wanted} not found.")

    print("Performance Passport v0.64 baseline benchmark")
    print(f"Date: {TODAY.isoformat()}")
    print("Read-only benchmark; no athlete data is modified.")

    all_records = []
    for athlete_id, athlete_name in athletes:
        for pass_number in range(1, args.passes + 1):
            all_records.extend(benchmark_athlete(athlete_id, athlete_name, pass_number))

    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    athlete_token = args.athlete.replace(" ", "-")
    out_path = OUT_DIR / f"v064-baseline-{athlete_token}-{stamp}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["athlete_id", "athlete_name", "pass", "builder", "seconds", "status"],
        )
        writer.writeheader()
        writer.writerows(all_records)

    print_summary(all_records)
    print(f"\nCSV written: {out_path}")


if __name__ == "__main__":
    main()

import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

from core.beginner_activity_evidence import (
    _distance_km,
    _eligible_sport,
    find_latest_beginner_activity_evidence,
)


class _Conn:
    def __init__(self, rows):
        self.rows = rows
    def execute(self, *_args, **_kwargs):
        return self
    def fetchall(self):
        return self.rows
    def close(self):
        pass


def _journey(stage="run_walk_short"):
    return SimpleNamespace(
        id=7,
        athlete_id=99,
        journey_type="couch_to_5k",
        current_stage=stage,
        started_at="2026-09-01",
    )


def test_distance_handles_legacy_km_and_metres():
    assert _distance_km(3.2) == 3.2
    assert _distance_km(5000) == 5.0


def test_running_is_eligible_for_beginner_session():
    assert _eligible_sport(
        "running", "", "Morning Run",
        stage="run_walk_short",
        roles={"running": "running"},
    )


def test_walk_is_only_eligible_for_walking_foundation():
    roles = {"walking": "walking"}
    assert _eligible_sport(
        "walking", "", "Lunch Walk",
        stage="walking_foundation", roles=roles,
    )
    assert not _eligible_sport(
        "walking", "", "Lunch Walk",
        stage="run_walk_short", roles=roles,
    )


def test_latest_activity_prefills_completion_and_5k():
    # First connection: reviewed-activity lookup. Second: activities.
    reviewed_conn = _Conn([])
    activities_conn = _Conn([
        (123, "2026-09-05", "Evening Run", "running", "",
         5.04, 1980, 2010),
    ])
    with (
        patch("core.beginner_activity_evidence.get_active_runner_journey",
              return_value=_journey()),
        patch("core.beginner_activity_evidence.get_athlete_sport_roles",
              return_value={"running": "running"}),
        patch("core.beginner_activity_evidence.get_connection",
              side_effect=[reviewed_conn, activities_conn]),
    ):
        evidence = find_latest_beginner_activity_evidence(
            99,
            planned_duration_s=1800,
            today=datetime.date(2026, 9, 5),
        )
    assert evidence is not None
    assert evidence.activity_id == 123
    assert evidence.likely_completed_as_planned is True
    assert evidence.completed_5k is True


def test_reviewed_activity_is_not_suggested_again():
    reviewed = _Conn([(json.dumps({"activity_id": 123}),)])
    activities = _Conn([
        (123, "2026-09-05", "Evening Run", "running", "",
         3.0, 1800, 1810),
    ])
    with (
        patch("core.beginner_activity_evidence.get_active_runner_journey",
              return_value=_journey()),
        patch("core.beginner_activity_evidence.get_athlete_sport_roles",
              return_value={"running": "running"}),
        patch("core.beginner_activity_evidence.get_connection",
              side_effect=[reviewed, activities]),
    ):
        evidence = find_latest_beginner_activity_evidence(
            99,
            planned_duration_s=1800,
            today=datetime.date(2026, 9, 5),
        )
    assert evidence is None


def test_short_activity_is_only_a_suggestion_not_forced_complete():
    with (
        patch("core.beginner_activity_evidence.get_active_runner_journey",
              return_value=_journey()),
        patch("core.beginner_activity_evidence.get_athlete_sport_roles",
              return_value={"running": "running"}),
        patch("core.beginner_activity_evidence.get_connection",
              side_effect=[
                  _Conn([]),
                  _Conn([(2, "2026-09-05", "Short Run", "running", "",
                          1.2, 600, 620)]),
              ]),
    ):
        evidence = find_latest_beginner_activity_evidence(
            99,
            planned_duration_s=1800,
            today=datetime.date(2026, 9, 5),
        )
    assert evidence is not None
    assert evidence.likely_completed_as_planned is False

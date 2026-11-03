import datetime
from unittest.mock import patch

from core.five_to_ten_k_assessment import (
    build_five_to_ten_k_recent_evidence,
    build_five_to_ten_k_assessment,
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


def test_numeric_sport_id_uses_athlete_running_role_mapping():
    rows = [
        ("2026-09-01", 5.0, "966023", "", "Evening Activity"),
        ("2026-09-03", 6.0, "966023", "", "Morning Activity"),
    ]
    with (
        patch("core.five_to_ten_k_assessment.get_connection", return_value=_Conn(rows)),
        patch(
            "core.five_to_ten_k_assessment.get_athlete_sport_roles",
            return_value={"966023": "running"},
        ),
    ):
        evidence = build_five_to_ten_k_recent_evidence(
            3,
            today=datetime.date(2026, 9, 5),
            lookback_days=28,
        )

    assert evidence.recent_run_count == 2
    assert evidence.longest_recent_run_km == 6.0


def test_numeric_non_running_role_is_excluded():
    rows = [
        ("2026-09-01", 25.0, "966024", "", "Bike Activity"),
    ]
    with (
        patch("core.five_to_ten_k_assessment.get_connection", return_value=_Conn(rows)),
        patch(
            "core.five_to_ten_k_assessment.get_athlete_sport_roles",
            return_value={"966024": "cycling"},
        ),
    ):
        evidence = build_five_to_ten_k_recent_evidence(
            3,
            today=datetime.date(2026, 9, 5),
            lookback_days=28,
        )

    assert evidence.recent_run_count == 0
    assert evidence.longest_recent_run_km == 0.0


def test_recent_5k_with_numeric_running_sport_unlocks_pathway():
    rows = [
        ("2026-08-20", 5.02, "966023", "", "Activity"),
        ("2026-08-23", 6.47, "966023", "", "Activity"),
        ("2026-08-27", 7.10, "966023", "", "Activity"),
        ("2026-08-30", 5.50, "966023", "", "Activity"),
    ]
    with (
        patch("core.five_to_ten_k_assessment.get_connection", return_value=_Conn(rows)),
        patch(
            "core.five_to_ten_k_assessment.get_athlete_sport_roles",
            return_value={"966023": "running"},
        ),
    ):
        assessment, evidence = build_five_to_ten_k_assessment(
            3,
            sessions_per_week=3,
            today=datetime.date(2026, 9, 5),
        )

    assert assessment.can_complete_5k is True
    assert evidence.longest_recent_run_km == 7.10


def test_plain_running_string_still_works_without_mapping():
    rows = [
        ("2026-09-01", 5.1, "running", "", "Easy Run"),
    ]
    with (
        patch("core.five_to_ten_k_assessment.get_connection", return_value=_Conn(rows)),
        patch(
            "core.five_to_ten_k_assessment.get_athlete_sport_roles",
            return_value={},
        ),
    ):
        evidence = build_five_to_ten_k_recent_evidence(
            1,
            today=datetime.date(2026, 9, 5),
            lookback_days=28,
        )

    assert evidence.recent_run_count == 1

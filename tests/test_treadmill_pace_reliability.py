from core.activity_reliability import (
    has_reliable_distance_and_pace,
    is_treadmill_activity,
)
from core.hall_of_fame import build_hall_of_fame
from core.home_latest_run import _load_runs
from core.performance_recognition import (
    build_recognition_index,
    recognition_key,
)


def test_explicit_treadmill_and_virtual_run_signals_are_detected():
    assert is_treadmill_activity(title="Treadmill Running") is True
    assert is_treadmill_activity(sport_id="virtual_run") is True
    assert is_treadmill_activity(
        raw_json_text='{"sub_sport": "treadmill"}'
    ) is True
    assert has_reliable_distance_and_pace(
        title="Steady treadmill HR122 - Run 900 Excite Live: Quick Start"
    ) is False


def test_ordinary_and_trail_runs_remain_pace_reliable():
    assert has_reliable_distance_and_pace(title="SLR 12 miles") is True
    assert has_reliable_distance_and_pace(
        title="Wakefield Trail Running"
    ) is True
    assert is_treadmill_activity(
        title="Run 900 Excite Live: Quick Start"
    ) is False


def test_richard_treadmill_winner_is_excluded_from_hall_of_fame():
    hall = build_hall_of_fame(1)

    assert 3428 not in {
        award.activity_id for award in hall.awards
    }
    assert 3428 not in {
        best.activity_id for best in hall.personal_bests
    }


def test_treadmill_run_does_not_enter_performance_rankings():
    runs = _load_runs(1)
    index = build_recognition_index(runs, athlete_id=1)
    treadmill = next(
        run
        for run in runs
        if run.activity_date == "2026-01-11"
        and run.title == "Treadmill Running"
    )

    assert recognition_key(treadmill) not in index

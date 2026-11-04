import datetime

from core.coaching import RunProfile
from core.performance_recognition import (
    _Candidate,
    _achievement_candidates,
    _recent_comparable_group,
)


def _candidate(
    date,
    *,
    distance=8.0,
    duration=3000.0,
    signal=1.0,
    category="easy",
):
    run = RunProfile(
        athlete_id=1,
        activity_date=date,
        title="Easy Run",
        sport_id="running",
        distance_km=distance,
        moving_time_seconds=duration,
        avg_hr=135,
        lt1_hr=150,
    )
    return _Candidate(
        key=date,
        run=run,
        category_key=category,
        category_label="Easy",
        icon="😊",
        signal=signal,
        actual_pace=duration / distance,
        adjusted_pace=duration / distance,
        environment_adjustment=0.0,
        environment_factors=(),
        moving_percent=99.0,
        base_confidence=0.9,
        provisional=False,
    )


def test_recent_aerobic_comparison_filters_old_and_dissimilar_runs():
    candidate = _candidate("2026-11-03")
    group = [
        candidate,
        _candidate("2026-10-20", distance=7.5),
        _candidate("2026-09-20", distance=8.5),
        _candidate("2026-08-20", distance=12.5),  # too long
        _candidate("2025-01-01", distance=8.0),   # too old
    ]

    result = _recent_comparable_group(
        candidate,
        group,
        reference_date=datetime.date(2026, 11, 4),
        days=365,
    )

    assert candidate in result
    assert len(result) == 3


def test_easy_headline_uses_recent_comparable_rank_not_lifetime_top_ten():
    candidate = _candidate("2026-11-03")

    achievements = _achievement_candidates(
        candidate=candidate,
        rank=71,
        total=796,
        recent_rank=18,
        recent_total=60,
    )

    labels = [item.label for item in achievements]

    assert "Top 10% Easy" not in labels
    assert "Top 5% Easy" not in labels


def test_recent_top_ten_can_still_be_celebrated_when_sample_is_strong():
    candidate = _candidate("2026-11-03")

    achievements = _achievement_candidates(
        candidate=candidate,
        rank=71,
        total=796,
        recent_rank=4,
        recent_total=50,
    )

    assert achievements[0].label == "Top 10% Easy"
    assert "recent" in achievements[0].detail.lower()

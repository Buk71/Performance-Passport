from functools import lru_cache

from core.home_latest_run import build_home_latest_run


@lru_cache(maxsize=4)
def _latest(athlete_id: int):
    return build_home_latest_run(athlete_id)


def test_richard_latest_run_uses_real_recognition():
    result = _latest(1)

    assert result.available is True
    assert result.activity_id == 9366
    assert result.activity_date == "2026-08-09"
    assert result.title == "SLR 12 miles"
    assert result.category == "Long Easy"

    # Lifetime recognition remains factual context.
    assert result.rank == 10
    assert result.comparison_count == 107
    assert result.top_percent == 9.3

    # Aerobic headlines are no longer driven by lifetime percentile alone.
    # Recent like-for-like evidence can surface the more useful coaching win.
    assert result.headline == "Excellent aerobic control"

    assert result.comparison_count_12m >= 1
    assert result.confidence > 0


def test_jo_latest_run_is_independent():
    richard = _latest(1)
    jo = _latest(3)

    assert jo.available is True
    assert jo.activity_id == 5577
    assert jo.activity_date == "2026-08-09"
    assert jo.title == "Easy"
    assert jo.category == "Easy"

    # Verified workouts no longer contaminate the comparable easy-run pool.
    assert jo.rank == 202
    assert jo.comparison_count > richard.comparison_count

    # Athlete evidence must remain independent.
    assert jo.activity_id != richard.activity_id
    assert jo.title != richard.title


def test_latest_run_surfaces_recent_comparison_context():
    richard = _latest(1)
    jo = _latest(3)

    assert richard.comparison_count_12m is not None
    assert jo.comparison_count_12m is not None
    assert richard.comparison_count_12m > 0
    assert jo.comparison_count_12m > 0

from functools import lru_cache

from core.home_latest_run import build_home_latest_run


@lru_cache(maxsize=2)
def _latest(athlete_id):
    return build_home_latest_run(athlete_id)


def test_richard_latest_run_uses_real_recognition():
    result = _latest(1)

    assert result.available is True
    assert result.activity_id == 9366
    assert result.activity_date == "2026-08-09"
    assert result.title == "SLR 12 miles"
    assert result.category == "Long Easy"
    assert result.rank == 10
    assert result.comparison_count == 107
    assert result.top_percent == 9.3
    assert result.headline == "Top 10% Long Easy"
    assert "endurance" in result.benefit.lower()
    assert result.environment_adjustment_s_per_km > 5


def test_jo_latest_run_is_independent():
    richard = _latest(1)
    jo = _latest(3)

    assert jo.available is True
    assert jo.activity_id == 5577
    assert jo.activity_date == "2026-08-09"
    assert jo.title == "Easy"
    assert jo.category == "Easy"
    assert jo.rank == 204
    assert jo.comparison_count == 599
    assert jo.headline == "Excellent flow"
    assert jo.title != richard.title

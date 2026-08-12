from core.hall_of_fame import _is_trail
from core.home_best_runs import build_home_best_runs


def test_richard_best_run_uses_real_hall_of_fame_data():
    result = build_home_best_runs(1)

    assert result.available is True
    assert result.candidate_count == 1902
    assert result.main.category == "Best Easy Run Ever"
    assert result.main.activity_id == 3754
    assert result.main.activity_date == "2026-07-23"
    assert result.main.score == 89.0
    assert result.main.avg_hr == 129.0
    assert result.main.distance_km == 7.17


def test_stopped_watch_ladder_is_not_an_aerobic_hall_of_fame_award():
    result = build_home_best_runs(1)

    assert 3177 not in {
        award.activity_id for award in result.category_bests
    }


def test_jo_best_run_is_independent():
    richard = build_home_best_runs(1)
    jo = build_home_best_runs(3)

    assert jo.available is True
    assert jo.candidate_count == 1090
    assert jo.main.activity_date == "2025-07-02"
    assert jo.main.activity_id != richard.main.activity_id
    assert jo.main.distance_km != richard.main.distance_km


def test_xc_matches_as_a_word_not_inside_excite():
    assert _is_trail("Wakefield XC") is True
    assert _is_trail("Cross-country race") is True
    assert _is_trail("Run 900 Excite Live: Quick Start") is False


def test_false_trail_is_removed_from_jo_home_categories():
    jo = build_home_best_runs(3)

    assert "Trail" not in {
        award.short_category for award in jo.category_bests
    }

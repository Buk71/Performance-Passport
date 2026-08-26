import pytest

from core.hall_of_fame import (
    MINIMUM_BEST_RUN_DISTANCE_KM,
    _is_trail,
    build_hall_of_fame,
)
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


@pytest.mark.parametrize("athlete_id", (1, 3, 4))
def test_every_real_athlete_best_run_is_at_least_five_kilometres(athlete_id):
    hall = build_hall_of_fame(athlete_id)
    home = build_home_best_runs(athlete_id)

    assert hall.awards
    assert all(
        award.distance_km >= MINIMUM_BEST_RUN_DISTANCE_KM
        for award in hall.awards
    )
    assert home.main is not None
    assert home.main.distance_km >= MINIMUM_BEST_RUN_DISTANCE_KM
    assert all(
        run.distance_km >= MINIMUM_BEST_RUN_DISTANCE_KM
        for run in home.category_bests
    )


def test_five_kilometre_best_run_rule_does_not_remove_race_personal_bests():
    richard = build_hall_of_fame(1)
    jo = build_hall_of_fame(3)

    assert {best.key for best in richard.personal_bests} >= {"5k", "10k"}
    assert {best.key for best in jo.personal_bests} >= {"5k", "10k"}

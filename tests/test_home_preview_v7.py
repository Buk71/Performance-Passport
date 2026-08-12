from functools import lru_cache

from core.home_best_runs import build_home_best_runs
from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.home_preview_v7 import (
    build_compact_goal_html,
    build_v7_hero_html,
    build_v7_lower_html,
)


@lru_cache(maxsize=2)
def _data(athlete_id):
    return (
        build_home_summary(athlete_id),
        build_home_predictions(athlete_id),
        build_home_latest_run(athlete_id),
        build_home_best_runs(athlete_id),
    )


def test_v7_hierarchy_uses_real_richard_data():
    home, predictions, latest, best = _data(1)
    goal_html = build_compact_goal_html(home)
    hero_html = build_v7_hero_html(1, home, predictions, latest)
    lower_html = build_v7_lower_html(home, best)

    assert "Sub 39:00" in goal_html
    assert "SLR 12 miles" in hero_html
    assert "#10" in hero_html
    assert "Trail Warrior" in hero_html
    assert hero_html.index("Performance Intelligence") < hero_html.index("Race Outlook")
    assert lower_html.index("This week") < lower_html.index("Up next")
    assert lower_html.index("Up next") < lower_html.index("Best runs")


def test_v7_keeps_jo_independent_and_does_not_invent_edge():
    home, predictions, latest, best = _data(3)
    goal_html = build_compact_goal_html(home)
    hero_html = build_v7_hero_html(3, home, predictions, latest)
    lower_html = build_v7_lower_html(home, best)

    assert "Sub 45" in goal_html
    assert "SLR 12 miles" not in hero_html
    assert "Trail Warrior" not in hero_html
    assert "Still emerging" in hero_html
    assert "Best runs" in lower_html


def test_v7_mobile_order_keeps_goal_after_passport():
    home, predictions, latest, _ = _data(1)
    html = build_v7_hero_html(1, home, predictions, latest)

    assert 'class="v7-passport"' in html
    assert 'class="v7-mobile-goal"' in html
    assert html.index('class="v7-passport"') < html.index('class="v7-mobile-goal"')
    assert html.index('class="v7-mobile-goal"') < html.index("Performance Intelligence")

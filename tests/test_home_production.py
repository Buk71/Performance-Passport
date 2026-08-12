from functools import lru_cache
from pathlib import Path

from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.home import (
    build_production_goal_html,
    build_production_hero_html,
)


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=2)
def _data(athlete_id):
    return (
        build_home_summary(athlete_id),
        build_home_predictions(athlete_id),
        build_home_latest_run(athlete_id),
    )


def test_production_home_preserves_approved_desktop_and_mobile_goal():
    summary, _, _ = _data(1)
    desktop = build_production_goal_html(summary)
    mobile = build_production_goal_html(summary, mobile=True)

    assert "10K development plan" in desktop
    assert desktop.count("39:00") == 1
    assert "height:auto" in mobile
    assert "overflow:visible" in mobile


def test_production_home_uses_real_independent_athlete_intelligence():
    richard = _data(1)
    jo = _data(3)
    richard_html = build_production_hero_html(1, *richard)
    jo_html = build_production_hero_html(3, *jo)

    assert "SLR 12 miles" in richard_html
    assert "Trail Warrior" in richard_html
    assert "38:17" in richard_html
    assert "Trail Warrior" not in jo_html
    assert "Still emerging" in jo_html
    assert "45:41" in jo_html


def test_production_home_has_sidebar_aware_intermediate_composition():
    richard = _data(1)
    html = build_production_hero_html(1, *richard)

    assert "production-home-hero-container" in html
    assert "production-home-hero" in html
    assert "production-home-passport" in html
    assert "production-home-intelligence" in html
    assert "production-home-outlook" in html
    assert "production-home-mobile-goal" in html
    assert "production-home-wide" not in html
    assert "production-home-intermediate" not in html
    assert "@media (min-width:1201px)" in html
    assert "@container (max-width:1200px)" in html
    assert "grid-template-columns:minmax(245px,.82fr)" in html
    assert "grid-column:1 / -1" in html
    assert "grid-row:2" in html
    assert "display:contents" not in html
    assert "overflow:hidden" in html
    assert "height:100%" in html
    assert html.count('<section class="v8-intelligence">') == 1
    assert html.count('<section class="v8-outlook">') == 1


def test_app_routes_home_to_locked_production_home():
    app_source = (ROOT / "app.py").read_text()
    home_source = (ROOT / "ui" / "home.py").read_text()

    assert "from ui.home import show_home_page" in app_source
    assert 'if page == "Home":\n    show_home_page()' in app_source
    assert "Home preview" not in home_source
    assert "padding-top:4.25rem" in home_source

from functools import lru_cache
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.activity_review import list_review_activities
from core.home_best_runs import build_home_best_runs
from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.activity_navigation import (
    ActivityReviewRequest,
    activity_review_url,
    clear_activity_review_params,
    read_activity_review_request,
)
from ui.home import (
    build_production_hero_html,
    build_production_lower_html,
)


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=2)
def _home_data(athlete_id: int):
    return (
        build_home_summary(athlete_id),
        build_home_predictions(athlete_id),
        build_home_latest_run(athlete_id),
        build_home_best_runs(athlete_id),
    )


def test_activity_review_url_round_trips_exact_evidence():
    url = activity_review_url(1, 9366)
    assert url == "?pp_page=Activities&pp_athlete=1&pp_activity=9366"

    request = read_activity_review_request(
        {
            "pp_page": "Activities",
            "pp_athlete": "1",
            "pp_activity": "9366",
        }
    )
    assert request == ActivityReviewRequest(athlete_id=1, activity_id=9366)


def test_navigation_request_rejects_incomplete_or_invalid_links():
    assert read_activity_review_request({"pp_page": "Activities"}) is None
    assert read_activity_review_request(
        {"pp_page": "Home", "pp_athlete": "1", "pp_activity": "9366"}
    ) is None
    assert read_activity_review_request(
        {"pp_page": "Activities", "pp_athlete": "not-an-id"}
    ) is None


def test_navigation_cleanup_preserves_unrelated_query_parameters():
    params = {
        "pp_page": "Activities",
        "pp_athlete": "1",
        "pp_activity": "9366",
        "keep": "value",
    }
    clear_activity_review_params(params)
    assert params == {"keep": "value"}


def test_latest_run_cards_link_to_real_independent_activity_reviews():
    richard = _home_data(1)
    jo = _home_data(3)
    richard_html = build_production_hero_html(1, *richard[:3])
    jo_html = build_production_hero_html(3, *jo[:3])

    assert richard[2].activity_id == 9366
    assert jo[2].activity_id == 5577
    assert "pp_activity=9366" in richard_html
    assert "pp_activity=5577" in jo_html
    assert "production-activity-link" in richard_html
    assert "View full analysis" in richard_html


def test_every_best_run_card_links_to_its_real_activity():
    for athlete_id in (1, 3):
        summary, _predictions, _latest, best_runs = _home_data(athlete_id)
        html = build_production_lower_html(summary, best_runs)
        expected_ids = {
            best_runs.main.activity_id,
            *(run.activity_id for run in best_runs.category_bests),
        }
        linked_ids = {
            item.activity_id for item in list_review_activities(athlete_id)
        }

        assert expected_ids <= linked_ids
        for activity_id in expected_ids:
            assert f"pp_activity={activity_id}" in html
        assert html.count("production-activity-link") >= len(expected_ids)


def test_activity_page_consumes_link_before_rendering_selectors():
    source = (ROOT / "ui" / "activities.py").read_text(encoding="utf-8")
    sidebar = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert source.index("_apply_home_activity_request()") < source.index(
        "render_athlete_selector("
    )
    assert 'st.session_state["activity_review_window"] = "All time"' in source
    assert 'st.session_state.pop("production_home_athlete_selector", None)' in source
    assert "read_activity_review_request(st.query_params)" in sidebar


@pytest.mark.parametrize(
    ("athlete_id", "activity_id", "athlete_name"),
    (
        (1, 9366, "Richard Burke"),
        (3, 5043, "Joanne Burke"),
    ),
)
def test_streamlit_deep_link_preselects_exact_real_activity(
    athlete_id,
    activity_id,
    athlete_name,
):
    app = AppTest.from_file(str(ROOT / "app.py"))
    app.query_params["pp_page"] = "Activities"
    app.query_params["pp_athlete"] = str(athlete_id)
    app.query_params["pp_activity"] = str(activity_id)
    app.run(timeout=180)

    assert not app.exception
    assert any(item.value == "Activities" for item in app.radio)
    assert any(
        item.label == "Runner" and item.value == athlete_name
        for item in app.selectbox
    )
    assert any(
        item.label == "Activity history" and item.value == "All time"
        for item in app.selectbox
    )
    assert any(
        item.label == "Choose an activity" and item.value == activity_id
        for item in app.selectbox
    )


def test_home_selector_and_content_share_one_athlete_after_round_trip():
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=180)

    home_selector = next(
        item for item in app.selectbox if item.label == "Athlete"
    )
    home_selector.set_value(1)
    app.run(timeout=180)

    app.query_params["pp_page"] = "Activities"
    app.query_params["pp_athlete"] = "1"
    app.query_params["pp_activity"] = "9366"
    app.run(timeout=180)

    primary_navigation = next(
        item for item in app.radio if item.label == "Primary navigation"
    )
    primary_navigation.set_value("Home")
    app.run(timeout=180)

    home_selector = next(
        item for item in app.selectbox if item.label == "Athlete"
    )
    assert home_selector.value == 1
    assert app.session_state["selected_athlete_id"] == 1
    assert app.session_state["selected_athlete_name"] == "Richard Burke"

    home_selector.set_value(3)
    app.run(timeout=180)

    home_selector = next(
        item for item in app.selectbox if item.label == "Athlete"
    )
    assert home_selector.value == 3
    assert app.session_state["selected_athlete_id"] == 3
    assert app.session_state["selected_athlete_name"] == "Joanne Burke"

"""Nutrition Coach links preserve page and athlete isolation."""

from pathlib import Path

from ui.nutrition_coach_navigation import (
    nutrition_coach_url,
    read_nutrition_coach_request,
)


ROOT = Path(__file__).resolve().parent.parent


def test_nutrition_coach_url_round_trips_one_athlete():
    url = nutrition_coach_url(4)
    query = url.split("?", 1)[1]
    params = dict(part.split("=", 1) for part in query.split("&"))
    params["pp_page"] = params["pp_page"].replace("+", " ")

    request = read_nutrition_coach_request(params)

    assert request is not None
    assert request.athlete_id == 4
    assert "pp_athlete=4" in url


def test_nutrition_coach_request_rejects_unknown_or_invalid_targets():
    assert read_nutrition_coach_request({"pp_page": "Home", "pp_athlete": "4"}) is None
    assert read_nutrition_coach_request({"pp_page": "Fuel Planner", "pp_athlete": "Paul"}) is None
    assert read_nutrition_coach_request({"pp_page": "Fuel Planner", "pp_athlete": "-1"}) is None


def test_home_nutrition_card_and_sidebar_use_the_stable_navigation_contract():
    home = (ROOT / "ui" / "lead_coach_home.py").read_text(encoding="utf-8")
    sidebar = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert "nutrition_coach_url(athlete_id)" in home
    assert '"Open your personalised weekly fuel plan", "nutrition"' in home
    assert "read_nutrition_coach_request(st.query_params)" in sidebar
    assert 'requested_page = "Fuel Planner"' in sidebar

from pathlib import Path
from types import SimpleNamespace

import ui.next_run as next_run
from ui.training_coach_navigation import (
    TrainingCoachRequest,
    clear_training_coach_params,
    read_training_coach_request,
    training_coach_url,
)


ROOT = Path(__file__).resolve().parent.parent


def test_training_coach_link_round_trip_preserves_athlete():
    assert training_coach_url(3) == (
        "?pp_page=Next+Run&pp_athlete=3#training-coach"
    )
    request = read_training_coach_request({
        "pp_page": "Next Run",
        "pp_athlete": "3",
    })
    assert request == TrainingCoachRequest(athlete_id=3)


def test_training_coach_link_rejects_wrong_route_or_invalid_athlete():
    assert read_training_coach_request({
        "pp_page": "Activities", "pp_athlete": "3",
    }) is None
    assert read_training_coach_request({
        "pp_page": "Next Run", "pp_athlete": "not-an-id",
    }) is None
    assert read_training_coach_request({
        "pp_page": "Next Run", "pp_athlete": "0",
    }) is None


def test_training_coach_link_cleanup_preserves_unrelated_parameters():
    params = {
        "pp_page": "Next Run",
        "pp_athlete": "1",
        "campaign": "coach-launch",
    }
    clear_training_coach_params(params)
    assert params == {"campaign": "coach-launch"}


def test_sidebar_and_home_connect_to_training_coach_without_reordering_menu():
    sidebar = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")
    home = (ROOT / "ui" / "lead_coach_home.py").read_text(encoding="utf-8")

    assert "read_training_coach_request(st.query_params)" in sidebar
    assert 'requested_page = "Next Run"' in sidebar
    assert "training_coach_url(athlete_id)" in home
    assert "Open Training Coach →" in home
    assert "Full session →" in home


def test_training_coach_deep_link_selects_only_a_valid_athlete(monkeypatch):
    state = {}
    params = {"pp_page": "Next Run", "pp_athlete": "3"}
    monkeypatch.setattr(
        next_run,
        "st",
        SimpleNamespace(session_state=state, query_params=params),
    )
    monkeypatch.setattr(
        next_run,
        "get_athletes",
        lambda: [(1, "Richard", "Burke"), (3, "Joanne", "Burke")],
    )

    next_run._apply_training_coach_request()

    assert state["selected_athlete_id"] == 3
    assert state["selected_athlete_name"] == "Joanne Burke"
    assert params == {}


def test_training_coach_deep_link_cannot_cross_to_an_unknown_athlete(monkeypatch):
    state = {"selected_athlete_id": 1, "selected_athlete_name": "Richard Burke"}
    params = {"pp_page": "Next Run", "pp_athlete": "999"}
    monkeypatch.setattr(
        next_run,
        "st",
        SimpleNamespace(session_state=state, query_params=params),
    )
    monkeypatch.setattr(
        next_run,
        "get_athletes",
        lambda: [(1, "Richard", "Burke"), (3, "Joanne", "Burke")],
    )

    next_run._apply_training_coach_request()

    assert state["selected_athlete_id"] == 1
    assert state["selected_athlete_name"] == "Richard Burke"
    assert params == {}

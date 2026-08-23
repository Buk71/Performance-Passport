from functools import lru_cache
from pathlib import Path

from core.coaching_team import build_coaching_team_detail
from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.coaching_navigation import (
    CoachingTeamRequest,
    clear_coaching_team_params,
    coaching_team_url,
    read_coaching_team_request,
)
from ui.coaching_team import build_coaching_team_html
from ui.home import build_production_hero_html


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=2)
def _team(athlete_id: int):
    return build_coaching_team_detail(athlete_id)


def test_coaching_team_link_round_trips_athlete_and_coach():
    assert coaching_team_url(1, "race") == (
        "?pp_page=Coaching+Team&pp_athlete=1&pp_coach=race#coach-race"
    )
    request = read_coaching_team_request(
        {
            "pp_page": "Coaching Team",
            "pp_athlete": "1",
            "pp_coach": "race",
        }
    )
    assert request == CoachingTeamRequest(athlete_id=1, coach_key="race")


def test_coaching_team_navigation_rejects_invalid_values_and_cleans_its_keys():
    assert read_coaching_team_request({"pp_page": "Coaching Team"}) is None
    assert read_coaching_team_request(
        {"pp_page": "Home", "pp_athlete": "1"}
    ) is None
    request = read_coaching_team_request(
        {
            "pp_page": "Coaching Team",
            "pp_athlete": "3",
            "pp_coach": "invented",
        }
    )
    assert request == CoachingTeamRequest(athlete_id=3, coach_key=None)

    params = {
        "pp_page": "Coaching Team",
        "pp_athlete": "1",
        "pp_coach": "workout",
        "keep": "value",
    }
    clear_coaching_team_params(params)
    assert params == {"keep": "value"}


def test_richard_team_exposes_three_votes_and_two_supporting_specialists():
    detail = _team(1)

    assert detail is not None
    assert detail.athlete_name == "Richard Burke"
    assert detail.lead_coach == "Threshold Coach"
    assert [coach.title for coach in detail.prediction_coaches] == [
        "Race Coach",
        "Workout Coach",
        "Threshold Coach",
    ]
    assert all(
        coach.contributes_to_consensus for coach in detail.prediction_coaches
    )
    assert sum(coach.is_lead for coach in detail.prediction_coaches) == 1
    assert [coach.title for coach in detail.supporting_coaches] == [
        "Aerobic & Durability Coach",
        "Environment Coach",
    ]
    assert not any(
        coach.contributes_to_consensus for coach in detail.supporting_coaches
    )
    assert all(coach.available for coach in detail.supporting_coaches)


def test_jo_team_remains_independent_from_richard():
    richard = _team(1)
    jo = _team(3)

    assert jo is not None
    assert jo.athlete_name == "Joanne Burke"
    assert jo.central_seconds != richard.central_seconds
    assert [
        coach.predicted_seconds for coach in jo.prediction_coaches
    ] != [
        coach.predicted_seconds for coach in richard.prediction_coaches
    ]
    assert jo.supporting_coaches[1].sample_size != (
        richard.supporting_coaches[1].sample_size
    )


def test_coaching_team_page_is_auditable_and_links_selected_real_runs():
    detail = _team(1)
    markup = build_coaching_team_html(detail, focus_key="workout")

    assert "One athlete.<br>Five evidence specialists." in markup
    assert "The three direct opinions" in markup
    assert "The supporting specialists" in markup
    assert "Aerobic &amp; Durability Coach" in markup
    assert "Environment Coach" in markup
    assert "Open evidence audit" in markup
    assert "Not an extra prediction vote" in markup
    assert 'id="coach-workout"' in markup
    assert 'class="ct-coach-card ct-focused"' in markup
    assert "pp_activity=3730" in markup
    assert "pp_activity=9358" in markup
    assert "pp_activity=3634" not in markup
    assert "color:#fff !important" in markup
    assert "font-size:15px" in markup
    assert "font-size:14.5px" in markup


def test_home_coach_cards_link_to_the_new_team_page():
    predictions = build_home_predictions(1)
    markup = build_production_hero_html(
        1,
        build_home_summary(1),
        predictions,
        build_home_latest_run(1),
    )

    assert "View team" in markup
    assert markup.count("pp_page=Coaching+Team") == 4
    assert "pp_coach=race" in markup
    assert "pp_coach=workout" in markup
    assert "pp_coach=threshold" in markup
    assert "color:#10263d !important" in markup
    assert ".production-coaching-card-link:visited" in markup


def test_coaching_team_is_wired_into_app_and_sidebar():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    sidebar = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert 'elif page == "Coaching Team"' in app
    assert '"Coaching Team"' in sidebar
    assert "read_coaching_team_request(st.query_params)" in sidebar

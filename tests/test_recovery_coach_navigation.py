from pathlib import Path

from ui.recovery_coach_navigation import (
    clear_recovery_coach_params,
    read_recovery_coach_request,
    recovery_coach_url,
)


ROOT = Path(__file__).resolve().parent.parent


def test_recovery_coach_url_round_trips_one_positive_athlete():
    assert recovery_coach_url(4) == "?pp_page=Recovery+Coach&pp_athlete=4#recovery-coach"
    request = read_recovery_coach_request(
        {"pp_page": "Recovery Coach", "pp_athlete": "4"}
    )
    assert request is not None
    assert request.athlete_id == 4


def test_recovery_coach_navigation_rejects_invalid_targets_and_clears_only_its_params():
    assert read_recovery_coach_request(
        {"pp_page": "Recovery Coach", "pp_athlete": "unknown"}
    ) is None
    params = {
        "pp_page": "Recovery Coach",
        "pp_athlete": "4",
        "unrelated": "keep",
    }
    clear_recovery_coach_params(params)
    assert params == {"unrelated": "keep"}


def test_home_sidebar_and_app_share_the_stable_recovery_route():
    home = (ROOT / "ui" / "lead_coach_home.py").read_text(encoding="utf-8")
    sidebar = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "recovery_coach_url(athlete_id)" in home
    assert 'requested_page = "Recovery Coach"' in sidebar
    assert 'elif page == "Recovery Coach"' in app

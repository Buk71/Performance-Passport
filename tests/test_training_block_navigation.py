from pathlib import Path

from ui.training_block_navigation import (
    TrainingBlockWeekRequest,
    clear_training_block_week_params,
    read_training_block_week_request,
    training_block_week_url,
)


ROOT = Path(__file__).resolve().parent.parent


def test_week_link_preserves_route_athlete_and_selection():
    assert training_block_week_url(3, 4) == (
        "?pp_page=Training+Blocks&pp_athlete=3&pp_training_week=4"
        "#training-week-detail"
    )
    request = read_training_block_week_request({
        "pp_page": "Training Blocks",
        "pp_athlete": "3",
        "pp_training_week": "4",
    })
    assert request == TrainingBlockWeekRequest(athlete_id=3, week_number=4)


def test_week_request_rejects_wrong_route_or_invalid_identity():
    assert read_training_block_week_request({
        "pp_page": "Home", "pp_athlete": "3", "pp_training_week": "2",
    }) is None
    assert read_training_block_week_request({
        "pp_page": "Training Blocks", "pp_athlete": "bad", "pp_training_week": "2",
    }) is None


def test_week_navigation_cleanup_preserves_unrelated_parameters():
    params = {
        "pp_page": "Training Blocks", "pp_athlete": "1",
        "pp_training_week": "2", "keep": "value",
    }
    clear_training_block_week_params(params)
    assert params == {"keep": "value"}

    sidebar = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")
    assert "read_training_block_week_request(st.query_params)" in sidebar
    assert 'requested_page = "Training Blocks"' in sidebar

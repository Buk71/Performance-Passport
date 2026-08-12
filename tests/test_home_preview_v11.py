from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.home_preview_v11 import build_v11_goal_html, build_v11_hero_html


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=2)
def _data(athlete_id):
    return (
        build_home_summary(athlete_id),
        build_home_predictions(athlete_id),
        build_home_latest_run(athlete_id),
    )


def test_v11_compact_goal_can_grow_and_cannot_clip():
    home, _, _ = _data(1)
    html = build_v11_goal_html(home, mobile=True)

    assert "height:auto" in html
    assert "overflow:visible" in html
    assert "grid-template-columns:auto minmax(0,1fr)" in html
    assert "10K development plan" in html
    assert html.count("39:00") == 1


def test_v11_desktop_goal_is_exactly_v10():
    home, _, _ = _data(1)

    from ui.home_preview_v10 import build_v10_goal_html

    assert build_v11_goal_html(home) == build_v10_goal_html(home)


def test_v11_preserves_real_intelligence_for_both_athletes():
    richard_home, richard_predictions, richard_latest = _data(1)
    jo_home, jo_predictions, jo_latest = _data(3)
    richard_html = build_v11_hero_html(
        1, richard_home, richard_predictions, richard_latest
    )
    jo_html = build_v11_hero_html(3, jo_home, jo_predictions, jo_latest)

    assert "SLR 12 miles" in richard_html
    assert "Trail Warrior" in richard_html
    assert "38:17" in richard_html
    assert "Trail Warrior" not in jo_html
    assert "Still emerging" in jo_html
    assert "45:41" in jo_html


def test_v11_protects_the_approved_v10_source():
    assert sha256((ROOT / "ui" / "home_preview_v10.py").read_bytes()).hexdigest() == (
        "49349e2311bed7310e751793d458377f3e4e9db15196dc0b0924211fe2c44a39"
    )

from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import re

from core.home_best_runs import build_home_best_runs
from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.home_preview_v10 import (
    _athlete_display_name,
    build_v10_goal_html,
    build_v10_hero_html,
    build_v10_lower_html,
)


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=2)
def _data(athlete_id):
    return (
        build_home_summary(athlete_id),
        build_home_predictions(athlete_id),
        build_home_latest_run(athlete_id),
        build_home_best_runs(athlete_id),
    )


def test_v10_richard_goal_is_not_repeated_and_direction_is_natural():
    home, _, _, _ = _data(1)
    goal_html = build_v10_goal_html(home)

    assert goal_html.count("39:00") == 1
    assert "10K development plan" in goal_html
    assert "adaptive direction" not in goal_html.lower()


def test_v10_jo_goal_is_not_repeated_and_uses_preferred_display_name():
    home, _, _, _ = _data(3)
    goal_html = build_v10_goal_html(home)

    assert "Sub 45" in goal_html
    assert '<span class="v8-goal-target">45:00</span>' not in goal_html
    assert _athlete_display_name((3, "Joanne", "Burke")) == "Jo Burke"
    assert _athlete_display_name((1, "Richard", "Burke")) == "Richard Burke"


def test_v10_keeps_real_intelligence_values_and_athlete_isolation():
    richard_home, richard_predictions, richard_latest, _ = _data(1)
    jo_home, jo_predictions, jo_latest, _ = _data(3)
    richard_html = build_v10_hero_html(
        1, richard_home, richard_predictions, richard_latest
    )
    jo_html = build_v10_hero_html(3, jo_home, jo_predictions, jo_latest)

    assert "SLR 12 miles" in richard_html
    assert "#10" in richard_html
    assert "Trail Warrior" in richard_html
    assert "38:17" in richard_html
    assert "39:10" in richard_html
    assert "39:48" in richard_html
    assert "Trail Warrior" not in jo_html
    assert "Still emerging" in jo_html
    assert "45:41" in jo_html
    assert "49:37" in jo_html
    assert "46:38" in jo_html


def test_v10_aligns_outlook_metadata_and_allows_week_copy_to_wrap():
    home, _, _, best = _data(1)
    source = (ROOT / "ui" / "home_preview_v10.py").read_text(encoding="utf-8")
    css_source = source.replace("{{", "{").replace("}}", "}")
    lower_html = build_v10_lower_html(home, best)

    assert ".v10-intelligence-shell .v8-scenario" in css_source
    assert "display:flex; flex-direction:column" in css_source
    assert "margin-top:auto; padding-top:5px" in css_source
    assert "overflow:visible" in lower_html
    assert lower_html.index("This week") < lower_html.index("Best runs")


def test_v10_retains_the_type_floor_baseline_and_protects_v9():
    source = (ROOT / "ui" / "home_preview_v10.py").read_text(encoding="utf-8")
    pixel_sizes = [
        float(value)
        for value in re.findall(r"font-size\s*:\s*([0-9.]+)px", source)
    ]

    assert not pixel_sizes or min(pixel_sizes) >= 10
    assert sha256((ROOT / "ui" / "home_preview_v9.py").read_bytes()).hexdigest() == (
        "16a848e28229c4279bb06829e169fe53fba3d1c35bab6519ce2314e915cf95d2"
    )

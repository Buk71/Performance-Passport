from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import re

from core.home_best_runs import build_home_best_runs
from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.home_preview_v9 import (
    build_v9_goal_html,
    build_v9_hero_html,
    build_v9_lower_html,
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


def test_v9_richard_keeps_real_intelligence_and_uses_concise_display_copy():
    home, predictions, latest, best = _data(1)
    hero_html = build_v9_hero_html(1, home, predictions, latest)
    lower_html = build_v9_lower_html(home, best)

    assert "SLR 12 miles" in hero_html
    assert "#10" in hero_html
    assert "Trail Warrior" in hero_html
    assert "Trail costs you 35% less than the standard model." in hero_html
    assert "Proven race results set your competitive ceiling." in hero_html
    assert "Cool · flat · light wind" in hero_html
    assert "Threshold Coach" not in hero_html
    assert lower_html.index("This week") < lower_html.index("Best runs")


def test_v9_keeps_jo_independent_and_does_not_invent_an_edge():
    home, predictions, latest, best = _data(3)
    hero_html = build_v9_hero_html(3, home, predictions, latest)
    lower_html = build_v9_lower_html(home, best)

    assert "SLR 12 miles" not in hero_html
    assert "Trail Warrior" not in hero_html
    assert "Still emerging" in hero_html
    assert "Still learning" in hero_html
    assert "45:41" in hero_html
    assert "50:44" in hero_html
    assert "46:39" in hero_html
    assert "Best runs" in lower_html


def test_v9_goal_removes_desktop_truncation_without_losing_goal_content():
    home, _, _, _ = _data(1)
    goal_html = build_v9_goal_html(home)

    assert "Sub 39:00" in goal_html
    assert home.block_name in goal_html
    assert ".v9-goal .v8-goal-direction-copy { display:none; }" in goal_html
    assert "overflow:visible" in goal_html


def test_v9_passport_and_race_outlook_share_an_exact_desktop_baseline():
    source = (ROOT / "ui" / "home_preview_v9.py").read_text(encoding="utf-8")
    css_source = source.replace("{{", "{").replace("}}", "}")

    assert "gap:8px; align-items:stretch" in css_source
    assert ".v9-passport .pp-shell," in css_source
    assert ".v9-passport .pp-passport { height:100%; }" in css_source
    assert ".v9-passport .pp-development" in css_source
    assert "flex:1 1 auto; display:flex; flex-direction:column" in css_source
    assert ".v9-passport .chart { flex:1 1 39px" in css_source


def test_v9_keeps_the_v8_type_floor_and_protects_v8_source():
    source = (ROOT / "ui" / "home_preview_v9.py").read_text(encoding="utf-8")
    pixel_sizes = [
        float(value)
        for value in re.findall(r"font-size\s*:\s*([0-9.]+)px", source)
    ]

    assert pixel_sizes
    assert min(pixel_sizes) >= 10
    assert sha256((ROOT / "ui" / "home_preview_v8.py").read_bytes()).hexdigest() == (
        "5ab0b1de09529acc2fd28e1716e31d88d21b3737d531376466f3fc8a638284da"
    )

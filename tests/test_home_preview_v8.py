from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import re

from core.home_best_runs import build_home_best_runs
from core.home_latest_run import build_home_latest_run
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.home_preview_v8 import (
    build_v8_goal_html,
    build_v8_hero_html,
    build_v8_lower_html,
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


def test_v8_hierarchy_uses_real_richard_data():
    home, predictions, latest, best = _data(1)
    goal_html = build_v8_goal_html(home)
    hero_html = build_v8_hero_html(1, home, predictions, latest)
    lower_html = build_v8_lower_html(home, best)

    assert "Sub 39:00" in goal_html
    assert "SLR 12 miles" in hero_html
    assert "#10" in hero_html
    assert "Trail Warrior" in hero_html
    assert hero_html.index("Performance Intelligence") < hero_html.index("Race Outlook")
    assert lower_html.index("This week") < lower_html.index("Up next")
    assert lower_html.index("Up next") < lower_html.index("Best runs")


def test_v8_keeps_jo_independent_and_does_not_invent_edge():
    home, predictions, latest, best = _data(3)
    goal_html = build_v8_goal_html(home)
    hero_html = build_v8_hero_html(3, home, predictions, latest)
    lower_html = build_v8_lower_html(home, best)

    assert "Sub 45" in goal_html
    assert "SLR 12 miles" not in hero_html
    assert "Trail Warrior" not in hero_html
    assert "Still emerging" in hero_html
    assert "Best runs" in lower_html


def test_v8_has_one_readable_type_floor_and_natural_height_panels():
    source = (ROOT / "ui" / "home_preview_v8.py").read_text(encoding="utf-8")
    pixel_sizes = [
        float(value)
        for value in re.findall(r"font-size\s*:\s*([0-9.]+)px", source)
    ]

    assert pixel_sizes
    assert min(pixel_sizes) >= 10
    assert "height:100%" not in source.replace(" ", "")
    assert "grid-template-rows:minmax(0,1fr)" not in source.replace(" ", "")


def test_v8_mobile_order_keeps_goal_after_passport():
    home, predictions, latest, _ = _data(1)
    html = build_v8_hero_html(1, home, predictions, latest)

    assert 'class="v8-passport"' in html
    assert 'class="v8-mobile-goal"' in html
    assert html.index('class="v8-passport"') < html.index('class="v8-mobile-goal"')
    assert html.index('class="v8-mobile-goal"') < html.index("Performance Intelligence")


def test_v8_does_not_modify_v6_or_v7_rollback_previews():
    expected = {
        "ui/home_preview.py": "9eb7f693e1cadf388a55d9acf6b0b83ca72ceca0f98f8535961cb4112d8f7523",
        "ui/home_preview_v7.py": "154daecf243526c3565842b23ca093f78ebd07c03d6845d95bedcaaf010d8822",
    }

    for relative_path, expected_digest in expected.items():
        actual_digest = sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual_digest == expected_digest

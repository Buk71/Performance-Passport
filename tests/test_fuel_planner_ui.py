import datetime
from pathlib import Path

from core.fuel_planner import NutritionProfile, compose_fuel_week
from ui.fuel_planner import build_day_fuel_html, build_fuel_week_overview_html


ROOT = Path(__file__).resolve().parent.parent


def _week():
    plan = {
        "week_number": 1, "start_date": "2026-08-17", "end_date": "2026-08-23",
        "phase": "Base", "emphasis": "Aerobic support", "days": [
            {"day": day, "session_type": "Long run" if index == 6 else "Easy",
             "detail": "10 mi" if index == 6 else "5 mi", "is_hard": index == 6}
            for index, day in enumerate((
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
            ))
        ],
    }
    return compose_fuel_week(
        athlete_id=1, training_block_id=2, block_name="Sub 39 Training Block", week=plan,
    )


def test_overview_is_responsive_and_explicitly_read_only_to_training():
    markup = build_fuel_week_overview_html(
        _week(), NutritionProfile(1, dietary_style="Vegetarian", servings=2),
    )
    assert "NEXT TRAINING WEEK" in markup
    assert "VEGETARIAN · 2 SERVINGS" in markup
    assert "never change the Training Block" in markup
    assert "container-type:inline-size" in markup
    assert "@container (max-width:720px)" in markup


def test_day_surface_explains_before_during_and_after():
    markup = build_day_fuel_html(_week().days[-1])
    assert "LONG RUN / RACE FUEL" in markup
    assert "Before" in markup
    assert "During" in markup
    assert "After" in markup


def test_production_page_contains_profile_choices_and_shopping_list():
    source = (ROOT / "ui" / "fuel_planner.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    sidebar = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert '"Dietary style"' in source
    assert '"Allergies or intolerances — separate with commas"' in source
    assert '"Save choices and build shopping list"' in source
    assert '"Omnivore balance: lunch and dinner lead with a rotating meat "' in source
    assert '"Combine every athlete saved for this week"' in source
    assert '"Download shopping list (CSV)"' in source
    assert 'page == "Fuel Planner"' in app
    assert '"Fuel Planner"' in sidebar

import datetime
from pathlib import Path

from core.fuel_planner import RECIPE_BY_ID, NutritionProfile, compose_fuel_week
from ui.fuel_planner import (
    build_day_fuel_html,
    build_fuel_week_overview_html,
    build_nutrition_coach_hero_html,
    build_nutrition_week_strip_html,
    build_recipe_choice_html,
)


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
    assert '"Save meal choices and update shopping list"' in source
    assert '"Omnivore balance: lunch and dinner lead with a rotating meat "' in source
    assert '"Combine every athlete saved for this week"' in source
    assert '"Download shopping list (CSV)"' in source
    assert 'meal_options(profile, day, slot, count=3)' in source
    assert 'st.tabs(' in source
    assert 'page == "Fuel Planner"' in app
    assert '"Fuel Planner"' in sidebar


def test_nutrition_coach_hero_leads_with_profile_and_key_session():
    markup = build_nutrition_coach_hero_html(
        "Richard Burke",
        NutritionProfile(1, dietary_style="Vegetarian", servings=2),
        _week(),
    )

    assert "Nutrition Coach · Richard" in markup
    assert "Fuel the work, without making food complicated." in markup
    assert "3 per meal" in markup
    assert "VEGETARIAN" not in markup
    assert "Vegetarian" in markup
    assert "color:#fff!important" in markup


def test_week_strip_connects_all_seven_days_to_training_demand():
    markup = build_nutrition_week_strip_html(_week())

    assert markup.count('class="nc-week-day ') == 7
    assert "One week, seven different demands." in markup
    assert "Long run / race" in markup
    assert "Meals support the plan; they never rewrite it." in markup


def test_selected_recipe_card_explains_practical_choice_and_optional_detail():
    recipe = RECIPE_BY_ID["d_tofu_noodles"]
    markup = build_recipe_choice_html(
        recipe,
        choice_label="Nutrition Coach recommendation",
        show_detail=True,
    )

    assert recipe.name in markup
    assert "Nutrition Coach recommendation" in markup
    assert "Carbohydrate-supportive" in markup
    assert "Higher protein" in markup
    assert "720 kcal" in markup

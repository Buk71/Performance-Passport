import datetime

from core.fuel_planner import (
    MEAL_SLOTS,
    NutritionProfile,
    compose_fuel_week,
    load_next_fuel_week,
    meal_options,
)
from core.goals import build_goal_hierarchy
from core.training_block_designer import (
    build_training_history_profile,
    design_training_block,
    recommend_preferences,
)


REFERENCE_DATE = datetime.date(2026, 8, 14)


def test_jo_real_saved_block_becomes_an_independent_fuel_week():
    week = load_next_fuel_week(3, reference_date=REFERENCE_DATE)

    assert week is not None
    assert week.athlete_id == 3
    assert week.block_name == "Sub 45 Training Block"
    assert week.start_date == "2026-08-17"
    assert [day.demand for day in week.days] == [
        "Rest / recovery", "Quality", "Easy", "Easy",
        "Rest / recovery", "Easy", "Long run / race",
    ]


def test_richard_real_history_can_feed_nutrition_without_saving_test_data():
    history = build_training_history_profile(1, reference_date=REFERENCE_DATE)
    hierarchy = build_goal_hierarchy(1, reference_date=REFERENCE_DATE)
    design = design_training_block(
        history=history,
        hierarchy=hierarchy,
        preferences=recommend_preferences(history),
        reference_date=REFERENCE_DATE,
    )
    plan = design.to_dict()
    week = compose_fuel_week(
        athlete_id=1,
        training_block_id=999,
        block_name=design.block_name,
        week=plan["weeks"][0],
    )
    vegan = NutritionProfile(
        athlete_id=1,
        dietary_style="Vegan",
        max_cook_minutes=90,
    )

    assert week.athlete_id == 1
    assert week.block_name == "Sub 39:00 Training Block"
    assert len(week.days) == 7
    assert all(
        len(meal_options(vegan, day, slot)) == 3
        for day in week.days
        for slot in MEAL_SLOTS
    )
    # The production loader remains honest: Richard has generated direction
    # but no active saved block in this handover database.
    assert load_next_fuel_week(1, reference_date=REFERENCE_DATE) is None

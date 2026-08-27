import datetime
import sqlite3
import unittest
from unittest.mock import patch

from core.fuel_planner import (
    DIETARY_STYLES,
    MEAL_SLOTS,
    RECIPE_BY_ID,
    FuelDay,
    MealSelection,
    NutritionProfile,
    build_shopping_list,
    compose_fuel_week,
    load_nutrition_profile,
    load_week_selections,
    meal_options,
    save_nutrition_profile,
    save_week_selections,
    training_demand,
)


def _day(date="2026-08-17", demand="Quality"):
    return FuelDay(
        day="Monday", date=date, session_type="Threshold development",
        session_detail="Controlled quality", demand=demand,
        focus="Performance day", pre_training="Eat", during_training="Drink",
        recovery="Recover",
    )


class FuelPlannerCoreTests(unittest.TestCase):
    def test_every_diet_has_real_choice_in_every_meal_slot(self):
        for style in DIETARY_STYLES:
            profile = NutritionProfile(
                athlete_id=1, dietary_style=style, max_cook_minutes=90,
            )
            for slot in MEAL_SLOTS:
                options = meal_options(profile, _day(), slot)
                self.assertGreaterEqual(len(options), 3, (style, slot))
                if style == "Vegan":
                    self.assertTrue(all(item.dietary_style == "Vegan" for item in options))

    def test_default_choice_contract_is_one_recommendation_plus_two_alternatives(self):
        profile = NutritionProfile(
            athlete_id=1, dietary_style="Omnivore", max_cook_minutes=90,
        )
        options = meal_options(profile, _day(), "Dinner")

        self.assertEqual(len(options), 3)
        self.assertEqual(len({recipe.id for recipe in options}), 3)
        self.assertIn(options[0].dietary_style, {"Omnivore", "Pescatarian"})
        self.assertIn(options[1].dietary_style, {"Vegetarian", "Vegan"})

    def test_third_alternative_is_a_complete_shoppable_recipe(self):
        profile = NutritionProfile(
            athlete_id=1, dietary_style="Vegetarian", max_cook_minutes=90,
        )
        recipe = meal_options(profile, _day(), "Dinner")[2]
        choice = MealSelection(
            1, 9, "2026-08-17", "2026-08-17", "Dinner", recipe.id, 2,
        )

        items = build_shopping_list((choice,), include_pantry=True)

        self.assertTrue(items)
        self.assertEqual(
            {item.name for item in items},
            {ingredient.name for ingredient in recipe.ingredients},
        )

    def test_choices_rotate_between_days(self):
        profile = NutritionProfile(athlete_id=1, dietary_style="Vegan", max_cook_minutes=90)
        first = meal_options(profile, _day("2026-08-17"), "Dinner")
        second = meal_options(profile, _day("2026-08-18"), "Dinner")
        self.assertNotEqual([item.id for item in first], [item.id for item in second])

    def test_omnivore_main_meals_balance_animal_and_plant_choices(self):
        profile = NutritionProfile(
            athlete_id=3, dietary_style="Omnivore", max_cook_minutes=90,
        )
        animal_choices = set()
        for offset in range(7):
            date = (datetime.date(2026, 8, 17) + datetime.timedelta(days=offset)).isoformat()
            for slot in ("Lunch", "Dinner"):
                options = meal_options(profile, _day(date), slot)
                self.assertIn(options[0].dietary_style, {"Omnivore", "Pescatarian"})
                self.assertIn(options[1].dietary_style, {"Vegetarian", "Vegan"})
                animal_choices.add(options[0].id)
        self.assertGreaterEqual(len(animal_choices), 6)

    def test_pescatarian_main_meals_lead_with_fish_not_meat(self):
        profile = NutritionProfile(
            athlete_id=3, dietary_style="Pescatarian", max_cook_minutes=90,
        )
        for slot in ("Lunch", "Dinner"):
            options = meal_options(profile, _day(), slot)
            self.assertEqual(options[0].dietary_style, "Pescatarian")
            self.assertIn(options[1].dietary_style, {"Vegetarian", "Vegan"})

    def test_allergy_and_dislike_filters_remove_recipes(self):
        profile = NutritionProfile(
            athlete_id=1, dietary_style="Vegan", max_cook_minutes=90,
            allergies=("soya",), dislikes=("mushrooms",),
        )
        for slot in MEAL_SLOTS:
            for recipe in meal_options(profile, _day(), slot, count=10):
                self.assertNotIn("Soya", recipe.allergens)
                searchable = " ".join(
                    [recipe.name, *(item.name for item in recipe.ingredients)]
                ).lower()
                self.assertNotIn("mushrooms", searchable)

    def test_training_demand_uses_saved_session_purpose(self):
        self.assertEqual(training_demand("Rest"), "Rest / recovery")
        self.assertEqual(training_demand("Recovery"), "Easy")
        self.assertEqual(training_demand("Threshold development", is_hard=True), "Quality")
        self.assertEqual(training_demand("Long run", is_hard=True), "Long run / race")

    def test_composed_week_preserves_training_and_maps_fuel_demand(self):
        source = {
            "week_number": 1, "start_date": "2026-08-17", "end_date": "2026-08-23",
            "phase": "Base", "emphasis": "Durable routine", "days": [
                {"day": "Monday", "session_type": "Rest", "detail": "No running", "is_hard": False},
                {"day": "Tuesday", "session_type": "Threshold", "detail": "Controlled quality", "is_hard": True},
                {"day": "Wednesday", "session_type": "Easy", "detail": "5 mi", "is_hard": False},
                {"day": "Thursday", "session_type": "Recovery", "detail": "4 mi", "is_hard": False},
                {"day": "Friday", "session_type": "Rest", "detail": "No running", "is_hard": False},
                {"day": "Saturday", "session_type": "Easy", "detail": "5 mi", "is_hard": False},
                {"day": "Sunday", "session_type": "Long run", "detail": "10 mi", "is_hard": True},
            ],
        }
        result = compose_fuel_week(
            athlete_id=1, training_block_id=9, block_name="10K block", week=source,
        )
        self.assertEqual(result.days[1].session_detail, "Controlled quality")
        self.assertEqual(result.days[1].demand, "Quality")
        self.assertEqual(result.days[-1].demand, "Long run / race")
        self.assertEqual(source["days"][1]["session_type"], "Threshold")

    def test_shopping_list_combines_repeated_ingredients_and_servings(self):
        choices = (
            MealSelection(1, 9, "2026-08-17", "2026-08-17", "Breakfast", "b_berry_oats", 2),
            MealSelection(1, 9, "2026-08-17", "2026-08-18", "Recovery snack", "s_choc_banana", 2),
        )
        items = build_shopping_list(choices, include_pantry=False)
        bananas = next(item for item in items if item.name == "Bananas")
        self.assertEqual(bananas.amount, 4)
        self.assertEqual(bananas.unit, "item")
        self.assertNotIn("Ground cinnamon", {item.name for item in items})


class FuelPlannerPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE athletes (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT);
            CREATE TABLE training_blocks (id INTEGER PRIMARY KEY, athlete_id INTEGER);
            INSERT INTO athletes VALUES (1, 'Richard', 'Burke');
            INSERT INTO athletes VALUES (3, 'Joanne', 'Burke');
            INSERT INTO training_blocks VALUES (9, 1);
            """
        )

    def tearDown(self):
        self.connection.close()

    def _connect(self):
        return self.connection

    def test_profile_and_week_choices_round_trip_without_cross_athlete_leakage(self):
        # Keep the shared in-memory connection open by returning a non-closing proxy.
        class Proxy:
            def __init__(self, connection):
                self.connection = connection
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def close(self):
                pass

        with patch("core.fuel_planner.get_connection", lambda: Proxy(self.connection)):
            profile = NutritionProfile(
                athlete_id=1, dietary_style="Vegan", servings=2,
                allergies=("Peanuts",), dislikes=("Mushrooms",),
                max_cook_minutes=30, budget_style="Value conscious",
            )
            save_nutrition_profile(profile)
            loaded = load_nutrition_profile(1)
            self.assertEqual(loaded.dietary_style, "Vegan")
            self.assertEqual(loaded.allergies, ("Peanuts",))
            self.assertIsNone(load_nutrition_profile(3))

            choices = (
                MealSelection(1, 9, "2026-08-17", "2026-08-17", "Breakfast", "b_berry_oats", 2),
                MealSelection(1, 9, "2026-08-17", "2026-08-17", "Lunch", "l_lentil_quinoa", 2),
            )
            self.assertEqual(save_week_selections(choices), 2)
            saved = load_week_selections(1, "2026-08-17")
            self.assertEqual(saved[("2026-08-17", "Lunch")].recipe_id, "l_lentil_quinoa")
            self.assertEqual(load_week_selections(3, "2026-08-17"), {})


if __name__ == "__main__":
    unittest.main()

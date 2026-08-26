"""Deterministic next-week fuelling and shopping-list planning.

Fuel Planner is downstream of the athlete-approved Training Block. It reads
the effective weekly shape (including accepted Block Review overlays) but can
never change that training plan. A curated recipe catalogue keeps dietary
filtering, portions and shopping quantities auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import datetime
import io
import json
from typing import Any, Iterable

from core.block_review import apply_accepted_block_reviews
from core.database import create_nutrition_tables, get_connection
from core.training_blocks import (
    get_active_training_block,
    get_training_block_design,
)


DIETARY_STYLES = ("Omnivore", "Pescatarian", "Vegetarian", "Vegan")
BUDGET_STYLES = ("Value conscious", "Standard", "Flexible")
MEAL_SLOTS = ("Breakfast", "Lunch", "Dinner", "Recovery snack")
DEMANDS = ("Rest / recovery", "Easy", "Quality", "Long run / race")
MODEL_VERSION = 1


@dataclass(frozen=True)
class Ingredient:
    name: str
    amount: float
    unit: str
    category: str
    pantry: bool = False


@dataclass(frozen=True)
class Recipe:
    id: str
    name: str
    slot: str
    dietary_style: str
    summary: str
    ingredients: tuple[Ingredient, ...]
    allergens: tuple[str, ...]
    demand_tags: tuple[str, ...]
    cook_minutes: int
    energy_kcal: int
    carbohydrate_g: int
    protein_g: int
    batch_friendly: bool = False


@dataclass(frozen=True)
class NutritionProfile:
    athlete_id: int
    dietary_style: str = "Omnivore"
    servings: int = 1
    allergies: tuple[str, ...] = ()
    dislikes: tuple[str, ...] = ()
    max_cook_minutes: int = 45
    budget_style: str = "Standard"
    use_leftovers: bool = True
    show_nutrition_detail: bool = False
    updated_at: str | None = None


@dataclass(frozen=True)
class FuelDay:
    day: str
    date: str
    session_type: str
    session_detail: str
    demand: str
    focus: str
    pre_training: str
    during_training: str
    recovery: str


@dataclass(frozen=True)
class FuelWeek:
    athlete_id: int
    training_block_id: int
    block_name: str
    week_number: int
    start_date: str
    end_date: str
    phase: str
    emphasis: str
    days: tuple[FuelDay, ...]
    source: str = "Accepted Training Block"
    model_version: int = MODEL_VERSION


@dataclass(frozen=True)
class MealSelection:
    athlete_id: int
    training_block_id: int
    week_start: str
    meal_date: str
    meal_slot: str
    recipe_id: str
    servings: int


@dataclass(frozen=True)
class ShoppingItem:
    name: str
    amount: float
    unit: str
    category: str
    pantry: bool


def _i(
    name: str,
    amount: float,
    unit: str,
    category: str,
    pantry: bool = False,
) -> Ingredient:
    return Ingredient(name, amount, unit, category, pantry)


def _r(
    recipe_id: str,
    name: str,
    slot: str,
    style: str,
    summary: str,
    ingredients: tuple[Ingredient, ...],
    allergens: tuple[str, ...],
    demands: tuple[str, ...],
    minutes: int,
    kcal: int,
    carbs: int,
    protein: int,
    batch: bool = False,
) -> Recipe:
    return Recipe(
        recipe_id, name, slot, style, summary, ingredients, allergens,
        demands, minutes, kcal, carbs, protein, batch,
    )


RECIPES = (
    # Breakfasts: the vegan set is deliberately broad enough to remain a
    # genuine weekly choice rather than a single token substitution.
    _r("b_berry_oats", "Berry, banana & chia overnight oats", "Breakfast", "Vegan",
       "Fortified soya milk, oats and fruit for an easy carbohydrate-protein start.",
       (_i("Porridge oats", 70, "g", "Bakery & grains"), _i("Fortified soya milk", 250, "ml", "Chilled"), _i("Bananas", 1, "item", "Fruit & vegetables"), _i("Frozen berries", 100, "g", "Fruit & vegetables"), _i("Chia seeds", 12, "g", "Cupboard")),
       ("Soya",), DEMANDS, 5, 570, 91, 19),
    _r("b_apple_walnut", "Apple & walnut porridge", "Breakfast", "Vegan",
       "Warm oats with fruit, walnuts and a calcium-fortified drink.",
       (_i("Porridge oats", 70, "g", "Bakery & grains"), _i("Fortified oat drink", 300, "ml", "Chilled"), _i("Apples", 1, "item", "Fruit & vegetables"), _i("Walnuts", 20, "g", "Cupboard"), _i("Ground cinnamon", 1, "tsp", "Cupboard", True)),
       ("Gluten", "Tree nuts"), DEMANDS, 8, 545, 78, 14),
    _r("b_tofu_wrap", "Tofu, spinach & tomato breakfast wrap", "Breakfast", "Vegan",
       "A savoury higher-protein breakfast suited to demanding days.",
       (_i("Wholemeal wraps", 2, "item", "Bakery & grains"), _i("Calcium-set tofu", 150, "g", "Plant protein"), _i("Baby spinach", 50, "g", "Fruit & vegetables"), _i("Tomatoes", 2, "item", "Fruit & vegetables"), _i("Avocado", .5, "item", "Fruit & vegetables"), _i("Rapeseed oil", 1, "tsp", "Cupboard", True)),
       ("Gluten", "Soya"), ("Easy", "Quality", "Long run / race"), 15, 610, 66, 30),
    _r("b_banana_toast", "Banana peanut toast & soya yoghurt", "Breakfast", "Vegan",
       "Quick, familiar carbohydrate with plant protein for pre-run mornings.",
       (_i("Wholemeal bread", 3, "slice", "Bakery & grains"), _i("Bananas", 1, "item", "Fruit & vegetables"), _i("Peanut butter", 25, "g", "Cupboard"), _i("Fortified soya yoghurt", 150, "g", "Chilled")),
       ("Gluten", "Peanuts", "Soya"), ("Easy", "Quality", "Long run / race"), 5, 600, 88, 23),
    _r("b_yoghurt_muesli", "Greek yoghurt, muesli & berries", "Breakfast", "Vegetarian",
       "A no-cook breakfast with carbohydrate, fruit and dairy protein.",
       (_i("Greek yoghurt", 250, "g", "Chilled"), _i("Muesli", 70, "g", "Bakery & grains"), _i("Frozen berries", 100, "g", "Fruit & vegetables"), _i("Honey", 15, "g", "Cupboard")),
       ("Milk", "Gluten", "Tree nuts"), DEMANDS, 3, 520, 70, 29),
    _r("b_eggs_toast", "Eggs, avocado & wholemeal toast", "Breakfast", "Vegetarian",
       "Egg protein, wholegrain carbohydrate and unsaturated fat.",
       (_i("Eggs", 3, "item", "Chilled"), _i("Wholemeal bread", 3, "slice", "Bakery & grains"), _i("Avocado", .5, "item", "Fruit & vegetables"), _i("Tomatoes", 2, "item", "Fruit & vegetables")),
       ("Egg", "Gluten"), ("Rest / recovery", "Easy", "Quality"), 12, 590, 55, 30),

    # Lunches.
    _r("l_lentil_quinoa", "Lentil, quinoa & roast vegetable bowl", "Lunch", "Vegan",
       "Iron-rich pulses with vitamin-C-rich vegetables and wholegrain carbohydrate.",
       (_i("Cooked lentils", 200, "g", "Plant protein"), _i("Quinoa", 90, "g", "Bakery & grains"), _i("Mixed peppers", 2, "item", "Fruit & vegetables"), _i("Courgettes", 1, "item", "Fruit & vegetables"), _i("Lemons", .5, "item", "Fruit & vegetables"), _i("Pumpkin seeds", 20, "g", "Cupboard"), _i("Olive oil", 1, "tbsp", "Cupboard", True)),
       (), DEMANDS, 30, 690, 101, 29, True),
    _r("l_chickpea_wrap", "Chickpea, hummus & salad wraps", "Lunch", "Vegan",
       "Portable wraps with pulses, salad and tahini-based hummus.",
       (_i("Wholemeal wraps", 2, "item", "Bakery & grains"), _i("Chickpeas", 1, "tin", "Plant protein"), _i("Hummus", 60, "g", "Chilled"), _i("Mixed salad leaves", 60, "g", "Fruit & vegetables"), _i("Cucumber", .5, "item", "Fruit & vegetables"), _i("Tomatoes", 2, "item", "Fruit & vegetables")),
       ("Gluten", "Sesame"), DEMANDS, 10, 640, 91, 25),
    _r("l_tofu_rice", "Ginger tofu rice bowl", "Lunch", "Vegan",
       "A high-carbohydrate bowl with tofu and colourful vegetables.",
       (_i("Calcium-set tofu", 180, "g", "Plant protein"), _i("Brown rice", 100, "g", "Bakery & grains"), _i("Broccoli", 150, "g", "Fruit & vegetables"), _i("Carrots", 2, "item", "Fruit & vegetables"), _i("Reduced-salt soy sauce", 1, "tbsp", "Cupboard", True), _i("Fresh ginger", 10, "g", "Fruit & vegetables"), _i("Rapeseed oil", 1, "tsp", "Cupboard", True)),
       ("Soya",), ("Easy", "Quality", "Long run / race"), 25, 700, 96, 32, True),
    _r("l_bean_potato", "Three-bean chilli jacket potato", "Lunch", "Vegan",
       "Batch-friendly carbohydrate and mixed pulses for recovery.",
       (_i("Baking potatoes", 2, "item", "Fruit & vegetables"), _i("Mixed beans", 1, "tin", "Plant protein"), _i("Chopped tomatoes", 1, "tin", "Cupboard"), _i("Onions", 1, "item", "Fruit & vegetables"), _i("Mixed peppers", 1, "item", "Fruit & vegetables"), _i("Smoked paprika", 1, "tsp", "Cupboard", True)),
       (), DEMANDS, 40, 670, 121, 27, True),
    _r("l_feta_couscous", "Feta, chickpea & couscous salad", "Lunch", "Vegetarian",
       "Quick grain salad with pulses, vegetables and feta.",
       (_i("Wholewheat couscous", 100, "g", "Bakery & grains"), _i("Chickpeas", .75, "tin", "Plant protein"), _i("Feta", 60, "g", "Chilled"), _i("Cucumber", .5, "item", "Fruit & vegetables"), _i("Tomatoes", 2, "item", "Fruit & vegetables"), _i("Lemons", .5, "item", "Fruit & vegetables")),
       ("Gluten", "Milk"), DEMANDS, 12, 680, 96, 28),
    _r("l_egg_potato", "Egg, new potato & green bean bowl", "Lunch", "Vegetarian",
       "Simple potato-based lunch with eggs and vegetables.",
       (_i("New potatoes", 350, "g", "Fruit & vegetables"), _i("Eggs", 3, "item", "Chilled"), _i("Green beans", 150, "g", "Fruit & vegetables"), _i("Mixed salad leaves", 60, "g", "Fruit & vegetables"), _i("Wholegrain mustard", 1, "tsp", "Cupboard", True)),
       ("Egg", "Mustard"), ("Rest / recovery", "Easy", "Quality"), 25, 590, 69, 29),
    _r("l_tuna_pasta", "Tuna, sweetcorn & tomato pasta", "Lunch", "Pescatarian",
       "A practical recovery lunch with pasta and lean fish protein.",
       (_i("Wholewheat pasta", 110, "g", "Bakery & grains"), _i("Tuna in spring water", 1, "tin", "Fish & meat"), _i("Sweetcorn", .5, "tin", "Cupboard"), _i("Cherry tomatoes", 150, "g", "Fruit & vegetables"), _i("Greek yoghurt", 50, "g", "Chilled")),
       ("Fish", "Gluten", "Milk"), DEMANDS, 18, 650, 91, 44),
    _r("l_salmon_grain", "Salmon, couscous & green vegetable bowl", "Lunch", "Pescatarian",
       "A balanced grain bowl with oily fish and green vegetables.",
       (_i("Hot-smoked salmon", 120, "g", "Fish & meat"), _i("Wholewheat couscous", 100, "g", "Bakery & grains"), _i("Broccoli", 120, "g", "Fruit & vegetables"), _i("Peas", 80, "g", "Fruit & vegetables"), _i("Lemons", .5, "item", "Fruit & vegetables")),
       ("Fish", "Gluten"), DEMANDS, 15, 670, 82, 43),
    _r("l_chicken_rice", "Chicken, rice & rainbow vegetable bowl", "Lunch", "Omnivore",
       "Lean protein with rice and mixed vegetables after training.",
       (_i("Chicken breast", 160, "g", "Fish & meat"), _i("Brown rice", 100, "g", "Bakery & grains"), _i("Broccoli", 120, "g", "Fruit & vegetables"), _i("Mixed peppers", 1, "item", "Fruit & vegetables"), _i("Carrots", 1, "item", "Fruit & vegetables"), _i("Reduced-salt soy sauce", 1, "tbsp", "Cupboard", True)),
       ("Soya",), DEMANDS, 25, 690, 89, 51, True),
    _r("l_turkey_wrap", "Turkey, avocado & salad wraps", "Lunch", "Omnivore",
       "Lean turkey, wholegrain wraps and crunchy salad for a practical lunch.",
       (_i("Cooked turkey breast", 140, "g", "Fish & meat"), _i("Wholemeal wraps", 2, "item", "Bakery & grains"), _i("Avocado", .5, "item", "Fruit & vegetables"), _i("Mixed salad leaves", 60, "g", "Fruit & vegetables"), _i("Tomatoes", 2, "item", "Fruit & vegetables"), _i("Greek yoghurt", 40, "g", "Chilled")),
       ("Gluten", "Milk"), DEMANDS, 8, 620, 65, 48),
    _r("l_beef_noodle", "Lean beef & vegetable noodle salad", "Lunch", "Omnivore",
       "Lean beef with noodles and colourful vegetables in a light dressing.",
       (_i("Lean beef strips", 150, "g", "Fish & meat"), _i("Wholewheat noodles", 100, "g", "Bakery & grains"), _i("Stir-fry vegetables", 250, "g", "Fruit & vegetables"), _i("Reduced-salt soy sauce", 1, "tbsp", "Cupboard", True), _i("Limes", .5, "item", "Fruit & vegetables")),
       ("Gluten", "Soya"), DEMANDS, 18, 660, 78, 47),

    # Dinners.
    _r("d_lentil_bolognese", "Red lentil bolognese with wholewheat spaghetti", "Dinner", "Vegan",
       "A batch-friendly pasta dinner with pulses and vegetables.",
       (_i("Wholewheat spaghetti", 120, "g", "Bakery & grains"), _i("Red lentils", 90, "g", "Plant protein"), _i("Chopped tomatoes", 1, "tin", "Cupboard"), _i("Onions", 1, "item", "Fruit & vegetables"), _i("Carrots", 2, "item", "Fruit & vegetables"), _i("Mushrooms", 150, "g", "Fruit & vegetables"), _i("Dried mixed herbs", 1, "tsp", "Cupboard", True)),
       ("Gluten",), DEMANDS, 35, 760, 128, 34, True),
    _r("d_tofu_noodles", "Tofu vegetable stir-fry with noodles", "Dinner", "Vegan",
       "Fast carbohydrate and plant protein for a training evening.",
       (_i("Wholewheat noodles", 120, "g", "Bakery & grains"), _i("Calcium-set tofu", 200, "g", "Plant protein"), _i("Stir-fry vegetables", 300, "g", "Fruit & vegetables"), _i("Reduced-salt soy sauce", 1, "tbsp", "Cupboard", True), _i("Fresh ginger", 10, "g", "Fruit & vegetables"), _i("Rapeseed oil", 1, "tsp", "Cupboard", True)),
       ("Gluten", "Soya"), ("Easy", "Quality", "Long run / race"), 18, 720, 98, 38),
    _r("d_bean_chilli", "Three-bean chilli with brown rice", "Dinner", "Vegan",
       "Mixed pulses, rice and vegetables in a useful batch meal.",
       (_i("Brown rice", 110, "g", "Bakery & grains"), _i("Mixed beans", 1, "tin", "Plant protein"), _i("Chopped tomatoes", 1, "tin", "Cupboard"), _i("Onions", 1, "item", "Fruit & vegetables"), _i("Mixed peppers", 2, "item", "Fruit & vegetables"), _i("Avocado", .5, "item", "Fruit & vegetables"), _i("Smoked paprika", 1, "tsp", "Cupboard", True)),
       (), DEMANDS, 35, 780, 132, 29, True),
    _r("d_chickpea_curry", "Chickpea, spinach & sweet potato curry", "Dinner", "Vegan",
       "A colourful curry with rice, pulses and iron-rich greens.",
       (_i("Basmati rice", 110, "g", "Bakery & grains"), _i("Chickpeas", 1, "tin", "Plant protein"), _i("Sweet potatoes", 300, "g", "Fruit & vegetables"), _i("Baby spinach", 100, "g", "Fruit & vegetables"), _i("Light coconut milk", .5, "tin", "Cupboard"), _i("Curry powder", 1, "tbsp", "Cupboard", True)),
       (), DEMANDS, 35, 810, 141, 26, True),
    _r("d_halloumi_tray", "Halloumi vegetable traybake with couscous", "Dinner", "Vegetarian",
       "Low-fuss roast vegetables, grain and halloumi.",
       (_i("Halloumi", 100, "g", "Chilled"), _i("Wholewheat couscous", 110, "g", "Bakery & grains"), _i("Courgettes", 1, "item", "Fruit & vegetables"), _i("Mixed peppers", 2, "item", "Fruit & vegetables"), _i("Red onions", 1, "item", "Fruit & vegetables"), _i("Olive oil", 1, "tbsp", "Cupboard", True)),
       ("Milk", "Gluten"), DEMANDS, 35, 790, 94, 34, True),
    _r("d_ricotta_pasta", "Spinach, ricotta & tomato pasta", "Dinner", "Vegetarian",
       "Comforting pasta with spinach and dairy protein.",
       (_i("Wholewheat pasta", 120, "g", "Bakery & grains"), _i("Ricotta", 150, "g", "Chilled"), _i("Baby spinach", 100, "g", "Fruit & vegetables"), _i("Passata", 250, "ml", "Cupboard"), _i("Onions", 1, "item", "Fruit & vegetables")),
       ("Milk", "Gluten"), ("Easy", "Quality", "Long run / race"), 25, 750, 101, 36),
    _r("d_salmon_potato", "Salmon, potatoes & greens", "Dinner", "Pescatarian",
       "Oily fish with potatoes and green vegetables.",
       (_i("Salmon fillets", 1, "item", "Fish & meat"), _i("New potatoes", 400, "g", "Fruit & vegetables"), _i("Broccoli", 180, "g", "Fruit & vegetables"), _i("Peas", 100, "g", "Fruit & vegetables"), _i("Lemons", .5, "item", "Fruit & vegetables")),
       ("Fish",), DEMANDS, 30, 720, 79, 48),
    _r("d_cod_rice", "Herby cod, tomato rice & peas", "Dinner", "Pescatarian",
       "White fish with rice, tomatoes and peas for a lighter balanced dinner.",
       (_i("Cod fillets", 1, "item", "Fish & meat"), _i("Basmati rice", 110, "g", "Bakery & grains"), _i("Passata", 200, "ml", "Cupboard"), _i("Peas", 120, "g", "Fruit & vegetables"), _i("Dried mixed herbs", 1, "tsp", "Cupboard", True)),
       ("Fish",), DEMANDS, 28, 650, 91, 44),
    _r("d_chicken_fajita", "Chicken fajita rice bowl", "Dinner", "Omnivore",
       "Rice, lean chicken, beans and colourful vegetables.",
       (_i("Chicken breast", 180, "g", "Fish & meat"), _i("Basmati rice", 110, "g", "Bakery & grains"), _i("Black beans", .5, "tin", "Plant protein"), _i("Mixed peppers", 2, "item", "Fruit & vegetables"), _i("Onions", 1, "item", "Fruit & vegetables"), _i("Avocado", .5, "item", "Fruit & vegetables"), _i("Fajita seasoning", 1, "tbsp", "Cupboard", True)),
       (), DEMANDS, 30, 850, 113, 58, True),
    _r("d_turkey_meatballs", "Turkey meatballs with tomato spaghetti", "Dinner", "Omnivore",
       "Lean turkey meatballs, wholewheat pasta and tomato sauce.",
       (_i("Turkey mince", 180, "g", "Fish & meat"), _i("Wholewheat spaghetti", 120, "g", "Bakery & grains"), _i("Passata", 250, "ml", "Cupboard"), _i("Onions", 1, "item", "Fruit & vegetables"), _i("Courgettes", 1, "item", "Fruit & vegetables"), _i("Dried mixed herbs", 1, "tsp", "Cupboard", True)),
       ("Gluten",), DEMANDS, 35, 770, 101, 52, True),
    _r("d_beef_stirfry", "Lean beef, broccoli & rice stir-fry", "Dinner", "Omnivore",
       "Lean beef with rice and vegetables for an iron-rich mixed-diet option.",
       (_i("Lean beef strips", 170, "g", "Fish & meat"), _i("Brown rice", 110, "g", "Bakery & grains"), _i("Broccoli", 180, "g", "Fruit & vegetables"), _i("Mixed peppers", 1, "item", "Fruit & vegetables"), _i("Reduced-salt soy sauce", 1, "tbsp", "Cupboard", True), _i("Fresh ginger", 10, "g", "Fruit & vegetables")),
       ("Soya",), DEMANDS, 25, 760, 91, 52),

    # Recovery snacks. These are food options, not automatic supplement advice.
    _r("s_soya_berry", "Soya yoghurt, berries & granola", "Recovery snack", "Vegan",
       "A quick carbohydrate-protein combination after training.",
       (_i("Fortified soya yoghurt", 200, "g", "Chilled"), _i("Frozen berries", 100, "g", "Fruit & vegetables"), _i("Granola", 40, "g", "Bakery & grains")),
       ("Soya", "Gluten", "Tree nuts"), DEMANDS, 2, 340, 50, 15),
    _r("s_choc_banana", "Chocolate soya drink & banana", "Recovery snack", "Vegan",
       "No-cook fluid, carbohydrate and plant protein.",
       (_i("Chocolate fortified soya drink", 400, "ml", "Chilled"), _i("Bananas", 1, "item", "Fruit & vegetables")),
       ("Soya",), ("Easy", "Quality", "Long run / race"), 1, 330, 58, 15),
    _r("s_hummus_pitta", "Hummus, wholemeal pitta & peppers", "Recovery snack", "Vegan",
       "A savoury snack with carbohydrate and pulse-based protein.",
       (_i("Wholemeal pitta", 1, "item", "Bakery & grains"), _i("Hummus", 60, "g", "Chilled"), _i("Mixed peppers", 1, "item", "Fruit & vegetables")),
       ("Gluten", "Sesame"), DEMANDS, 3, 350, 50, 13),
    _r("s_oat_bites", "Date, oat & seed bites", "Recovery snack", "Vegan",
       "Portable batch snack for busy training days.",
       (_i("Dates", 60, "g", "Fruit & vegetables"), _i("Porridge oats", 35, "g", "Bakery & grains"), _i("Pumpkin seeds", 20, "g", "Cupboard"), _i("Cocoa powder", 1, "tsp", "Cupboard", True)),
       ("Gluten",), DEMANDS, 10, 360, 54, 12, True),
    _r("s_greek_yoghurt", "Greek yoghurt, banana & honey", "Recovery snack", "Vegetarian",
       "Dairy protein with fruit and carbohydrate.",
       (_i("Greek yoghurt", 200, "g", "Chilled"), _i("Bananas", 1, "item", "Fruit & vegetables"), _i("Honey", 15, "g", "Cupboard")),
       ("Milk",), DEMANDS, 2, 310, 46, 21),
    _r("s_cottage_toast", "Cottage cheese & tomato toast", "Recovery snack", "Vegetarian",
       "A savoury protein-rich snack with wholegrain carbohydrate.",
       (_i("Cottage cheese", 150, "g", "Chilled"), _i("Wholemeal bread", 2, "slice", "Bakery & grains"), _i("Tomatoes", 1, "item", "Fruit & vegetables")),
       ("Milk", "Gluten"), DEMANDS, 4, 330, 37, 25),
)

RECIPE_BY_ID = {recipe.id: recipe for recipe in RECIPES}


def parse_terms(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """Normalise comma/newline-separated preferences without losing labels."""
    if value is None:
        return ()
    parts = value if not isinstance(value, str) else value.replace("\n", ",").split(",")
    return tuple(dict.fromkeys(str(part).strip() for part in parts if str(part).strip()))


def _style_allows(profile_style: str, recipe_style: str) -> bool:
    maximum = DIETARY_STYLES.index(profile_style)
    minimum = DIETARY_STYLES.index(recipe_style)
    # The ordering runs broadest to most restrictive. An omnivore can choose
    # every recipe; a vegan receives vegan recipes only.
    return minimum >= maximum


def _normal(value: str) -> str:
    return " ".join(value.casefold().replace("-", " ").split())


def _allergy_terms(values: Iterable[str]) -> set[str]:
    aliases = {
        "dairy": ("milk",),
        "soy": ("soya",),
        "nuts": ("tree nuts", "peanuts"),
        "nut": ("tree nuts", "peanuts"),
    }
    terms = {_normal(value) for value in values}
    for value in tuple(terms):
        terms.update(aliases.get(value, ()))
    return terms


def recipe_is_compatible(recipe: Recipe, profile: NutritionProfile) -> bool:
    if not _style_allows(profile.dietary_style, recipe.dietary_style):
        return False
    if recipe.cook_minutes > profile.max_cook_minutes:
        return False
    allergies = _allergy_terms(profile.allergies)
    recipe_allergens = {_normal(item) for item in recipe.allergens}
    if allergies & recipe_allergens:
        return False
    disliked = tuple(_normal(item) for item in profile.dislikes)
    searchable = _normal(
        " ".join([recipe.name, recipe.summary, *(item.name for item in recipe.ingredients)])
    )
    return not any(item and item in searchable for item in disliked)


def meal_options(
    profile: NutritionProfile,
    fuel_day: FuelDay,
    meal_slot: str,
    *,
    count: int = 2,
) -> tuple[Recipe, ...]:
    """Return stable but day-varying choices for one meal slot."""
    if meal_slot not in MEAL_SLOTS:
        raise ValueError(f"Unsupported meal slot: {meal_slot}")
    eligible = [
        recipe for recipe in RECIPES
        if recipe.slot == meal_slot and recipe_is_compatible(recipe, profile)
    ]
    if not eligible:
        return ()

    higher_cost_signals = {
        "Salmon fillets", "Chicken breast", "Halloumi", "Ricotta",
        "Avocado", "Quinoa", "Feta", "Walnuts",
    }

    def priority(recipe: Recipe) -> tuple[int, int, int, str]:
        demand = 0 if fuel_day.demand in recipe.demand_tags else 1
        cost = sum(
            ingredient.name in higher_cost_signals
            for ingredient in recipe.ingredients
        ) if profile.budget_style == "Value conscious" else 0
        batch = (
            0 if profile.use_leftovers and recipe.batch_friendly else 1
        ) if meal_slot in {"Lunch", "Dinner"} else 0
        return demand, cost, batch, recipe.id

    def rotated(items: list[Recipe], salt: int = 0) -> list[Recipe]:
        pool = sorted(items, key=priority)
        if profile.budget_style == "Value conscious" or (
            profile.use_leftovers and meal_slot in {"Lunch", "Dinner"}
        ):
            pool = pool[:max(count + 2, count)]
        if not pool:
            return []
        day = datetime.date.fromisoformat(fuel_day.date)
        offset = (
            day.toordinal() + MEAL_SLOTS.index(meal_slot) + salt
        ) % len(pool)
        return pool[offset:] + pool[:offset]

    primary_styles: set[str]
    alternate_styles: set[str]
    if profile.dietary_style == "Omnivore" and meal_slot in {"Lunch", "Dinner"}:
        primary_styles = {"Omnivore", "Pescatarian"}
        alternate_styles = {"Vegetarian", "Vegan"}
    elif profile.dietary_style == "Pescatarian" and meal_slot in {"Lunch", "Dinner"}:
        primary_styles = {"Pescatarian"}
        alternate_styles = {"Vegetarian", "Vegan"}
    elif profile.dietary_style in {"Omnivore", "Pescatarian", "Vegetarian"}:
        # Breakfast and recovery snacks do not need token meat additions. Lead
        # with a complete egg/dairy option and retain a plant-based alternative.
        primary_styles = {"Vegetarian"}
        alternate_styles = {"Vegan"}
    else:
        primary_styles = {"Vegan"}
        alternate_styles = {"Vegan"}

    primary = rotated(
        [recipe for recipe in eligible if recipe.dietary_style in primary_styles]
    )
    alternate = rotated(
        [recipe for recipe in eligible if recipe.dietary_style in alternate_styles],
        salt=1,
    )
    selected: list[Recipe] = []
    if primary:
        selected.append(primary[0])
    if alternate:
        selected.append(alternate[0])

    # Personal exclusions can empty either group. Fill safely from the complete
    # compatible catalogue without duplicating an already selected recipe.
    all_rotated = rotated(eligible, salt=2)
    for recipe in [*primary[1:], *alternate[1:], *all_rotated]:
        if recipe not in selected:
            selected.append(recipe)
        if len(selected) >= count:
            break
    return tuple(selected[:count])


def training_demand(session_type: str, *, is_hard: bool = False) -> str:
    text = _normal(session_type)
    if any(token in text for token in ("race", "long run")):
        return "Long run / race"
    if is_hard or any(token in text for token in (
        "threshold", "interval", "vo2", "repetition", "hill", "race pace",
    )):
        return "Quality"
    if any(token in text for token in ("easy", "recovery", "running")):
        return "Easy"
    return "Rest / recovery"


def _fuel_guidance(demand: str) -> tuple[str, str, str, str]:
    if demand == "Long run / race":
        return (
            "Highest-fuel day: prioritise familiar carbohydrate, fluids and a substantial recovery meal.",
            "Use a familiar carbohydrate-rich meal 2–3 hours before; keep fat and fibre comfortable for you.",
            "For hard running beyond about an hour, use the athlete's practised drink/food/gel strategy rather than trying anything new.",
            "Begin replacing fluid and carbohydrate promptly, then include a balanced meal with protein.",
        )
    if demand == "Quality":
        return (
            "Performance day: place useful carbohydrate before the session and carbohydrate plus protein afterwards.",
            "Avoid arriving under-fuelled; choose a familiar meal or snack that sits comfortably.",
            "Water is usually enough for shorter sessions; longer hard work may need a practised carbohydrate option.",
            "Pair carbohydrate and protein after training, especially when the next session is within 24 hours.",
        )
    if demand == "Easy":
        return (
            "Steady-fuel day: support routine recovery without treating an easy run like a race.",
            "Normal meals are usually sufficient; add a light snack if timing or hunger requires it.",
            "Drink to thirst and carry fluid when conditions or duration make that sensible.",
            "Return to the normal meal pattern with carbohydrate, protein and colourful plants.",
        )
    return (
        "Recovery day: maintain regular meals, protein distribution, plants and hydration.",
        "No special pre-training fuel is required unless another activity is planned.",
        "No during-run fuel is required.",
        "Use the day to replenish normally rather than restricting food because running volume is lower.",
    )


def fuel_guidance_for_demand(
    demand: str,
) -> tuple[str, str, str, str]:
    """Return the established Fuel Planner guidance for one training demand.

    This small public boundary lets other coaching surfaces reuse the curated
    guidance without copying nutrition rules into their presentation layer.
    """
    return _fuel_guidance(demand)


def compose_fuel_week(
    *,
    athlete_id: int,
    training_block_id: int,
    block_name: str,
    week: dict[str, Any],
) -> FuelWeek:
    start = datetime.date.fromisoformat(str(week["start_date"])[:10])
    days = []
    for index, planned in enumerate(week.get("days") or ()):
        demand = training_demand(
            str(planned.get("session_type") or "Rest"),
            is_hard=bool(planned.get("is_hard")),
        )
        focus, pre, during, recovery = _fuel_guidance(demand)
        days.append(FuelDay(
            day=str(planned.get("day") or start.strftime("%A")),
            date=(start + datetime.timedelta(days=index)).isoformat(),
            session_type=str(planned.get("session_type") or "Rest"),
            session_detail=str(planned.get("detail") or "No running"),
            demand=demand,
            focus=focus,
            pre_training=pre,
            during_training=during,
            recovery=recovery,
        ))
    return FuelWeek(
        athlete_id=athlete_id,
        training_block_id=training_block_id,
        block_name=block_name,
        week_number=int(week.get("week_number") or 1),
        start_date=str(week["start_date"]),
        end_date=str(week.get("end_date") or (start + datetime.timedelta(days=6)).isoformat()),
        phase=str(week.get("phase") or "Training"),
        emphasis=str(week.get("emphasis") or "Approved weekly shape"),
        days=tuple(days),
    )


def _next_monday(reference_date: datetime.date) -> datetime.date:
    return reference_date + datetime.timedelta(days=(7 - reference_date.weekday()) % 7)


def _select_next_week(
    weeks: Iterable[dict[str, Any]],
    reference_date: datetime.date,
) -> dict[str, Any] | None:
    target = _next_monday(reference_date)
    parsed = []
    for week in weeks:
        try:
            start = datetime.date.fromisoformat(str(week.get("start_date"))[:10])
            end = datetime.date.fromisoformat(str(week.get("end_date"))[:10])
        except (TypeError, ValueError):
            continue
        parsed.append((start, end, week))
    for start, end, week in parsed:
        if start <= target <= end:
            return week
    future = [item for item in parsed if item[0] > target]
    return min(future, default=(None, None, None), key=lambda item: item[0])[2]


def load_next_fuel_week(
    athlete_id: int,
    *,
    reference_date: datetime.date | None = None,
) -> FuelWeek | None:
    block = get_active_training_block(athlete_id)
    if block is None:
        return None
    saved = get_training_block_design(block.id, athlete_id=athlete_id)
    if saved is None:
        return None
    effective = apply_accepted_block_reviews(
        saved.plan,
        athlete_id=athlete_id,
        training_block_id=block.id,
    )
    week = _select_next_week(
        effective.get("weeks") or (),
        reference_date or datetime.date.today(),
    )
    if week is None:
        return None
    return compose_fuel_week(
        athlete_id=athlete_id,
        training_block_id=block.id,
        block_name=block.name,
        week=week,
    )


def default_nutrition_profile(athlete_id: int) -> NutritionProfile:
    return NutritionProfile(athlete_id=athlete_id)


def load_nutrition_profile(athlete_id: int) -> NutritionProfile | None:
    connection = get_connection()
    cursor = connection.cursor()
    create_nutrition_tables(cursor)
    cursor.execute(
        """
        SELECT athlete_id, dietary_style, servings, allergies_json,
               dislikes_json, max_cook_minutes, budget_style, use_leftovers,
               show_nutrition_detail, updated_at
        FROM athlete_nutrition_profiles
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )
    row = cursor.fetchone()
    connection.close()
    if row is None:
        return None
    return NutritionProfile(
        athlete_id=int(row[0]), dietary_style=row[1], servings=int(row[2]),
        allergies=tuple(json.loads(row[3])), dislikes=tuple(json.loads(row[4])),
        max_cook_minutes=int(row[5]), budget_style=row[6],
        use_leftovers=bool(row[7]), show_nutrition_detail=bool(row[8]),
        updated_at=row[9],
    )


def save_nutrition_profile(profile: NutritionProfile) -> None:
    if profile.dietary_style not in DIETARY_STYLES:
        raise ValueError(f"Unsupported dietary style: {profile.dietary_style}")
    if profile.budget_style not in BUDGET_STYLES:
        raise ValueError(f"Unsupported budget style: {profile.budget_style}")
    if profile.servings < 1 or profile.servings > 12:
        raise ValueError("Servings must be between 1 and 12.")
    connection = get_connection()
    cursor = connection.cursor()
    create_nutrition_tables(cursor)
    cursor.execute(
        """
        INSERT INTO athlete_nutrition_profiles (
            athlete_id, dietary_style, servings, allergies_json,
            dislikes_json, max_cook_minutes, budget_style, use_leftovers,
            show_nutrition_detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(athlete_id) DO UPDATE SET
            dietary_style = excluded.dietary_style,
            servings = excluded.servings,
            allergies_json = excluded.allergies_json,
            dislikes_json = excluded.dislikes_json,
            max_cook_minutes = excluded.max_cook_minutes,
            budget_style = excluded.budget_style,
            use_leftovers = excluded.use_leftovers,
            show_nutrition_detail = excluded.show_nutrition_detail,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            profile.athlete_id, profile.dietary_style, profile.servings,
            json.dumps(profile.allergies), json.dumps(profile.dislikes),
            profile.max_cook_minutes, profile.budget_style,
            int(profile.use_leftovers), int(profile.show_nutrition_detail),
        ),
    )
    connection.commit()
    connection.close()


def load_week_selections(
    athlete_id: int,
    week_start: str,
) -> dict[tuple[str, str], MealSelection]:
    connection = get_connection()
    cursor = connection.cursor()
    create_nutrition_tables(cursor)
    cursor.execute(
        """
        SELECT athlete_id, training_block_id, week_start, meal_date,
               meal_slot, recipe_id, servings
        FROM nutrition_week_selections
        WHERE athlete_id = ? AND week_start = ?
        ORDER BY meal_date, meal_slot
        """,
        (athlete_id, week_start),
    )
    selections = {
        (row[3], row[4]): MealSelection(
            athlete_id=int(row[0]), training_block_id=int(row[1]),
            week_start=row[2], meal_date=row[3], meal_slot=row[4],
            recipe_id=row[5], servings=int(row[6]),
        )
        for row in cursor.fetchall()
    }
    connection.close()
    return selections


def save_week_selections(selections: Iterable[MealSelection]) -> int:
    selected = tuple(selections)
    if not selected:
        return 0
    athlete_id = selected[0].athlete_id
    week_start = selected[0].week_start
    for choice in selected:
        if choice.athlete_id != athlete_id or choice.week_start != week_start:
            raise ValueError("One save may contain only one athlete and training week.")
        if choice.meal_slot not in MEAL_SLOTS or choice.recipe_id not in RECIPE_BY_ID:
            raise ValueError("A meal selection contains an unsupported slot or recipe.")
        if choice.servings < 1 or choice.servings > 12:
            raise ValueError("Servings must be between 1 and 12.")
    connection = get_connection()
    cursor = connection.cursor()
    create_nutrition_tables(cursor)
    cursor.execute(
        "DELETE FROM nutrition_week_selections WHERE athlete_id = ? AND week_start = ?",
        (athlete_id, week_start),
    )
    cursor.executemany(
        """
        INSERT INTO nutrition_week_selections (
            athlete_id, training_block_id, week_start, meal_date,
            meal_slot, recipe_id, servings
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                choice.athlete_id, choice.training_block_id,
                choice.week_start, choice.meal_date, choice.meal_slot,
                choice.recipe_id, choice.servings,
            )
            for choice in selected
        ],
    )
    connection.commit()
    connection.close()
    return len(selected)


def load_household_week_selections(
    week_start: str,
) -> tuple[tuple[str, MealSelection], ...]:
    connection = get_connection()
    cursor = connection.cursor()
    create_nutrition_tables(cursor)
    cursor.execute(
        """
        SELECT a.first_name, a.last_name, s.athlete_id,
               s.training_block_id, s.week_start, s.meal_date,
               s.meal_slot, s.recipe_id, s.servings
        FROM nutrition_week_selections s
        JOIN athletes a ON a.id = s.athlete_id
        WHERE s.week_start = ?
        ORDER BY a.first_name, a.last_name, s.meal_date, s.meal_slot
        """,
        (week_start,),
    )
    result = tuple(
        (
            f"{row[0] or ''} {row[1] or ''}".strip(),
            MealSelection(
                athlete_id=int(row[2]), training_block_id=int(row[3]),
                week_start=row[4], meal_date=row[5], meal_slot=row[6],
                recipe_id=row[7], servings=int(row[8]),
            ),
        )
        for row in cursor.fetchall()
    )
    connection.close()
    return result


def build_shopping_list(
    selections: Iterable[MealSelection],
    *,
    include_pantry: bool = True,
) -> tuple[ShoppingItem, ...]:
    totals: dict[tuple[str, str, str, bool], float] = {}
    for choice in selections:
        recipe = RECIPE_BY_ID.get(choice.recipe_id)
        if recipe is None:
            continue
        for ingredient in recipe.ingredients:
            if ingredient.pantry and not include_pantry:
                continue
            key = (
                ingredient.name, ingredient.unit,
                ingredient.category, ingredient.pantry,
            )
            totals[key] = totals.get(key, 0.0) + ingredient.amount * choice.servings
    return tuple(
        ShoppingItem(name, round(amount, 2), unit, category, pantry)
        for (name, unit, category, pantry), amount in sorted(
            totals.items(), key=lambda item: (item[0][2], item[0][0])
        )
    )


def format_quantity(amount: float, unit: str) -> str:
    if abs(amount - round(amount)) < .001:
        value = str(int(round(amount)))
    else:
        value = f"{amount:.2f}".rstrip("0").rstrip(".")
    return f"{value} {unit}"


def shopping_list_csv(items: Iterable[ShoppingItem]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(("Category", "Ingredient", "Quantity", "Pantry staple"))
    for item in items:
        writer.writerow((
            item.category, item.name, format_quantity(item.amount, item.unit),
            "Yes" if item.pantry else "No",
        ))
    return output.getvalue()

"""Stable same-app links into Nutrition Coach for one athlete."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


PAGE_PARAM = "pp_page"
ATHLETE_PARAM = "pp_athlete"
NUTRITION_COACH_PAGE = "Fuel Planner"
NUTRITION_COACH_PARAMS = (PAGE_PARAM, ATHLETE_PARAM)


@dataclass(frozen=True)
class NutritionCoachRequest:
    athlete_id: int


def _first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def nutrition_coach_url(athlete_id: int) -> str:
    return f"?{urlencode({PAGE_PARAM: NUTRITION_COACH_PAGE, ATHLETE_PARAM: int(athlete_id)})}"


def read_nutrition_coach_request(params) -> NutritionCoachRequest | None:
    if str(_first(params.get(PAGE_PARAM)) or "") != NUTRITION_COACH_PAGE:
        return None
    try:
        athlete_id = int(_first(params.get(ATHLETE_PARAM)))
    except (TypeError, ValueError):
        return None
    if athlete_id <= 0:
        return None
    return NutritionCoachRequest(athlete_id=athlete_id)


def clear_nutrition_coach_params(params) -> None:
    for key in NUTRITION_COACH_PARAMS:
        if key in params:
            del params[key]

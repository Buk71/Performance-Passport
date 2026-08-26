"""Stable same-app links from Lead Coach Home to Training Coach."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


PAGE_PARAM = "pp_page"
ATHLETE_PARAM = "pp_athlete"
TRAINING_COACH_PAGE = "Next Run"
TRAINING_COACH_PARAMS = (PAGE_PARAM, ATHLETE_PARAM)


@dataclass(frozen=True)
class TrainingCoachRequest:
    athlete_id: int


def _first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _positive_int(value) -> int | None:
    try:
        parsed = int(_first(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def training_coach_url(athlete_id: int) -> str:
    values = {
        PAGE_PARAM: TRAINING_COACH_PAGE,
        ATHLETE_PARAM: int(athlete_id),
    }
    return f"?{urlencode(values)}#training-coach"


def read_training_coach_request(params) -> TrainingCoachRequest | None:
    page = str(_first(params.get(PAGE_PARAM)) or "")
    if page != TRAINING_COACH_PAGE:
        return None
    athlete_id = _positive_int(params.get(ATHLETE_PARAM))
    if athlete_id is None:
        return None
    return TrainingCoachRequest(athlete_id=athlete_id)


def clear_training_coach_params(params) -> None:
    for key in TRAINING_COACH_PARAMS:
        if key in params:
            del params[key]

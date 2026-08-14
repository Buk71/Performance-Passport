"""Stable same-app links for selecting a Training Block week."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


PAGE_PARAM = "pp_page"
ATHLETE_PARAM = "pp_athlete"
WEEK_PARAM = "pp_training_week"
TRAINING_BLOCKS_PAGE = "Training Blocks"
TRAINING_BLOCK_PARAMS = (PAGE_PARAM, ATHLETE_PARAM, WEEK_PARAM)


@dataclass(frozen=True)
class TrainingBlockWeekRequest:
    athlete_id: int
    week_number: int


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


def training_block_week_url(athlete_id: int, week_number: int) -> str:
    """Build a link that preserves the route, athlete and selected week."""
    values = {
        PAGE_PARAM: TRAINING_BLOCKS_PAGE,
        ATHLETE_PARAM: int(athlete_id),
        WEEK_PARAM: int(week_number),
    }
    return f"?{urlencode(values)}#training-week-detail"


def read_training_block_week_request(params) -> TrainingBlockWeekRequest | None:
    page = str(_first(params.get(PAGE_PARAM)) or "")
    if page != TRAINING_BLOCKS_PAGE:
        return None
    athlete_id = _positive_int(params.get(ATHLETE_PARAM))
    week_number = _positive_int(params.get(WEEK_PARAM))
    if athlete_id is None or week_number is None:
        return None
    return TrainingBlockWeekRequest(
        athlete_id=athlete_id,
        week_number=week_number,
    )


def clear_training_block_week_params(params) -> None:
    for key in TRAINING_BLOCK_PARAMS:
        if key in params:
            del params[key]

"""Stable links between Home evidence and Activity Review.

The URL carries only navigation state. Activity Review still validates the
athlete/activity relationship against the canonical database before showing a
run, so a stale or edited link cannot cross athlete histories.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


PAGE_PARAM = "pp_page"
ATHLETE_PARAM = "pp_athlete"
ACTIVITY_PARAM = "pp_activity"
ACTIVITIES_PAGE = "Activities"
ACTIVITY_REVIEW_PARAMS = (
    PAGE_PARAM,
    ATHLETE_PARAM,
    ACTIVITY_PARAM,
)


@dataclass(frozen=True)
class ActivityReviewRequest:
    athlete_id: int
    activity_id: int | None = None


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


def activity_review_url(
    athlete_id: int,
    activity_id: int | None = None,
) -> str:
    """Build a same-app URL for one athlete's Activity Review evidence."""
    values = {
        PAGE_PARAM: ACTIVITIES_PAGE,
        ATHLETE_PARAM: int(athlete_id),
    }
    if activity_id is not None:
        values[ACTIVITY_PARAM] = int(activity_id)
    return f"?{urlencode(values)}"


def read_activity_review_request(params) -> ActivityReviewRequest | None:
    """Parse a Home deep link without trusting its athlete/activity values."""
    page = str(_first(params.get(PAGE_PARAM)) or "")
    if page != ACTIVITIES_PAGE:
        return None

    athlete_id = _positive_int(params.get(ATHLETE_PARAM))
    if athlete_id is None:
        return None

    return ActivityReviewRequest(
        athlete_id=athlete_id,
        activity_id=_positive_int(params.get(ACTIVITY_PARAM)),
    )


def clear_activity_review_params(params) -> None:
    """Consume only Performance Passport navigation parameters."""
    for key in ACTIVITY_REVIEW_PARAMS:
        if key in params:
            del params[key]

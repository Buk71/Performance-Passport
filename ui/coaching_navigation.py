"""Stable same-app links from Home to the Coaching Team."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


PAGE_PARAM = "pp_page"
ATHLETE_PARAM = "pp_athlete"
COACH_PARAM = "pp_coach"
COACHING_TEAM_PAGE = "Coaching Team"
COACHING_TEAM_PARAMS = (PAGE_PARAM, ATHLETE_PARAM, COACH_PARAM)
COACH_KEYS = {"race", "workout", "threshold", "aerobic", "environment"}


@dataclass(frozen=True)
class CoachingTeamRequest:
    athlete_id: int
    coach_key: str | None = None


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


def coaching_team_url(
    athlete_id: int,
    coach_key: str | None = None,
) -> str:
    """Build a same-app Coaching Team URL for one athlete."""
    values: dict[str, int | str] = {
        PAGE_PARAM: COACHING_TEAM_PAGE,
        ATHLETE_PARAM: int(athlete_id),
    }
    if coach_key in COACH_KEYS:
        values[COACH_PARAM] = coach_key
    fragment = f"#coach-{coach_key}" if coach_key in COACH_KEYS else ""
    return f"?{urlencode(values)}{fragment}"


def read_coaching_team_request(params) -> CoachingTeamRequest | None:
    """Parse a Coaching Team link without trusting its athlete value."""
    page = str(_first(params.get(PAGE_PARAM)) or "")
    if page != COACHING_TEAM_PAGE:
        return None

    athlete_id = _positive_int(params.get(ATHLETE_PARAM))
    if athlete_id is None:
        return None

    raw_key = str(_first(params.get(COACH_PARAM)) or "").strip().lower()
    coach_key = raw_key if raw_key in COACH_KEYS else None
    return CoachingTeamRequest(athlete_id=athlete_id, coach_key=coach_key)


def clear_coaching_team_params(params) -> None:
    """Consume only Performance Passport Coaching Team parameters."""
    for key in COACHING_TEAM_PARAMS:
        if key in params:
            del params[key]

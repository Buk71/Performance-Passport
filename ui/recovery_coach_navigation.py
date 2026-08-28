"""Stable same-app links into Recovery Coach for one athlete."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


PAGE_PARAM = "pp_page"
ATHLETE_PARAM = "pp_athlete"
RECOVERY_COACH_PAGE = "Recovery Coach"
RECOVERY_COACH_PARAMS = (PAGE_PARAM, ATHLETE_PARAM)


@dataclass(frozen=True)
class RecoveryCoachRequest:
    athlete_id: int


def _first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def recovery_coach_url(athlete_id: int) -> str:
    values = {
        PAGE_PARAM: RECOVERY_COACH_PAGE,
        ATHLETE_PARAM: int(athlete_id),
    }
    return f"?{urlencode(values)}#recovery-coach"


def read_recovery_coach_request(params) -> RecoveryCoachRequest | None:
    if str(_first(params.get(PAGE_PARAM)) or "") != RECOVERY_COACH_PAGE:
        return None
    try:
        athlete_id = int(_first(params.get(ATHLETE_PARAM)))
    except (TypeError, ValueError):
        return None
    if athlete_id <= 0:
        return None
    return RecoveryCoachRequest(athlete_id=athlete_id)


def clear_recovery_coach_params(params) -> None:
    for key in RECOVERY_COACH_PARAMS:
        if key in params:
            del params[key]

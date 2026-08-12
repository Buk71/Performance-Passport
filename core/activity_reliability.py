"""Shared activity-data reliability rules.

Classification describes what an athlete did. Reliability describes which
recorded measurements are suitable for comparison. Keeping those decisions
separate lets treadmill sessions contribute trustworthy duration and
heart-rate evidence without allowing device-estimated distance or pace to
distort records, rankings or efficiency models.
"""

from __future__ import annotations

import json
import re
from typing import Any


_TREADMILL_PATTERNS = (
    re.compile(r"\btread\s*mill\b", re.IGNORECASE),
    re.compile(r"\bindoor[\s_-]+runn?(?:ing)?\b", re.IGNORECASE),
    re.compile(r"\bvirtual[\s_-]*runn?(?:ing)?\b", re.IGNORECASE),
)

_RAW_ACTIVITY_KEYS = (
    "title",
    "name",
    "type",
    "type_id",
    "sport",
    "sport_id",
    "sportType",
    "sport_type",
    "activityType",
    "activity_type",
    "subSport",
    "sub_sport",
    "route_name",
)


def _contains_treadmill_signal(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return any(pattern.search(text) for pattern in _TREADMILL_PATTERNS)


def _raw_activity_values(raw_json_text: str | None) -> tuple[Any, ...]:
    if not raw_json_text:
        return ()

    try:
        raw = json.loads(raw_json_text)
    except (TypeError, json.JSONDecodeError):
        return ()

    if not isinstance(raw, dict):
        return ()

    values = []
    for key in _RAW_ACTIVITY_KEYS:
        if key in raw:
            values.append(raw[key])

    return tuple(values)


def is_treadmill_activity(
    *,
    title: str | None = None,
    sport_id: str | None = None,
    route_name: str | None = None,
    raw_json_text: str | None = None,
) -> bool:
    """Return True only when explicit metadata identifies indoor treadmill use."""
    values = (
        title,
        sport_id,
        route_name,
        *_raw_activity_values(raw_json_text),
    )
    return any(_contains_treadmill_signal(value) for value in values)


def has_reliable_distance_and_pace(
    *,
    title: str | None = None,
    sport_id: str | None = None,
    route_name: str | None = None,
    raw_json_text: str | None = None,
) -> bool:
    """Whether recorded distance and pace may enter comparative intelligence."""
    return not is_treadmill_activity(
        title=title,
        sport_id=sport_id,
        route_name=route_name,
        raw_json_text=raw_json_text,
    )

"""Shared activity-distance unit boundary for Performance Passport.

Historical activity data currently contains two legitimate storage conventions:
legacy Runalyze rows store ``activities.distance_m`` in kilometres, while Garmin
FIT rows store metres. New importers should declare ``distance_unit`` (``m`` or
``km``) in raw activity metadata. Downstream code should call this module rather
than infer units independently.
"""
from __future__ import annotations

import json
from typing import Any

_METRE_UNITS = {"m", "meter", "meters", "metre", "metres"}
_KILOMETRE_UNITS = {"km", "kilometer", "kilometers", "kilometre", "kilometres"}


def _metadata_unit(raw_json_text: str | None) -> str | None:
    if not raw_json_text:
        return None
    try:
        raw = json.loads(raw_json_text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    containers = (raw, raw.get("metadata"))
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in ("distance_unit", "distanceUnit"):
            value = container.get(key)
            if value is not None:
                return str(value).strip().lower()
    return None


def _known_metres_source(raw_json_text: str | None) -> bool:
    text = str(raw_json_text or "").lower()
    return (
        '"garmin_fit"' in text
        or '"source_activity_id": "garmin_' in text
        or '"source_activity_id":"garmin_' in text
    )


def normalize_activity_distance_km(
    value: Any,
    raw_json_text: str | None = None,
    declared_unit: str | None = None,
) -> float | None:
    """Convert a stored activity distance to kilometres.

    Precedence is explicit unit -> metadata unit -> known source -> legacy
    fallback. The fallback preserves historical Runalyze rows while continuing
    to understand conventional metre values such as 5000 and 10000.
    """
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return None
    if distance <= 0:
        return None

    unit = str(declared_unit or _metadata_unit(raw_json_text) or "").strip().lower()
    if unit in _METRE_UNITS:
        return distance / 1000.0
    if unit in _KILOMETRE_UNITS:
        return distance
    if _known_metres_source(raw_json_text):
        return distance / 1000.0
    return distance / 1000.0 if distance > 250.0 else distance

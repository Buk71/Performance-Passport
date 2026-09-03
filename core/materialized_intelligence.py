"""Persistent typed materialisation helpers for Performance Passport v0.64.

This is the production-oriented evolution of the Paul beta snapshot lesson:
store reusable *intelligence objects*, not rendered HTML.

Objects are encoded as JSON so they survive Python/Streamlit restarts and can be
invalidated by the athlete source-data version.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import importlib
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, TypeVar

from core.intelligence_store import load_intelligence, save_intelligence

T = TypeVar("T")


def _encode(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            "__kind__": "dataclass",
            "class": f"{value.__class__.__module__}:{value.__class__.__qualname__}",
            "fields": {
                field.name: _encode(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        }
    if isinstance(value, tuple):
        return {"__kind__": "tuple", "items": [_encode(item) for item in value]}
    if isinstance(value, list):
        return {"__kind__": "list", "items": [_encode(item) for item in value]}
    if isinstance(value, set):
        return {"__kind__": "set", "items": [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {
            "__kind__": "dict",
            "items": [[_encode(key), _encode(item)] for key, item in value.items()],
        }
    if isinstance(value, dt.datetime):
        return {"__kind__": "datetime", "value": value.isoformat()}
    if isinstance(value, dt.date):
        return {"__kind__": "date", "value": value.isoformat()}
    if isinstance(value, Path):
        return {"__kind__": "path", "value": str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported materialised intelligence value: {type(value)!r}")


def _resolve_class(reference: str):
    module_name, qualname = reference.split(":", 1)
    if not module_name.startswith("core."):
        raise ValueError(f"Materialised class outside core package: {reference}")
    obj = importlib.import_module(module_name)
    for part in qualname.split("."):
        obj = getattr(obj, part)
    return obj


def _decode(value: Any) -> Any:
    if not isinstance(value, dict) or "__kind__" not in value:
        return value
    kind = value["__kind__"]
    if kind == "dataclass":
        cls = _resolve_class(value["class"])
        fields = {name: _decode(item) for name, item in value["fields"].items()}
        return cls(**fields)
    if kind == "tuple":
        return tuple(_decode(item) for item in value["items"])
    if kind == "list":
        return [_decode(item) for item in value["items"]]
    if kind == "set":
        return set(_decode(item) for item in value["items"])
    if kind == "dict":
        return {_decode(key): _decode(item) for key, item in value["items"]}
    if kind == "datetime":
        return dt.datetime.fromisoformat(value["value"])
    if kind == "date":
        return dt.date.fromisoformat(value["value"])
    if kind == "path":
        return Path(value["value"])
    raise ValueError(f"Unknown materialised intelligence kind: {kind}")


def load_typed_intelligence(
    athlete_id: int,
    intelligence_key: str,
    *,
    source_version: tuple[Any, ...],
) -> Any | None:
    record = load_intelligence(
        int(athlete_id),
        intelligence_key,
        source_version=source_version,
    )
    if record is None:
        return None
    try:
        return _decode(record.payload)
    except Exception:
        # Never let an old/incompatible materialised payload break the app.
        return None


def save_typed_intelligence(
    athlete_id: int,
    intelligence_key: str,
    value: Any,
    *,
    source_version: tuple[Any, ...],
    horizon: str = "current",
) -> None:
    save_intelligence(
        int(athlete_id),
        intelligence_key,
        _encode(value),
        source_version=source_version,
        horizon=horizon,
    )


def get_or_build_typed_intelligence(
    athlete_id: int,
    intelligence_key: str,
    *,
    source_version: tuple[Any, ...],
    builder: Callable[[], T],
    horizon: str = "current",
    source_version_provider: Callable[[], tuple[Any, ...]] | None = None,
) -> T:
    """Load a versioned artifact or build it once.

    Some existing Performance Passport builders perform legitimate idempotent
    maintenance writes (for example workout-library maintenance) while they are
    calculating intelligence. Those writes can advance the broad athlete cache
    version during the build itself.

    The lookup must use the version observed *before* the build. On a miss, the
    stored artifact should use the version observed *after* the build so it is
    reusable on the very next navigation action.
    """
    cached = load_typed_intelligence(
        athlete_id,
        intelligence_key,
        source_version=source_version,
    )
    if cached is not None:
        return cached

    value = builder()
    final_source_version = (
        tuple(source_version_provider())
        if source_version_provider is not None
        else tuple(source_version)
    )
    save_typed_intelligence(
        athlete_id,
        intelligence_key,
        value,
        source_version=final_source_version,
        horizon=horizon,
    )
    return value


def stable_key_fragment(value: Any) -> str:
    """Compact deterministic key fragment for goals/variants."""
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

"""Significant historical evidence preservation for Performance Passport v0.64.

Archive compression must never discard important athlete evidence. This module
creates a durable PB index from the existing verified-race logic and stores it
inside the v0.64 athlete intelligence store.

The PB index is deliberately based on *all* athlete history. The Recent /
Current / Archive horizons affect repeated coaching calculations, not PB
eligibility.

Whenever athlete source data changes, refresh_significant_pb_index() can rebuild
this compact index. Future v0.64 coach migrations should read this preserved
index alongside recent/current raw evidence rather than scanning thousands of
routine archived activities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.cache_version import get_athlete_cache_version
from core.intelligence_store import load_intelligence, save_intelligence
from core.database import get_personal_best_overrides
from core.pb_shape import find_race_pb


PB_INDEX_KEY = "significant.pb_index.v1"

STANDARD_PB_DISTANCES = (
    ("5k", "5K", 5.0),
    ("5_mile", "5 mile", 8.04672),
    ("10k", "10K", 10.0),
    ("10_mile", "10 mile", 16.09344),
    ("half_marathon", "Half marathon", 21.0975),
    ("marathon", "Marathon", 42.195),
)


@dataclass(frozen=True)
class PreservedPB:
    distance_key: str
    label: str
    activity_id: int | None
    activity_date: str | None
    title: str
    distance_km: float
    time_s: float
    classification: str
    confidence: float
    source: str = "gps_detected"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "distance_key": self.distance_key,
            "label": self.label,
            "activity_id": self.activity_id,
            "activity_date": self.activity_date,
            "title": self.title,
            "distance_km": self.distance_km,
            "time_s": self.time_s,
            "classification": self.classification,
            "confidence": self.confidence,
            "source": self.source,
            "notes": self.notes,
        }


def build_significant_pb_index(athlete_id: int) -> dict[str, dict[str, Any]]:
    """Build the effective all-time PB index.

    Precedence is explicit:
      1. athlete-entered official PB override;
      2. automatically detected GPS/verified race PB.

    The GPS activity remains useful supporting evidence when an official
    override exists, but the factual PB time/date shown to coaches comes from
    the official result.
    """
    athlete_id = int(athlete_id)
    official_overrides = get_personal_best_overrides(athlete_id)
    index: dict[str, dict[str, Any]] = {}

    for distance_key, label, distance_km in STANDARD_PB_DISTANCES:
        detected = find_race_pb(
            athlete_id=athlete_id,
            goal_distance_km=float(distance_km),
        )
        official = official_overrides.get(distance_key)

        if official is not None:
            preserved = PreservedPB(
                distance_key=distance_key,
                label=label,
                activity_id=(
                    int(detected["activity_id"])
                    if detected is not None and detected.get("activity_id") is not None
                    else None
                ),
                activity_date=(
                    str(official.get("event_date"))
                    if official.get("event_date")
                    else (
                        str(detected["date"])
                        if detected is not None and detected.get("date")
                        else None
                    )
                ),
                title=(
                    str(detected.get("title") or "Official race result")
                    if detected is not None
                    else "Official race result"
                ),
                distance_km=float(distance_km),
                time_s=float(official["official_time_s"]),
                classification="official_override",
                confidence=1.0,
                source="official_override",
                notes=official.get("notes"),
            )
            index[distance_key] = preserved.to_dict()
            continue

        if detected is None:
            continue

        preserved = PreservedPB(
            distance_key=distance_key,
            label=label,
            activity_id=int(detected["activity_id"]),
            activity_date=str(detected["date"]),
            title=str(detected.get("title") or "Race effort"),
            distance_km=float(detected["distance_km"]),
            time_s=float(detected["time_s"]),
            classification=str(detected.get("classification") or ""),
            confidence=float(detected.get("confidence") or 0.0),
            source="gps_detected",
        )
        index[distance_key] = preserved.to_dict()

    return index


def refresh_significant_pb_index(
    athlete_id: int,
    *,
    source_version: tuple[Any, ...] | None = None,
) -> dict[str, dict[str, Any]]:
    """Rebuild and persist the all-time PB index.

    This intentionally scans verified PB candidates across all athlete history.
    It is a refresh operation after athlete data changes, not a page-navigation
    operation. New PBs therefore replace older PBs immediately when refreshed.
    """
    athlete_id = int(athlete_id)
    version = (
        tuple(source_version)
        if source_version is not None
        else tuple(get_athlete_cache_version(athlete_id))
    )
    index = build_significant_pb_index(athlete_id)
    save_intelligence(
        athlete_id,
        PB_INDEX_KEY,
        index,
        source_version=version,
        horizon="all",
    )
    return index


def load_significant_pb_index(
    athlete_id: int,
    *,
    source_version: tuple[Any, ...] | None = None,
    require_current_version: bool = True,
) -> dict[str, dict[str, Any]] | None:
    """Load the preserved all-time PB index.

    By default the index must match current athlete source data. That prevents a
    newly imported PB from being hidden behind stale materialised intelligence.
    """
    athlete_id = int(athlete_id)
    version = None
    if require_current_version:
        version = (
            tuple(source_version)
            if source_version is not None
            else tuple(get_athlete_cache_version(athlete_id))
        )
    record = load_intelligence(
        athlete_id,
        PB_INDEX_KEY,
        source_version=version,
    )
    if record is None:
        return None
    return dict(record.payload or {})


def get_preserved_pb(
    athlete_id: int,
    distance_key: str,
    *,
    source_version: tuple[Any, ...] | None = None,
) -> dict[str, Any] | None:
    index = load_significant_pb_index(
        athlete_id,
        source_version=source_version,
        require_current_version=True,
    )
    if index is None:
        return None
    value = index.get(str(distance_key))
    return dict(value) if value is not None else None

from __future__ import annotations

import core.materialized_intelligence as materialized
from core.distance_prediction_outlook import DistancePredictionAnchor


def _example_anchor(seconds: float = 1200.0) -> DistancePredictionAnchor:
    return DistancePredictionAnchor(
        key="5k",
        label="5K",
        distance_km=5.0,
        available=True,
        central_seconds=seconds,
        confidence=0.8,
        evidence_source_count=3,
        source="test",
        explanation="Test anchor",
    )


def test_typed_materialisation_round_trip(monkeypatch):
    stored = {}

    def fake_load(athlete_id, key, source_version=None):
        payload = stored.get((athlete_id, key, tuple(source_version or ())))
        if payload is None:
            return None

        class Record:
            pass

        record = Record()
        record.payload = payload
        return record

    def fake_save(athlete_id, key, payload, source_version, horizon):
        stored[(athlete_id, key, tuple(source_version))] = payload

    monkeypatch.setattr(materialized, "load_intelligence", fake_load)
    monkeypatch.setattr(materialized, "save_intelligence", fake_save)

    source_version = ("activities", 10)
    original = _example_anchor()

    materialized.save_typed_intelligence(
        1,
        "example",
        original,
        source_version=source_version,
    )
    loaded = materialized.load_typed_intelligence(
        1,
        "example",
        source_version=source_version,
    )

    assert loaded == original


def test_get_or_build_only_builds_once_for_same_version(monkeypatch):
    stored = {}
    calls = {"count": 0}

    def fake_load(athlete_id, key, source_version=None):
        payload = stored.get((athlete_id, key, tuple(source_version or ())))
        if payload is None:
            return None

        class Record:
            pass

        record = Record()
        record.payload = payload
        return record

    def fake_save(athlete_id, key, payload, source_version, horizon):
        stored[(athlete_id, key, tuple(source_version))] = payload

    monkeypatch.setattr(materialized, "load_intelligence", fake_load)
    monkeypatch.setattr(materialized, "save_intelligence", fake_save)

    def builder():
        calls["count"] += 1
        return _example_anchor(1200.0 + calls["count"])

    first = materialized.get_or_build_typed_intelligence(
        1,
        "race.example",
        source_version=("v", 1),
        builder=builder,
    )
    second = materialized.get_or_build_typed_intelligence(
        1,
        "race.example",
        source_version=("v", 1),
        builder=builder,
    )

    assert first == second
    assert calls["count"] == 1


def test_new_source_version_forces_rebuild(monkeypatch):
    stored = {}
    calls = {"count": 0}

    def fake_load(athlete_id, key, source_version=None):
        payload = stored.get((athlete_id, key, tuple(source_version or ())))
        if payload is None:
            return None

        class Record:
            pass

        record = Record()
        record.payload = payload
        return record

    def fake_save(athlete_id, key, payload, source_version, horizon):
        stored[(athlete_id, key, tuple(source_version))] = payload

    monkeypatch.setattr(materialized, "load_intelligence", fake_load)
    monkeypatch.setattr(materialized, "save_intelligence", fake_save)

    def builder():
        calls["count"] += 1
        return _example_anchor(1200.0 + calls["count"])

    first = materialized.get_or_build_typed_intelligence(
        1,
        "race.example",
        source_version=("activities", 10),
        builder=builder,
    )
    second = materialized.get_or_build_typed_intelligence(
        1,
        "race.example",
        source_version=("activities", 11),
        builder=builder,
    )

    assert first.central_seconds == 1201.0
    assert second.central_seconds == 1202.0
    assert calls["count"] == 2


def test_goal_key_is_deterministic_and_goal_specific():
    first = materialized.stable_key_fragment(
        {"distance_m": 10000, "target_time_s": 2340, "goal_name": "10K"}
    )
    reordered = materialized.stable_key_fragment(
        {"goal_name": "10K", "target_time_s": 2340, "distance_m": 10000}
    )
    different = materialized.stable_key_fragment(
        {"distance_m": 5000, "target_time_s": 1140, "goal_name": "5K"}
    )

    assert first == reordered
    assert first != different

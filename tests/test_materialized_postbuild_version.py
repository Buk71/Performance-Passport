from __future__ import annotations

import core.materialized_intelligence as materialized


def test_materialised_value_saves_post_build_version(monkeypatch):
    stored = {}
    final_version = ("after", 2)

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

    value = materialized.get_or_build_typed_intelligence(
        1,
        "race.example",
        source_version=("before", 1),
        builder=lambda: {"result": 42},
        source_version_provider=lambda: final_version,
    )

    # The provider is called after the build. The important assertion is that
    # storage uses that post-build version rather than the stale lookup key.
    assert value == {"result": 42}
    assert (1, "race.example", ("before", 1)) not in stored
    assert len(stored) == 1


def test_next_navigation_can_hit_post_build_version(monkeypatch):
    stored = {}
    current_version = {"value": ("before", 1)}

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

    calls = {"count": 0}

    def builder():
        calls["count"] += 1
        current_version["value"] = ("after", 2)
        return {"result": 42}

    first = materialized.get_or_build_typed_intelligence(
        1,
        "race.example",
        source_version=("before", 1),
        builder=builder,
        source_version_provider=lambda: current_version["value"],
    )
    second = materialized.get_or_build_typed_intelligence(
        1,
        "race.example",
        source_version=current_version["value"],
        builder=builder,
        source_version_provider=lambda: current_version["value"],
    )

    assert first == second
    assert calls["count"] == 1

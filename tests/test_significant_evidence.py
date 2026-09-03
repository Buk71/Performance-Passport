from __future__ import annotations

import core.database as database
import core.significant_evidence as significant
from core.intelligence_store import load_intelligence


def _seed_athlete(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        tmp_path / "performance_passport.db",
    )
    database.initialise_database()
    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO athletes
            (id, first_name, last_name, date_of_birth, sex)
        VALUES (1, 'Test', 'Runner', '1980-01-01', 'Male')
        """
    )
    conn.commit()
    conn.close()


def test_build_pb_index_keeps_old_pbs_regardless_of_age(monkeypatch):
    calls = []

    def fake_find_race_pb(*, athlete_id, goal_distance_km):
        calls.append(goal_distance_km)
        if abs(goal_distance_km - 10.0) < 0.01:
            return {
                "activity_id": 99,
                "date": "2018-05-01",
                "title": "Old but still valid 10K PB",
                "distance_km": 10.0,
                "time_s": 2390.0,
                "classification": "confirmed_race",
                "confidence": 0.95,
            }
        return None

    monkeypatch.setattr(significant, "find_race_pb", fake_find_race_pb)
    index = significant.build_significant_pb_index(1)

    assert "10k" in index
    assert index["10k"]["activity_id"] == 99
    assert index["10k"]["activity_date"] == "2018-05-01"
    assert index["10k"]["time_s"] == 2390.0
    assert len(calls) == len(significant.STANDARD_PB_DISTANCES)


def test_refresh_replaces_old_pb_when_new_pb_exists(tmp_path, monkeypatch):
    _seed_athlete(tmp_path, monkeypatch)

    current_pb = {
        "activity_id": 10,
        "date": "2022-01-01",
        "title": "Old 5K PB",
        "distance_km": 5.0,
        "time_s": 1200.0,
        "classification": "confirmed_race",
        "confidence": 0.95,
    }

    def first_pb(*, athlete_id, goal_distance_km):
        return current_pb if abs(goal_distance_km - 5.0) < 0.01 else None

    monkeypatch.setattr(significant, "find_race_pb", first_pb)
    significant.refresh_significant_pb_index(
        1,
        source_version=("activities", 10),
    )

    stored = load_intelligence(
        1,
        significant.PB_INDEX_KEY,
        source_version=("activities", 10),
    )
    assert stored.payload["5k"]["activity_id"] == 10
    assert stored.payload["5k"]["time_s"] == 1200.0

    new_pb = dict(current_pb)
    new_pb.update(
        {
            "activity_id": 11,
            "date": "2026-09-03",
            "title": "New 5K PB",
            "time_s": 1175.0,
        }
    )

    def second_pb(*, athlete_id, goal_distance_km):
        return new_pb if abs(goal_distance_km - 5.0) < 0.01 else None

    monkeypatch.setattr(significant, "find_race_pb", second_pb)
    significant.refresh_significant_pb_index(
        1,
        source_version=("activities", 11),
    )

    refreshed = load_intelligence(
        1,
        significant.PB_INDEX_KEY,
        source_version=("activities", 11),
    )
    assert refreshed.payload["5k"]["activity_id"] == 11
    assert refreshed.payload["5k"]["time_s"] == 1175.0

    # The stale source version must no longer be accepted.
    assert (
        load_intelligence(
            1,
            significant.PB_INDEX_KEY,
            source_version=("activities", 10),
        )
        is None
    )


def test_current_version_guard_prevents_stale_pb_index(tmp_path, monkeypatch):
    _seed_athlete(tmp_path, monkeypatch)

    monkeypatch.setattr(
        significant,
        "build_significant_pb_index",
        lambda athlete_id: {
            "10k": {
                "activity_id": 42,
                "time_s": 2400.0,
            }
        },
    )
    significant.refresh_significant_pb_index(
        1,
        source_version=("activities", 42),
    )

    assert significant.load_significant_pb_index(
        1,
        source_version=("activities", 42),
    ) is not None
    assert significant.load_significant_pb_index(
        1,
        source_version=("activities", 43),
    ) is None


def test_standard_pb_distances_include_core_race_distances():
    keys = {row[0] for row in significant.STANDARD_PB_DISTANCES}
    assert {
        "5k",
        "5_mile",
        "10k",
        "10_mile",
        "half_marathon",
        "marathon",
    } <= keys

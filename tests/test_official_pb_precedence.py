from __future__ import annotations

import core.significant_evidence as significant


def test_official_override_takes_precedence_over_detected_gps_pb(monkeypatch):
    monkeypatch.setattr(
        significant,
        "get_personal_best_overrides",
        lambda athlete_id: {
            "5k": {
                "official_time_s": 1147.0,
                "event_date": "2026-05-05",
                "notes": "Official chip result",
            }
        },
    )

    def detected(*, athlete_id, goal_distance_km):
        if abs(goal_distance_km - 5.0) < 0.01:
            return {
                "activity_id": 123,
                "date": "2026-05-05",
                "title": "City 5K",
                "distance_km": 5.03,
                "time_s": 1145.0,
                "classification": "confirmed_race",
                "confidence": 0.98,
            }
        return None

    monkeypatch.setattr(significant, "find_race_pb", detected)
    index = significant.build_significant_pb_index(1)

    assert index["5k"]["time_s"] == 1147.0
    assert index["5k"]["source"] == "official_override"
    assert index["5k"]["classification"] == "official_override"
    assert index["5k"]["activity_id"] == 123
    assert index["5k"]["activity_date"] == "2026-05-05"


def test_detected_pb_is_used_when_no_official_override(monkeypatch):
    monkeypatch.setattr(
        significant,
        "get_personal_best_overrides",
        lambda athlete_id: {},
    )

    def detected(*, athlete_id, goal_distance_km):
        if abs(goal_distance_km - 10.0) < 0.01:
            return {
                "activity_id": 77,
                "date": "2026-02-01",
                "title": "10K race",
                "distance_km": 10.01,
                "time_s": 2380.0,
                "classification": "confirmed_race",
                "confidence": 0.95,
            }
        return None

    monkeypatch.setattr(significant, "find_race_pb", detected)
    index = significant.build_significant_pb_index(1)

    assert index["10k"]["time_s"] == 2380.0
    assert index["10k"]["source"] == "gps_detected"
    assert index["10k"]["activity_id"] == 77


def test_official_override_can_exist_without_matching_activity(monkeypatch):
    monkeypatch.setattr(
        significant,
        "get_personal_best_overrides",
        lambda athlete_id: {
            "half_marathon": {
                "official_time_s": 5350.0,
                "event_date": "2023-09-23",
                "notes": None,
            }
        },
    )
    monkeypatch.setattr(significant, "find_race_pb", lambda **kwargs: None)

    index = significant.build_significant_pb_index(1)

    pb = index["half_marathon"]
    assert pb["time_s"] == 5350.0
    assert pb["activity_id"] is None
    assert pb["source"] == "official_override"
    assert pb["confidence"] == 1.0


def test_existing_override_distances_are_preserved():
    keys = {row[0] for row in significant.STANDARD_PB_DISTANCES}
    assert {"5k", "10k", "half_marathon"} <= keys

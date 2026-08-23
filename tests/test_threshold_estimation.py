"""Real-athlete golden checks for automatic personal threshold estimates."""

import sqlite3

import core.database as database
from core.database import get_effective_athlete_thresholds
from core.threshold_estimation import (
    clear_threshold_estimation_cache,
    estimate_athlete_thresholds,
)


def test_richard_estimate_agrees_with_known_profile_without_replacing_it():
    estimate = estimate_athlete_thresholds(1)
    effective = get_effective_athlete_thresholds(1)

    assert estimate.available is True
    assert estimate.lt1.confidence == "Strong"
    assert 150 <= estimate.lt1.value_bpm <= 154
    assert 157 <= estimate.lt2.value_bpm <= 162
    assert estimate.lt1.value_bpm < estimate.lt2.value_bpm < estimate.max_hr_basis
    assert effective["lt1_hr"] == 152
    assert effective["lt2_hr"] == 161
    assert effective["estimated_lt1_hr"] == estimate.lt1.value_bpm
    assert effective["estimated_lt2_hr"] == estimate.lt2.value_bpm


def test_jo_estimate_is_independent_and_keeps_profile_values_active():
    estimate = estimate_athlete_thresholds(3)
    effective = get_effective_athlete_thresholds(3)

    assert estimate.reliable_run_count >= 500
    assert 163 <= estimate.lt1.value_bpm <= 171
    assert 174 <= estimate.lt2.value_bpm <= 182
    assert effective["lt1_hr"] == 171
    assert effective["lt2_hr"] == 187
    assert effective["source"] == "Athlete profile values"


def test_paul_estimate_is_sensible_despite_intermittent_heart_rate_history():
    estimate = estimate_athlete_thresholds(4)
    effective = get_effective_athlete_thresholds(4)

    assert estimate.lt1.confidence == "Strong"
    assert 162 <= estimate.lt1.value_bpm <= 168
    assert 173 <= estimate.lt2.value_bpm <= 180
    assert estimate.lt1.high_bpm < estimate.lt2.high_bpm
    assert effective["lt1_hr"] == 165
    assert effective["lt2_hr"] == 173


def test_estimates_explain_uncertainty_and_evidence_source():
    estimate = estimate_athlete_thresholds(1)

    assert estimate.lt1.low_bpm < estimate.lt1.value_bpm < estimate.lt1.high_bpm
    assert estimate.lt2.low_bpm < estimate.lt2.value_bpm < estimate.lt2.high_bpm
    assert "aerobic" in estimate.lt1.method.lower()
    assert "high-effort" in estimate.lt2.method.lower()
    assert estimate.latest_evidence_date is not None
    assert any("laboratory" in item.lower() for item in estimate.limitations)


def test_new_athlete_uses_training_estimates_when_profile_values_are_blank(
    tmp_path, monkeypatch,
):
    path = tmp_path / "threshold-estimate.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE athletes (
            id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
            resting_hr INTEGER, max_hr INTEGER, lt1_hr INTEGER, lt2_hr INTEGER
        );
        CREATE TABLE activities (
            id INTEGER PRIMARY KEY, athlete_id INTEGER, activity_date TEXT,
            activity_datetime TEXT, title TEXT, sport_id TEXT, distance_m REAL,
            moving_time_s REAL, avg_hr REAL, max_hr REAL, route_name TEXT,
            raw_json TEXT
        );
        CREATE TABLE athlete_sport_mappings (
            athlete_id INTEGER, sport_id TEXT, sport_role TEXT,
            PRIMARY KEY (athlete_id, sport_id)
        );
        INSERT INTO athletes VALUES (99, 'New', 'Runner', 48, NULL, NULL, NULL);
        INSERT INTO athlete_sport_mappings VALUES (99, 'run', 'running');
        """
    )
    connection.executemany(
        """INSERT INTO activities VALUES
           (?, 99, ?, ?, 'Steady run', 'run', 8.0, 2700, ?, ?, NULL, '{}')""",
        [
            (
                index,
                f"2026-07-{(index % 28) + 1:02d}",
                f"2026-07-{(index % 28) + 1:02d} 09:00:00",
                135 + (index % 25),
                150 + (index % 25),
            )
            for index in range(1, 41)
        ],
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(database, "DATABASE_PATH", path)
    database.get_athlete_sport_roles.cache_clear()
    database.get_activity_overrides.cache_clear()
    clear_threshold_estimation_cache()

    effective = get_effective_athlete_thresholds(99)

    assert effective["source"] == "Estimated from training history"
    assert effective["lt1_hr"] == effective["estimated_lt1_hr"]
    assert effective["lt2_hr"] == effective["estimated_lt2_hr"]
    assert effective["lt1_hr"] < effective["lt2_hr"] < effective["athlete_max_hr"]

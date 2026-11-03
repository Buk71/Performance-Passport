import sqlite3

from core.distance_units import normalize_activity_distance_km
from core.database import get_connection


def test_declared_metres_are_converted_at_any_magnitude():
    raw = '{"distance_unit": "m", "source": "future_importer"}'
    assert normalize_activity_distance_km(200, raw) == 0.2
    assert normalize_activity_distance_km(5000, raw) == 5.0


def test_declared_kilometres_are_preserved():
    raw = '{"distance_unit": "km", "source": "future_importer"}'
    assert normalize_activity_distance_km(5.0, raw) == 5.0
    assert normalize_activity_distance_km(42.195, raw) == 42.195


def test_garmin_fit_remains_metres_without_explicit_unit():
    raw = '{"garmin_fit": {}, "source_activity_id": "garmin_123"}'
    assert normalize_activity_distance_km(229.02, raw) == 0.22902
    assert normalize_activity_distance_km(10047.15, raw) == 10.04715


def test_legacy_runalyze_rows_remain_kilometres():
    assert normalize_activity_distance_km(5.01, None) == 5.01
    assert normalize_activity_distance_km(21.10, None) == 21.10


def test_unknown_source_keeps_legacy_fallback():
    assert normalize_activity_distance_km(10000, '{}') == 10.0
    assert normalize_activity_distance_km(10.0, '{}') == 10.0


def test_database_connection_registers_shared_sql_function():
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT pp_distance_km(?, ?), pp_distance_km(?, ?)",
            (
                200.0,
                '{"distance_unit":"m"}',
                5.0,
                '{"distance_unit":"km"}',
            ),
        ).fetchone()
    finally:
        conn.close()
    assert row == (0.2, 5.0)

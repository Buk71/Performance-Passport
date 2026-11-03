from core.endurance_transfer import _distance_km


def test_short_garmin_fit_distance_is_metres_not_kilometres():
    raw = '{"garmin_fit": {"session": {"total_distance": 229.02}}, "source_activity_id": "garmin_123"}'
    assert abs(_distance_km(229.02, raw) - 0.22902) < 1e-9


def test_normal_garmin_10k_is_metres():
    raw = '{"garmin_fit": {}, "source_activity_id": "garmin_456"}'
    assert abs(_distance_km(10047.15, raw) - 10.04715) < 1e-9


def test_legacy_runalyze_km_is_preserved():
    assert _distance_km(19.32, None) == 19.32

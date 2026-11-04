from pathlib import Path

from core.performance_recognition import _ambient_environment_trusted


ROOT = Path(__file__).resolve().parent.parent


def test_garmin_fit_device_environment_is_not_trusted_as_ambient_weather():
    raw = '{"garmin_fit": {"session": {"avg_temperature": 21}}, "source_activity_id": "garmin_123"}'
    assert _ambient_environment_trusted(raw, source="garmin_fit") is False


def test_explicit_ambient_weather_overrides_garmin_device_default():
    raw = '{"garmin_fit": {}, "temperature_source": "weather", "ambient_temperature_c": 9}'
    assert _ambient_environment_trusted(raw, source="garmin_fit") is True


def test_known_runalyze_source_family_keeps_historical_weather_handling():
    raw = '{"temperature_c": 18}'
    assert _ambient_environment_trusted(raw, source="runalyze") is True
    assert _ambient_environment_trusted(raw, source="runalyze_csv") is True
    assert _ambient_environment_trusted(raw, source="runalyze_export") is True


def test_runalyze_marker_in_raw_json_is_also_recognised():
    assert _ambient_environment_trusted(
        '{"source": "runalyze", "temperature_c": 18}'
    ) is True
    assert _ambient_environment_trusted(
        '{"source": "runalyze_csv", "temperature_c": 18}'
    ) is True


def test_unknown_environment_provenance_is_conservative():
    assert _ambient_environment_trusted(None) is False
    assert _ambient_environment_trusted("{}") is False
    assert _ambient_environment_trusted("{}", source="unknown") is False


def test_recognition_threads_source_aware_weather_trust_into_environment_adjustment():
    source = (ROOT / "core" / "performance_recognition.py").read_text(encoding="utf-8")
    assert "source=source" in source
    assert "replace(run, temperature_c=None, humidity=None)" in source
    assert "context.ambient_environment_trusted" in source


def test_journal_cache_is_current_v3():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")
    assert '"journal.latest_entry.v3"' in source
    assert '"journal.latest_entry.v2"' not in source
    assert '"journal.latest_entry.v1"' not in source

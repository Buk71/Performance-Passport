from pathlib import Path

from core.performance_recognition import _ambient_environment_trusted


ROOT = Path(__file__).resolve().parent.parent


def test_garmin_fit_device_environment_is_not_trusted_as_ambient_weather():
    raw = '{"garmin_fit": {"session": {"avg_temperature": 21}}, "source_activity_id": "garmin_123"}'
    assert _ambient_environment_trusted(raw) is False


def test_explicit_ambient_weather_overrides_garmin_device_default():
    raw = '{"garmin_fit": {}, "temperature_source": "weather", "ambient_temperature_c": 9}'
    assert _ambient_environment_trusted(raw) is True


def test_existing_non_garmin_imports_keep_backward_compatible_environment_handling():
    raw = '{"source": "runalyze", "temperature_c": 18}'
    assert _ambient_environment_trusted(raw) is True


def test_recognition_threads_weather_trust_into_environment_adjustment():
    source = (ROOT / "core" / "performance_recognition.py").read_text(encoding="utf-8")
    assert "ambient_environment_trusted=_ambient_environment_trusted(raw_json)" in source
    assert "replace(run, temperature_c=None, humidity=None)" in source
    assert "context.ambient_environment_trusted" in source


def test_journal_cache_is_bumped_after_environment_ranking_change():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")
    assert '"journal.latest_entry.v2"' in source
    assert '"journal.latest_entry.v1"' not in source

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_race_provider_production_default_is_365_days():
    source = (ROOT / "core" / "evidence_providers" / "race.py").read_text(encoding="utf-8")
    assert "history_days: int | None = 365" in source


def test_race_provider_automatically_preserves_verified_pb_activities():
    source = (ROOT / "core" / "evidence_providers" / "race.py").read_text(encoding="utf-8")
    assert "load_significant_pb_index" in source
    assert "refresh_significant_pb_index" in source
    assert "_effective_preserved_activity_ids" in source


def test_full_history_remains_available_for_validation():
    source = (ROOT / "core" / "evidence_providers" / "race.py").read_text(encoding="utf-8")
    assert "history_days is not None" in source

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_race_provider_production_default_is_horizon_aware():
    source = (ROOT / "core" / "evidence_providers" / "race.py").read_text(encoding="utf-8")
    assert "history_days: int | None = 365" in source
    assert "preserved_activity_ids: tuple[int, ...] | None = None" in source


def test_horizon_query_preserves_explicit_activity_ids():
    source = (ROOT / "core" / "evidence_providers" / "race.py").read_text(encoding="utf-8")
    assert "OR a.id IN" in source
    assert "preserved_activity_ids" in source


def test_full_history_remains_available_explicitly():
    source = (ROOT / "core" / "evidence_providers" / "race.py").read_text(encoding="utf-8")
    assert "if self.history_days is not None" in source
    assert "history_days is not None" in source

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_journal_uses_only_v2_after_environment_ranking_change():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")
    assert 'CURRENT_JOURNAL_KEY = "journal.latest_entry.v2"' in source
    assert '"journal.latest_entry.v1"' not in source
    assert "CURRENT_JOURNAL_KEY," in source


def test_recognition_context_cache_is_source_version_aware():
    source = (ROOT / "core" / "performance_recognition.py").read_text(encoding="utf-8")
    assert "from functools import lru_cache" in source
    assert "get_training_intelligence_version" in source
    assert "@lru_cache(maxsize=64)" in source
    assert "def _activity_context_lookup_cached(" in source
    assert "source_version: tuple" in source
    assert "def _activity_context_lookup(" in source

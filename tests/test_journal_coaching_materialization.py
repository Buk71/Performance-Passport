from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_journal_uses_persistent_training_intelligence():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")

    assert "_build_latest_journal_entry_uncached" in source
    assert "get_training_intelligence_version" in source
    assert "get_or_build_typed_intelligence" in source
    assert '"journal.latest_entry.v3"' in source
    assert '"journal.latest_entry.v1"' not in source


def test_journal_cache_is_source_version_aware():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")

    assert "source_version = tuple(get_training_intelligence_version" in source
    assert "source_version_provider=lambda" in source


def test_journal_and_coaching_team_keep_separate_materialised_keys():
    journal = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")
    coaching = (ROOT / "core" / "coaching_team.py").read_text(encoding="utf-8")

    assert "journal.latest_entry.v3" in journal
    assert "journal.latest_entry.v3" not in coaching
    assert "get_or_build_typed_intelligence" in coaching
